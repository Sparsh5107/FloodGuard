from datetime import timedelta
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.decorators import action
from rest_framework.response import Response
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from core.models import Sensor, WaterLevel, Alert
from core.utils import get_sensor_status
from .serializers import SensorSerializer, WaterLevelSerializer, AlertSerializer
from core.notifications.service import NotificationService

OFFLINE_TIMEOUT = timedelta(seconds=10)

# Flood alert thresholds (in cm)
THRESHOLD_WARNING = 30
THRESHOLD_DANGER = 50
THRESHOLD_CRITICAL = 70

# Smart logging settings
CHANGE_THRESHOLD = 5  # Log if water level changes by more than 5 cm
TIME_THRESHOLD = timedelta(minutes=5)  # Log if 5 minutes passed since last log

# Notification executor for async email sending
_notification_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="flood-alert")


class SensorViewSet(viewsets.ModelViewSet):
    queryset = Sensor.objects.all()
    serializer_class = SensorSerializer


class WaterLevelViewSet(viewsets.ModelViewSet):
    queryset = WaterLevel.objects.all()
    serializer_class = WaterLevelSerializer


class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.is_resolved = True
        alert.save(update_fields=['is_resolved'])
        return Response({'status': 'ok'})


@api_view(['POST'])
def receive_sensor_data(request):
    """Endpoint for ESP32 to post sensor readings"""
    device_id = request.data.get('device_id')
    level_cm = request.data.get('level_cm')

    if level_cm is None:
        return Response({'error': 'level_cm is required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        level_cm = float(level_cm)
    except (TypeError, ValueError):
        return Response({'error': 'level_cm must be a number'}, status=status.HTTP_400_BAD_REQUEST)

    if level_cm < 0 or level_cm > 100:
        return Response({'error': 'level_cm must be between 0 and 100'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        sensor = Sensor.objects.get(device_id=device_id)
    except Sensor.DoesNotExist:
        return Response({'error': 'Sensor not found'}, status=status.HTTP_404_NOT_FOUND)

    sensor.last_seen = timezone.now()
    sensor.save(update_fields=['last_seen'])

    channel_layer = get_channel_layer()
    status_val = get_sensor_status(sensor, timezone.now())["status"]
    now = timezone.now()

    # 1. ALWAYS broadcast sensor update via WebSocket (real-time UI)
    async_to_sync(channel_layer.group_send)(
        'sensor_data',
        {
            'type': 'sensor_update',
            'device_id': sensor.device_id,
            'level_cm': level_cm,
            'status': status_val,
            'timestamp': now.isoformat(),
            'is_alert': level_cm >= THRESHOLD_WARNING,
        }
    )

    # 2. If alert threshold crossed → broadcast + save alert to DB immediately
    is_alert = level_cm >= THRESHOLD_WARNING
    if is_alert:
        if level_cm >= THRESHOLD_CRITICAL:
            alert_type = 'critical'
            message = f'CRITICAL: Water level at {level_cm}cm - Immediate action required!'
        elif level_cm >= THRESHOLD_DANGER:
            alert_type = 'danger'
            message = f'DANGER: Water level at {level_cm}cm - Flooding imminent!'
        else:
            alert_type = 'warning'
            message = f'WARNING: Water level at {level_cm}cm - Monitor closely'

        async_to_sync(channel_layer.group_send)(
            'sensor_data',
            {
                'type': 'alert_update',
                'alert_type': alert_type,
                'sensor_name': sensor.name,
                'message': message,
                'timestamp': now.isoformat(),
            }
        )

    # 3. Smart logging: only save to DB if significant change or alert
    last_reading = WaterLevel.objects.filter(sensor=sensor).order_by('-timestamp').first()
    should_save = is_alert

    if not should_save and last_reading is not None:
        time_since_last = now - last_reading.timestamp
        level_change = abs(level_cm - last_reading.level_cm)
        if level_change > CHANGE_THRESHOLD or time_since_last >= TIME_THRESHOLD:
            should_save = True
    elif not should_save and last_reading is None:
        should_save = True

    if not should_save:
        return Response({'status': 'skipped', 'reason': 'No significant change'})

    # 4. Save reading to DB
    reading = WaterLevel.objects.create(
        sensor=sensor,
        level_cm=level_cm,
        is_alert=is_alert
    )

    # 5. If alert and not already saved alert record, create it now
    if is_alert:
        existing_alert = Alert.objects.filter(
            sensor=sensor, alert_type=alert_type,
            created_at__gte=now - timedelta(seconds=10)
        ).exists()
        if not existing_alert:
            alert = Alert.objects.create(
                sensor=sensor,
                water_level=reading,
                alert_type=alert_type,
                message=message
            )
            _notification_executor.submit(NotificationService.send_alert_email, alert)

    return Response({'status': 'ok', 'reading_id': reading.id})


@api_view(['GET'])
def sensor_status_api(request):
    """API endpoint for polling sensor status changes"""
    sensors = Sensor.objects.all()
    now = timezone.now()
    result = []

    for sensor in sensors:
        status_result = get_sensor_status(sensor, now)
        result.append({
            'device_id': sensor.device_id,
            'name': sensor.name,
            'location': sensor.location,
            'status': status_result["status"],
            'level_cm': status_result["current_level"],
            'last_seen': sensor.last_seen.isoformat() if sensor.last_seen else None,
            'latitude': sensor.latitude,
            'longitude': sensor.longitude,
        })

    response = Response({'sensors': result})
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@api_view(['GET'])
def sensor_history_api(request, device_id):
    """Return last 24 hours of water level history for a sensor"""
    try:
        sensor = Sensor.objects.get(device_id=device_id)
    except Sensor.DoesNotExist:
        return Response({'error': 'Sensor not found'}, status=status.HTTP_404_NOT_FOUND)

    hours = int(request.query_params.get('hours', 24))
    hours = min(max(hours, 1), 72)
    since = timezone.now() - timedelta(hours=hours)
    readings = WaterLevel.objects.filter(
        sensor=sensor, timestamp__gte=since
    ).order_by('timestamp').values('timestamp', 'level_cm')

    history = [
        {'timestamp': r['timestamp'].isoformat(), 'level_cm': r['level_cm']}
        for r in readings
    ]

    return Response({'device_id': device_id, 'history': history})


@api_view(['GET'])
def system_stats_api(request):
    """System-wide statistics for mobile app."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    sensors = Sensor.objects.all()
    total_sensors = sensors.count()
    online_sensors = sensors.filter(
        last_seen__gte=now - timedelta(seconds=5)
    ).count()

    total_readings = WaterLevel.objects.count()
    readings_today = WaterLevel.objects.filter(
        timestamp__gte=today_start
    ).count()

    total_alerts = Alert.objects.count()
    unresolved_alerts = Alert.objects.filter(is_resolved=False).count()

    return Response({
        'total_sensors': total_sensors,
        'active_sensors': online_sensors,
        'online_sensors': online_sensors,
        'unresolved_alerts': unresolved_alerts,
        'total_readings': total_readings,
        'total_alerts': total_alerts,
        'readings_today': readings_today,
    })


@api_view(['GET'])
def dashboard_data_api(request):
    """API endpoint for polling readings and alerts"""
    readings = WaterLevel.objects.select_related('sensor').order_by('-timestamp')[:10]
    alerts = Alert.objects.select_related('sensor').order_by('-created_at')[:20]

    readings_data = [{
        'sensor_name': r.sensor.name,
        'location': r.sensor.location,
        'level_cm': r.level_cm,
        'is_alert': r.is_alert,
        'timestamp': r.timestamp.strftime('%b %d, %H:%M:%S'),
    } for r in readings]

    alerts_data = [{
        'id': a.id,
        'sensor_name': a.sensor.name,
        'location': a.sensor.location,
        'alert_type': a.alert_type,
        'message': a.message,
        'is_resolved': a.is_resolved,
        'created_at': a.created_at.strftime('%b %d, %H:%M:%S'),
    } for a in alerts]

    response = Response({'readings': readings_data, 'alerts': alerts_data})
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response



