"""
train_novel_pair_models.py
────────────────────────────────────────────────────────────────────────────────
Task Assignment — Novel-Pair Delay-Risk Model (for Layer 3)
────────────────────────────────────────────────────────────────────────────────
train.py's models were trained on ALL 52 features in master_preprocessed.csv,
including assignment-specific ones (skill_match_score, availability_match_score,
workload_compatibility_score, experience_match_score, reassignment_count,
emp_fitness) that only exist for a task<->employee pair that has ALREADY been
assigned. Layer 3 needs to score pairs that have never been assigned, so those
models can't be reused as-is.

Diagnosis before building this (see conversation): stripping down to only
features computable for any pair —
  - classification (assignment_success): accuracy DROPS to 0.551, below the
    0.565 majority-class baseline. The classifier has negative value here;
    its only real signal (reassignment_count) doesn't exist pre-assignment.
    NOT trained here — deliberately excluded from Layer 3.
  - regression (delay_risk_score): R² actually IMPROVES to 0.858 (vs 0.840
    on the full assignment-specific feature set). Delay risk is driven by
    task/employee/project characteristics more than the specific pairing,
    so it generalizes well. This IS trained here and becomes the backbone
    of scheduler.py.

Output: artifacts/novel_pair_regressor.pkl, artifacts/novel_pair_regressor_results.csv

Run:  python train_novel_pair_models.py
Next: python scheduler.py
"""

import os
import warnings
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS   = os.path.join(BASE_DIR, "artifacts")
MASTER_PATH = os.path.join(ARTIFACTS, "master_preprocessed.csv")

RANDOM_STATE = 42
TARGET_REG   = "delay_risk_score"

# Only features computable for a task/employee pair with NO assignment
# history — no skill_match_score, availability_match_score,
# workload_compatibility_score, experience_match_score, reassignment_count,
# or emp_fitness (which is itself built from those assignment-specific
# match scores, see preprocessing.py::engineer_interactions).
NOVEL_PAIR_FEATURES = [
    # employee-level
    "technical_proficiency_score", "domain_expertise_score", "historical_performance_score",
    "average_task_completion_rate", "collaboration_score", "burnout_risk_score",
    "work_life_balance_score", "recent_overtime_hours", "health_risk", "schedule_load_ratio",
    "real_skill_match",
    # task-level
    "task_type", "priority", "complexity", "estimated_hours", "story_points",
    "n_required_skills", "has_cert_req", "required_certifications", "required_role",
    "required_seniority", "technical_complexity_score", "planned_duration_days",
    "n_dependencies", "days_overdue", "buffer_days", "rework_count", "risk_level",
    "business_impact", "requires_collaboration", "has_subtasks", "technical_debt_added",
    "urgency_ratio", "skill_gap",
    # project-level
    "success_probability", "budget_overrun_risk", "scope_creep_indicator",
    "strategic_importance", "days_ahead_behind",
]


def load_master() -> pd.DataFrame:
    if not os.path.isfile(MASTER_PATH):
        raise FileNotFoundError(f"{MASTER_PATH} not found — run preprocessing.py first.")
    df = pd.read_csv(MASTER_PATH)
    print(f"  Loaded master_preprocessed.csv → {df.shape}")
    return df


def train_novel_pair_regressor(df: pd.DataFrame):
    cols = [c for c in NOVEL_PAIR_FEATURES if c in df.columns]
    dropped = set(NOVEL_PAIR_FEATURES) - set(cols)
    if dropped:
        print(f"  ⚠ Not present in master_preprocessed.csv, skipped: {sorted(dropped)}")
    print(f"  Using {len(cols)} novel-pair-computable features")

    X = df[cols]
    y = df[TARGET_REG].astype(float)

    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_STATE
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full, y_train_full, test_size=0.125, random_state=RANDOM_STATE
    )
    print(f"  train={len(X_train)}  val={len(X_val)}  test={len(X_test)}")

    model = RandomForestRegressor(
        n_estimators=300, max_depth=12, min_samples_leaf=5,
        random_state=RANDOM_STATE, n_jobs=-1
    )
    model.fit(X_train, y_train)

    val_pred, test_pred = model.predict(X_val), model.predict(X_test)
    results = pd.DataFrame([{
        "model": "random_forest_novel_pair",
        "val_MAE": mean_absolute_error(y_val, val_pred),
        "val_RMSE": np.sqrt(mean_squared_error(y_val, val_pred)),
        "val_R2": r2_score(y_val, val_pred),
        "test_MAE": mean_absolute_error(y_test, test_pred),
        "test_RMSE": np.sqrt(mean_squared_error(y_test, test_pred)),
        "test_R2": r2_score(y_test, test_pred),
    }])
    print(results.round(3).to_string(index=False))

    joblib.dump(model, os.path.join(ARTIFACTS, "novel_pair_regressor.pkl"))
    results.to_csv(os.path.join(ARTIFACTS, "novel_pair_regressor_results.csv"), index=False)
    print(f"\n  Saved artifacts/novel_pair_regressor.pkl")
    print(f"  Saved artifacts/novel_pair_regressor_results.csv")

    # Feature importances — useful sanity check that nothing surprising is
    # driving predictions (e.g. an ID-like column that shouldn't matter).
    importances = pd.Series(model.feature_importances_, index=cols).sort_values(ascending=False)
    print("\n  Top 10 feature importances:")
    print(importances.head(10).round(3).to_string())

    return model, cols


if __name__ == "__main__":
    print("="*70)
    print("  TRAINING NOVEL-PAIR DELAY-RISK REGRESSOR (Layer 3 backbone)")
    print("="*70)
    df = load_master()
    train_novel_pair_regressor(df)
    print("\nNext: python scheduler.py")
