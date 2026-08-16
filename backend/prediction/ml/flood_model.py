"""Flood prediction model — Random Forest classifier wrapper.

Handles prediction, feature importance, and model metadata.
"""

import logging
import numpy as np
from prediction.services.model_loader import load_model
from prediction.constants import RISK_LABELS

logger = logging.getLogger(__name__)

MODEL_FILE = "flood_model.pkl"
SCALER_FILE = "flood_scaler.pkl"


class FloodModel:
    """Random Forest flood prediction model."""

    def __init__(self):
        self.model = None
        self.scaler = None
        self.is_loaded = False

    def load(self):
        """Load the trained model from disk."""
        self.model = load_model(MODEL_FILE)
        self.scaler = load_model(SCALER_FILE)
        self.is_loaded = self.model is not None
        if self.is_loaded and self.scaler is None:
            logger.warning("flood_scaler.pkl not found — ML predictions will run without feature scaling")
        return self.is_loaded

    def predict(self, features):
        """Predict flood probability from feature vector.

        Args:
            features: dict or list of feature values

        Returns:
            dict with flood_probability, flood_risk_level, confidence, feature_importance
        """
        if not self.is_loaded:
            return None

        # Convert dict to list if needed
        if isinstance(features, dict):
            feature_values = list(features.values())
        else:
            feature_values = features

        # Reshape for sklearn (expects 2D array)
        X = np.array(feature_values).reshape(1, -1)

        # Scale features if scaler exists
        if self.scaler is not None:
            X = self.scaler.transform(X)

        # Get prediction and probabilities
        prediction = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]

        # Flood probability is the max probability across all classes
        # But we want the probability of HIGH or CRITICAL specifically
        flood_prob = float(probabilities[2] + probabilities[3]) * 100 if len(probabilities) > 3 else float(max(probabilities)) * 100

        # Risk level from prediction
        risk_level = RISK_LABELS.get(prediction, "LOW")

        # Confidence from probability spread
        confidence = float(max(probabilities))

        # Feature importance
        feature_importance = self._get_feature_importance()

        return {
            "flood_probability": round(min(flood_prob, 100), 1),
            "flood_risk_level": risk_level,
            "confidence": round(confidence, 3),
            "class_probabilities": {
                RISK_LABELS.get(i, f"class_{i}"): round(float(p) * 100, 1)
                for i, p in enumerate(probabilities)
            },
            "feature_importance": feature_importance,
        }

    def _get_feature_importance(self):
        """Get top feature importances from the model."""
        if self.model is None:
            return []

        importances = self.model.feature_importances_
        from prediction.services.synthetic_data import get_feature_names
        feature_names = get_feature_names()

        # Sort by importance
        pairs = list(zip(feature_names, importances))
        pairs.sort(key=lambda x: x[1], reverse=True)

        return [
            {"name": name, "importance": round(float(imp), 4)}
            for name, imp in pairs[:10]
        ]

    def is_available(self):
        """Check if model is loaded and ready."""
        return self.is_loaded


