import json
import threading
from django.shortcuts import render
from django.http import JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.core.cache import cache
from core.models import Sensor
from prediction.services.prediction_service import PredictionService
from prediction.models import PredictionResult, PredictionHistory

# Cache timeout for predictions (5 minutes)
PREDICTIONS_CACHE_TIMEOUT = 300


def _serialize_prediction(pred):
    """Convert a prediction dict to a JSON-serializable dict."""
    sensor = pred["sensor"]
    return {
        "device_id": sensor.device_id,
        "name": sensor.name,
        "location": sensor.location,
        "latitude": sensor.latitude,
        "longitude": sensor.longitude,
        "current_level": pred["current_level"],
        "rise_rate": pred["rise_rate"],
        "last_seen": sensor.last_seen.isoformat() if sensor.last_seen else None,

        "weather_risk": pred["weather_risk"],
        "weather_risk_level": pred["weather_risk_level"],
        "weather_factors": pred["weather_factors"],

        "flood_probability": pred["flood_probability"],
        "flood_risk_level": pred["flood_risk_level"],

        "anomaly_score": pred["anomaly_score"],
        "is_anomaly": pred["is_anomaly"],
        "anomaly_description": pred["anomaly_description"],
        "anomaly_classification": pred["anomaly_classification"],

        "time_to_warning": pred["time_to_warning"],
        "time_to_critical": pred["time_to_critical"],
        "distance_to_critical": pred["distance_to_critical"],

        "confidence": pred["confidence"],
        "data_quality": pred["data_quality"],
        "model_version": pred["model_version"],
        "ml_used": pred["ml_used"],

        "explanation": pred["explanation"],
        "forecast": pred["forecast"],
        "ml_prediction": pred.get("ml_prediction"),
    }


def _serialize_from_db():
    """Build prediction JSON from saved PredictionResult rows (instant, no API calls)."""
    results = PredictionResult.objects.select_related('sensor').all()
    if not results.exists():
        return None
    serialized = []
    for pr in results:
        sensor = pr.sensor
        serialized.append({
            "device_id": sensor.device_id,
            "name": sensor.name,
            "location": sensor.location,
            "latitude": sensor.latitude,
            "longitude": sensor.longitude,
            "current_level": pr.current_level,
            "rise_rate": pr.rise_rate,
            "last_seen": sensor.last_seen.isoformat() if sensor.last_seen else None,

            "weather_risk": pr.weather_risk,
            "weather_risk_level": pr.weather_risk_level,
            "weather_factors": pr.weather_factors or [],

            "flood_probability": pr.flood_probability,
            "flood_risk_level": pr.flood_risk_level,

            "anomaly_score": pr.anomaly_score,
            "is_anomaly": pr.is_anomaly,
            "anomaly_description": pr.anomaly_description,
            "anomaly_classification": "NORMAL",

            "time_to_warning": pr.time_to_warning or None,
            "time_to_critical": pr.time_to_critical or None,
            "distance_to_critical": pr.distance_to_critical,

            "confidence": pr.confidence,
            "data_quality": pr.data_quality,
            "model_version": pr.model_version,
            "ml_used": "ml" in pr.model_version,

            "explanation": pr.flood_factors or {},
            "forecast": [],
            "ml_prediction": None,
        })
    return json.dumps(serialized, cls=DjangoJSONEncoder)


def _refresh_cache_async():
    """Regenerate predictions and update cache in background."""
    try:
        service = PredictionService()
        predictions = service.generate_all_predictions()
        serialized = [_serialize_prediction(p) for p in predictions]
        predictions_json = json.dumps(serialized, cls=DjangoJSONEncoder)
        cache.set("all_predictions_json", predictions_json, PREDICTIONS_CACHE_TIMEOUT)
    except Exception:
        pass


def _get_cached_predictions():
    """Get predictions from cache, DB, or generate fresh ones.

    Priority:
    1. In-memory cache (instant)
    2. Database PredictionResult table (instant, stale-ok) + trigger background refresh
    3. Synchronous generation (slow, first-time only)
    """
    cache_key = "all_predictions_json"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Try DB — instant, no weather API calls
    db_json = _serialize_from_db()
    if db_json:
        # Serve DB data immediately, refresh cache in background
        threading.Thread(target=_refresh_cache_async, daemon=True).start()
        cache.set(cache_key, db_json, PREDICTIONS_CACHE_TIMEOUT)
        return db_json

    # First time ever — generate synchronously
    service = PredictionService()
    predictions = service.generate_all_predictions()
    serialized = [_serialize_prediction(p) for p in predictions]
    predictions_json = json.dumps(serialized, cls=DjangoJSONEncoder)

    cache.set(cache_key, predictions_json, PREDICTIONS_CACHE_TIMEOUT)
    return predictions_json


