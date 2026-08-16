"""Weather Risk Engine — rule-based scoring (0-100).

No ML needed. Works immediately with zero training data.
Combines precipitation probability, rainfall intensity, accumulation,
weather severity, and atmospheric conditions into a single risk score.
"""

from prediction.utils import weather_severity as _weather_severity


def _classify_risk(score):
    """Map numeric score to risk level."""
    if score <= 20:
        return "LOW"
    elif score <= 40:
        return "MODERATE"
    elif score <= 65:
        return "ELEVATED"
    elif score <= 85:
        return "HIGH"
    else:
        return "CRITICAL"


def calculate_weather_risk(forecast, rainfall_summary=None):
    """Calculate weather risk score from hourly forecast data.

    Args:
        forecast: list of hourly forecast dicts from WeatherService.get_hourly_forecast()
        rainfall_summary: optional dict from WeatherService.get_rainfall_summary()

    Returns:
        dict with weather_risk (0-100), risk_level, factors, data_quality
    """
    if not forecast:
        return {
            "weather_risk": 0,
            "risk_level": "LOW",
            "factors": [],
            "data_quality": "unavailable",
        }

    score = 0
    factors = []

    # Use next 12 hours for scoring
    upcoming = forecast[:12]
    current = forecast[0] if forecast else {}

    # 1. Precipitation probability (0-30 points)
    max_prob = max((h["precipitation_probability"] for h in upcoming), default=0)
    if max_prob > 80:
        prob_score = 30
    elif max_prob > 50:
        prob_score = 20
    elif max_prob > 20:
        prob_score = 10
    else:
        prob_score = 0

    if prob_score > 0:
        factors.append({
            "name": "precipitation_probability",
            "label": "Rain Probability",
            "value": f"{max_prob}%",
            "score": prob_score,
            "max_score": 30,
        })
    score += prob_score

    # 2. Rainfall intensity - max hourly rate (0-30 points)
    max_intensity = max((h["precipitation"] for h in upcoming), default=0)
    if max_intensity > 20:
        intensity_score = 30
    elif max_intensity > 7:
        intensity_score = 25
    elif max_intensity > 2:
        intensity_score = 15
    elif max_intensity > 0:
        intensity_score = 5
    else:
        intensity_score = 0

    if intensity_score > 0:
        factors.append({
            "name": "rainfall_intensity",
            "label": "Rainfall Intensity",
            "value": f"{max_intensity} mm/h",
            "score": intensity_score,
            "max_score": 30,
        })
    score += intensity_score

    # 3. Rainfall accumulation (0-20 points)
    rain_3h = sum(h["rain"] for h in upcoming[:3])
    rain_6h = sum(h["rain"] for h in upcoming[:6])

    accumulation_score = 0
    if rain_6h > 30:
        accumulation_score = 20
    elif rain_6h > 15:
        accumulation_score = 15
    elif rain_3h > 10:
        accumulation_score = 12
    elif rain_3h > 5:
        accumulation_score = 8
    elif rain_3h > 1:
        accumulation_score = 4

    if accumulation_score > 0:
        factors.append({
            "name": "rainfall_accumulation",
            "label": "Rainfall Accumulation",
            "value": f"{rain_3h:.1f}mm/3h, {rain_6h:.1f}mm/6h",
            "score": accumulation_score,
            "max_score": 20,
        })
    score += accumulation_score

    # 4. Weather condition severity (0-10 points)
    max_severity = max((_weather_severity(h["weather_code"]) for h in upcoming), default=0)
    severity_score = min(max_severity, 10)

    if severity_score > 0:
        factors.append({
            "name": "weather_severity",
            "label": "Weather Severity",
            "value": f"Code {current.get('weather_code', 0)}",
            "score": severity_score,
            "max_score": 10,
        })
    score += severity_score

    # 5. Humidity and cloud cover (0-10 points)
    humidity = current.get("humidity", 0)
    cloud = current.get("cloud_cover", 0)
    atmo_score = 0
    if humidity > 90 and cloud > 80:
        atmo_score = 10
    elif humidity > 80 and cloud > 60:
        atmo_score = 6
    elif humidity > 70:
        atmo_score = 3

    if atmo_score > 0:
        factors.append({
            "name": "atmospheric_conditions",
            "label": "Atmospheric Conditions",
            "value": f"{humidity}% humidity, {cloud}% cloud",
            "score": atmo_score,
            "max_score": 10,
        })
    score += atmo_score

    final_score = min(score, 100)

    return {
        "weather_risk": final_score,
        "risk_level": _classify_risk(final_score),
        "factors": factors,
        "data_quality": "good",
    }
