import json
from channels.generic.websocket import WebsocketConsumer


class SensorDataConsumer(WebsocketConsumer):
    def connect(self):
        self.sensor_group_name = 'sensor_data'
        self.channel_layer.group_add(
            self.sensor_group_name,
            self.channel_name
        )
        self.accept()

    def disconnect(self, close_code):
        self.channel_layer.group_discard(
            self.sensor_group_name,
            self.channel_name
        )

    def receive(self, text_data):
        pass

    def sensor_update(self, event):
        self.send(text_data=json.dumps({
            'type': 'sensor_update',
            'device_id': event['device_id'],
            'level_cm': event['level_cm'],
            'status': event['status'],
            'timestamp': event['timestamp'],
            'is_alert': event.get('is_alert', False),
        }))

    def alert_update(self, event):
        self.send(text_data=json.dumps({
            'type': 'alert_update',
            'alert_type': event['alert_type'],
            'sensor_name': event['sensor_name'],
            'message': event['message'],
            'timestamp': event['timestamp'],
        }))
