"""
scheduler.py
────────────────────────────────────────────────────────────────────────────────
Task Assignment — Layer 3: Heuristic Scheduler
────────────────────────────────────────────────────────────────────────────────
Combines:
  - the novel_pair_regressor.pkl delay-risk prediction (validated: R2=0.851
    on pairs with zero assignment history — the strongest, most trustworthy
    signal available for a never-assigned task/employee pair)
  - explainable heuristics: skill fit, availability/workload, historical
    reliability, and burnout/health risk

into a single 0-100 composite score, and ranks EVERY employee in
employee_profile.csv against a task — not just employees who happen to have
a historical assignment record for it (that was the limitation of
inference.py's recommend_employees()).

NOT included: the assignment_success classifier. Diagnosis (see train.py /
train_novel_pair_models.py comments) showed it scores BELOW the majority-
class baseline once assignment-specific features are removed — it would
actively hurt ranking quality here, so it's deliberately left out rather
than included with a token weight.

Composite score weights (sum to 1.0):
  0.35  predicted delay risk (inverted — lower risk is better)   [validated, R2=0.851]
  0.25  skill fit (real_skill_match)                             [validated correlate]
  0.15  availability (inverse of schedule_load_ratio)             [heuristic]
  0.15  historical reliability (average_task_completion_rate)     [validated correlate,
                                                                    30%->51% success gradient]
  0.10  health/burnout risk (inverted)                            [heuristic — avoid loading
                                                                    urgent/risky tasks onto
                                                                    already-strained employees]
These weights are a starting point, not a tuned optimum — see
run_weight_sensitivity() at the bottom for how to sanity-check them, and
treat them as a tunable config once the team has real assignment outcomes
to validate ranking quality against.

Run:  python scheduler.py                    (demo: ranks all employees for one task)
      python scheduler.py --task-id TSK0001 --top-n 5
"""

import os
import argparse
import json
import warnings
import numpy as np
import pandas as pd
import joblib

from preprocessing import compute_skill_match

warnings.filterwarnings("ignore")

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(BASE_DIR, "artifacts")

WEIGHTS = {
    "delay_risk":    0.35,
    "skill_fit":     0.25,
    "availability":  0.15,
    "reliability":   0.15,
    "health":        0.10,
}

_employees = None
_tasks = None
_projects = None
_regressor = None


def _load():
    global _employees, _tasks, _projects, _regressor
    if _employees is None:
        path = os.path.join(ARTIFACTS, "employee_profile.csv")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{path} not found — run profiles.py first.")
        _employees = pd.read_csv(path)
    if _tasks is None:
        path = os.path.join(ARTIFACTS, "task_profile.csv")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{path} not found — run profiles.py first.")
        _tasks = pd.read_csv(path)
    if _projects is None:
        path = os.path.join(ARTIFACTS, "project_profile.csv")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{path} not found — run profiles.py first.")
        _projects = pd.read_csv(path)
    if _regressor is None:
        path = os.path.join(ARTIFACTS, "novel_pair_regressor.pkl")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{path} not found — run train_novel_pair_models.py first.")
        _regressor = joblib.load(path)
    return _employees, _tasks, _projects, _regressor


