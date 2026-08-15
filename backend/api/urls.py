from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'sensors', views.SensorViewSet)
router.register(r'water-levels', views.WaterLevelViewSet)
router.register(r'alerts', views.AlertViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('sensor-data/', views.receive_sensor_data, name='receive-sensor-data'),
    path('sensor-status/', views.sensor_status_api, name='sensor-status'),
    path('system-stats/', views.system_stats_api, name='system-stats'),
    path('dashboard-data/', views.dashboard_data_api, name='dashboard-data'),
    path('sensor-history/<str:device_id>/', views.sensor_history_api, name='sensor-history'),
]
