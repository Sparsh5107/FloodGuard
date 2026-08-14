from django.contrib import admin
from .models import Sensor, WaterLevel, Alert, NotificationRecipient, NotificationLog

@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ['device_id', 'name', 'location', 'is_active']

@admin.register(WaterLevel)
class WaterLevelAdmin(admin.ModelAdmin):
    list_display = ['sensor', 'level_cm', 'timestamp', 'is_alert']

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['sensor', 'alert_type', 'is_resolved', 'created_at']

@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'alert_types', 'is_active', 'created_at']
    list_filter = ['is_active', 'alert_types']
    filter_horizontal = ['sensors']

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['alert', 'channel', 'recipient', 'status', 'sent_at']
    list_filter = ['channel', 'status']
    readonly_fields = ['alert', 'channel', 'recipient', 'status', 'error_message', 'sent_at']
