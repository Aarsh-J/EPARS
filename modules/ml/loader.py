"""
modules/ml/loader.py
========================
Lazy singleton loaders for the pickled models in ml_models/. Each is a
module-level cache so repeated requests don't re-hit disk. See ml_models/README.md
for what's inside each pickle and where the pieces were recovered from.
"""

import logging
from pathlib import Path
from threading import Lock
from typing import Any, Callable


MODELS_DIR = Path(__file__).resolve().parents[2] / "ml_models"
_MODEL_CACHE: dict[str, Any] = {}
_MODEL_LOAD_LOCK = Lock()
_LOGGER = logging.getLogger(__name__)


def _load_once(name: str, load: Callable[[], Any]) -> Any:
    with _MODEL_LOAD_LOCK:
        if name in _MODEL_CACHE:
            return _MODEL_CACHE[name]

        _LOGGER.info("Loading %s model artifacts", name)
        try:
            model = load()
        except Exception:
            _LOGGER.exception("Failed to load %s model artifacts", name)
            raise

        _MODEL_CACHE[name] = model
        return model


def _joblib_load(path: Path) -> Any:
    import joblib

    return joblib.load(path)


def get_performance_model() -> dict:
    """
    Returns {"model": Ridge, "scaler": StandardScaler, "type": "ridge"}. The
    two pieces ship as separate pickles (performance_ridge_model.pkl /
    performance_scaler.pkl) — this wraps them into the same dict shape the
    rest of modules/ml/ already expects.
    """
    return _load_once(
        "performance",
        lambda: {
            "model": _joblib_load(MODELS_DIR / "performance_ridge_model.pkl"),
            "scaler": _joblib_load(MODELS_DIR / "performance_scaler.pkl"),
            "type": "ridge",
        },
    )


def get_burnout_model() -> dict:
    """Returns {"model": GradientBoostingRegressor, "features": [...], "low_max": float, "medium_max": float}."""
    return _load_once("burnout", lambda: _joblib_load(MODELS_DIR / "burnout_model_bundle.pkl"))


def get_task_assignment_model() -> Any:
    """Returns the novel_pair_regressor RandomForestRegressor (Model3, Layer 3)."""
    return _load_once("task_assignment_model", lambda: _joblib_load(MODELS_DIR / "task_assignment_regressor.pkl"))


def get_task_assignment_encoders() -> dict:
    """Returns {column_name: fitted LabelEncoder} for task_assignment's categorical inputs."""
    return _load_once(
        "task_assignment_encoders",
        lambda: _joblib_load(MODELS_DIR / "task_assignment_label_encoders.joblib"),
    )


def get_team_composition_model() -> dict:
    """Model4 composition-anomaly bundle (plain dict)."""
    return _load_once("team_composition", lambda: _joblib_load(MODELS_DIR / "team_composition_bundle.pkl"))


def preload_models() -> dict[str, str]:
    """
    Explicit operator warm-up helper. The API deliberately does not call this
    during startup; each model is loaded by the endpoint that needs it.
    """
    errors = {}
    loaders = (
        ("performance", get_performance_model),
        ("burnout", get_burnout_model),
        ("task_assignment_model", get_task_assignment_model),
        ("task_assignment_encoders", get_task_assignment_encoders),
        ("team_composition", get_team_composition_model),
    )
    for name, loader in loaders:
        try:
            loader()
        except Exception as e:  # noqa: BLE001 — we want to catch+log any pickle/env issue here
            errors[name] = str(e)
            _LOGGER.exception("Failed to preload %s model artifacts", name)
    return errors
