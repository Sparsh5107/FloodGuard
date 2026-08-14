from rest_framework import serializers
from core.models import Sensor, WaterLevel, Alert


class SensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = '__all__'


class WaterLevelSerializer(serializers.ModelSerializer):
    sensor_name = serializers.CharField(source='sensor.name', read_only=True)

    class Meta:
        model = WaterLevel
        fields = ['id', 'sensor', 'sensor_name', 'level_cm', 'timestamp', 'is_alert']


class AlertSerializer(serializers.ModelSerializer):
    sensor_name = serializers.CharField(source='sensor.name', read_only=True)

    class Meta:
        model = Alert
        fields = ['id', 'sensor', 'sensor_name', 'water_level', 'alert_type', 'message', 'is_resolved', 'created_at']
