from django.urls import path
from . import views

urlpatterns = [
    path("predictions/", views.predictions_view, name="predictions"),
    path("api/predictions/", views.predictions_api, name="predictions_api"),
    path("api/predictions/refresh/", views.predictions_refresh_api, name="predictions_refresh_api"),
    path("api/predictions/whatif/", views.whatif_simulator_api, name="whatif_simulator_api"),
    path("api/predictions/<str:device_id>/", views.prediction_detail_api, name="prediction_detail_api"),
    path("api/predictions/<str:device_id>/history/", views.prediction_history_api, name="prediction_history_api"),
]