def _build_pair_features(task_row: pd.Series, emp_row: pd.Series, proj_row: pd.Series | None) -> dict:
    """Assemble one feature row for a (task, employee) pair, matching
    novel_pair_regressor's exact training feature set — computed fresh,
    with no dependency on task_assignments.csv."""

    real_skill_match = compute_skill_match(
        task_row.get("required_skills", ""), emp_row.get("primary_skills", "")
    )
    n_required = task_row.get("n_required_skills", 0) or 0
    n_primary  = emp_row.get("n_primary_skills", 0) or 0
    skill_gap = max(0, n_required - n_primary)

    buf = task_row.get("buffer_days", 1) or 1
    buf = buf if buf != 0 else 1
    urgency_ratio = float(np.clip((task_row.get("days_overdue", 0) or 0) / buf, -10, 10))

    row = {
        "technical_proficiency_score":  emp_row.get("technical_proficiency_score", 50),
        "domain_expertise_score":       emp_row.get("domain_expertise_score", 50),
        "historical_performance_score": emp_row.get("historical_performance_score", 50),
        "average_task_completion_rate": emp_row.get("average_task_completion_rate", 70),
        "collaboration_score":          emp_row.get("collaboration_score", 50),
        "burnout_risk_score":           emp_row.get("burnout_risk_score", 30),
        "recent_overtime_hours":        emp_row.get("recent_overtime_hours", 0),
        "health_risk":                  emp_row.get("health_risk", 15),
        "schedule_load_ratio":          emp_row.get("schedule_load_ratio", 1.0),
        "real_skill_match":             real_skill_match,
        "task_type":                    task_row.get("task_type", 0),
        "priority":                     task_row.get("priority", 0),
        "complexity":                   task_row.get("complexity", 0),
        "estimated_hours":              task_row.get("estimated_hours", 8),
        "story_points":                 task_row.get("story_points", 3),
        "n_required_skills":            n_required,
        "has_cert_req":                 task_row.get("has_cert_req", 0),
        "required_role":                task_row.get("required_role", 0),
        "required_seniority":           task_row.get("required_seniority", 0),
        "planned_duration_days":        task_row.get("planned_duration_days", 5),
        "n_dependencies":               task_row.get("n_dependencies", 0),
        "days_overdue":                 task_row.get("days_overdue", 0),
        "buffer_days":                  buf,
        "rework_count":                 task_row.get("rework_count", 0),
        "risk_level":                   task_row.get("risk_level", 0),
        "business_impact":              task_row.get("business_impact", 0),
        "requires_collaboration":       task_row.get("requires_collaboration", 0),
        "urgency_ratio":                urgency_ratio,
        "skill_gap":                    skill_gap,
        "success_probability":          proj_row.get("success_probability", 60) if proj_row is not None else 60,
        "budget_overrun_risk":          proj_row.get("budget_overrun_risk", 30) if proj_row is not None else 30,
        "scope_creep_indicator":        proj_row.get("scope_creep_indicator", 0) if proj_row is not None else 0,
        "days_ahead_behind":            proj_row.get("days_ahead_behind", 0) if proj_row is not None else 0,
    }
    return row


def _predict_delay_risk(pair_features: dict, regressor) -> float:
    cols = list(regressor.feature_names_in_)
    X = pd.DataFrame([{c: pair_features.get(c, 0) for c in cols}])
    return float(regressor.predict(X)[0])


def _composite_score(pair_features: dict, predicted_delay: float) -> dict:
    delay_component        = np.clip(100 - predicted_delay, 0, 100)
    skill_component        = np.clip(pair_features["real_skill_match"], 0, 100)
    availability_component = np.clip(100 - pair_features["schedule_load_ratio"] * 20, 0, 100)
    reliability_component  = np.clip(pair_features["average_task_completion_rate"], 0, 100)
    health_component       = np.clip(100 - pair_features["health_risk"] * 2, 0, 100)

    composite = (
        WEIGHTS["delay_risk"]   * delay_component +
        WEIGHTS["skill_fit"]    * skill_component +
        WEIGHTS["availability"] * availability_component +
        WEIGHTS["reliability"]  * reliability_component +
        WEIGHTS["health"]       * health_component
    )
    return {
        "composite_score": round(float(composite), 1),
        "delay_component": round(float(delay_component), 1),
        "skill_component": round(float(skill_component), 1),
        "availability_component": round(float(availability_component), 1),
        "reliability_component": round(float(reliability_component), 1),
        "health_component": round(float(health_component), 1),
    }


