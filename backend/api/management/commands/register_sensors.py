from django.core.management.base import BaseCommand
from core.models import Sensor


class Command(BaseCommand):
    help = 'Register ESP32 sensors in the database'

    def handle(self, *args, **options):
        sensors = [
            {
                'device_id': 'esp32-001',
                'name': 'Sensor A',
                'location': 'Location A',
            },
            {
                'device_id': 'esp32-002',
                'name': 'Sensor B',
                'location': 'Location B',
            },
        ]

        for sensor_data in sensors:
            sensor, created = Sensor.objects.get_or_create(
                device_id=sensor_data['device_id'],
                defaults=sensor_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created sensor: {sensor.name}'))
            else:
                self.stdout.write(f'Sensor already exists: {sensor.name}')
