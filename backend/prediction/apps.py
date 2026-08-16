import os
from django.apps import AppConfig


class PredictionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'prediction'

    def ready(self):
        """Start background prediction updater when Django starts."""
        # Only start in the main process (not in reloader or management commands)
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('DJANGO_SETTINGS_MODULE'):
            try:
                from prediction.background import start_background_updater
                start_background_updater()
            except Exception:
                pass  # Don't crash if background thread fails to start
