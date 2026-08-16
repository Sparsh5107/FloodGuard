"""Water level predictor — time-to-flood estimation.

Uses linear regression + decay model to estimate when water
will reach warning (30cm) and critical (70cm) thresholds.
"""

from prediction.constants import WARNING_THRESHOLD, CRITICAL_THRESHOLD

MAX_FORECAST_MINUTES = 60


def estimate_time_to_critical(recent_readings, timestamps):
    """Estimate when water level reaches critical threshold.

    Args:
        recent_readings: list of float water level values (newest last)
        timestamps: list of datetime objects corresponding to readings

    Returns:
        dict with time_to_warning, time_to_critical, distance_to_critical,
             current_rise_rate, confidence, and multi-horizon forecast
    """
    if not recent_readings or len(recent_readings) < 3:
        return {
            "time_to_warning": None,
            "time_to_critical": None,
            "distance_to_warning": None,
            "distance_to_critical": None,
            "current_rise_rate": 0,
            "confidence": "low",
            "forecast": [],
        }

    current_level = recent_readings[-1]

    # Calculate rise rate using linear regression on last 10 readings
    n = min(10, len(recent_readings))
    recent_levels = recent_readings[-n:]
    rise_rate = _linear_slope(recent_levels)

    # Distance to thresholds
    dist_warning = WARNING_THRESHOLD - current_level
    dist_critical = CRITICAL_THRESHOLD - current_level

    # Estimate time to thresholds
    time_to_warning = _estimate_time(dist_warning, rise_rate)
    time_to_critical = _estimate_time(dist_critical, rise_rate)

    # Confidence based on forecast distance
    if time_to_critical is None:
        confidence = "high" if rise_rate <= 0 else "low"
    elif time_to_critical > MAX_FORECAST_MINUTES:
        confidence = "low"
    elif time_to_critical > 30:
        confidence = "medium"
    else:
        confidence = "high"

    # Multi-horizon forecast
    forecast = forecast_water_levels(recent_levels, horizons=[5, 10, 15, 30, 60])

    return {
        "time_to_warning": _format_time(time_to_warning),
        "time_to_critical": _format_time(time_to_critical),
        "distance_to_warning": round(dist_warning, 1),
        "distance_to_critical": round(dist_critical, 1),
        "current_rise_rate": round(rise_rate, 3),
        "confidence": confidence,
        "forecast": forecast,
    }


def forecast_water_levels(levels, horizons=None):
    """Predict water level at future time points.

    Args:
        levels: list of recent water level values (newest last)
        horizons: list of minutes into the future to predict

    Returns:
        list of dicts: [{minutes: 5, level: 42.3}, ...]
    """
    if horizons is None:
        horizons = [5, 10, 15, 30, 60]

    if not levels or len(levels) < 2:
        return [{"minutes": h, "level": levels[-1] if levels else 0} for h in horizons]

    current = levels[-1]
    slope = _linear_slope(levels)

    results = []
    for h in horizons:
        # Linear extrapolation with decay factor
        # Decay: rain intensity usually decreases over time
        decay = 0.95 ** (h / 15)  # 5% decay per 15 minutes
        predicted = current + slope * h * decay
        results.append({
            "minutes": h,
            "level": round(predicted, 1),
        })

    return results


def _estimate_time(distance, rise_rate):
    """Estimate minutes until distance is covered at current rate."""
    if rise_rate <= 0 or distance <= 0:
        return None

    # Simple estimate with 20% safety margin
    simple_minutes = distance / rise_rate
    adjusted = simple_minutes * 1.2

    if adjusted > MAX_FORECAST_MINUTES:
        return None

    return round(adjusted, 1)


def _linear_slope(values):
    """Calculate slope using linear regression (least squares)."""
    n = len(values)
    if n < 2:
        return 0

    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0

    return numerator / denominator


def _format_time(minutes):
    """Format minutes into human-readable string."""
    if minutes is None:
        return None

    if minutes <= 0:
        return "ALREADY_EXCEEDED"
    elif minutes < 1:
        return "Less than 1 min"
    elif minutes < 60:
        return f"~{int(round(minutes))} min"
    else:
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        if mins == 0:
            return f"~{hours}h"
        return f"~{hours}h {mins}m"