def predictions_view(request):
    """Render the predictions dashboard page (fast - uses cache)."""
    predictions_json = _get_cached_predictions()

    context = {
        "predictions_json": predictions_json,
    }
    return render(request, "predictions.html", context)


def predictions_api(request):
    """API endpoint: return predictions for all sensors as JSON (fast - uses cache)."""
    predictions_json = _get_cached_predictions()
    predictions = json.loads(predictions_json)

    return JsonResponse({"predictions": predictions}, encoder=DjangoJSONEncoder)


def predictions_refresh_api(request):
    """API endpoint: force refresh predictions cache."""
    from prediction.background import trigger_update
    trigger_update()

    # Return fresh predictions
    predictions_json = _get_cached_predictions()
    predictions = json.loads(predictions_json)

    return JsonResponse({
        "predictions": predictions,
        "refreshed": True,
    }, encoder=DjangoJSONEncoder)


def prediction_detail_api(request, device_id):
    """API endpoint: return prediction for a single sensor."""
    try:
        sensor = Sensor.objects.get(device_id=device_id)
    except Sensor.DoesNotExist:
        return JsonResponse({"error": "Sensor not found"}, status=404)

    service = PredictionService()
    pred = service.generate_prediction(sensor)

    return JsonResponse(_serialize_prediction(pred), encoder=DjangoJSONEncoder)


def prediction_history_api(request, device_id):
    """API endpoint: return prediction history for charts."""
    try:
        sensor = Sensor.objects.get(device_id=device_id)
    except Sensor.DoesNotExist:
        return JsonResponse({"error": "Sensor not found"}, status=404)

    history = PredictionHistory.objects.filter(sensor=sensor)[:50]

    data = [{
        "flood_probability": h.flood_probability,
        "weather_risk": h.weather_risk,
        "current_level": h.current_level,
        "timestamp": h.timestamp.isoformat(),
    } for h in history]

    return JsonResponse({"history": data}, encoder=DjangoJSONEncoder)


