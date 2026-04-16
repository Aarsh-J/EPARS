"""
06_backfill.py — Backfill derived columns into employees.csv and
team_formations.csv using actual data from all other generated tables.

Backfills:
  employees:
    - recent_overtime_hours   (from workload_history last 30 days)
    - average_task_completion_rate (from task_assignments)
    - current_project_count   (from active task_assignments)
    - is_available            (current_project_count < 3)
    - successful_project_count (from projects via team_formations)
    - failed_project_count    (from projects via team_formations)
    - past_team_members       (from team_formations history)
    - productivity_trend      (from workload_history rolling trend)
    - burnout_risk_score      (recalculated from actual overtime + days_since_leave)
    - stress_level            (bucketed from burnout_risk_score)
    - leadership_potential    (recalculated with actual successful_project_count)

  team_formations:
    - actual_performance_score (weighted avg of quality + deadline + budget + satisfaction)
    - met_deadline             (actual_end_date <= planned_end_date)
    - completion_time_days     (actual_end_date - formation_date)
    - quality_rating           (avg task quality_score for team members)
    - budget_adherence         (consumed_resources / budget × 100)
    - project_completed        (from project.current_status)
    - team_status              (from project status)
    - dissolution_date         (from project.actual_end_date)
    - resource_utilization     (consumed / allocated × 100)
    - skill_utilization_rate   (team skills vs project required_skills)
"""

import os
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config import (
    SENIORITY_LP_BASE, SENIORITY_TECH_BASE, SENIORITY_DOMAIN_BASE,
    clamp, get_emp_skills,
)

OUT_DIR = os.environ.get("OUT_DIR", "./output")

TODAY = date(2025, 4, 16)
THIRTY_DAYS_AGO = TODAY - timedelta(days=30)


# ─── Helpers (mirror 01_employees_projects.py formulas) ──────────────────────

def calc_burnout_risk(overtime_hours: float, days_since_leave: int) -> float:
    overtime_factor = min(overtime_hours / 20.0, 1.0) * 60
    leave_factor    = min(days_since_leave / 180.0, 1.0) * 40
    base = overtime_factor * 0.55 + leave_factor * 0.45
    return clamp(round(base + np.random.normal(0, 5), 1), 0.0, 100.0)


def stress_from_burnout(burnout: float) -> str:
    if burnout >= 67:
        return "High"
    elif burnout >= 34:
        return "Medium"
    return "Low"


def calc_leadership_potential(seniority: str, successful_projects: int,
                               collaboration_score) -> float:
    lp_base     = SENIORITY_LP_BASE.get(seniority, 40)
    success_norm= min(successful_projects / 20.0, 1.0) * 100
    collab_norm = (float(collaboration_score) / 10.0) * 100
    base = lp_base * 0.45 + success_norm * 0.30 + collab_norm * 0.25
    return clamp(round(base + np.random.normal(0, 5), 1), 5.0, 100.0)


# ─── EMPLOYEES BACKFILL ───────────────────────────────────────────────────────

