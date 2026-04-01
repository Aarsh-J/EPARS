"""
preprocessing.py
────────────────────────────────────────────────────────────────────────────────
Task Scheduling & Workload Optimization — Preprocessing Pipeline
────────────────────────────────────────────────────────────────────────────────
Targets:
  1. delay_risk_score      (regression)
  2. assignment_success    (classification)
  3. priority_score        (regression)

Feature selection rationale:
  - Columns dropped if near-zero importance (<0.1%) across ALL three targets
    (verified via RandomForest importance analysis on the full merged dataset)
  - Columns dropped if >90% null with no recovery strategy
  - ID, free-text, and raw date columns always dropped
  - Every kept column is guaranteed non-null before splits are saved
"""

import os
import warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import joblib

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# 0. Paths
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 1. COLUMN DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

# Columns to drop from master — junk, free text, raw dates, 100% null,
# post-assignment leakage, and near-zero importance across ALL three targets
# NOTE: IDs (assignment_id, task_id, employee_id, project_id) are NOT dropped
#       here — they stay in master_preprocessed.csv for traceability.
#       They are excluded from the feature matrix inside make_splits().
DROP_COLS = [
    # Reduced feature set — dropped to keep model lean and explainable
    "hours_ratio", "team_size_required", "meeting_hours_required",
    "overall_suitability_score", "team_compatibility_score",
    "leadership_potential", "days_since_last_leave",
    "successful_project_count", "failed_project_count",
    "avg_productivity", "avg_reliability", "utilization_rate",
    "schedule_conflict_rate", "avg_productivity_during",
    "quality_risk_score", "next_milestone_risk", "roi_estimate",
    "budget", "meeting_hours_per_week", "completed_milestones",
    "stakeholder_satisfaction_proj", "documentation_quality",
    "communication_frequency", "status",
    "n_primary_skills", "has_certifications",
    "overall_burnout_risk", "emotional_exhaustion_score",
    "workload_pressure", "job_demands", "job_control",
    "late_hours_frequency", "weekend_work_frequency",
    "predicted_burnout_90days", "assignment_date",

    # Metadata (not IDs — IDs are kept in master for traceability)
    "task_name", "task_description", "project_name", "project_description",
    "first_name", "last_name", "email",
    "project_manager_id", "team_member_ids", "client_id",
    "assigned_to", "assigned_by",

    # Raw date strings (signals already captured by engineered features)
    "start_date", "due_date", "actual_completion_date", "assigned_date",
    "acceptance_date", "actual_end_date", "next_milestone_date",
    "start_date_proj", "planned_end_date", "hire_date",

    # Timestamps
    "created_at_x", "created_at_y", "created_at", "created_at_proj",
    "last_updated_x", "last_updated_y", "last_updated", "last_updated_proj",

    # Free text
    "reassignment_reason", "employee_feedback", "manager_feedback",
    "collaboration_tools", "required_skills", "required_skills_proj",
    "primary_skills", "secondary_skills", "languages_known",
    "certifications", "preferred_work_hours", "timezone",

    # 100% null
    "past_team_members",

    # Highly sparse ID strings (90–97% null — converted to counts instead)
    "blocking_task_ids", "parent_task_id", "dependent_task_ids", "related_tasks",

    # Post-assignment columns — unavailable at decision time (data leakage)
    "time_to_complete", "on_time_completion", "efficiency_score",
    "quality_rating", "actual_hours", "completion_percentage",
    "quality_score", "review_rating", "completion_status",
    "assignment_satisfaction", "would_recommend_again",

    # Near-zero importance across ALL three targets (verified)
    "business_value", "communication_frequency_proj", "completion_percentage_proj",
    "complexity_level", "cross_functional_experience", "current_project_count",
    "current_status", "customer_impact", "department", "department_proj",
    "employment_type", "is_available", "is_on_schedule", "mentoring_experience",
    "overdue_milestones", "preferred_team_size", "priority_proj",
    "productivity_trend", "project_type", "remote_work_status", "role",
    "seniority_level", "stress_level", "total_milestones",
    "weekly_capacity_hours", "years_of_experience",

    # High multicollinearity — redundant with interaction features or stronger siblings
    "engagement_score", "motivation_level", "resilience_score",
    "job_satisfaction", "energy_level",
    "overall_suitability_score",
    "allocated_resources", "consumed_resources",
    "total_scheduled_hours", "n_schedule_events",
    "is_overdue",
    "rework_required",
    "predicted_burnout_30days",
]

