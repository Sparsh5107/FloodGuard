import requests

FLOOD_API_BASE = "https://flood-api.open-meteo.com/v1/flood"


def get_river_discharge(latitude, longitude, days=30):
    """Get river discharge forecast from GloFAS flood API."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "river_discharge,river_discharge_mean,river_discharge_max,river_discharge_min,river_discharge_median",
        "forecast_days": days,
    }
    try:
        resp = requests.get(FLOOD_API_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        daily = data.get("daily", {})

        times = daily.get("time", [])
        result = []
        for i, t in enumerate(times):
            result.append({
                "date": t,
                "river_discharge": daily.get("river_discharge", [])[i] if i < len(daily.get("river_discharge", [])) else None,
                "river_discharge_mean": daily.get("river_discharge_mean", [])[i] if i < len(daily.get("river_discharge_mean", [])) else None,
                "river_discharge_max": daily.get("river_discharge_max", [])[i] if i < len(daily.get("river_discharge_max", [])) else None,
                "river_discharge_min": daily.get("river_discharge_min", [])[i] if i < len(daily.get("river_discharge_min", [])) else None,
                "river_discharge_median": daily.get("river_discharge_median", [])[i] if i < len(daily.get("river_discharge_median", [])) else None,
            })

        if not result:
            return None

        current_discharge = result[0].get("river_discharge") or result[0].get("river_discharge_mean")
        peak_discharge = max(
            (r.get("river_discharge") or r.get("river_discharge_mean") or 0 for r in result),
            default=0,
        )
        avg_discharge = None
        valid_values = [r.get("river_discharge") or r.get("river_discharge_mean") for r in result if r.get("river_discharge") or r.get("river_discharge_mean")]
        if valid_values:
            avg_discharge = round(sum(valid_values) / len(valid_values), 2)

        return {
            "daily": result,
            "summary": {
                "current_discharge": current_discharge,
                "peak_discharge_30d": round(peak_discharge, 2) if peak_discharge else None,
                "avg_discharge_30d": avg_discharge,
                "is_above_average": current_discharge > avg_discharge if current_discharge and avg_discharge else None,
            },
        }
    except requests.RequestException:
        return None
