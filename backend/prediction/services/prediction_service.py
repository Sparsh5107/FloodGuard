"""Prediction service — orchestrates all engines into a single prediction.

Combines weather risk, sensor analysis, anomaly detection, ML model,
and time-to-flood estimation into a unified flood probability score.
"""

from django.utils import timezone
from core.models import Sensor, WaterLevel
from prediction.weather.service import WeatherService
from prediction.weather.risk_engine import calculate_weather_risk
from prediction.ml.features import (
    build_sensor_features, build_weather_features, build_anomaly_features
)
from prediction.ml.anomaly_detector import detect_anomaly
from prediction.ml.water_level_predictor import estimate_time_to_critical
from prediction.ml.explainer import Explainer
from prediction.ml.flood_model import FloodModel
from prediction.models import PredictionResult, PredictionHistory

# Risk fusion weights (used when ML model is not available)
WEIGHT_WEATHER = 0.30
WEIGHT_SENSOR = 0.40
WEIGHT_ANOMALY = 0.15
WEIGHT_HISTORY = 0.15

# Thresholds for risk level classification
RISK_THRESHOLDS = {
    "LOW": (0, 20),
    "MODERATE": (20, 40),
    "ELEVATED": (40, 65),
    "HIGH": (65, 85),
    "CRITICAL": (85, 100),
}

# Module-level cache for ML model (loaded once, reused across requests)
_cached_flood_model = None
_cached_model_loaded = False


