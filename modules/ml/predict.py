"""
modules/ml/predict.py
==========================
Public entry points: predict_performance() and predict_burnout(). Both do
feature assembly + imputation + inference and return a plain dict, so
FastAPI routes don't need to know anything about pandas/numpy/sklearn.
"""

import pandas as pd

from .burnout_features import assemble_burnout_features
from .feature_specs import (
    BURNOUT_FEATURES,
    BURNOUT_LOW_MAX,
    BURNOUT_MEDIUM_MAX,
    BURNOUT_TOP_FEATURES,
    PERFORMANCE_FEATURES,
)
from .loader import get_burnout_model, get_performance_model
from .performance_features import assemble_performance_features

# GradientBoostingRegressor's bucketed classes, in the order thresholds apply.
# "Medium" is renamed "Moderate" to keep the existing 4-tier vocabulary the UI/DB
# already use (_CLASS_COLOR, burnout_ai_assessments.ai_predicted_class); there is
# no longer a 4th "Critical" tier — the source model only ever produces 3 buckets.
_BURNOUT_CLASS_NAMES = ("Low", "Moderate", "High")


def predict_performance(employee_id: str, review_id: str | None = None) -> dict:
    bundle = get_performance_model()
    model, scaler = bundle["model"], bundle["scaler"]

    vector, imputed = assemble_performance_features(employee_id, review_id)

    row = pd.DataFrame([[vector[name] for name in PERFORMANCE_FEATURES]], columns=PERFORMANCE_FEATURES)
    scaled = scaler.transform(row)
    score = float(model.predict(scaled)[0])
    score = max(0.0, min(100.0, score))

    # imputed counts the up-to-11 raw formula/history inputs (not just the 2
    # final model features) — proportionally similar cutoffs to the previous
    # model's 5/15-out-of-53 thresholds, scaled down to this model's ~11 inputs.
    return {
        "predicted_score": round(score, 1),
        "confidence": "high" if len(imputed) <= 1 else "medium" if len(imputed) <= 3 else "low",
        "imputed_features": sorted(imputed),
        "real_feature_count": 11 - len(imputed),
        "total_feature_count": 11,
    }


def predict_burnout(employee_id: str) -> dict:
    bundle = get_burnout_model()
    model, features = bundle["model"], bundle["features"]

    vector, imputed = assemble_burnout_features(employee_id)
    df = pd.DataFrame([[vector[name] for name in features]], columns=features)

    raw_score = float(model.predict(df)[0])
    raw_score = max(0.0, min(100.0, raw_score))

    if raw_score < BURNOUT_LOW_MAX:
        predicted_class = "Low"
    elif raw_score < BURNOUT_MEDIUM_MAX:
        predicted_class = "Moderate"
    else:
        predicted_class = "High"

    # This model is a regressor with percentile-bucketed output, not a
    # classifier — there's no native predict_proba. predicted_probabilities is
    # a one-hot vector on the bucketed class (not a calibrated distribution),
    # kept for backward compatibility with callers (reassignment.py's
    # risk_fraction, the justification prompt) that read this dict by class key.
    predicted_probabilities = {name: (1.0 if name == predicted_class else 0.0) for name in _BURNOUT_CLASS_NAMES}

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
        "predicted_score": round(raw_score, 1),
        "predicted_probabilities": predicted_probabilities,
        "class_thresholds": {"low_max": BURNOUT_LOW_MAX, "medium_max": BURNOUT_MEDIUM_MAX},
        "confidence": confidence,
        "imputed_features": sorted(imputed),
        "missing_top_features": missing_top_features,
        "real_feature_count": len(BURNOUT_FEATURES) - len(imputed),
        "total_feature_count": len(BURNOUT_FEATURES),
        "top_contributing_features": BURNOUT_TOP_FEATURES,
    }
