from datetime import timedelta
import json
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q, Avg
from django.core.serializers.json import DjangoJSONEncoder
from .models import Sensor, WaterLevel, Alert

OFFLINE_TIMEOUT = timedelta(seconds=2)


def dashboard(request):
    """Main dashboard view"""
    sensors = Sensor.objects.all()
    latest_readings = WaterLevel.objects.select_related('sensor')[:10]
    
    # Get current status for each sensor (rising, falling, stable, or offline)
    sensor_status = []
    now = timezone.now()
    active_count = 0
    total_level = 0
    sensor_count = 0
    
    for sensor in sensors:
        if sensor.last_seen is None or now - sensor.last_seen > OFFLINE_TIMEOUT:
            status = 'offline'
            current = 0
        else:
            active_count += 1
            # Check water level trend
            readings = WaterLevel.objects.filter(sensor=sensor).order_by('-timestamp')[:2]
            readings_list = list(readings)
            if len(readings_list) == 2:
                current = readings_list[0].level_cm
                previous = readings_list[1].level_cm
                if current > previous:
                    status = 'rising'
                elif current < previous:
                    status = 'falling'
                else:
                    status = 'stable'
            elif len(readings_list) == 1:
                status = 'stable'
                current = readings_list[0].level_cm
            else:
                status = 'no_data'
                current = 0
            
            total_level += current
            sensor_count += 1
        
        sensor_status.append({
            'sensor': sensor,
            'current_level': current,
            'status': status,
        })
    
    # Get last 20 alerts for alert log
    alert_logs = Alert.objects.select_related('sensor').order_by('-created_at')[:20]
    active_alerts = Alert.objects.filter(is_resolved=False).count()
    avg_level = round(total_level / sensor_count, 1) if sensor_count > 0 else 0

    context = {
        'sensors': sensors,
        'latest_readings': latest_readings,
        'sensor_status': sensor_status,
        'alert_logs': alert_logs,
        'total_sensors': sensors.count(),
        'active_sensors': active_count,
        'active_alerts': active_alerts,
        'avg_level': avg_level,
    }
    return render(request, 'dashboard.html', context)


def data_view(request):
    """Readings and alerts page"""
    latest_readings = WaterLevel.objects.select_related('sensor')[:20]
    alert_logs = Alert.objects.select_related('sensor').order_by('-created_at')[:20]
    sensors = Sensor.objects.all()
    now = timezone.now()

    # Build sensor data for individual charts
    sensor_chart_data = []
    for sensor in sensors:
        if sensor.last_seen is None or (now - sensor.last_seen) > OFFLINE_TIMEOUT:
            status = 'offline'
            current_level = 0
        else:
            readings = WaterLevel.objects.filter(sensor=sensor).order_by('-timestamp')[:2]
            readings_list = list(readings)
            if len(readings_list) >= 1:
                current_level = readings_list[0].level_cm
                if len(readings_list) == 2:
                    if readings_list[0].level_cm > readings_list[1].level_cm:
                        status = 'rising'
                    elif readings[0].level_cm < readings[1].level_cm:
                        status = 'falling'
                    else:
                        status = 'stable'
                else:
                    status = 'stable'
            else:
                status = 'no_data'
                current_level = 0

        # Determine alert level
        if current_level >= 70:
            alert_level = 'critical'
        elif current_level >= 50:
            alert_level = 'danger'
        elif current_level >= 30:
            alert_level = 'warning'
        else:
            alert_level = 'normal'

        sensor_chart_data.append({
            'device_id': sensor.device_id,
            'name': sensor.name,
            'location': sensor.location,
            'level': current_level,
            'status': status,
            'alert_level': alert_level,
        })

    # Alert counts for summary
    alert_counts = {
        'warning': Alert.objects.filter(alert_type='warning').count(),
        'danger': Alert.objects.filter(alert_type='danger').count(),
        'critical': Alert.objects.filter(alert_type='critical').count(),
    }

    context = {
        'latest_readings': latest_readings,
        'alert_logs': alert_logs,
        'readings_count': len(latest_readings),
        'alerts_count': len(alert_logs),
        'sensors_json': json.dumps(sensor_chart_data, cls=DjangoJSONEncoder),
        'alert_counts': alert_counts,
    }
    return render(request, 'data.html', context)


def map_view(request):
    """Map view showing sensor locations"""
    return render(request, 'map.html')


def predictions_view(request):
    """Predictions page with weather, flood, and trend analysis"""
    return render(request, 'predictions.html')


