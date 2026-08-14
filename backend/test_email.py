"""Quick SMTP connection test. Run: python test_email.py"""
import os
import sys
from pathlib import Path

# Load env before Django setup
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

os.environ['DJANGO_SETTINGS_MODULE'] = 'floodguard.settings'

import django
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print(f"SMTP Host:    {settings.EMAIL_HOST}")
print(f"SMTP Port:    {settings.EMAIL_PORT}")
print(f"TLS:          {settings.EMAIL_USE_TLS}")
print(f"From:         {settings.DEFAULT_FROM_EMAIL}")
print(f"User:         {settings.EMAIL_HOST_USER}")
print(f"Password set: {'Yes' if settings.EMAIL_HOST_PASSWORD else 'NO - MISSING'}")
print()

test_email = input("Enter recipient email to send test to (or Enter to skip): ").strip()
if not test_email:
    print("Skipped. No email sent.")
    sys.exit(0)

try:
    sent = send_mail(
        subject="[FloodGuard Test] Email connection working",
        message="If you see this, FloodGuard email notifications are configured correctly.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[test_email],
        fail_silently=False,
    )
    print(f"SUCCESS - Email sent to {test_email}")
except Exception as e:
    print(f"FAILED - {e}")