class PredictionService:
    """Orchestrates all prediction engines."""

    def __init__(self):
        global _cached_flood_model, _cached_model_loaded
        self.weather_service = WeatherService()
        self.explainer = Explainer()
        # Reuse cached ML model instead of loading from disk every time
        if not _cached_model_loaded:
            _cached_flood_model = FloodModel()
            _cached_flood_model.load()
            _cached_model_loaded = True
        self.flood_model = _cached_flood_model

    def generate_prediction(self, sensor):
        """Generate complete prediction for a single sensor.

        Args:
            sensor: Sensor model instance

        Returns:
            dict with all prediction data
        """
        # 1. Get recent readings
        readings = list(WaterLevel.objects.filter(sensor=sensor)
                       .order_by('-timestamp')[:50])
        levels = [r.level_cm for r in readings]
        timestamps = [r.timestamp for r in readings]

        # 2. Get weather data
        forecast = []
        rainfall_summary = None
        weather_risk = {
            "weather_risk": 0,
            "risk_level": "LOW",
            "factors": [],
            "data_quality": "unavailable",
        }

        if sensor.latitude and sensor.longitude:
            forecast = self.weather_service.get_hourly_forecast(
                sensor.latitude, sensor.longitude
            )
            rainfall_summary = self.weather_service.get_rainfall_summary(
                sensor.latitude, sensor.longitude
            )
            weather_risk = calculate_weather_risk(forecast, rainfall_summary)

        # 3. Detect anomalies
        anomaly_result = detect_anomaly(levels)

        # 4. Build sensor features
        sensor_features = build_sensor_features(sensor, readings)
        current_level = sensor_features["current_level"]
        rise_rate = sensor_features["rise_rate"]

        # 5. Estimate time-to-flood
        time_estimate = estimate_time_to_critical(levels, timestamps)

        # 6. Calculate sensor-based risk (0-100)
        sensor_risk = self._calculate_sensor_risk(sensor_features, time_estimate)

        # 7. Calculate historical risk (0-100)
        history_risk = self._calculate_history_risk(sensor)

        # 8. Get ML prediction (if model available)
        ml_prediction = None
        ml_used = False
        if self.flood_model.is_available():
            ml_features = self._build_ml_features(
                sensor_features, forecast, rainfall_summary, anomaly_result
            )
            ml_prediction = self.flood_model.predict(ml_features)
            if ml_prediction:
                ml_used = True

        # 9. Calculate final flood probability
        if ml_used and ml_prediction:
            # Use ML prediction, but blend with rule-based for robustness
            rule_based = self._fuse_risks(
                weather_risk["weather_risk"],
                sensor_risk,
                anomaly_result["anomaly_score"] * 100,
                history_risk,
            )
            # 70% ML, 30% rule-based
            flood_probability = ml_prediction["flood_probability"] * 0.7 + rule_based * 0.3
            flood_risk_level = ml_prediction["flood_risk_level"]
        else:
            # Rule-based fallback
            flood_probability = self._fuse_risks(
                weather_risk["weather_risk"],
                sensor_risk,
                anomaly_result["anomaly_score"] * 100,
                history_risk,
            )
            flood_risk_level = self._classify_risk(flood_probability)

        # 10. Determine confidence
        confidence = self._determine_confidence(
            len(levels), weather_risk["data_quality"], time_estimate["confidence"],
            ml_used=ml_used
        )

        # 11. Build explanation
        features = {
            "precip_prob_3h": next(
                (f["value"].rstrip("%") for f in weather_risk["factors"]
                 if f["name"] == "precipitation_probability"), "0"
            ),
            "rainfall_3h": sum(h["rain"] for h in forecast[:3]) if forecast else 0,
            "rainfall_6h": sum(h["rain"] for h in forecast[:6]) if forecast else 0,
            "humidity": forecast[0].get("humidity", 0) if forecast else 0,
            "current_level": current_level,
            "rise_rate": rise_rate,
            "acceleration": sensor_features.get("acceleration", 0),
            "distance_to_warning": sensor_features.get("distance_to_warning", 30),
            "distance_to_critical": sensor_features.get("distance_to_critical", 70),
            "is_anomaly": 1 if anomaly_result["is_anomaly"] else 0,
            "z_score": anomaly_result["z_score"],
        }

        # Convert precip_prob_3h back to float
        try:
            features["precip_prob_3h"] = float(features["precip_prob_3h"])
        except (ValueError, TypeError):
            features["precip_prob_3h"] = 0

        explanation = self.explainer.explain(
            {
                "flood_probability": flood_probability,
                "flood_risk_level": flood_risk_level,
            },
            features,
        )

        # 12. Build result
        result = {
            "sensor": sensor,
            "current_level": current_level,
            "rise_rate": rise_rate,

            # Weather
            "weather_risk": weather_risk["weather_risk"],
            "weather_risk_level": weather_risk["risk_level"],
            "weather_factors": weather_risk["factors"],

            # Flood prediction
            "flood_probability": round(flood_probability, 1),
            "flood_risk_level": flood_risk_level,

            # Anomaly
            "anomaly_score": anomaly_result["anomaly_score"],
            "is_anomaly": anomaly_result["is_anomaly"],
            "anomaly_description": anomaly_result["description"],
            "anomaly_classification": anomaly_result["classification"],

            # Time-to-flood
            "time_to_warning": time_estimate["time_to_warning"],
            "time_to_critical": time_estimate["time_to_critical"],
            "distance_to_critical": time_estimate["distance_to_critical"],

            # Metadata
            "confidence": confidence,
            "data_quality": weather_risk["data_quality"],
            "model_version": "v0.3-ml" if ml_used else "v0.3-rules",
            "ml_used": ml_used,

            # Explanation
            "explanation": explanation,

            # Forecast for charts
            "forecast": time_estimate["forecast"],

            # ML details (if available)
            "ml_prediction": ml_prediction,

            # Raw features (for potential ML use)
            "features": {
                "sensor": sensor_features,
                "weather": build_weather_features(forecast, rainfall_summary),
                "anomaly": build_anomaly_features(anomaly_result),
            },
        }

        # 13. Store in database
        self._save_result(result)

        return result

    def generate_all_predictions(self):
        """Generate predictions for all active sensors.

        Returns:
            list of prediction dicts
        """
        sensors = Sensor.objects.filter(is_active=True)
        predictions = []
        for sensor in sensors:
            pred = self.generate_prediction(sensor)
            predictions.append(pred)
        return predictions

    def _build_ml_features(self, sensor_features, forecast, rainfall_summary, anomaly_result):
        """Build feature vector in the format expected by the ML model."""
        weather_features = build_weather_features(forecast, rainfall_summary)
        anomaly_features = build_anomaly_features(anomaly_result)

        # Feature order must match FEATURE_NAMES in synthetic_data.py
        feature_values = [
            # Sensor features
            sensor_features.get("current_level", 0),
            sensor_features.get("level_1m_ago", 0),
            sensor_features.get("level_5m_ago", 0),
            sensor_features.get("level_10m_ago", 0),
            sensor_features.get("level_15m_ago", 0),
            sensor_features.get("rise_rate", 0),
            sensor_features.get("acceleration", 0),
            sensor_features.get("rolling_avg_10", 0),
            sensor_features.get("rolling_std_10", 0),
            sensor_features.get("recent_max", 0),
            sensor_features.get("recent_min", 0),
            sensor_features.get("distance_to_warning", 30),
            sensor_features.get("distance_to_critical", 70),
            # Weather features
            weather_features.get("precip_prob_current", 0),
            weather_features.get("precip_prob_1h", 0),
            weather_features.get("precip_prob_3h", 0),
            weather_features.get("rainfall_1h", 0),
            weather_features.get("rainfall_3h", 0),
            weather_features.get("rainfall_6h", 0),
            weather_features.get("rain_intensity", 0),
            weather_features.get("humidity", 0),
            weather_features.get("cloud_cover", 0),
            weather_features.get("weather_severity", 0),
            # Anomaly features
            anomaly_features.get("anomaly_score", 0),
            anomaly_features.get("z_score", 0),
            anomaly_features.get("is_anomaly", 0),
        ]

        return feature_values

    def _calculate_sensor_risk(self, features, time_estimate):
        """Calculate risk based on sensor readings (0-100)."""
        current = features["current_level"]
        rise_rate = features["rise_rate"]

        # Base risk from current level
        if current >= 70:
            base_risk = 90
        elif current >= 50:
            base_risk = 60 + (current - 50) * 1.5
        elif current >= 30:
            base_risk = 20 + (current - 30) * 2
        else:
            base_risk = current * 0.67

        # Rise rate multiplier
        rate_multiplier = 1.0
        if rise_rate > 3:
            rate_multiplier = 1.5
        elif rise_rate > 1.5:
            rate_multiplier = 1.3
        elif rise_rate > 0.5:
            rate_multiplier = 1.1
        elif rise_rate < -0.5:
            rate_multiplier = 0.8

        risk = base_risk * rate_multiplier
        return min(risk, 100)

    def _calculate_history_risk(self, sensor):
        """Calculate risk based on historical alert frequency."""
        from core.models import Alert

        week_ago = timezone.now() - timezone.timedelta(days=7)
        alert_count = Alert.objects.filter(
            sensor=sensor, created_at__gte=week_ago
        ).count()

        if alert_count >= 10:
            return 80
        elif alert_count >= 5:
            return 60
        elif alert_count >= 2:
            return 40
        elif alert_count >= 1:
            return 20
        return 5

    def _fuse_risks(self, weather_risk, sensor_risk, anomaly_score, history_risk):
        """Combine all risk signals into final probability."""
        fused = (
            weather_risk * WEIGHT_WEATHER +
            sensor_risk * WEIGHT_SENSOR +
            anomaly_score * WEIGHT_ANOMALY +
            history_risk * WEIGHT_HISTORY
        )
        return min(max(fused, 0), 100)

    def _classify_risk(self, score):
        """Map score to risk level."""
        for level, (low, high) in RISK_THRESHOLDS.items():
            if low <= score < high:
                return level
        return "CRITICAL"

    def _determine_confidence(self, readings_count, weather_quality, time_confidence, ml_used=False):
        """Determine overall confidence level."""
        if readings_count < 5 or weather_quality == "unavailable":
            return "low"
        if readings_count < 10 or weather_quality == "partial":
            return "low"
        if ml_used:
            return "high"
        if time_confidence == "low":
            return "medium"
        return "high"

    def _save_result(self, result):
        """Save prediction to database."""
        PredictionResult.objects.update_or_create(
            sensor=result["sensor"],
            defaults={
                "weather_risk": result["weather_risk"],
                "weather_risk_level": result["weather_risk_level"],
                "weather_factors": result["weather_factors"],
                "flood_probability": result["flood_probability"],
                "flood_risk_level": result["flood_risk_level"],
                "flood_factors": result["explanation"],
                "anomaly_score": result["anomaly_score"],
                "is_anomaly": result["is_anomaly"],
                "anomaly_description": result["anomaly_description"],
                "time_to_warning": result["time_to_warning"] or "",
                "time_to_critical": result["time_to_critical"] or "",
                "distance_to_critical": result["distance_to_critical"],
                "current_level": result["current_level"],
                "rise_rate": result["rise_rate"],
                "confidence": result["confidence"],
                "data_quality": result["data_quality"],
                "model_version": result["model_version"],
            }
        )

        # Save history snapshot
        PredictionHistory.objects.create(
            sensor=result["sensor"],
            flood_probability=result["flood_probability"],
            weather_risk=result["weather_risk"],
            current_level=result["current_level"],
        )
