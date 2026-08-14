import requests
from datetime import datetime, timedelta

OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"


def get_current_weather(latitude, longitude):
    """Get current weather conditions for a sensor location."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,rain,precipitation,weather_code,wind_speed_10m,wind_direction_10m,cloud_cover,surface_pressure",
        "timezone": "auto",
    }
    try:
        resp = requests.get(OPEN_METEO_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        current = data.get("current", {})

        weather_codes = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
            55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain",
            65: "Heavy rain", 71: "Slight snow", 73: "Moderate snow",
            75: "Heavy snow", 80: "Slight showers", 81: "Moderate showers",
            82: "Violent showers", 85: "Slight snow showers", 86: "Heavy snow showers",
            95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
        }
        code = current.get("weather_code", 0)

        return {
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "rain": current.get("rain", 0),
            "precipitation": current.get("precipitation", 0),
            "weather_code": code,
            "weather_description": weather_codes.get(code, "Unknown"),
            "wind_speed": current.get("wind_speed_10m"),
            "wind_direction": current.get("wind_direction_10m"),
            "cloud_cover": current.get("cloud_cover"),
            "pressure": current.get("surface_pressure"),
        }
    except requests.RequestException:
        return None


def get_rainfall_forecast(latitude, longitude, days=3):
    """Get hourly rainfall forecast for the next N days."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "precipitation,precipitation_probability,rain,soil_moisture_0_to_1cm",
        "timezone": "auto",
        "forecast_days": days,
    }
    try:
        resp = requests.get(OPEN_METEO_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        hourly = data.get("hourly", {})

        times = hourly.get("time", [])
        result = []
        for i, t in enumerate(times):
            result.append({
                "time": t,
                "precipitation": hourly.get("precipitation", [])[i] if i < len(hourly.get("precipitation", [])) else 0,
                "precipitation_probability": hourly.get("precipitation_probability", [])[i] if i < len(hourly.get("precipitation_probability", [])) else 0,
                "rain": hourly.get("rain", [])[i] if i < len(hourly.get("rain", [])) else 0,
                "soil_moisture": hourly.get("soil_moisture_0_to_1cm", [])[i] if i < len(hourly.get("soil_moisture_0_to_1cm", [])) else None,
            })

        rain_24h = sum(r.get("rain", 0) for r in result[:24])
        rain_72h = sum(r.get("rain", 0) for r in result)
        max_precip_prob = max((r.get("precipitation_probability", 0) for r in result[:24]), default=0)
        avg_soil = None
        soil_vals = [r["soil_moisture"] for r in result[:24] if r["soil_moisture"] is not None]
        if soil_vals:
            avg_soil = round(sum(soil_vals) / len(soil_vals), 3)

        return {
            "hourly": result[:72],
            "summary": {
                "rain_24h": round(rain_24h, 1),
                "rain_72h": round(rain_72h, 1),
                "max_precipitation_probability_24h": max_precip_prob,
                "avg_soil_moisture_24h": avg_soil,
            },
        }
    except requests.RequestException:
        return None


def get_daily_forecast(latitude, longitude, days=7):
    """Get daily weather summary for the next N days."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "precipitation_sum,rain_sum,precipitation_hours,precipitation_probability_max,weather_code,temperature_2m_max,temperature_2m_min,wind_speed_10m_max",
        "timezone": "auto",
        "forecast_days": days,
    }
    try:
        resp = requests.get(OPEN_METEO_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        daily = data.get("daily", {})

        times = daily.get("time", [])
        result = []
        for i, t in enumerate(times):
            result.append({
                "date": t,
                "precipitation_sum": daily.get("precipitation_sum", [])[i] if i < len(daily.get("precipitation_sum", [])) else 0,
                "rain_sum": daily.get("rain_sum", [])[i] if i < len(daily.get("rain_sum", [])) else 0,
                "precipitation_hours": daily.get("precipitation_hours", [])[i] if i < len(daily.get("precipitation_hours", [])) else 0,
                "precipitation_probability_max": daily.get("precipitation_probability_max", [])[i] if i < len(daily.get("precipitation_probability_max", [])) else 0,
                "weather_code": daily.get("weather_code", [])[i] if i < len(daily.get("weather_code", [])) else 0,
                "temp_max": daily.get("temperature_2m_max", [])[i] if i < len(daily.get("temperature_2m_max", [])) else 0,
                "temp_min": daily.get("temperature_2m_min", [])[i] if i < len(daily.get("temperature_2m_min", [])) else 0,
                "wind_max": daily.get("wind_speed_10m_max", [])[i] if i < len(daily.get("wind_speed_10m_max", [])) else 0,
            })

        return {"daily": result}
    except requests.RequestException:
        return None
