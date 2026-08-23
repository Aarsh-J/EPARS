"""
profiles.py
────────────────────────────────────────────────────────────────────────────────
Task Assignment — Standalone Employee / Task / Project Profiles
────────────────────────────────────────────────────────────────────────────────
master_preprocessed.csv is built at ASSIGNMENT grain — one row per historical
task<->employee pairing — so it only has features for pairs that have already
happened. scheduler.py (Layer 3) needs to score pairs that never happened.

This module builds three standalone tables, each computable with zero
knowledge of any specific assignment:

  employee_profile.csv  — one row per employee   (from employees.csv,
                           burnout_indicators.csv, performance_reviews.csv,
                           schedules.csv)
  task_profile.csv       — one row per task        (from tasks.csv)
  project_profile.csv    — one row per project      (from projects.csv)

It reuses the exact cleaning/aggregation functions from preprocessing.py
(clean_employees, aggregate_burnout, aggregate_reviews, aggregate_schedules,
clean_tasks, clean_projects) so these profiles never drift out of sync with
how master_preprocessed.csv was built.

Run:  python profiles.py [--data-dir PATH]
Next: python train_novel_pair_models.py
"""

import os
import argparse
import warnings
import pandas as pd

import preprocessing
from preprocessing import (
    resolve_data_dir, load_raw,
    clean_employees, aggregate_burnout, aggregate_reviews, aggregate_schedules,
    clean_tasks, clean_projects,
)

warnings.filterwarnings("ignore")

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(BASE_DIR, "artifacts")


def build_employee_profile(dfs: dict) -> pd.DataFrame:
    employees = clean_employees(dfs["employees"])
    burnout   = aggregate_burnout(dfs["burnout"])
    reviews   = aggregate_reviews(dfs["reviews"])
    schedules = aggregate_schedules(dfs["schedules"])

    profile = (
        employees
        .merge(burnout,   on="employee_id", how="left")
        .merge(reviews,   on="employee_id", how="left")
        .merge(schedules, on="employee_id", how="left")
    )

    # Same engineered fields as engineer_interactions(), but computed here
    # from real per-employee values (not assignment-specific defaults),
    # since this table has no assignment context at all.
    cap = profile.get("weekly_capacity_hours", pd.Series(40.0, index=profile.index)).fillna(40).replace(0, 40)
    sched = profile.get("total_scheduled_hours", pd.Series(0.0, index=profile.index)).fillna(0)
    profile["schedule_load_ratio"] = (sched / cap).clip(0, 10)

    profile["health_risk"] = (
        profile.get("burnout_risk_score", pd.Series(0, index=profile.index)).fillna(0) * 0.5 +
        profile.get("overall_burnout_risk", pd.Series(0, index=profile.index)).fillna(0) * 0.3 +
        profile.get("predicted_burnout_30days", pd.Series(0, index=profile.index)).fillna(0) * 0.2
    )

    # Fill remaining numeric nulls with column median so scoring never crashes
    # on an employee missing a review/burnout/schedule record.
    for col in profile.select_dtypes(include="number").columns:
        if profile[col].isnull().any():
            profile[col] = profile[col].fillna(profile[col].median())

    return profile


def build_task_profile(dfs: dict) -> pd.DataFrame:
    tasks = clean_tasks(dfs["tasks"])
    # keep project_id + raw due_date/start_date context by re-pulling from
    # the raw table since clean_tasks() drops project_id/date columns
    tasks_raw = dfs["tasks"][["task_id", "project_id"]]
    profile = tasks.merge(tasks_raw, on="task_id", how="left")

    # Categoricals (task_type, priority, complexity, required_role,
    # required_seniority, risk_level, business_impact) must be encoded with
    # the SAME fitted LabelEncoders master_preprocessed.csv used, or the
    # regressor trained on it will reject/misread these values. fit=False
    # falls back to the encoder's first known class for anything unseen.
    profile = preprocessing.encode_categoricals(profile, fit=False)

    for col in profile.select_dtypes(include="number").columns:
        if profile[col].isnull().any():
            profile[col] = profile[col].fillna(profile[col].median())

    return profile


def build_project_profile(dfs: dict) -> pd.DataFrame:
    return clean_projects(dfs["projects"])


def run_profiles(data_dir: str, output_dir: str = ARTIFACTS):
    os.makedirs(output_dir, exist_ok=True)

    le_path = os.path.join(output_dir, "label_encoders.joblib")
    if not os.path.isfile(le_path):
        raise FileNotFoundError(f"{le_path} not found — run preprocessing.py first.")
    import joblib as _joblib
    preprocessing.LABEL_ENCODERS.update(_joblib.load(le_path))
    print(f"[0] Loaded {len(preprocessing.LABEL_ENCODERS)} fitted label encoders")

    print("\n[1] Loading raw data …")
    dfs = load_raw(data_dir)

    print("\n[2] Building employee_profile.csv …")
    emp_profile = build_employee_profile(dfs)
    emp_path = os.path.join(output_dir, "employee_profile.csv")
    emp_profile.to_csv(emp_path, index=False)
    print(f"    {emp_profile.shape} → {emp_path}")

    print("\n[3] Building task_profile.csv …")
    task_profile = build_task_profile(dfs)
    task_path = os.path.join(output_dir, "task_profile.csv")
    task_profile.to_csv(task_path, index=False)
    print(f"    {task_profile.shape} → {task_path}")

    print("\n[4] Building project_profile.csv …")
    proj_profile = build_project_profile(dfs)
    proj_path = os.path.join(output_dir, "project_profile.csv")
    proj_profile.to_csv(proj_path, index=False)
    print(f"    {proj_profile.shape} → {proj_path}")

    print("\nDone. Next: python train_novel_pair_models.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build standalone employee/task/project profiles")
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()
    run_profiles(resolve_data_dir(args.data_dir))
