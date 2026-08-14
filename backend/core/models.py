from django.db import models
from django.contrib.auth.models import User


class Sensor(models.Model):
    """ESP32 sensor device"""
    device_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=300)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_connected = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.device_id})"


class WaterLevel(models.Model):
    """Water level readings from sensors"""
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='readings')
    level_cm = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_alert = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.sensor.name}: {self.level_cm}cm @ {self.timestamp}"


class Alert(models.Model):
    """Flood alerts"""
    ALERT_TYPES = [
        ('warning', 'Warning'),
        ('danger', 'Danger'),
        ('critical', 'Critical'),
    ]
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE)
    water_level = models.ForeignKey(WaterLevel, on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.alert_type} - {self.sensor.name}"


class NotificationRecipient(models.Model):
    """Who gets notified for which sensors/alert types"""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    alert_types = models.JSONField(default=list)
    sensors = models.ManyToManyField(Sensor, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def wants_alert(self, sensor, alert_type):
        if not self.is_active:
            return False
        if self.sensors.exists() and sensor not in self.sensors.all():
            return False
        if self.alert_types and alert_type not in self.alert_types:
            return False
        return True

    def __str__(self):
        return f"{self.name} ({self.email})"


class NotificationLog(models.Model):
    """Log of notification delivery attempts"""
    CHANNELS = [
        ('email', 'Email'),
    ]
    STATUS = [
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='notification_logs')
    channel = models.CharField(max_length=20, choices=CHANNELS)
    recipient = models.EmailField()
    status = models.CharField(max_length=10, choices=STATUS)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.channel} to {self.recipient} - {self.status}"


# Extend Alert model with acknowledgment fields
Alert.add_to_class('acknowledged_by', models.ForeignKey(
    User, null=True, blank=True, on_delete=models.SET_NULL, related_name='acknowledged_alerts'
))
Alert.add_to_class('acknowledged_at', models.DateTimeField(null=True, blank=True))
