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
# Recovered from code/workload_preprocessing.py (commit 9126e7e1). Originally
# only 16 of these 36 existed in the live burnout_indicators schema; the other
# 20 (including this model's top 3 weighted features: reported_stress_level,
# reported_fatigue_level, sleep_quality) were ADD COLUMN'd + backfilled from
# dataset_v2/burnout_indicators.csv (see docs — same generated dataset the
# model was trained on, verified 100% employee_id overlap with live data
# before backfilling). All 36 are now live.
BURNOUT_SYMPTOM_COLS_LIVE = [
    "emotional_exhaustion_score", "depersonalization_score",
    "reduced_accomplishment_score", "workload_pressure", "role_ambiguity",
    "work_life_conflict", "job_demands", "job_control", "role_conflict",
    "late_hours_frequency", "weekend_work_frequency", "missed_breaks_count",
    "vacation_days_unused", "sick_days_taken", "absence_rate",
    "phys_health",  # <- physical_health_concerns (bool -> int)
    "mental_supp",  # <- mental_health_support_needed (bool -> int)
    "energy_level", "job_satisfaction", "engagement_score", "motivation_level",
    "sense_of_accomplishment", "organizational_commitment", "social_support_score",
    "manager_support_score", "team_cohesion", "workplace_relationships",
    "isolation_feeling", "coping_effectiveness", "resource_adequacy",
    "work_recovery_ability", "resilience_score",
    "stress_enc",  # <- reported_stress_level, via BURNOUT_STRESS_MAP
    "fatigue_enc",  # <- reported_fatigue_level, via BURNOUT_FATIGUE_MAP
    "sleep_enc",  # <- sleep_quality, via BURNOUT_SLEEP_MAP
    "trend_enc",  # <- burnout_trend, via BURNOUT_TREND_MAP
]

BURNOUT_STRESS_MAP = {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}
BURNOUT_FATIGUE_MAP = {"Low": 1, "Medium": 2, "High": 3, "Severe": 4}
BURNOUT_SLEEP_MAP = {"Very Poor": 1, "Poor": 2, "Fair": 3, "Good": 4}
BURNOUT_TREND_MAP = {"Decreasing": -1, "Stable": 0, "Increasing": 1, "Rapidly Increasing": 2}

# ── Burnout: static employees.* features ──
BURNOUT_SENIORITY_MAP = {"Junior": 1, "Mid": 2, "Senior": 3, "Lead": 4, "Principal": 5}
BURNOUT_PROD_MAP = {"Decreasing": -1, "Stable": 0, "Increasing": 1}
BURNOUT_EMP_STRESS_MAP = {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}

# communication_effectiveness, work_life_balance_score, cross_functional_experience,
# and mentoring_experience were likewise ADD COLUMN'd + backfilled from
# dataset_v2/employees.csv (only ~47% employee_id overlap for this table — the
# rest stay unbackfilled/imputed, which is honest given no matching source data).
BURNOUT_EMP_COLS_LIVE = [
    "years_of_experience", "weekly_capacity_hours", "current_project_count",
    "technical_proficiency_score", "domain_expertise_score",
    "historical_performance_score", "average_task_completion_rate",
    "collaboration_score", "communication_effectiveness", "leadership_potential",
    "burnout_risk_score", "recent_overtime_hours", "days_since_last_leave",
    "work_life_balance_score", "successful_project_count", "failed_project_count",
    "cross_functional_experience", "mentoring_experience",
    "is_available",  # bool -> int
]
