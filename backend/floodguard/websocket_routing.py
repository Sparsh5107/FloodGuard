from django.urls import re_path
from floodguard import consumers

websocket_urlpatterns = [
    re_path(r'ws/sensors/$', consumers.SensorDataConsumer.as_asgi()),
]
