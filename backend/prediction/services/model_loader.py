"""Model loader — persists and loads .pkl model files."""

import joblib
from pathlib import Path

# Directory for persisted models
MODEL_DIR = Path(__file__).parent.parent / "ml_models"


def ensure_model_dir():
    """Create model directory if it doesn't exist."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)


def save_model(model, filename):
    """Save a model to disk.

    Args:
        model: trained sklearn model or scaler
        filename: e.g. "flood_model.pkl"
    """
    ensure_model_dir()
    filepath = MODEL_DIR / filename
    joblib.dump(model, filepath)
    return str(filepath)


def load_model(filename):
    """Load a model from disk.

    Args:
        filename: e.g. "flood_model.pkl"

    Returns:
        Loaded model, or None if file doesn't exist.
    """
    filepath = MODEL_DIR / filename
    if not filepath.exists():
        return None
    return joblib.load(filepath)


def model_exists(filename):
    """Check if a model file exists."""
    filepath = MODEL_DIR / filename
    return filepath.exists()


def get_model_info(filename):
    """Get metadata about a saved model."""
    filepath = MODEL_DIR / filename
    if not filepath.exists():
        return None

    stat = filepath.stat()
    return {
        "filename": filename,
        "path": str(filepath),
        "size_kb": round(stat.st_size / 1024, 1),
        "modified": stat.st_mtime,
    }
