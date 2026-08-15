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



