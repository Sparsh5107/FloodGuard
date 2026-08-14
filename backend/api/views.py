from datetime import timedelta
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from core.models import Sensor, WaterLevel, Alert
from .serializers import SensorSerializer, WaterLevelSerializer, AlertSerializer
from core.notifications.service import NotificationService
from core.weather import get_current_weather, get_rainfall_forecast, get_daily_forecast
from core.flood_api import get_river_discharge
from core.prediction import get_all_predictions, predict_flood

OFFLINE_TIMEOUT = timedelta(seconds=2)

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

    try:
        sensor = Sensor.objects.get(device_id=device_id)
    except Sensor.DoesNotExist:
        return Response({'error': 'Sensor not found'}, status=status.HTTP_404_NOT_FOUND)

    sensor.last_seen = timezone.now()
    sensor.save(update_fields=['last_seen'])

    # Smart logging: check if we should save this reading
    last_reading = WaterLevel.objects.filter(sensor=sensor).order_by('-timestamp').first()
    should_save = False

    if last_reading is None:
        # First reading for this sensor — always save
        should_save = True
    else:
        time_since_last = timezone.now() - last_reading.timestamp
        level_change = abs(level_cm - last_reading.level_cm)

        # Save if: change > 5 cm OR 5 minutes passed
        if level_change > CHANGE_THRESHOLD or time_since_last >= TIME_THRESHOLD:
            should_save = True

    if not should_save:
        return Response({'status': 'skipped', 'reason': 'No significant change'})

    # Save the reading
    is_alert = level_cm >= THRESHOLD_WARNING

    reading = WaterLevel.objects.create(
        sensor=sensor,
        level_cm=level_cm,
        is_alert=is_alert
    )

    # Create alert if threshold exceeded
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
        if sensor.last_seen is None or (now - sensor.last_seen) > OFFLINE_TIMEOUT:
            current_status = 'offline'
            current_level = 0
        else:
            readings = WaterLevel.objects.filter(sensor=sensor).order_by('-timestamp')[:1]
            if readings.exists():
                current_level = readings.first().level_cm
                prev_readings = list(WaterLevel.objects.filter(sensor=sensor).order_by('-timestamp')[:2])
                if len(prev_readings) == 2:
                    if prev_readings[0].level_cm > prev_readings[1].level_cm:
                        current_status = 'rising'
                    elif prev_readings[0].level_cm < prev_readings[1].level_cm:
                        current_status = 'falling'
                    else:
                        current_status = 'stable'
                else:
                    current_status = 'stable'
            else:
                current_status = 'no_data'
                current_level = 0

        result.append({
            'device_id': sensor.device_id,
            'name': sensor.name,
            'location': sensor.location,
            'status': current_status,
            'level_cm': current_level,
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

    since = timezone.now() - timedelta(hours=24)
    readings = WaterLevel.objects.filter(
        sensor=sensor, timestamp__gte=since
    ).order_by('timestamp').values('timestamp', 'level_cm')

    history = [
        {'timestamp': r['timestamp'].isoformat(), 'level_cm': r['level_cm']}
        for r in readings
    ]

    return Response({'device_id': device_id, 'history': history})


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
        'sensor_name': a.sensor.name,
        'location': a.sensor.location,
        'alert_type': a.alert_type,
        'message': a.message,
        'created_at': a.created_at.strftime('%b %d, %H:%M:%S'),
    } for a in alerts]

    response = Response({'readings': readings_data, 'alerts': alerts_data})
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@api_view(['GET'])
def weather_api(request):
    """Get weather data for all sensors."""
    sensors = Sensor.objects.filter(is_active=True)
    results = []

    for sensor in sensors:
        if sensor.latitude is None or sensor.longitude is None:
            results.append({"device_id": sensor.device_id, "name": sensor.name, "weather": None})
            continue

        current = get_current_weather(sensor.latitude, sensor.longitude)
        forecast = get_rainfall_forecast(sensor.latitude, sensor.longitude, days=3)
        daily = get_daily_forecast(sensor.latitude, sensor.longitude, days=7)

        results.append({
            "device_id": sensor.device_id,
            "name": sensor.name,
            "location": sensor.location,
            "weather": current,
            "rainfall_forecast": forecast.get("summary") if forecast else None,
            "daily_forecast": daily.get("daily", [])[:7] if daily else [],
        })

    return Response({"sensors": results})


@api_view(['GET'])
def flood_data_api(request):
    """Get river discharge data for all sensors."""
    sensors = Sensor.objects.filter(is_active=True)
    results = []

    for sensor in sensors:
        if sensor.latitude is None or sensor.longitude is None:
            results.append({"device_id": sensor.device_id, "name": sensor.name, "flood_data": None})
            continue

        flood = get_river_discharge(sensor.latitude, sensor.longitude, days=30)
        results.append({
            "device_id": sensor.device_id,
            "name": sensor.name,
            "location": sensor.location,
            "flood_data": flood,
        })

    return Response({"sensors": results})


@api_view(['GET'])
def predictions_api(request):
    """Get flood predictions for all sensors."""
    predictions = get_all_predictions()
    return Response({"predictions": predictions})


@api_view(['GET'])
def prediction_api(request, device_id):
    """Get flood prediction for a single sensor."""
    try:
        sensor = Sensor.objects.get(device_id=device_id)
    except Sensor.DoesNotExist:
        return Response({'error': 'Sensor not found'}, status=status.HTTP_404_NOT_FOUND)

    prediction = predict_flood(sensor)
    return Response(prediction)
