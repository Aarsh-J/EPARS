"""
modules/ml/feature_specs.py
================================
Feature order, encodings, and live-DB-availability for both models. Recovered
from the original (now-deleted) training scripts in git history — see
ml_models/README.md for exact commit provenance. Do not hand-edit the feature
order lists; they must match each pickle's expected input exactly.
"""

import json
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[2] / "ml_models"

_perf_spec = json.loads((MODELS_DIR / "performance_feature_list.json").read_text())
PERFORMANCE_FEATURES: list[str] = _perf_spec["features"]
PERFORMANCE_NOT_LIVE: set[str] = set(_perf_spec["not_available_in_live_db"])

_burnout_meta = json.loads((MODELS_DIR / "burnout_model_metadata.json").read_text())
BURNOUT_FEATURES: list[str] = _burnout_meta["feature_columns"]
BURNOUT_LABEL_MAP: dict[str, str] = _burnout_meta["label_map"]
BURNOUT_CLASS_THRESHOLDS: dict[str, str] = _burnout_meta["class_thresholds"]
BURNOUT_TOP_FEATURES: dict[str, float] = _burnout_meta["top_features"]

# review_type LabelEncoder wasn't committed to git (only feature_list.pkl,
# performance_model.pkl, test_indices.pkl were). Reconstructed as sklearn's
# LabelEncoder would produce it: alphabetical order over the distinct values
# actually present in performance_reviews.review_type.
REVIEW_TYPE_ENCODING = {
    "Annual": 0,
    "Probationary": 1,
    "Project-based": 2,
    "Quarterly": 3,
}

# ── Burnout: symptom columns from burnout_indicators (aggregated mean/max/std) ──
# Recovered from code/workload_preprocessing.py (commit 9126e7e1). Columns not
# present in the live burnout_indicators schema are listed separately; their
# _mean/_max/_std slots are left NaN and handled by the pipeline's own
# SimpleImputer(strategy="median").
BURNOUT_SYMPTOM_COLS_LIVE = [
    "emotional_exhaustion_score", "depersonalization_score",
    "reduced_accomplishment_score", "role_ambiguity", "job_control",
    "late_hours_frequency", "weekend_work_frequency", "missed_breaks_count",
    "vacation_days_unused", "sick_days_taken", "absence_rate",
    "mental_supp",  # <- mental_health_support_needed (bool -> int)
    "job_satisfaction", "social_support_score", "manager_support_score",
    "trend_enc",  # <- burnout_trend, via BURNOUT_TREND_MAP
]

BURNOUT_SYMPTOM_COLS_MISSING = [
    "workload_pressure", "work_life_conflict", "job_demands", "role_conflict",
    "phys_health", "energy_level", "engagement_score", "motivation_level",
    "sense_of_accomplishment", "organizational_commitment", "team_cohesion",
    "workplace_relationships", "isolation_feeling", "coping_effectiveness",
    "resource_adequacy", "work_recovery_ability", "resilience_score",
    "stress_enc", "fatigue_enc", "sleep_enc",
]

BURNOUT_TREND_MAP = {"Decreasing": -1, "Stable": 0, "Increasing": 1, "Rapidly Increasing": 2}

# ── Burnout: static employees.* features ──
BURNOUT_SENIORITY_MAP = {"Junior": 1, "Mid": 2, "Senior": 3, "Lead": 4, "Principal": 5}
BURNOUT_PROD_MAP = {"Decreasing": -1, "Stable": 0, "Increasing": 1}
BURNOUT_EMP_STRESS_MAP = {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}

BURNOUT_EMP_COLS_LIVE = [
    "years_of_experience", "weekly_capacity_hours", "current_project_count",
    "technical_proficiency_score", "domain_expertise_score",
    "historical_performance_score", "average_task_completion_rate",
    "collaboration_score", "leadership_potential", "burnout_risk_score",
    "recent_overtime_hours", "days_since_last_leave",
    "successful_project_count", "failed_project_count",
    "is_available",  # bool -> int
]

BURNOUT_EMP_COLS_MISSING = [
    "communication_effectiveness", "work_life_balance_score",
    "cross_functional_experience", "mentoring_experience",
]