def backfill_employees(emp_df, ta_df, wh_df, tf_df, proj_df) -> pd.DataFrame:
    df      = emp_df.copy()
    emp_ids = set(df["employee_id"])

    # ── recent_overtime_hours (last 30 days from workload_history) ───────────
    wh_df["_date"] = pd.to_datetime(wh_df["date"])
    recent_wh      = wh_df[wh_df["_date"] >= pd.Timestamp(THIRTY_DAYS_AGO)]
    recent_ot      = recent_wh.groupby("employee_id")["overtime_hours"].sum()
    df["recent_overtime_hours"] = df["employee_id"].map(recent_ot).fillna(0.0).round(1)

    # ── current_project_count (active In Progress assignments) ───────────────
    active_ta   = ta_df[ta_df["completion_status"] == "In Progress"]
    proj_counts = active_ta.groupby("employee_id")["project_id"].nunique()
    df["current_project_count"] = (
        df["employee_id"].map(proj_counts).fillna(0).astype(int)
    )
    df["is_available"] = df["current_project_count"] < 3

    # ── average_task_completion_rate (on_time_completion from assignments) ───
    completed_ta  = ta_df[ta_df["completion_status"] == "Completed"]
    on_time_rate  = (completed_ta.groupby("employee_id")["on_time_completion"]
                     .mean() * 100)
    df["average_task_completion_rate"] = (
        df["employee_id"].map(on_time_rate)
        .fillna(df["average_task_completion_rate"])  # keep seed if no data
        .round(1)
    )
    df["average_task_completion_rate"] = df["average_task_completion_rate"].apply(
        lambda x: clamp(x, 0.0, 100.0)
    )

    # ── successful / failed project counts (from team_formations → projects) ─
    proj_outcome = dict(zip(proj_df["project_id"], proj_df["current_status"]))
    emp_success: dict = {e: 0 for e in emp_ids}
    emp_failed : dict = {e: 0 for e in emp_ids}

    for _, row in tf_df.iterrows():
        pid    = row["project_id"]
        outcome= proj_outcome.get(pid, "Active")
        members= [m.strip() for m in str(row.get("member_ids", "")).split(",")
                  if m.strip()]
        members.append(str(row.get("team_lead_id", "")))
        for m in members:
            if m in emp_ids:
                if outcome == "Completed":
                    emp_success[m] = emp_success.get(m, 0) + 1
                elif outcome in ("Cancelled",):
                    emp_failed[m] = emp_failed.get(m, 0) + 1

    df["successful_project_count"] = df["employee_id"].map(emp_success).fillna(0).astype(int)
    df["failed_project_count"]     = df["employee_id"].map(emp_failed ).fillna(0).astype(int)

    # ── past_team_members (comma-sep IDs from team_formations history) ───────
    emp_past_teammates: dict = {e: set() for e in emp_ids}
    for _, row in tf_df.iterrows():
        members = [m.strip() for m in str(row.get("member_ids", "")).split(",")
                   if m.strip()]
        members.append(str(row.get("team_lead_id", "")))
        members = [m for m in members if m in emp_ids]
        for m in members:
            teammates = set(members) - {m}
            emp_past_teammates[m].update(teammates)

    df["past_team_members"] = df["employee_id"].map(
        lambda e: ",".join(sorted(emp_past_teammates.get(e, set())))
    )

    # ── productivity_trend (from workload_history rolling avg) ───────────────
    wh_sorted = wh_df.sort_values(["employee_id", "_date"])

    def _trend(grp):
        scores = grp["productivity_score"].dropna().tolist()
        if len(scores) < 4:
            return "Stable"
        first_half = np.mean(scores[:len(scores)//2])
        second_half= np.mean(scores[len(scores)//2:])
        delta = second_half - first_half
        if delta > 5:
            return "Increasing"
        elif delta < -5:
            return "Decreasing"
        return "Stable"

    trend_map = wh_sorted.groupby("employee_id").apply(_trend)
    df["productivity_trend"] = df["employee_id"].map(trend_map).fillna("Stable")

    # ── burnout_risk_score (recalculate from actual data) ────────────────────
    np.random.seed(99)   # reproducible noise for backfill
    df["burnout_risk_score"] = df.apply(
        lambda r: calc_burnout_risk(
            float(r["recent_overtime_hours"]),
            int(r["days_since_last_leave"])
        ), axis=1
    )
    df["stress_level"] = df["burnout_risk_score"].apply(stress_from_burnout)

    # ── leadership_potential (recalculate with actual project success) ───────
    df["leadership_potential"] = df.apply(
        lambda r: calc_leadership_potential(
            r["seniority_level"],
            int(r["successful_project_count"]),
            r["collaboration_score"]
        ), axis=1
    )

    return df


# ─── TEAM FORMATIONS BACKFILL ─────────────────────────────────────────────────

def backfill_team_formations(tf_df, proj_df, tasks_df, emp_df) -> pd.DataFrame:
    df = tf_df.copy()

    proj_status_map  = dict(zip(proj_df["project_id"], proj_df["current_status"]))
    proj_actual_end  = dict(zip(proj_df["project_id"], proj_df["actual_end_date"]))
    proj_planned_end = dict(zip(proj_df["project_id"], proj_df["planned_end_date"]))
    proj_budget      = dict(zip(proj_df["project_id"], proj_df["budget"]))
    proj_alloc       = dict(zip(proj_df["project_id"], proj_df["allocated_resources"]))
    proj_consumed    = dict(zip(proj_df["project_id"], proj_df["consumed_resources"]))
    proj_stkh_sat    = dict(zip(proj_df["project_id"], proj_df["stakeholder_satisfaction"]))
    proj_req_skills  = dict(zip(proj_df["project_id"], proj_df["required_skills"]))

    emp_skill_map = {row["employee_id"]: get_emp_skills(row)
                     for _, row in emp_df.iterrows()}

    # Average task quality per project
    completed_tasks = tasks_df[tasks_df["status"] == "Completed"]
    task_quality_by_proj = (
        completed_tasks.groupby("project_id")["quality_score"].mean()
    )

    new_rows = []
    for _, row in df.iterrows():
        pid    = row["project_id"]
        status = proj_status_map.get(pid, "Active")
        completed = status == "Completed"

        # project_completed
        proj_completed = completed

        # team_status
        if status == "Completed":
            team_status = "Completed"
        elif status in ("Cancelled",):
            team_status = "Disbanded"
        elif status == "On Hold":
            team_status = "On Hold"
        else:
            team_status = "Active"

        # dissolution_date
        actual_end = proj_actual_end.get(pid)
        dissolution_date = actual_end if team_status in ("Completed", "Disbanded") else None
        dissolution_rsn  = ("Project Complete" if team_status == "Completed"
                            else "Reorganization" if team_status == "Disbanded"
                            else None)

        # met_deadline and completion_time_days
        met_deadline = None
        comp_time    = None
        if completed and actual_end and pd.notna(actual_end):
            actual_end_dt  = date.fromisoformat(str(actual_end))
            planned_end_dt = date.fromisoformat(str(proj_planned_end.get(pid, actual_end)))
            form_dt        = date.fromisoformat(str(row["formation_date"]))
            met_deadline   = actual_end_dt <= planned_end_dt
            comp_time      = float((actual_end_dt - form_dt).days)

        # quality_rating: avg task quality for this team's project
        avg_q = task_quality_by_proj.get(pid, None)
        quality_rating = int(round(avg_q)) if avg_q is not None and not np.isnan(avg_q) else (
            row.get("quality_rating")
        )

        # budget_adherence: consumed / budget × 100
        budget   = float(proj_budget.get(pid, 1) or 1)
        consumed = float(proj_consumed.get(pid, 0) or 0)
        budget_adh = clamp(round(consumed / max(budget, 1) * 100, 1), 0.0, 200.0) \
                     if completed else None

        # resource_utilization: consumed / allocated × 100
        alloc    = float(proj_alloc.get(pid, 1) or 1)
        res_util = clamp(round(consumed / max(alloc, 1) * 100, 1), 0.0, 150.0)

        # skill_utilization_rate
        req_skills_str = proj_req_skills.get(pid, "")
        req_set = {s.strip() for s in str(req_skills_str).split(",") if s.strip()}
        members = [m.strip() for m in str(row.get("member_ids", "")).split(",") if m.strip()]
        members.append(str(row.get("team_lead_id", "")))
        covered = set()
        for m in members:
            covered |= emp_skill_map.get(m, set()) & req_set
        skill_util = clamp(round(
            (len(covered) / max(len(req_set), 1)) * 100, 1
        ), 0.0, 100.0)

        # stakeholder_satisfaction (from project if available)
        stkh_sat_proj = proj_stkh_sat.get(pid)
        stkh_sat_final = row.get("stakeholder_satisfaction")
        if completed and stkh_sat_proj is not None and not (
                isinstance(stkh_sat_proj, float) and np.isnan(stkh_sat_proj)):
            stkh_sat_final = int(round(float(stkh_sat_proj)))

        # actual_performance_score: weighted avg of quality + deadline + budget + satisfaction
        if completed:
            q_norm    = (float(quality_rating) / 10 * 100) if quality_rating else 75.0
            dl_norm   = 100.0 if met_deadline else 50.0
            # budget_adherence → penalty over 100
            ba_norm   = max(0.0, 100 - max(float(budget_adh or 100) - 100, 0) * 1.5)
            sat_norm  = (float(stkh_sat_final or 7) / 10 * 100)
            actual_perf = clamp(round(
                q_norm   * 0.35 + dl_norm  * 0.30
                + ba_norm * 0.20 + sat_norm * 0.15
                + np.random.normal(0, 3), 1
            ), 20.0, 100.0)
        else:
            actual_perf = row.get("actual_performance_score")

        updated = row.to_dict()
        updated.update({
            "project_completed":      proj_completed,
            "completion_time_days":   comp_time,
            "met_deadline":           met_deadline,
            "quality_rating":         quality_rating,
            "budget_adherence":       budget_adh,
            "stakeholder_satisfaction": stkh_sat_final,
            "actual_performance_score": actual_perf,
            "resource_utilization":   res_util,
            "skill_utilization_rate": skill_util,
            "team_status":            team_status,
            "dissolution_date":       dissolution_date,
            "dissolution_reason":     dissolution_rsn,
        })
        new_rows.append(updated)

    return pd.DataFrame(new_rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    np.random.seed(42)

    print("Loading all tables...")
    emp_df   = pd.read_csv(f"{OUT_DIR}/employees.csv")
    ta_df    = pd.read_csv(f"{OUT_DIR}/task_assignments.csv")
    wh_df    = pd.read_csv(f"{OUT_DIR}/workload_history.csv")
    tf_df    = pd.read_csv(f"{OUT_DIR}/team_formations.csv")
    proj_df  = pd.read_csv(f"{OUT_DIR}/projects.csv")
    tasks_df = pd.read_csv(f"{OUT_DIR}/tasks.csv")
    print(f"  Loaded: {len(emp_df)} emp | {len(ta_df)} assign | {len(wh_df)} workload"
          f" | {len(tf_df)} teams | {len(proj_df)} proj | {len(tasks_df)} tasks")

    print("\nBackfilling employees.csv...")
    emp_df = backfill_employees(emp_df, ta_df, wh_df, tf_df, proj_df)
    emp_df.to_csv(f"{OUT_DIR}/employees.csv", index=False)
    print(f"  OK employees.csv overwritten ({len(emp_df)} rows)")

    print("\nBackfilling team_formations.csv...")
    tf_df = backfill_team_formations(tf_df, proj_df, tasks_df, emp_df)
    tf_df.to_csv(f"{OUT_DIR}/team_formations.csv", index=False)
    print(f"  OK team_formations.csv overwritten ({len(tf_df)} rows)")

    print("\nBackfill summary:")
    print(f"  is_available=True        : {emp_df['is_available'].sum()}/{len(emp_df)}")
    print(f"  current_project_count>0  : {(emp_df['current_project_count']>0).sum()}/{len(emp_df)}")
    print(f"  avg successful_projects  : {emp_df['successful_project_count'].mean():.1f}")
    print(f"  burnout_risk range       : {emp_df['burnout_risk_score'].min():.1f} – "
          f"{emp_df['burnout_risk_score'].max():.1f}")
    print(f"  stress_level dist:\n{emp_df['stress_level'].value_counts().to_string()}")
    print(f"  productivity_trend dist:\n{emp_df['productivity_trend'].value_counts().to_string()}")

    tf_done = tf_df[tf_df["actual_performance_score"].notna()]
    if len(tf_done) > 5:
        corr = tf_done["predicted_success_rate"].corr(tf_done["actual_performance_score"])
        print(f"\n  team pred/actual correlation (post-backfill): {corr:.3f}")