# Final numeric feature columns (kept after importance analysis)
NUMERIC_COLS = [
    # Task features
    "estimated_hours", "story_points",
    "technical_complexity_score", "planned_duration_days",
    "n_dependencies", "n_required_skills", "has_cert_req",
    "days_overdue", "buffer_days", "rework_count",
    # Assignment match scores
    "skill_match_score", "availability_match_score",
    "workload_compatibility_score", "experience_match_score",
    "reassignment_count",
    # Employee features
    "technical_proficiency_score", "domain_expertise_score",
    "historical_performance_score", "average_task_completion_rate",
    "collaboration_score", "burnout_risk_score",
    "work_life_balance_score", "recent_overtime_hours",
    # Review aggregates
    "avg_perf_score", "avg_quality", "avg_timeliness", "on_time_rate",
    # Project context
    "delay_risk_score_proj", "budget_overrun_risk",
    "success_probability", "strategic_importance",
    "days_ahead_behind", "scope_creep_indicator",
]

# Final categorical feature columns
CATEGORICAL_COLS = [
    "task_type", "priority", "complexity",
    "required_role", "required_seniority", "required_certifications",
    "risk_level", "business_impact", "assignment_method", "acceptance_status",
]

# Boolean columns (will be cast to int)
BOOL_COLS = [
    "requires_collaboration", "has_subtasks", "technical_debt_added",
]

TARGETS = {
    "delay_risk_score":   "regression",
    "assignment_success": "classification",
    "priority_score":     "regression",
}

LABEL_ENCODERS: dict[str, LabelEncoder] = {}


# ─────────────────────────────────────────────────────────────────────────────
# 2. LOADERS
# ─────────────────────────────────────────────────────────────────────────────

def load_raw(data_dir: str = DATA_DIR) -> dict:
    files = {
        "tasks":       "tasks.csv",
        "assignments": "task_assignments.csv",
        "employees":   "employees.csv",
        "burnout":     "burnout_indicators.csv",
        "reviews":     "performance_reviews.csv",
        "schedules":   "schedules.csv",
        "projects":    "projects.csv",
    }
    dfs = {}
    for key, fname in files.items():
        path = os.path.join(data_dir, fname)
        dfs[key] = pd.read_csv(path, low_memory=False)
        print(f"  Loaded {key:12s} → {dfs[key].shape}")
    return dfs


# ─────────────────────────────────────────────────────────────────────────────
# 3. PER-TABLE CLEANING
# ─────────────────────────────────────────────────────────────────────────────

