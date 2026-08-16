"""Shared utility functions for the core app."""

from datetime import timedelta
from django.utils import timezone
from core.models import WaterLevel

OFFLINE_TIMEOUT = timedelta(seconds=5)


def get_sensor_status(sensor, now=None):
    """Get the current status and level for a sensor.

    Args:
        sensor: Sensor model instance
        now: current timezone-aware datetime (optional, defaults to timezone.now())

    Returns:
        dict with status ('offline', 'rising', 'falling', 'stable', 'no_data'),
             current_level (float)
    """
    if now is None:
        now = timezone.now()

    if sensor.last_seen is None or (now - sensor.last_seen) > OFFLINE_TIMEOUT:
        return {"status": "offline", "current_level": 0}

    readings = WaterLevel.objects.filter(sensor=sensor).order_by('-timestamp')[:2]
    readings_list = list(readings)

    if len(readings_list) == 2:
        current_level = readings_list[0].level_cm

        # Safe zone: always stable below 30cm
        if current_level < 30:
            status = "stable"
        else:
            # Check readings over last 10 seconds
            since = now - timedelta(seconds=10)
            recent = WaterLevel.objects.filter(
                sensor=sensor, timestamp__gte=since
            ).order_by('timestamp').values_list('level_cm', flat=True)
            recent_list = list(recent)

            if len(recent_list) < 2:
                status = "stable"
            else:
                level_range = max(recent_list) - min(recent_list)
                if level_range > 0.3:
                    # Actively changing
                    if recent_list[-1] > recent_list[0]:
                        status = "rising"
                    else:
                        status = "falling"
                else:
                    # Constant for >10 seconds
                    status = "stable"

    elif len(readings_list) == 1:
        status = "stable"
        current_level = readings_list[0].level_cm
    else:
        status = "no_data"
        current_level = 0

    return {"status": status, "current_level": current_level}
