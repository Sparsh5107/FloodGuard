import requests
from datetime import datetime
from prediction.constants import OPEN_METEO_BASE, WEATHER_CODES

# Simple in-memory cache: key = (lat, lon), value = (timestamp, data)
_cache = {}
_CACHE_TTL_SECONDS = 900  # 15 minutes


class WeatherService:
    """Open-Meteo API client for current conditions and hourly forecasts."""

    def _cache_key(self, lat, lon):
        return (round(lat, 2), round(lon, 2))

    def _is_cached(self, key):
        if key in _cache:
            ts, _ = _cache[key]
            if (datetime.now() - ts).total_seconds() < _CACHE_TTL_SECONDS:
                return True
        return False

    def get_current(self, latitude, longitude):
        """Get current weather conditions for a sensor location."""
        key = self._cache_key(latitude, longitude)
        if self._is_cached(key):
            return _cache[key][1].get("current_raw")

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

            code = current.get("weather_code", 0)

            result = {
                "temperature": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "rain": current.get("rain", 0),
                "precipitation": current.get("precipitation", 0),
                "weather_code": code,
                "weather_description": WEATHER_CODES.get(code, "Unknown"),
                "wind_speed": current.get("wind_speed_10m"),
                "wind_direction": current.get("wind_direction_10m"),
                "cloud_cover": current.get("cloud_cover"),
                "pressure": current.get("surface_pressure"),
            }

            # Cache it
            if key not in _cache:
                _cache[key] = (datetime.now(), {})
            _cache[key][1]["current_raw"] = result

            return result
        except requests.RequestException:
            return None

    def get_hourly_forecast(self, latitude, longitude, days=3):
        """Get hourly forecast for next N days.

        Returns a list of dicts, each with:
            time, precipitation_probability, precipitation, rain,
            humidity, cloud_cover, weather_code
        """
        # Check cache first (reuse if available)
        key = self._cache_key(latitude, longitude)
        cache_key_forecast = f"forecast_{key}_{days}"
        if cache_key_forecast in _cache:
            ts, data = _cache[cache_key_forecast]
            if (datetime.now() - ts).total_seconds() < _CACHE_TTL_SECONDS:
                return data

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "precipitation_probability,precipitation,rain,relative_humidity_2m,cloud_cover,weather_code",
            "forecast_days": days,
            "timezone": "auto",
        }
        try:
            resp = requests.get(OPEN_METEO_BASE, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            hourly = data.get("hourly", {})

            times = hourly.get("time", [])
            precip_prob = hourly.get("precipitation_probability", [])
            precipitation = hourly.get("precipitation", [])
            rain = hourly.get("rain", [])
            humidity = hourly.get("relative_humidity_2m", [])
            cloud_cover = hourly.get("cloud_cover", [])
            weather_code = hourly.get("weather_code", [])

            forecast = []
            for i in range(len(times)):
                forecast.append({
                    "time": times[i],
                    "precipitation_probability": precip_prob[i] if i < len(precip_prob) else 0,
                    "precipitation": precipitation[i] if i < len(precipitation) else 0,
                    "rain": rain[i] if i < len(rain) else 0,
                    "humidity": humidity[i] if i < len(humidity) else 0,
                    "cloud_cover": cloud_cover[i] if i < len(cloud_cover) else 0,
                    "weather_code": weather_code[i] if i < len(weather_code) else 0,
                })

            # Cache the result
            _cache[cache_key_forecast] = (datetime.now(), forecast)

            return forecast
        except requests.RequestException:
            return []

    def get_rainfall_summary(self, latitude, longitude):
        """Get aggregated rainfall metrics from hourly forecast.

        Returns:
            rain_1h, rain_3h, rain_6h, rain_24h,
            max_intensity, avg_probability
        """
        forecast = self.get_hourly_forecast(latitude, longitude, days=2)
        if not forecast:
            return None

        # Take next 24 hours
        upcoming = forecast[:24]

        rain_1h = upcoming[0]["rain"] if len(upcoming) > 0 else 0
        rain_3h = sum(h["rain"] for h in upcoming[:3])
        rain_6h = sum(h["rain"] for h in upcoming[:6])
        rain_24h = sum(h["rain"] for h in upcoming)
        max_intensity = max((h["precipitation"] for h in upcoming), default=0)
        avg_probability = sum(h["precipitation_probability"] for h in upcoming) / max(len(upcoming), 1)

        return {
            "rain_1h": round(rain_1h, 2),
            "rain_3h": round(rain_3h, 2),
            "rain_6h": round(rain_6h, 2),
            "rain_24h": round(rain_24h, 2),
            "max_intensity": round(max_intensity, 2),
            "avg_probability": round(avg_probability, 1),
        }
