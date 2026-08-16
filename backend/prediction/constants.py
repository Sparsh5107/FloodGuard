"""Shared constants for the prediction system."""

# Open-Meteo API base URL
OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"

# WMO weather code descriptions
WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain",
    65: "Heavy rain", 71: "Slight snow", 73: "Moderate snow",
    75: "Heavy snow", 80: "Slight showers", 81: "Moderate showers",
    82: "Violent showers", 85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}

# Risk level labels for ML model
RISK_LABELS = {0: "LOW", 1: "MODERATE", 2: "HIGH", 3: "CRITICAL"}

# Flood thresholds (cm)
WARNING_THRESHOLD = 30.0
DANGER_THRESHOLD = 50.0
CRITICAL_THRESHOLD = 70.0
