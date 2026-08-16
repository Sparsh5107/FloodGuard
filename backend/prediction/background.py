"""Background prediction updater — runs predictions in background thread.

Periodically updates predictions cache so page loads are always fast.
"""

import threading
import time
import json
import logging
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)

# Cache key and timeout
CACHE_KEY = "all_predictions_json"
CACHE_TIMEOUT = 600  # 10 minutes
UPDATE_INTERVAL = 300  # 5 minutes between updates

# Background thread reference
_background_thread = None
_stop_event = threading.Event()


def _update_predictions():
    """Generate predictions and update cache."""
    try:
        from prediction.services.prediction_service import PredictionService
        from prediction.views import _serialize_prediction

        service = PredictionService()
        predictions = service.generate_all_predictions()
        serialized = [_serialize_prediction(p) for p in predictions]
        predictions_json = json.dumps(serialized, cls=DjangoJSONEncoder)

        cache.set(CACHE_KEY, predictions_json, CACHE_TIMEOUT)
        logger.info(f"Background prediction update: {len(predictions)} sensors updated")
    except Exception as e:
        logger.error(f"Background prediction update failed: {e}")


def _background_loop():
    """Background thread loop — updates predictions periodically."""
    logger.info("Background prediction updater started")

    # Initial update on startup
    _update_predictions()

    while not _stop_event.is_set():
        # Wait for the update interval (or until stopped)
        _stop_event.wait(UPDATE_INTERVAL)

        if not _stop_event.is_set():
            _update_predictions()

    logger.info("Background prediction updater stopped")


def start_background_updater():
    """Start the background prediction updater thread."""
    global _background_thread

    if _background_thread is not None and _background_thread.is_alive():
        logger.info("Background updater already running")
        return

    _stop_event.clear()
    _background_thread = threading.Thread(
        target=_background_loop,
        daemon=True,
        name="prediction-updater"
    )
    _background_thread.start()
    logger.info("Background prediction updater thread started")


def trigger_update():
    """Manually trigger an immediate prediction update."""
    _update_predictions()
