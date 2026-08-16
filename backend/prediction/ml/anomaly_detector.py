"""Anomaly detector — rolling Z-score approach.

Detects unusual water level behavior using simple statistics.
Works with as few as 10 readings, no ML training needed.
"""

from prediction.utils import std as _std


def detect_anomaly(recent_readings, window=20):
    """Detect anomalies in water level readings.

    Args:
        recent_readings: list of float water level values (newest last)
        window: number of recent readings for baseline calculation

    Returns:
        dict with is_anomaly, anomaly_score, z_score, rate_of_change,
             acceleration, classification, description
    """
    if not recent_readings or len(recent_readings) < 3:
        return {
            "is_anomaly": False,
            "anomaly_score": 0,
            "z_score": 0,
            "rate_of_change": 0,
            "acceleration": 0,
            "classification": "INSUFFICIENT_DATA",
            "description": "Not enough data to detect anomalies",
        }

    # Ensure we have enough for the window
    actual_window = min(window, len(recent_readings))
    recent = recent_readings[-actual_window:]

    # Calculate mean and std
    mean = sum(recent) / len(recent)
    std = _std(recent)

    if std < 1e-6:
        std = 1e-6  # avoid division by zero

    current = recent_readings[-1]
    z_score = (current - mean) / std

    # Rate of change (cm per reading)
    rate_1 = recent_readings[-1] - recent_readings[-2]

    # Acceleration (change in rate)
    if len(recent_readings) >= 3:
        rate_2 = recent_readings[-2] - recent_readings[-3]
        acceleration = rate_1 - rate_2
    else:
        acceleration = 0

    # Classification
    classification = _classify(z_score, rate_1, acceleration)

    # Anomaly score: 0 (normal) to 1 (very anomalous)
    anomaly_score = min(abs(z_score) / 5.0, 1.0)

    # Thresholds
    is_anomaly = abs(z_score) > 2.5 or acceleration > 5 or rate_1 > 8

    description = _describe(z_score, rate_1, acceleration, classification)

    return {
        "is_anomaly": is_anomaly,
        "anomaly_score": round(anomaly_score, 3),
        "z_score": round(z_score, 2),
        "rate_of_change": round(rate_1, 2),
        "acceleration": round(acceleration, 2),
        "classification": classification,
        "description": description,
    }


def _classify(z_score, rate, acceleration):
    """Classify the anomaly type."""
    if abs(z_score) > 2.5:
        if rate > 0:
            return "RAPID_RISE"
        else:
            return "RAPID_DROP"

    if rate > 8:
        return "SURGE_ALERT"

    if acceleration > 3:
        return "ACCELERATING"

    if acceleration < -3:
        return "DECELERATING"

    return "NORMAL"


def _describe(z_score, rate, acceleration, classification):
    """Generate human-readable description."""
    descriptions = {
        "RAPID_RISE": f"Water level rising abnormally fast ({rate:+.1f} cm/reading, {abs(z_score):.1f} std devs above normal)",
        "RAPID_DROP": f"Water level dropping abnormally fast ({rate:+.1f} cm/reading, {abs(z_score):.1f} std devs below normal)",
        "SURGE_ALERT": f"Surge detected: water rising at {rate:.1f} cm/reading",
        "ACCELERATING": f"Water level rise is accelerating ({acceleration:+.1f} cm/reading^2)",
        "DECELERATING": f"Water level rise is decelerating ({acceleration:+.1f} cm/reading^2)",
        "NORMAL": "Water level behavior is normal",
        "INSUFFICIENT_DATA": "Not enough data to detect anomalies",
    }
    return descriptions.get(classification, "Unknown")
