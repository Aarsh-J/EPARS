"""
modules/ml/predict.py
==========================
Public entry points: predict_performance() and predict_burnout(). Both do
feature assembly + imputation + inference and return a plain dict, so
FastAPI routes don't need to know anything about pandas/numpy/sklearn.
"""

import numpy as np
import pandas as pd

from .burnout_features import assemble_burnout_features
from .feature_specs import (
    BURNOUT_CLASS_THRESHOLDS,
    BURNOUT_FEATURES,
    BURNOUT_LABEL_MAP,
    BURNOUT_TOP_FEATURES,
    PERFORMANCE_FEATURES,
)
from .loader import get_burnout_model, get_performance_model
from .performance_features import assemble_performance_features, compute_composites


def predict_performance(employee_id: str, review_id: str | None = None) -> dict:
    bundle = get_performance_model()
    model, scaler = bundle["model"], bundle["scaler"]
    means = dict(zip(scaler.feature_names_in_, scaler.mean_))

    raw, imputed = assemble_performance_features(employee_id, review_id)

    # Impute missing raw inputs with the scaler's training mean *before*
    # computing composites, so composite formulas run on a complete vector
    # (matches what the model saw at training time when a field was unknown).
    composite_names = {
        "output_quality_composite", "overtime_ratio", "peer_productivity_gap",
        "fb_composite_rating",
    }
    for name in PERFORMANCE_FEATURES:
        if name not in composite_names and raw.get(name) is None:
            raw[name] = means[name]

    compute_composites(raw)

    vector = [raw[name] for name in PERFORMANCE_FEATURES]
    scaled = scaler.transform([vector])
    score = float(model.predict(scaled)[0])
    score = max(0.0, min(100.0, score))

    return {
        "predicted_score": round(score, 1),
        "confidence": "high" if len(imputed) <= 5 else "medium" if len(imputed) <= 15 else "low",
        "imputed_features": sorted(imputed),
        "real_feature_count": len(PERFORMANCE_FEATURES) - len(imputed),
        "total_feature_count": len(PERFORMANCE_FEATURES),
    }


def predict_burnout(employee_id: str) -> dict:
    model = get_burnout_model()

    vector, imputed = assemble_burnout_features(employee_id)
    df = pd.DataFrame([[vector[name] for name in BURNOUT_FEATURES]], columns=BURNOUT_FEATURES)
    df = df.replace({None: np.nan})

    proba = model.predict_proba(df)[0]
    class_idx = int(np.argmax(proba))
    predicted_class = BURNOUT_LABEL_MAP[str(class_idx)]

    # Top-weighted features (per the model's recovered feature_importances_)
    # that are missing here — surfaced so the UI can show *why* confidence is low.
    missing_top_features = [f for f in BURNOUT_TOP_FEATURES if f in imputed]
    top_weight_missing = sum(BURNOUT_TOP_FEATURES[f] for f in missing_top_features)

    if top_weight_missing >= 0.3:
        confidence = "low"
    elif top_weight_missing >= 0.1:
        confidence = "medium"
    else:
        confidence = "high"

    return {
        "predicted_class": predicted_class,
        "predicted_probabilities": {
            BURNOUT_LABEL_MAP[str(i)]: round(float(p), 4) for i, p in enumerate(proba)
        },
        "class_thresholds": BURNOUT_CLASS_THRESHOLDS,
        "confidence": confidence,
        "imputed_features": sorted(imputed),
        "missing_top_features": missing_top_features,
        "real_feature_count": len(BURNOUT_FEATURES) - len(imputed),
        "total_feature_count": len(BURNOUT_FEATURES),
        "top_contributing_features": BURNOUT_TOP_FEATURES,
    }
