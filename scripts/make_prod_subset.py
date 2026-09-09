"""
scripts/make_prod_subset.py

Builds a small, referentially-consistent "prod demo" dataset by subsetting the
real dataset/*.csv files (the same data already loaded into the dev Supabase
project and used to calibrate the ML models) down to ~5 employees per
department (35 total across the 7 departments), plus every row in the other
9 tables that actually relates to those employees.

Unlike a fresh synthetic generation, this guarantees the output matches the
exact schema and value scales the deployed models expect (no column/scale
drift risk).

Usage:
    python scripts/make_prod_subset.py

Reads from:  dataset/
Writes to:   dataset-prod/
"""

import csv
import os
import random
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(SCRIPT_DIR, "..", "dataset")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "dataset-prod")
PER_DEPT   = 5          # 5 employees x 7 departments = 35 total
SEED       = 42

os.makedirs(OUTPUT_DIR, exist_ok=True)


def read_csv(name):
    path = os.path.join(INPUT_DIR, name)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames


def write_csv(name, rows, fieldnames):
    path = os.path.join(OUTPUT_DIR, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {name:<24} {len(rows):>6} rows -> {path}")


def split_ids(cell):
    if not cell:
        return set()
    return {x.strip() for x in cell.split(",") if x.strip()}


def main():
    rng = random.Random(SEED)

    employees, emp_fields = read_csv("employees.csv")
    by_dept = defaultdict(list)
    for row in employees:
        by_dept[row["department"]].append(row)

    print("Selecting employees per department:")
    selected_employees = []
    for dept in sorted(by_dept):
        pool = by_dept[dept]
        k = min(PER_DEPT, len(pool))
        picked = rng.sample(pool, k)
        selected_employees.extend(picked)
        print(f"  {dept:<14} {k}/{len(pool)} selected")

    emp_ids = {row["employee_id"] for row in selected_employees}
    print(f"\nTotal employees selected: {len(emp_ids)}\n")

    task_assignments, ta_fields = read_csv("task_assignments.csv")
    tasks, task_fields = read_csv("tasks.csv")
    projects, proj_fields = read_csv("projects.csv")
    team_formations, tf_fields = read_csv("team_formations.csv")
    workload_history, wl_fields = read_csv("workload_history.csv")
    schedules, sch_fields = read_csv("schedules.csv")
    burnout_indicators, bi_fields = read_csv("burnout_indicators.csv")
    feedback, fb_fields = read_csv("feedback.csv")
    performance_reviews, pr_fields = read_csv("performance_reviews.csv")

    # task_assignments: direct employee link
    sel_ta = [r for r in task_assignments if r["employee_id"] in emp_ids]
    ta_task_ids = {r["task_id"] for r in sel_ta if r.get("task_id")}
    ta_proj_ids = {r["project_id"] for r in sel_ta if r.get("project_id")}

    # tasks: referenced by selected task_assignments OR directly assigned_to a selected employee
    sel_tasks = [
        r for r in tasks
        if r["task_id"] in ta_task_ids or r.get("assigned_to") in emp_ids
    ]
    task_proj_ids = {r["project_id"] for r in sel_tasks if r.get("project_id")}

    # team_formations: lead or any member is a selected employee
    sel_tf = [
        r for r in team_formations
        if r.get("team_lead_id") in emp_ids or (split_ids(r.get("member_ids")) & emp_ids)
    ]
    tf_proj_ids = {r["project_id"] for r in sel_tf if r.get("project_id")}

    # projects: referenced by kept tasks/teams, or managed by / staffed with a selected employee
    keep_proj_ids = ta_proj_ids | task_proj_ids | tf_proj_ids
    sel_projects = [
        r for r in projects
        if r["project_id"] in keep_proj_ids
        or r.get("project_manager_id") in emp_ids
        or (split_ids(r.get("team_member_ids")) & emp_ids)
    ]

    # direct employee_id tables
    sel_workload = [r for r in workload_history if r["employee_id"] in emp_ids]
    sel_schedules = [r for r in schedules if r["employee_id"] in emp_ids]
    sel_burnout = [r for r in burnout_indicators if r["employee_id"] in emp_ids]

    # feedback: provider or recipient
    sel_feedback = [
        r for r in feedback
        if r.get("provider_id") in emp_ids or r.get("recipient_id") in emp_ids
    ]

    # performance_reviews: reviewee or reviewer
    sel_reviews = [
        r for r in performance_reviews
        if r.get("employee_id") in emp_ids or r.get("reviewer_id") in emp_ids
    ]

    print("Writing subset CSVs:")
    write_csv("employees.csv", selected_employees, emp_fields)
    write_csv("projects.csv", sel_projects, proj_fields)
    write_csv("tasks.csv", sel_tasks, task_fields)
    write_csv("task_assignments.csv", sel_ta, ta_fields)
    write_csv("schedules.csv", sel_schedules, sch_fields)
    write_csv("workload_history.csv", sel_workload, wl_fields)
    write_csv("team_formations.csv", sel_tf, tf_fields)
    write_csv("feedback.csv", sel_feedback, fb_fields)
    write_csv("performance_reviews.csv", sel_reviews, pr_fields)
    write_csv("burnout_indicators.csv", sel_burnout, bi_fields)

    print("\nDone.")


if __name__ == "__main__":
    main()
