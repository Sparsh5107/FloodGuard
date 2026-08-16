"""Explainer — generates human-readable explanations for predictions.

Uses feature contribution scoring to explain why a prediction
was made, without requiring SHAP or model-specific integration.
"""


class Explainer:
    """Generate plain-English explanations for flood predictions."""

    def explain(self, prediction, features):
        """Generate explanation for a prediction.

        Args:
            prediction: dict with flood_probability, flood_risk_level, etc.
            features: dict of all feature values

        Returns:
            dict with summary and factors list
        """
        factors = []

        # Weather contributions
        self._add_weather_factors(features, factors)

        # Sensor contributions
        self._add_sensor_factors(features, factors)

        # Anomaly
        self._add_anomaly_factors(features, factors)

        # Proximity to threshold
        self._add_threshold_factors(features, factors)

        # Sort by contribution percentage (highest first)
        factors.sort(key=lambda x: x["contribution_pct"], reverse=True)

        summary = self._generate_summary(prediction, factors)

        return {
            "summary": summary,
            "factors": factors,
        }

    def _add_weather_factors(self, features, factors):
        """Add weather-related explanation factors."""
        precip_prob = features.get("precip_prob_3h", 0)
        rainfall_3h = features.get("rainfall_3h", 0)
        rainfall_6h = features.get("rainfall_6h", 0)
        humidity = features.get("humidity", 0)

        if precip_prob > 70:
            factors.append({
                "icon": "rain",
                "text": f"{precip_prob}% rain probability in 3 hours",
                "impact": "high",
                "contribution_pct": 30,
            })
        elif precip_prob > 40:
            factors.append({
                "icon": "rain",
                "text": f"{precip_prob}% rain probability",
                "impact": "medium",
                "contribution_pct": 20,
            })

        if rainfall_3h > 10:
            factors.append({
                "icon": "cloud",
                "text": f"Heavy rainfall expected: {rainfall_3h:.1f}mm in 3 hours",
                "impact": "high",
                "contribution_pct": 25,
            })
        elif rainfall_3h > 3:
            factors.append({
                "icon": "cloud",
                "text": f"Moderate rainfall: {rainfall_3h:.1f}mm in 3 hours",
                "impact": "medium",
                "contribution_pct": 15,
            })

        if rainfall_6h > 20:
            factors.append({
                "icon": "cloud",
                "text": f"{rainfall_6h:.1f}mm expected in 6 hours",
                "impact": "medium",
                "contribution_pct": 10,
            })

        if humidity > 90:
            factors.append({
                "icon": "droplet",
                "text": f"High humidity: {humidity}%",
                "impact": "low",
                "contribution_pct": 5,
            })

    def _add_sensor_factors(self, features, factors):
        """Add sensor-related explanation factors."""
        rise_rate = features.get("rise_rate", 0)
        acceleration = features.get("acceleration", 0)
        current = features.get("current_level", 0)

        if rise_rate > 2:
            factors.append({
                "icon": "rising",
                "text": f"Water rising fast at {rise_rate:.1f} cm/min",
                "impact": "high",
                "contribution_pct": 28,
            })
        elif rise_rate > 0.5:
            factors.append({
                "icon": "rising",
                "text": f"Water rising at {rise_rate:.1f} cm/min",
                "impact": "medium",
                "contribution_pct": 15,
            })
        elif rise_rate < -1:
            factors.append({
                "icon": "falling",
                "text": f"Water level falling at {abs(rise_rate):.1f} cm/min",
                "impact": "low",
                "contribution_pct": -10,
            })

        if acceleration > 3:
            factors.append({
                "icon": "warning",
                "text": f"Rise is accelerating ({acceleration:+.1f})",
                "impact": "high",
                "contribution_pct": 12,
            })

    def _add_anomaly_factors(self, features, factors):
        """Add anomaly-related explanation factors."""
        is_anomaly = features.get("is_anomaly", 0)
        z_score = features.get("z_score", 0)

        if is_anomaly:
            factors.append({
                "icon": "warning",
                "text": f"Abnormal surge detected (z-score: {z_score})",
                "impact": "high",
                "contribution_pct": 18,
            })

    def _add_threshold_factors(self, features, factors):
        """Add threshold proximity factors."""
        current = features.get("current_level", 0)
        dist_warning = features.get("distance_to_warning", 30)
        dist_critical = features.get("distance_to_critical", 70)

        if dist_critical < 10:
            factors.append({
                "icon": "target",
                "text": f"Only {dist_critical:.0f}cm to critical threshold (70cm)",
                "impact": "high",
                "contribution_pct": 15,
            })
        elif dist_critical < 25:
            factors.append({
                "icon": "target",
                "text": f"{dist_critical:.0f}cm to critical threshold",
                "impact": "medium",
                "contribution_pct": 10,
            })
        elif dist_warning < 5:
            factors.append({
                "icon": "target",
                "text": f"Close to warning threshold ({dist_warning:.0f}cm away)",
                "impact": "medium",
                "contribution_pct": 8,
            })

    def _generate_summary(self, prediction, factors):
        """Generate one-line summary."""
        level = prediction.get("flood_risk_level", "LOW")
        prob = prediction.get("flood_probability", 0)

        if not factors:
            return f"{level} risk ({prob}%)"

        top_factor = factors[0]["text"]
        return f"{level} risk ({prob}%) — primarily driven by: {top_factor}"
