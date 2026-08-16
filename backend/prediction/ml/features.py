"""Feature engineering pipeline — builds feature vectors from sensor + weather data."""

from datetime import timedelta
from django.utils import timezone
from core.models import WaterLevel
from prediction.constants import WARNING_THRESHOLD, CRITICAL_THRESHOLD
from prediction.utils import std as _std, weather_severity as _weather_severity


def build_sensor_features(sensor, readings):
    """Build sensor-based features from recent WaterLevel readings.

    Args:
        sensor: Sensor model instance
        readings: QuerySet or list of WaterLevel objects, newest first

    Returns:
        dict of feature_name -> value
    """
    levels = [r.level_cm for r in readings]
    timestamps = [r.timestamp for r in readings]

    features = {
        "current_level": levels[0] if levels else 0,
    }

    if len(levels) == 0:
        return features

    # Level at various time offsets
    now = timezone.now()
    for label, ago_minutes in [("level_1m_ago", 1), ("level_5m_ago", 5),
                                ("level_10m_ago", 10), ("level_15m_ago", 15)]:
        target_time = now - timedelta(minutes=ago_minutes)
        level = _find_closest_level(levels, timestamps, target_time)
        features[label] = level if level is not None else levels[0]

    # Rise rate: (current - 5min ago) / 5 minutes
    if features["level_5m_ago"] is not None and features["level_5m_ago"] > 0:
        delta = features["current_level"] - features["level_5m_ago"]
        features["rise_rate"] = round(delta / 5.0, 3)  # cm per minute
    else:
        features["rise_rate"] = 0.0

    # Acceleration: change in rise rate
    if len(levels) >= 5:
        recent_rate = (levels[0] - levels[2]) / 2.0 if len(levels) >= 3 else 0
        older_rate = (levels[2] - levels[4]) / 2.0 if len(levels) >= 5 else 0
        features["acceleration"] = round(recent_rate - older_rate, 3)
    else:
        features["acceleration"] = 0.0

    # Rolling stats (last 10 readings)
    recent_10 = levels[:10]
    features["rolling_avg_10"] = round(sum(recent_10) / len(recent_10), 2) if recent_10 else 0
    features["rolling_std_10"] = round(_std(recent_10), 3) if len(recent_10) >= 2 else 0

    # Recent min/max (last 20 readings)
    recent_20 = levels[:20]
    features["recent_max"] = max(recent_20) if recent_20 else 0
    features["recent_min"] = min(recent_20) if recent_20 else 0

    # Distance to thresholds
    features["distance_to_warning"] = round(WARNING_THRESHOLD - features["current_level"], 1)
    features["distance_to_critical"] = round(CRITICAL_THRESHOLD - features["current_level"], 1)

    return features


def build_weather_features(forecast, rainfall_summary):
    """Build weather-based features from forecast data.

    Args:
        forecast: list of hourly forecast dicts from WeatherService
        rainfall_summary: dict from WeatherService.get_rainfall_summary()

    Returns:
        dict of feature_name -> value
    """
    features = {}

    if not forecast:
        return {
            "precip_prob_current": 0,
            "precip_prob_1h": 0,
            "precip_prob_3h": 0,
            "rainfall_1h": 0,
            "rainfall_3h": 0,
            "rainfall_6h": 0,
            "rain_intensity": 0,
            "humidity": 0,
            "cloud_cover": 0,
            "weather_severity": 0,
        }

    current = forecast[0]
    upcoming_12 = forecast[:12]

    features["precip_prob_current"] = current.get("precipitation_probability", 0)
    features["precip_prob_1h"] = max((h["precipitation_probability"] for h in forecast[:1]), default=0)
    features["precip_prob_3h"] = max((h["precipitation_probability"] for h in forecast[:3]), default=0)
    features["rainfall_1h"] = sum(h["rain"] for h in forecast[:1])
    features["rainfall_3h"] = sum(h["rain"] for h in forecast[:3])
    features["rainfall_6h"] = sum(h["rain"] for h in forecast[:6])
    features["rain_intensity"] = max((h["precipitation"] for h in upcoming_12), default=0)
    features["humidity"] = current.get("humidity", 0)
    features["cloud_cover"] = current.get("cloud_cover", 0)
    features["weather_severity"] = _weather_severity(current.get("weather_code", 0))

    return features


def build_anomaly_features(anomaly_result):
    """Extract anomaly features from anomaly detector output."""
    return {
        "anomaly_score": anomaly_result.get("anomaly_score", 0),
        "z_score": anomaly_result.get("z_score", 0),
        "is_anomaly": 1 if anomaly_result.get("is_anomaly", False) else 0,
    }


def _find_closest_level(levels, timestamps, target_time):
    """Find the water level closest to a target time."""
    best_idx = 0
    best_diff = abs((timestamps[0] - target_time).total_seconds()) if timestamps else float("inf")

    for i, ts in enumerate(timestamps):
        diff = abs((ts - target_time).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best_idx = i

    if best_diff > 600:  # More than 10 minutes off
        return None
    return levels[best_idx]