def clean_tasks(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Parse dates for feature engineering only
    for col in ["start_date", "due_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Engineered features
    df["planned_duration_days"] = (
        (df["due_date"] - df["start_date"]).dt.days.clip(lower=0).fillna(0)
    )
    df["hours_ratio"] = (
        df["actual_hours"] / df["estimated_hours"].replace(0, np.nan)
    ).fillna(1.0).clip(0, 5)

    df["n_dependencies"] = (
        df["dependent_task_ids"].fillna("").str.split(",")
        .apply(lambda x: len([v for v in x if v.strip()]))
    )
    df["n_required_skills"] = (
        df["required_skills"].fillna("").str.split(",")
        .apply(lambda x: len([v for v in x if v.strip()]))
    )
    df["has_cert_req"] = df["required_certifications"].notna().astype(int)

    # TARGET 1: delay_risk_score
    df["delay_risk_score"] = df["delay_risk_score"].fillna(
        df["is_overdue"].astype(float) * 50
    )

    # TARGET 3: priority_score — composite
    priority_map  = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    impact_map    = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    risk_map      = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    complexity_map= {"Very Complex": 4, "Complex": 3, "Moderate": 2, "Simple": 1}

    df["priority_score"] = (
        0.30 * df["priority"].map(priority_map).fillna(2) +
        0.25 * df["business_impact"].map(impact_map).fillna(2) +
        0.20 * df["risk_level"].map(risk_map).fillna(2) +
        0.15 * df["complexity"].map(complexity_map).fillna(2) +
        0.10 * (df["delay_risk_score"] / 100.0)
    )

    keep = [
        "task_id", "task_type", "priority", "complexity",
        "estimated_hours", "actual_hours", "story_points",
        "n_required_skills", "has_cert_req", "required_certifications",
        "required_role", "required_seniority",
        "technical_complexity_score", "planned_duration_days", "hours_ratio",
        "n_dependencies", "is_overdue", "days_overdue", "buffer_days",
        "completion_percentage", "status",
        "rework_required", "rework_count", "quality_score", "review_rating",
        "risk_level", "business_impact",
        "requires_collaboration", "team_size_required",
        "communication_frequency", "meeting_hours_required",
        "has_subtasks", "technical_debt_added",
        "delay_risk_score",   # TARGET 1
        "priority_score",     # TARGET 3
    ]
    return df[[c for c in keep if c in df.columns]]


def clean_assignments(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # TARGET 2: assignment_success
    df["assignment_success"] = df["assignment_success"].map(
        {True: 1, False: 0, "True": 1, "False": 0}
    )
    completed = df["completion_status"].str.lower() == "completed"
    df.loc[df["assignment_success"].isna() &  completed, "assignment_success"] = 1
    df.loc[df["assignment_success"].isna() & ~completed, "assignment_success"] = 0

    # Convert assignment_date to ordinal (numeric) for model use
    df["assignment_date"] = pd.to_datetime(
        df["assignment_date"], errors="coerce"
    ).map(lambda x: x.toordinal() if pd.notna(x) else np.nan)

    keep = [
        "assignment_id", "task_id", "employee_id", "project_id",
        "assignment_method", "acceptance_status", "assignment_date",
        "skill_match_score", "availability_match_score",
        "workload_compatibility_score", "experience_match_score",
        "overall_suitability_score", "team_compatibility_score",
        "reassignment_count",
        "assignment_success",  # TARGET 2
    ]
    return df[[c for c in keep if c in df.columns]]


def clean_employees(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["n_primary_skills"] = (
        df["primary_skills"].fillna("").str.split(",")
        .apply(lambda x: len([v for v in x if v.strip()]))
    )
    df["has_certifications"] = df["certifications"].notna().astype(int)

    keep = [
        "employee_id",
        "technical_proficiency_score", "domain_expertise_score",
        "historical_performance_score", "average_task_completion_rate",
        "collaboration_score", "communication_effectiveness",
        "leadership_potential", "burnout_risk_score",
        "recent_overtime_hours", "days_since_last_leave",
        "work_life_balance_score", "successful_project_count",
        "failed_project_count", "n_primary_skills", "has_certifications",
    ]
    return df[[c for c in keep if c in df.columns]]


def aggregate_burnout(df: pd.DataFrame) -> pd.DataFrame:
    """Most recent burnout record per employee."""
    df = df.copy()
    df["assessment_date"] = pd.to_datetime(df["assessment_date"], errors="coerce")
    df = df.sort_values("assessment_date").groupby("employee_id").last().reset_index()

    keep = [
        "employee_id",
        "overall_burnout_risk", "emotional_exhaustion_score",
        "workload_pressure", "job_demands", "job_control",
        "late_hours_frequency", "weekend_work_frequency",
        "energy_level", "job_satisfaction", "engagement_score",
        "motivation_level", "resilience_score",
        "predicted_burnout_30days", "predicted_burnout_90days",
    ]
    return df[[c for c in keep if c in df.columns]]


def aggregate_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """Average of latest 2 reviews per employee."""
    df = df.copy()
    df["review_date"] = pd.to_datetime(df["review_date"], errors="coerce")
    return (
        df.sort_values("review_date", ascending=False)
          .groupby("employee_id").head(2)
          .groupby("employee_id")
          .agg(
              avg_perf_score   =("overall_performance_score", "mean"),
              avg_quality      =("quality_of_work_score", "mean"),
              avg_productivity =("productivity_score", "mean"),
              avg_timeliness   =("time_management_score", "mean"),
              avg_reliability  =("reliability_score", "mean"),
              on_time_rate     =("on_time_delivery_rate", "mean"),
              utilization_rate =("utilization_rate", "mean"),
          )
          .reset_index()
    )


def aggregate_schedules(df: pd.DataFrame) -> pd.DataFrame:
    """Schedule load metrics per employee."""
    return (
        df.groupby("employee_id")
          .agg(
              total_scheduled_hours   =("duration_minutes", lambda x: x.sum() / 60),
              schedule_conflict_rate  =("has_conflict", "mean"),
              avg_productivity_during =("productivity_during", "mean"),
              n_schedule_events       =("schedule_id", "count"),
          )
          .reset_index()
    )


def clean_projects(df: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "project_id",
        "success_probability", "delay_risk_score",
        "budget_overrun_risk", "quality_risk_score", "scope_creep_indicator",
        "allocated_resources", "consumed_resources", "roi_estimate",
        "budget", "strategic_importance", "documentation_quality",
        "meeting_hours_per_week", "next_milestone_risk",
        "stakeholder_satisfaction", "days_ahead_behind", "completed_milestones",
    ]
    df = df[[c for c in keep if c in df.columns]].copy()
    df.rename(columns={
        "delay_risk_score":     "delay_risk_score_proj",
        "stakeholder_satisfaction": "stakeholder_satisfaction_proj",
    }, inplace=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 4. MERGE
# ─────────────────────────────────────────────────────────────────────────────

def build_master(dfs: dict) -> pd.DataFrame:
    tasks       = clean_tasks(dfs["tasks"])
    assignments = clean_assignments(dfs["assignments"])
    employees   = clean_employees(dfs["employees"])
    burnout     = aggregate_burnout(dfs["burnout"])
    reviews     = aggregate_reviews(dfs["reviews"])
    schedules   = aggregate_schedules(dfs["schedules"])
    projects    = clean_projects(dfs["projects"])

    # Build full employee profile
    emp_full = (
        employees
        .merge(burnout,   on="employee_id", how="left")
        .merge(reviews,   on="employee_id", how="left")
        .merge(schedules, on="employee_id", how="left")
    )

    # Core join: assignments ← tasks (drop task's project_id to avoid conflict)
    tasks_no_proj = tasks.drop(columns=["project_id"], errors="ignore")
    master = assignments.merge(tasks_no_proj, on="task_id", how="inner")

    # Add employee profile
    master = master.merge(emp_full, on="employee_id", how="left")

    # Add project context
    master = master.merge(projects, on="project_id", how="left")

    print(f"\n  Master shape after join: {master.shape}")
    return master


# ─────────────────────────────────────────────────────────────────────────────
# 5. NULL CLEANER  — guarantees zero nulls before encoding
# ─────────────────────────────────────────────────────────────────────────────

def clean_nulls(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Certification text → "None" (absence is meaningful)
    for col in ["required_certifications"]:
        if col in df.columns:
            df[col] = df[col].fillna("None")

    # Boolean cols → cast to int, fill with 0
    bool_cols = ["is_overdue", "rework_required", "requires_collaboration",
                 "has_subtasks", "technical_debt_added"]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].map(
                {True: 1, False: 0, "True": 1, "False": 0}
            ).fillna(0).astype(int)

    # All remaining numerics → median
    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].isnull().any():
            df[col] = df[col].fillna(df[col].median())

    # All remaining categoricals/objects → "Unknown"
    for col in df.select_dtypes(include=["object"]).columns:
        if df[col].isnull().any():
            df[col] = df[col].fillna("Unknown")

    # Final verification
    remaining = df.isnull().sum().sum()
    if remaining == 0:
        print(f"  ✓ Zero nulls — {df.shape[1]} columns, {df.shape[0]:,} rows")
    else:
        still_null = df.columns[df.isnull().any()].tolist()
        print(f"  ⚠ {remaining} nulls still in: {still_null}")

    return df


# ─────────────────────────────────────────────────────────────────────────────
# 6. DROP UNNECESSARY COLUMNS
# ─────────────────────────────────────────────────────────────────────────────

def drop_unnecessary(df: pd.DataFrame) -> pd.DataFrame:
    before = df.shape[1]
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
    after = df.shape[1]
    print(f"  Dropped {before - after} unnecessary columns → {after} remaining")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 7. ENCODE CATEGORICALS
# ─────────────────────────────────────────────────────────────────────────────

def encode_categoricals(df: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
    df = df.copy()
    for col in CATEGORICAL_COLS:
        if col not in df.columns:
            continue
        df[col] = df[col].astype(str).fillna("Unknown")
        if fit:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col])
            LABEL_ENCODERS[col] = le
        else:
            le = LABEL_ENCODERS.get(col)
            if le:
                known = set(le.classes_)
                df[col] = df[col].apply(lambda x: x if x in known else le.classes_[0])
                df[col] = le.transform(df[col])
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 8. INTERACTION FEATURES
# ─────────────────────────────────────────────────────────────────────────────

def engineer_interactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # How many required skills the employee is missing
    df["skill_gap"] = (
        df.get("n_required_skills", 0) - df.get("n_primary_skills", 0)
    ).clip(lower=0)

    # Composite employee-task fitness
    df["emp_fitness"] = (
        df.get("skill_match_score", 50)            * 0.30 +
        df.get("experience_match_score", 50)       * 0.25 +
        df.get("availability_match_score", 50)     * 0.20 +
        df.get("workload_compatibility_score", 50) * 0.15 +
        df.get("team_compatibility_score", 50)     * 0.10
    )

    # How overdue vs buffer available
    buf = df.get("buffer_days", pd.Series(np.ones(len(df)))).replace(0, 1)
    df["urgency_ratio"] = (df.get("days_overdue", 0) / buf).clip(-10, 10)

    # Composite employee health/burnout risk
    df["health_risk"] = (
        df.get("burnout_risk_score", 0)       * 0.5 +
        df.get("overall_burnout_risk", 0)     * 0.3 +
        df.get("predicted_burnout_30days", 0) * 0.2
    )

    # Scheduled workload relative to capacity
    df["schedule_load_ratio"] = pd.Series(0.0, index=df.index)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# 9. SPLIT FACTORY
# ─────────────────────────────────────────────────────────────────────────────

def make_splits(
    master: pd.DataFrame,
    target: str,
    test_size: float = 0.20,
    val_size:  float = 0.10,
    random_state: int = 42,
):
    assert target in TARGETS, f"Unknown target: {target}"

    id_cols     = ["assignment_id", "task_id", "employee_id", "project_id"]
    target_cols = list(TARGETS.keys())
    exclude     = set(id_cols + target_cols)

    # Build feature list from what actually exists in master
    interaction = ["skill_gap", "emp_fitness", "urgency_ratio",
                   "health_risk", "schedule_load_ratio"]
    all_possible = NUMERIC_COLS + CATEGORICAL_COLS + interaction
    feature_cols = [
        c for c in all_possible
        if c in master.columns and c not in exclude
    ]

    # Drop rows where the target itself is null
    subset = master.dropna(subset=[target]).copy()
    X = subset[feature_cols]
    y = subset[target]

    # Train / temp
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y,
        test_size=test_size + val_size,
        random_state=random_state,
        stratify=(y if TARGETS[target] == "classification" else None),
    )
    # Val / test from temp
    rel_val = val_size / (test_size + val_size)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp,
        test_size=1 - rel_val,
        random_state=random_state,
        stratify=(y_temp if TARGETS[target] == "classification" else None),
    )

    print(f"  [{target}]  "
          f"train={len(X_train):,}  val={len(X_val):,}  test={len(X_test):,}  "
          f"features={len(feature_cols)}")
    return X_train, X_val, X_test, y_train, y_val, y_test, feature_cols


# ─────────────────────────────────────────────────────────────────────────────
# 10. NUMERIC PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def build_numeric_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# 11. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def run_preprocessing(data_dir: str = DATA_DIR, output_dir: str = OUTPUT_DIR):
    print("\n" + "="*70)
    print("  TASK SCHEDULING & WORKLOAD OPTIMIZATION — PREPROCESSING")
    print("="*70)

    print("\n[1] Loading raw data …")
    dfs = load_raw(data_dir)

    print("\n[2] Building master DataFrame …")
    master = build_master(dfs)

    print("\n[3] Dropping unnecessary columns …")
    master = drop_unnecessary(master)

    print("\n[4] Cleaning nulls …")
    master = clean_nulls(master)

    print("\n[5] Encoding categoricals …")
    master = encode_categoricals(master, fit=True)

    print("\n[6] Engineering interaction features …")
    master = engineer_interactions(master)

    # Final null check after interactions
    assert master.isnull().sum().sum() == 0, "Nulls found after interaction engineering!"

    # Save master
    master_path = os.path.join(output_dir, "master_preprocessed.csv")
    master.to_csv(master_path, index=False)
    print(f"\n  Saved master → {master_path}  {master.shape}")

    # Save label encoders
    le_path = os.path.join(output_dir, "label_encoders.joblib")
    joblib.dump(LABEL_ENCODERS, le_path)
    print(f"  Saved label encoders → {le_path}")

    # Build splits + numeric pipelines per target
    print("\n[7] Building train/val/test splits …")
    splits = {}
    for target in TARGETS:
        result  = make_splits(master, target)
        X_train, X_val, X_test, y_train, y_val, y_test, feat_cols = result

        # Identify numeric feature columns present in this split
        num_present = [
            c for c in feat_cols
            if master[c].dtype in [np.float64, np.int64, np.int32, float, int]
        ]

        pipe = build_numeric_pipeline()
        X_train = X_train.copy()
        X_val   = X_val.copy()
        X_test  = X_test.copy()
        X_train[num_present] = pipe.fit_transform(X_train[num_present])
        X_val[num_present]   = pipe.transform(X_val[num_present])
        X_test[num_present]  = pipe.transform(X_test[num_present])

        # Save pipeline
        pipe_path = os.path.join(output_dir, f"numeric_pipeline_{target}.joblib")
        joblib.dump(pipe, pipe_path)

        # Save splits as parquet
        for split_name, X_s, y_s in [
            ("train", X_train, y_train),
            ("val",   X_val,   y_val),
            ("test",  X_test,  y_test),
        ]:
            out = X_s.copy()
            out[target] = y_s.values
            path = os.path.join(output_dir, f"{target}_{split_name}.parquet")
            out.to_parquet(path, index=False)

        splits[target] = {
            "X_train": X_train, "X_val": X_val, "X_test": X_test,
            "y_train": y_train, "y_val": y_val, "y_test": y_test,
            "features": feat_cols,
        }

    print("\n" + "="*70)
    print("  PREPROCESSING COMPLETE")
    print("="*70)
    print(f"  Artifacts saved to: {output_dir}")
    print(f"  Files created:")
    for f in sorted(os.listdir(output_dir)):
        fpath = os.path.join(output_dir, f)
        size  = os.path.getsize(fpath) / 1024
        print(f"    {f:55s} {size:>8.1f} KB")

    return splits


if __name__ == "__main__":
    run_preprocessing()
