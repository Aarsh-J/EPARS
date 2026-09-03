"""
modules/ml/loader.py
========================
Lazy singleton loaders for the pickled models in ml_models/. Each is a
module-level cache so repeated requests don't re-hit disk. See ml_models/README.md
for what's inside each pickle and where the pieces were recovered from.
"""

from functools import lru_cache
from pathlib import Path

import joblib

MODELS_DIR = Path(__file__).resolve().parents[2] / "ml_models"


@lru_cache(maxsize=1)
def get_performance_model():
    """
    Returns {"model": Ridge, "scaler": StandardScaler, "type": "ridge"}. The
    two pieces ship as separate pickles (performance_ridge_model.pkl /
    performance_scaler.pkl) — this wraps them into the same dict shape the
    rest of modules/ml/ already expects.
    """
    return {
        "model": joblib.load(MODELS_DIR / "performance_ridge_model.pkl"),
        "scaler": joblib.load(MODELS_DIR / "performance_scaler.pkl"),
        "type": "ridge",
    }


@lru_cache(maxsize=1)
def get_burnout_model():
    """Returns {"model": GradientBoostingRegressor, "features": [...], "low_max": float, "medium_max": float}."""
    return joblib.load(MODELS_DIR / "burnout_model_bundle.pkl")


def preload_models():
    """
    Call once at API startup so a broken/missing pickle fails fast with a clear
    log line, instead of surfacing as an opaque 500 on the first real request.
    """
    errors = {}
    for name, loader in (("performance", get_performance_model), ("burnout", get_burnout_model)):
        try:
            loader()
        except Exception as e:  # noqa: BLE001 — we want to catch+log any pickle/env issue here
            errors[name] = str(e)
    return errors