def whatif_simulator_api(request):
    """API endpoint: simulate flood risk using SCS Curve Number method."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    device_id = body.get("device_id")
    rainfall_mm = float(body.get("rainfall_mm", 0))
    duration_hours = float(body.get("duration_hours", 1))
    soil_type = body.get("soil_type", "loam")
    land_use = body.get("land_use", "residential")

    try:
        sensor = Sensor.objects.get(device_id=device_id)
    except Sensor.DoesNotExist:
        return JsonResponse({"error": "Sensor not found"}, status=404)

    # Get current state
    from core.models import WaterLevel

    latest = WaterLevel.objects.filter(sensor=sensor).order_by('-timestamp').first()
    current_level = latest.level_cm if latest else 25.0

    # === SCS CURVE NUMBER LOOKUP TABLE ===
    # CN values from USDA NRCS TR-55
    CN_TABLE = {
        "forest":      {"sandy": 30, "loam": 40, "clay_loam": 48, "clay": 55},
        "pasture":     {"sandy": 39, "loam": 55, "clay_loam": 67, "clay": 74},
        "agriculture": {"sandy": 55, "loam": 68, "clay_loam": 76, "clay": 82},
        "residential": {"sandy": 61, "loam": 74, "clay_loam": 82, "clay": 87},
        "commercial":  {"sandy": 85, "loam": 90, "clay_loam": 94, "clay": 98},
    }

    # Soil type descriptions
    SOIL_DESC = {
        "sandy": "High infiltration, low runoff",
        "loam": "Moderate infiltration",
        "clay_loam": "Low infiltration, moderate runoff",
        "clay": "Very low infiltration, high runoff",
    }

    # Land use descriptions
    LAND_DESC = {
        "forest": "Trees, high infiltration, low runoff",
        "pasture": "Grass, moderate infiltration",
        "agriculture": "Crops, variable infiltration",
        "residential": "Houses with yards, moderate-high runoff",
        "commercial": "Mostly pavement, very high runoff",
    }

    # === STEP 1: Get CN value ===
    cn = CN_TABLE.get(land_use, {}).get(soil_type, 74)

    # === STEP 2: SCS Runoff Equation ===
    # S = potential maximum retention (mm)
    # Ia = initial abstraction (mm)
    # Q = direct runoff (mm)
    S = 1000.0 / cn - 10.0
    Ia = 0.2 * S

    if rainfall_mm <= Ia:
        runoff_mm = 0.0  # No runoff - all absorbed
    else:
        runoff_mm = (rainfall_mm - Ia) ** 2 / (rainfall_mm - Ia + S)

    runoff_pct = (runoff_mm / rainfall_mm * 100) if rainfall_mm > 0 else 0

    # === STEP 3: Rainfall intensity ===
    intensity = rainfall_mm / max(duration_hours, 1)  # mm/hr

    # Classify intensity (WMO standard)
    if intensity < 2.5:
        intensity_class = "LIGHT"
        intensity_desc = "Drizzle, steady light rain"
    elif intensity < 7.5:
        intensity_class = "MODERATE"
        intensity_desc = "Steady rainfall, visible accumulation"
    elif intensity < 50:
        intensity_class = "HEAVY"
        intensity_desc = "Intense rain, poor visibility"
    else:
        intensity_class = "EXTREME"
        intensity_desc = "Tropical deluge, flash flood risk"

    # === STEP 4: Convert runoff to water level rise (cm) ===
    # 1mm runoff = 0.1cm water level rise (simplified)
    rise_cm = runoff_mm / 10.0

    # === STEP 5: Projected level ===
    projected_level = current_level + rise_cm
    projected_level = max(0, projected_level)

    # === STEP 6: Risk calculation ===
    if projected_level >= 70:
        risk = 90 + min((projected_level - 70) / 10, 10)
    elif projected_level >= 50:
        risk = 65 + (projected_level - 50) * 1.25
    elif projected_level >= 30:
        risk = 35 + (projected_level - 30) * 1.5
    elif projected_level >= 15:
        risk = 15 + (projected_level - 15) * 1.33
    else:
        risk = projected_level * 1.0

    risk = min(max(risk, 0), 100)

    # === STEP 7: Time to critical ===
    dist_critical = 70 - projected_level
    if dist_critical <= 0:
        time_to_critical = "ALREADY_EXCEEDED"
    elif rise_cm > 0 and duration_hours > 0:
        rise_per_min = rise_cm / (duration_hours * 60)
        minutes_to_critical = (dist_critical / rise_per_min) * 1.2
        if minutes_to_critical <= 60:
            time_to_critical = f"~{int(round(minutes_to_critical))} min"
        elif minutes_to_critical <= 360:
            hours = int(minutes_to_critical // 60)
            mins = int(minutes_to_critical % 60)
            time_to_critical = f"~{hours}h {mins}m"
        else:
            time_to_critical = None
    else:
        time_to_critical = None

    # === STEP 8: Risk level ===
    if risk >= 85:
        risk_level = "CRITICAL"
    elif risk >= 65:
        risk_level = "HIGH"
    elif risk >= 40:
        risk_level = "ELEVATED"
    elif risk >= 20:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return JsonResponse({
        "device_id": device_id,
        "current_level": round(current_level, 1),
        "rainfall_mm": rainfall_mm,
        "duration_hours": duration_hours,
        "soil_type": soil_type,
        "soil_desc": SOIL_DESC.get(soil_type, ""),
        "land_use": land_use,
        "land_desc": LAND_DESC.get(land_use, ""),
        "cn": cn,
        "retention": round(S, 1),
        "initial_abstraction": round(Ia, 1),
        "intensity": round(intensity, 1),
        "intensity_class": intensity_class,
        "intensity_desc": intensity_desc,
        "runoff_mm": round(runoff_mm, 1),
        "runoff_pct": round(runoff_pct, 1),
        "rise_cm": round(rise_cm, 1),
        "projected_level": round(projected_level, 1),
        "flood_risk": round(risk, 1),
        "risk_level": risk_level,
        "time_to_critical": time_to_critical,
        "would_exceed_warning": projected_level >= 30,
        "would_exceed_critical": projected_level >= 70,
    })