def score_pair(task_id: str, employee_id: str) -> dict:
    """Score ANY (task_id, employee_id) pair — no assignment history required."""
    employees, tasks, projects, regressor = _load()

    task_match = tasks[tasks["task_id"] == task_id]
    if task_match.empty:
        raise ValueError(f"Unknown task_id: {task_id!r}")
    task_row = task_match.iloc[0]

    emp_match = employees[employees["employee_id"] == employee_id]
    if emp_match.empty:
        raise ValueError(f"Unknown employee_id: {employee_id!r}")
    emp_row = emp_match.iloc[0]

    proj_row = None
    project_id = task_row.get("project_id")
    if pd.notna(project_id):
        proj_match = projects[projects["project_id"] == project_id]
        if not proj_match.empty:
            proj_row = proj_match.iloc[0]

    pair_features = _build_pair_features(task_row, emp_row, proj_row)
    predicted_delay = _predict_delay_risk(pair_features, regressor)
    scores = _composite_score(pair_features, predicted_delay)

    return {
        "task_id": task_id,
        "employee_id": employee_id,
        "predicted_delay_risk": round(predicted_delay, 1),
        "real_skill_match": pair_features["real_skill_match"],
        **scores,
    }


def _build_pair_features_batch(task_row: pd.Series, proj_row: pd.Series | None, employees: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized version of _build_pair_features(): builds the full feature
    matrix for ONE task against ALL employees in a single pass, so
    recommend_top_n() can call regressor.predict() once instead of once
    per employee. That loop-of-single-row-predicts was the entire cost of
    the 32s runtime measured against the 1,500-employee pool — this cuts
    it to a single batched call.
    """
    n = len(employees)

    required = set(s.strip().lower() for s in str(task_row.get("required_skills", "")).split(",") if s.strip())

    def skill_match_row(primary_skills):
        available = set(s.strip().lower() for s in str(primary_skills).split(",") if s.strip())
        if not required:
            return 100.0
        return round(len(required & available) / len(required) * 100, 2)

    real_skill_match = employees.get("primary_skills", pd.Series([""] * n)).apply(skill_match_row)

    n_required = task_row.get("n_required_skills", 0) or 0
    n_primary = employees.get("n_primary_skills", pd.Series([0] * n)).fillna(0)
    skill_gap = (n_required - n_primary).clip(lower=0)

    buf = task_row.get("buffer_days", 1) or 1
    buf = buf if buf != 0 else 1
    urgency_ratio = float(np.clip((task_row.get("days_overdue", 0) or 0) / buf, -10, 10))

    proj_get = (lambda k, d: proj_row.get(k, d)) if proj_row is not None else (lambda k, d: d)

    batch = pd.DataFrame({
        "technical_proficiency_score":  employees.get("technical_proficiency_score", 50).fillna(50),
        "domain_expertise_score":       employees.get("domain_expertise_score", 50).fillna(50),
        "historical_performance_score": employees.get("historical_performance_score", 50).fillna(50),
        "average_task_completion_rate": employees.get("average_task_completion_rate", 70).fillna(70),
        "collaboration_score":          employees.get("collaboration_score", 50).fillna(50),
        "burnout_risk_score":           employees.get("burnout_risk_score", 30).fillna(30),
        "recent_overtime_hours":        employees.get("recent_overtime_hours", 0).fillna(0),
        "health_risk":                  employees.get("health_risk", 15).fillna(15),
        "schedule_load_ratio":          employees.get("schedule_load_ratio", 1.0).fillna(1.0),
        "real_skill_match":             real_skill_match,
        "task_type":                    task_row.get("task_type", 0),
        "priority":                     task_row.get("priority", 0),
        "complexity":                   task_row.get("complexity", 0),
        "estimated_hours":              task_row.get("estimated_hours", 8),
        "story_points":                 task_row.get("story_points", 3),
        "n_required_skills":            n_required,
        "has_cert_req":                 task_row.get("has_cert_req", 0),
        "required_role":                task_row.get("required_role", 0),
        "required_seniority":           task_row.get("required_seniority", 0),
        "planned_duration_days":        task_row.get("planned_duration_days", 5),
        "n_dependencies":               task_row.get("n_dependencies", 0),
        "days_overdue":                 task_row.get("days_overdue", 0),
        "buffer_days":                  buf,
        "rework_count":                 task_row.get("rework_count", 0),
        "risk_level":                   task_row.get("risk_level", 0),
        "business_impact":              task_row.get("business_impact", 0),
        "requires_collaboration":       task_row.get("requires_collaboration", 0),
        "urgency_ratio":                urgency_ratio,
        "skill_gap":                    skill_gap,
        "success_probability":          proj_get("success_probability", 60),
        "budget_overrun_risk":          proj_get("budget_overrun_risk", 30),
        "scope_creep_indicator":        proj_get("scope_creep_indicator", 0),
        "days_ahead_behind":            proj_get("days_ahead_behind", 0),
    })
    batch["employee_id"] = employees["employee_id"].values
    return batch


def recommend_top_n(task_id: str, top_n: int = 3, candidate_pool: list | None = None) -> list:
    """
    Rank employees for a task in a single batched pass (fast — one
    regressor.predict() call for the whole pool instead of one per
    employee). candidate_pool restricts to specific employee_ids (e.g. a
    team, or employees matching required_role); defaults to every
    employee in employee_profile.csv.
    """
    employees, tasks, projects, regressor = _load()

    task_match = tasks[tasks["task_id"] == task_id]
    if task_match.empty:
        raise ValueError(f"Unknown task_id: {task_id!r}")
    task_row = task_match.iloc[0]

    proj_row = None
    project_id = task_row.get("project_id")
    if pd.notna(project_id):
        proj_match = projects[projects["project_id"] == project_id]
        if not proj_match.empty:
            proj_row = proj_match.iloc[0]

    pool_df = employees[employees["employee_id"].isin(candidate_pool)] if candidate_pool is not None else employees

    if pool_df.empty:
        if candidate_pool is not None:
            raise ValueError(
                f"None of the given candidate_pool employee_ids were found in employee_profile.csv: {candidate_pool}"
            )
        raise ValueError("employee_profile.csv is empty — run profiles.py first.")

    batch = _build_pair_features_batch(task_row, proj_row, pool_df)
    feature_cols = list(regressor.feature_names_in_)
    predicted_delay = regressor.predict(batch[feature_cols])

    delay_component        = np.clip(100 - predicted_delay, 0, 100)
    skill_component        = np.clip(batch["real_skill_match"].values, 0, 100)
    availability_component = np.clip(100 - batch["schedule_load_ratio"].values * 20, 0, 100)
    reliability_component  = np.clip(batch["average_task_completion_rate"].values, 0, 100)
    health_component       = np.clip(100 - batch["health_risk"].values * 2, 0, 100)

    composite = (
        WEIGHTS["delay_risk"]   * delay_component +
        WEIGHTS["skill_fit"]    * skill_component +
        WEIGHTS["availability"] * availability_component +
        WEIGHTS["reliability"]  * reliability_component +
        WEIGHTS["health"]       * health_component
    )

    results = pd.DataFrame({
        "task_id": task_id,
        "employee_id": batch["employee_id"].values,
        "predicted_delay_risk": predicted_delay.round(1),
        "real_skill_match": batch["real_skill_match"].values,
        "composite_score": composite.round(1),
        "delay_component": delay_component.round(1),
        "skill_component": skill_component.round(1),
        "availability_component": availability_component.round(1),
        "reliability_component": reliability_component.round(1),
        "health_component": health_component.round(1),
    }).sort_values("composite_score", ascending=False).head(top_n)

    return results.to_dict(orient="records")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Layer 3 heuristic scheduler demo")
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--top-n", type=int, default=3)
    args = parser.parse_args()

    employees, tasks, projects, regressor = _load()
    print(f"Loaded {len(employees):,} employees, {len(tasks):,} tasks, {len(projects):,} projects.")

    task_id = args.task_id or tasks.iloc[0]["task_id"]
    print(f"\nRanking top {args.top_n} employees for task_id={task_id} "
          f"(out of all {len(employees):,} employees, none pre-filtered by history) …\n")

    top = recommend_top_n(task_id, top_n=args.top_n)
    print(json.dumps(top, indent=2))