from django.contrib import admin
from prediction.models import PredictionResult, PredictionHistory


@admin.register(PredictionResult)
class PredictionResultAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'flood_probability', 'flood_risk_level', 'weather_risk', 'confidence', 'model_version')
    list_filter = ('flood_risk_level', 'confidence', 'model_version')
    search_fields = ('sensor__name', 'sensor__device_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PredictionHistory)
class PredictionHistoryAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'flood_probability', 'weather_risk', 'current_level', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('sensor__name', 'sensor__device_id')
    readonly_fields = ('timestamp',)
