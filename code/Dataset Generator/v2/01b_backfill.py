"""
01b_backfill.py — Backfill derived columns into employees.csv (overwrites in place).

Derives from other generated tables:
  - is_available          : True if active task_assignment count < 3
  - current_project_count : count of active project assignments
  - mentoring_experience  : True if employee appears as reviewer_id in performance_reviews
  - cross_functional_experience: True if employee worked across >1 department in team_formations

Run AFTER all other scripts. Overwrites output/employees.csv.
"""

import os
import pandas as pd

OUT_DIR = os.environ.get("OUT_DIR", "./output")


def backfill_employees(
    emp_df: pd.DataFrame,
    ta_df: pd.DataFrame,
    rev_df: pd.DataFrame,
    tf_df: pd.DataFrame,
    proj_df: pd.DataFrame,
) -> pd.DataFrame:
    df = emp_df.copy()
    emp_ids = set(df["employee_id"])

    # ── is_available & current_project_count ──────────────────────────────────
    # Count active (In Progress) assignments per employee
    active_ta = ta_df[ta_df["completion_status"] == "In Progress"]
    active_proj_count = active_ta.groupby("employee_id")["project_id"].nunique()
    df["current_project_count"] = df["employee_id"].map(active_proj_count).fillna(0).astype(int)
    df["is_available"] = df["current_project_count"] < 3

    # ── mentoring_experience ───────────────────────────────────────────────────
    # Employee has mentoring experience if they appear as a reviewer
    reviewers = set(rev_df["reviewer_id"].dropna().unique())
    df["mentoring_experience"] = df["employee_id"].isin(reviewers)

    # ── cross_functional_experience ───────────────────────────────────────────
    # True if employee worked on teams spanning >1 project department
    # Build: employee → set of project departments they were part of
    proj_dept = dict(zip(proj_df["project_id"], proj_df["department"]))
    emp_depts: dict[str, set] = {eid: set() for eid in emp_ids}

    for _, row in tf_df.iterrows():
        pid  = row["project_id"]
        dept = proj_dept.get(pid)
        if not dept:
            continue
        all_members = [m.strip() for m in str(row["member_ids"]).split(",") if m.strip()]
        all_members.append(row["team_lead_id"])
        for emp_id in all_members:
            if emp_id in emp_depts:
                emp_depts[emp_id].add(dept)

    df["cross_functional_experience"] = df["employee_id"].map(
        lambda eid: len(emp_depts.get(eid, set())) > 1
    )

    return df


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading all tables for backfill...")
    emp_df  = pd.read_csv(f"{OUT_DIR}/employees.csv")
    ta_df   = pd.read_csv(f"{OUT_DIR}/task_assignments.csv")
    rev_df  = pd.read_csv(f"{OUT_DIR}/performance_reviews.csv")
    tf_df   = pd.read_csv(f"{OUT_DIR}/team_formations.csv")
    proj_df = pd.read_csv(f"{OUT_DIR}/projects.csv")

    print("Backfilling derived columns into employees.csv...")
    emp_df = backfill_employees(emp_df, ta_df, rev_df, tf_df, proj_df)

    emp_df.to_csv(f"{OUT_DIR}/employees.csv", index=False)
    print(f"  ✓ employees.csv overwritten ({len(emp_df)} rows)")

    print("\nBackfill summary:")
    print(f"  is_available=True        : {emp_df['is_available'].sum()}/{len(emp_df)}")
    print(f"  current_project_count>0  : {(emp_df['current_project_count']>0).sum()}/{len(emp_df)}")
    print(f"  mentoring_experience=True: {emp_df['mentoring_experience'].sum()}/{len(emp_df)}")
    print(f"  cross_functional=True    : {emp_df['cross_functional_experience'].sum()}/{len(emp_df)}")
    print(f"  avg current_project_count: {emp_df['current_project_count'].mean():.2f}")
