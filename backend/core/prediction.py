import numpy as np
from datetime import timedelta
from django.utils import timezone

THRESHOLDS = {
    "warning": 30,
    "danger": 50,
    "critical": 70,
}


def predict_flood(sensor, hours_ahead=6, num_simulations=1000):
    """Predict flood risk for a sensor using linear regression + Monte Carlo simulation."""
    from core.models import WaterLevel

    readings = list(
        WaterLevel.objects.filter(sensor=sensor)
        .order_by("-timestamp")
        .values_list("level_cm", "timestamp")[:50]
    )
    readings = list(reversed(readings))

    if len(readings) < 3:
        return {
            "device_id": sensor.device_id,
            "sensor_name": sensor.name,
            "location": sensor.location,
            "current_level": readings[-1][0] if readings else 0,
            "predictions": {k: {"time_to_threshold": None, "probability": 0} for k in THRESHOLDS},
            "trend_slope": 0,
            "trend_direction": "insufficient_data",
            "confidence": "low",
            "data_points_used": len(readings),
        }

    levels = np.array([r[0] for r in readings], dtype=float)
    timestamps = [r[1] for r in readings]

    t0 = timestamps[0]
    hours_elapsed = np.array([(t - t0).total_seconds() / 3600 for t in timestamps])

    coeffs = np.polyfit(hours_elapsed, levels, 1)
    slope = coeffs[0]
    intercept = coeffs[1]

    residuals = levels - (slope * hours_elapsed + intercept)
    std_error = float(np.std(residuals)) if len(residuals) > 1 else 5.0

    current_level = float(levels[-1])
    current_time = timestamps[-1]

    predictions = {}
    for name, threshold in THRESHOLDS.items():
        if slope <= 0:
            if current_level >= threshold:
                predictions[name] = {"time_to_threshold": "already_exceeded", "probability": 100.0}
            else:
                predictions[name] = {"time_to_threshold": None, "probability": 0}
        else:
            hours_to_threshold = (threshold - current_level) / slope
            if hours_to_threshold < 0:
                hours_to_threshold = 0

            if hours_to_threshold > hours_ahead * 2:
                predictions[name] = {"time_to_threshold": None, "probability": 0}
                continue

            total_hours = hours_to_threshold
            if total_hours < 1:
                time_str = f"{int(total_hours * 60)}m"
            else:
                h = int(total_hours)
                m = int((total_hours - h) * 60)
                time_str = f"{h}h {m}m"

            crossing_count = 0
            for _ in range(num_simulations):
                future_hours = np.linspace(0, hours_to_threshold + 1, int((hours_to_threshold + 1) * 10))
                noise = np.random.normal(0, std_error, len(future_hours))
                cumulative_noise = np.cumsum(noise) * 0.1
                predicted_levels = intercept + slope * (hours_elapsed[-1] + future_hours) + cumulative_noise

                if np.any(predicted_levels >= threshold):
                    crossing_count += 1

            probability = round((crossing_count / num_simulations) * 100, 1)

            predictions[name] = {"time_to_threshold": time_str, "probability": probability}

    if abs(slope) < 0.1:
        trend = "stable"
    elif slope > 0:
        trend = "rising"
    else:
        trend = "falling"

    confidence = "high" if len(readings) >= 20 else "medium" if len(readings) >= 10 else "low"

    return {
        "device_id": sensor.device_id,
        "sensor_name": sensor.name,
        "location": sensor.location,
        "current_level": current_level,
        "predictions": predictions,
        "trend_slope": round(slope, 3),
        "trend_direction": trend,
        "confidence": confidence,
        "data_points_used": len(readings),
    }


def get_all_predictions():
    """Get predictions for all active sensors."""
    from core.models import Sensor

    sensors = Sensor.objects.filter(is_active=True)
    results = []
    for sensor in sensors:
        results.append(predict_flood(sensor))
    return results
