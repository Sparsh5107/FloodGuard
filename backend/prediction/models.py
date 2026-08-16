from django.db import models


class PredictionResult(models.Model):
    """Stores the latest prediction for each sensor."""
    sensor = models.OneToOneField('core.Sensor', on_delete=models.CASCADE, related_name='prediction')

    # Weather Risk Layer
    weather_risk = models.FloatField(default=0)
    weather_risk_level = models.CharField(max_length=20, default='LOW')
    weather_factors = models.JSONField(default=dict)

    # Full Flood Prediction
    flood_probability = models.FloatField(default=0)
    flood_risk_level = models.CharField(max_length=20, default='LOW')
    flood_factors = models.JSONField(default=dict)

    # Anomaly
    anomaly_score = models.FloatField(default=0)
    is_anomaly = models.BooleanField(default=False)
    anomaly_description = models.CharField(max_length=200, blank=True)

    # Time-to-Flood
    time_to_warning = models.CharField(max_length=20, blank=True)
    time_to_critical = models.CharField(max_length=20, blank=True)
    distance_to_critical = models.FloatField(null=True, blank=True)

    # Sensor state
    current_level = models.FloatField(default=0)
    rise_rate = models.FloatField(default=0)

    # Metadata
    confidence = models.CharField(max_length=10, default='low')
    data_quality = models.CharField(max_length=20, default='insufficient')
    model_version = models.CharField(max_length=20, default='v0.1')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Prediction for {self.sensor.name} - {self.flood_risk_level}"


class PredictionHistory(models.Model):
    """Stores prediction snapshots for historical charts."""
    sensor = models.ForeignKey('core.Sensor', on_delete=models.CASCADE, related_name='prediction_history')
    flood_probability = models.FloatField()
    weather_risk = models.FloatField()
    current_level = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['sensor', 'timestamp']),
        ]

    def __str__(self):
        return f"History {self.sensor.name} - {self.flood_probability}%"
