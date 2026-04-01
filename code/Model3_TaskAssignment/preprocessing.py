"""
preprocessing.py
────────────────────────────────────────────────────────────────────────────────
Task Scheduling & Workload Optimization — Preprocessing Pipeline
────────────────────────────────────────────────────────────────────────────────
Reads 7 raw CSVs, merges, cleans, encodes, and engineers features.
Output: artifacts/master_preprocessed.csv + artifacts/label_encoders.joblib

Run:  python preprocessing.py
Next: python make_splits.py
"""

import os
import warnings
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
import joblib

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# 0. Paths
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(__file__)
DATA_DIR   = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "dataset_v2"))
OUTPUT_DIR = os.path.join(BASE_DIR, "artifacts")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 1. COLUMN DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

DROP_COLS = [
    # Metadata
    "task_name", "task_description", "project_name", "project_description",
    "first_name", "last_name", "email",
    "project_manager_id", "team_member_ids", "client_id",
    "assigned_to", "assigned_by",

    # Raw date strings
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

    # Highly sparse ID strings
    "blocking_task_ids", "parent_task_id", "dependent_task_ids", "related_tasks",

    # Post-assignment leakage
    "time_to_complete", "on_time_completion", "efficiency_score",
    "quality_rating", "actual_hours", "completion_percentage",
    "quality_score", "review_rating", "completion_status",
    "assignment_satisfaction", "would_recommend_again",

    # Near-zero importance
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

    # Reduced feature set — dropped to keep model lean and explainable
    "hours_ratio", "team_size_required", "meeting_hours_required",
    "team_compatibility_score",
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

    # Dropped target
    "priority_score",
]

CATEGORICAL_COLS = [
    "task_type", "priority", "complexity",
    "required_role", "required_seniority", "required_certifications",
    "risk_level", "business_impact", "assignment_method", "acceptance_status",
]

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

    for col in ["start_date", "due_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

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

    df["delay_risk_score"] = df["delay_risk_score"].fillna(
        df["is_overdue"].astype(float) * 50
    )

    keep = [
        "task_id", "task_type", "priority", "complexity",
        "estimated_hours", "story_points",
        "n_required_skills", "has_cert_req", "required_certifications",
        "required_role", "required_seniority",
        "technical_complexity_score", "planned_duration_days",
        "n_dependencies", "days_overdue", "buffer_days",
        "rework_count", "risk_level", "business_impact",
        "requires_collaboration", "has_subtasks", "technical_debt_added",
        "delay_risk_score",
    ]
    return df[[c for c in keep if c in df.columns]]


def clean_assignments(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["assignment_success"] = df["assignment_success"].map(
        {True: 1, False: 0, "True": 1, "False": 0}
    )
    completed = df["completion_status"].str.lower() == "completed"
    df.loc[df["assignment_success"].isna() &  completed, "assignment_success"] = 1
    df.loc[df["assignment_success"].isna() & ~completed, "assignment_success"] = 0

    keep = [
        "assignment_id", "task_id", "employee_id", "project_id",
        "assignment_method", "acceptance_status",
        "skill_match_score", "availability_match_score",
        "workload_compatibility_score", "experience_match_score",
        "reassignment_count",
        "assignment_success",
    ]
    return df[[c for c in keep if c in df.columns]]


def clean_employees(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["n_primary_skills"] = (
        df["primary_skills"].fillna("").str.split(",")
        .apply(lambda x: len([v for v in x if v.strip()]))
    )

    keep = [
        "employee_id",
        "technical_proficiency_score", "domain_expertise_score",
        "historical_performance_score", "average_task_completion_rate",
        "collaboration_score", "burnout_risk_score",
        "work_life_balance_score", "recent_overtime_hours",
        "n_primary_skills",
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
        "delay_risk_score":         "delay_risk_score_proj",
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

    emp_full = (
        employees
        .merge(burnout,   on="employee_id", how="left")
        .merge(reviews,   on="employee_id", how="left")
        .merge(schedules, on="employee_id", how="left")
    )

    tasks_no_proj = tasks.drop(columns=["project_id"], errors="ignore")
    master = assignments.merge(tasks_no_proj, on="task_id", how="inner")
    master = master.merge(emp_full, on="employee_id", how="left")
    master = master.merge(projects, on="project_id", how="left")

    print(f"\n  Master shape after join: {master.shape}")
    return master


# ─────────────────────────────────────────────────────────────────────────────
# 5. DROP UNNECESSARY COLUMNS
# ─────────────────────────────────────────────────────────────────────────────

def drop_unnecessary(df: pd.DataFrame) -> pd.DataFrame:
    before = df.shape[1]
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
    after = df.shape[1]
    print(f"  Dropped {before - after} columns → {after} remaining")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 6. NULL CLEANER
# ─────────────────────────────────────────────────────────────────────────────

def clean_nulls(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in ["required_certifications"]:
        if col in df.columns:
            df[col] = df[col].fillna("None")

    bool_cols = ["requires_collaboration", "has_subtasks", "technical_debt_added"]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].map(
                {True: 1, False: 0, "True": 1, "False": 0}
            ).fillna(0).astype(int)

    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].isnull().any():
            df[col] = df[col].fillna(df[col].median())

    for col in df.select_dtypes(include=["object"]).columns:
        if df[col].isnull().any():
            df[col] = df[col].fillna("Unknown")

    remaining = df.isnull().sum().sum()
    if remaining == 0:
        print(f"  ✓ Zero nulls — {df.shape[1]} columns, {df.shape[0]:,} rows")
    else:
        print(f"  ⚠ {remaining} nulls still in: {df.columns[df.isnull().any()].tolist()}")

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

    df["skill_gap"] = (
        df.get("n_required_skills", 0) - df.get("n_primary_skills", 0)
    ).clip(lower=0)

    df["emp_fitness"] = (
        df.get("skill_match_score", 50)            * 0.30 +
        df.get("experience_match_score", 50)       * 0.25 +
        df.get("availability_match_score", 50)     * 0.20 +
        df.get("workload_compatibility_score", 50) * 0.15 +
        df.get("team_compatibility_score", 50)     * 0.10
    )

    buf = df.get("buffer_days", pd.Series(np.ones(len(df)), index=df.index)).replace(0, 1)
    df["urgency_ratio"] = (df.get("days_overdue", 0) / buf).clip(-10, 10)

    df["health_risk"] = (
        df.get("burnout_risk_score", 0)   * 0.5 +
        df.get("overall_burnout_risk", 0) * 0.3 +
        df.get("predicted_burnout_30days", 0) * 0.2
    )

    df["schedule_load_ratio"] = pd.Series(0.0, index=df.index)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# 9. MAIN
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

    assert master.isnull().sum().sum() == 0, "Nulls found after interaction engineering!"

    # Save master CSV
    master_path = os.path.join(output_dir, "master_preprocessed.csv")
    master.to_csv(master_path, index=False)
    print(f"\n  Saved master → {master_path}  {master.shape}")

    # Save label encoders
    le_path = os.path.join(output_dir, "label_encoders.joblib")
    joblib.dump(LABEL_ENCODERS, le_path)
    print(f"  Saved label encoders → {le_path}")

    print("\n" + "="*70)
    print("  PREPROCESSING COMPLETE — run make_splits.py next")
    print("="*70)


if __name__ == "__main__":
    run_preprocessing()