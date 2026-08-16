import logging
import time
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from core.models import NotificationRecipient, NotificationLog, Alert

logger = logging.getLogger(__name__)

# In-memory rate limit tracker: {recipient_email: last_sent_timestamp}
_rate_limit_cache = {}

ALERT_SUBJECTS = {
    'warning': 'WARNING',
    'danger': 'DANGER',
    'critical': 'CRITICAL',
}


class NotificationService:
    @staticmethod
    def _is_rate_limited(email: str) -> bool:
        """Check if a recipient was emailed too recently."""
        last_sent = _rate_limit_cache.get(email)
        if last_sent is None:
            return False
        cooldown = getattr(settings, 'EMAIL_RATE_LIMIT_SECONDS', 300)
        return (time.time() - last_sent) < cooldown

    @staticmethod
    def _update_rate_limit(email: str):
        """Record the send time for rate limiting."""
        _rate_limit_cache[email] = time.time()

    @staticmethod
    def send_alert_email(alert: Alert, max_retries: int = 2):
        """Send email notification for any alert type with retry and rate limiting."""
        recipients = NotificationRecipient.objects.filter(is_active=True)
        alert_label = ALERT_SUBJECTS.get(alert.alert_type, alert.alert_type.upper())

        for recipient in recipients:
            if not recipient.wants_alert(alert.sensor, alert.alert_type):
                continue

            if NotificationService._is_rate_limited(recipient.email):
                logger.info("Rate limited: %s for alert %s", recipient.email, alert.id)
                continue

            subject = f"[{alert_label}] Flood Alert: {alert.sensor.name}"
            html_message = render_to_string('emails/critical_alert.html', {
                'alert': alert,
                'sensor': alert.sensor,
                'recipient_name': recipient.name,
                'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
            })
            plain_message = strip_tags(html_message)

            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    send_mail(
                        subject=subject,
                        message=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[recipient.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    NotificationLog.objects.create(
                        alert=alert, channel='email', recipient=recipient.email, status='sent'
                    )
                    NotificationService._update_rate_limit(recipient.email)
                    last_error = None
                    break
                except Exception as e:
                    last_error = str(e)
                    logger.warning(
                        "Email attempt %d/%d failed for %s: %s",
                        attempt + 1, max_retries + 1, recipient.email, last_error
                    )

            if last_error is not None:
                NotificationLog.objects.create(
                    alert=alert, channel='email', recipient=recipient.email,
                    status='failed', error_message=last_error
                )


