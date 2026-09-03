"""
modules/ml/task_assignment_predict.py
=========================================
Model3, Layer 3: scores/ranks (task, employee) pairs with NO assignment
history required — ported from preprocessor:code/Model3_TaskAssignment/scheduler.py,
swapping its CSV-backed employee/task/project profiles for the live-DB
functions in task_assignment_features.py. Composite weighting and component
breakdown kept identical to the source (see that file's docstring for why
each weight was chosen and why the assignment_success classifier — Layers 1/2
— was deliberately excluded).
"""

import numpy as np
import pandas as pd

from .loader import get_task_assignment_model
from .task_assignment_features import (
    compute_skill_match,
    get_all_employee_profiles,
    get_employee_profile_row,
    get_project_profile_row,
    get_task_profile_row,
)

WEIGHTS = {
    "delay_risk": 0.35,
    "skill_fit": 0.25,
    "availability": 0.15,
    "reliability": 0.15,
    "health": 0.10,
}


def _urgency_ratio(days_overdue: float, buffer_days: float) -> float:
    buf = buffer_days if buffer_days else 1
    return float(np.clip(days_overdue / buf, -10, 10))


def _build_pair_row(task: dict, emp: dict, proj: dict) -> dict:
    real_skill_match = compute_skill_match(task["required_skills"], emp["primary_skills"])
    skill_gap = max(0, task["n_required_skills"] - emp["n_primary_skills"])

    return {
        "technical_proficiency_score": emp["technical_proficiency_score"],
        "domain_expertise_score": emp["domain_expertise_score"],
        "historical_performance_score": emp["historical_performance_score"],
        "average_task_completion_rate": emp["average_task_completion_rate"],
        "collaboration_score": emp["collaboration_score"],
        "burnout_risk_score": emp["burnout_risk_score"],
        "recent_overtime_hours": emp["recent_overtime_hours"],
        "health_risk": emp["health_risk"],
        "schedule_load_ratio": emp["schedule_load_ratio"],
        "real_skill_match": real_skill_match,
        "task_type": task["task_type"],
        "priority": task["priority"],
        "complexity": task["complexity"],
        "estimated_hours": task["estimated_hours"],
        "story_points": task["story_points"],
        "n_required_skills": task["n_required_skills"],
        "has_cert_req": task["has_cert_req"],
        "required_role": task["required_role"],
        "required_seniority": task["required_seniority"],
        "planned_duration_days": task["planned_duration_days"],
        "n_dependencies": task["n_dependencies"],
        "days_overdue": task["days_overdue"],
        "buffer_days": task["buffer_days"],
        "rework_count": task["rework_count"],
        "risk_level": task["risk_level"],
        "business_impact": task["business_impact"],
        "requires_collaboration": task["requires_collaboration"],
        "urgency_ratio": _urgency_ratio(task["days_overdue"], task["buffer_days"]),
        "skill_gap": skill_gap,
        "success_probability": proj.get("success_probability", 60) if proj else 60,
        "budget_overrun_risk": proj.get("budget_overrun_risk", 30) if proj else 30,
        "scope_creep_indicator": proj.get("scope_creep_indicator", 0) if proj else 0,
        "days_ahead_behind": proj.get("days_ahead_behind", 0) if proj else 0,
    }


def _composite(row: dict, predicted_delay: float) -> dict:
    delay_component = float(np.clip(100 - predicted_delay, 0, 100))
    skill_component = float(np.clip(row["real_skill_match"], 0, 100))
    availability_component = float(np.clip(100 - row["schedule_load_ratio"] * 20, 0, 100))
    reliability_component = float(np.clip(row["average_task_completion_rate"], 0, 100))
    health_component = float(np.clip(100 - row["health_risk"] * 2, 0, 100))

    composite = (
        WEIGHTS["delay_risk"] * delay_component
        + WEIGHTS["skill_fit"] * skill_component
        + WEIGHTS["availability"] * availability_component
        + WEIGHTS["reliability"] * reliability_component
        + WEIGHTS["health"] * health_component
    )
    return {
        "composite_score": round(composite, 1),
        "delay_component": round(delay_component, 1),
        "skill_component": round(skill_component, 1),
        "availability_component": round(availability_component, 1),
        "reliability_component": round(reliability_component, 1),
        "health_component": round(health_component, 1),
    }


def score_pair(task_id: str, employee_id: str) -> dict:
    """Score ANY (task_id, employee_id) pair — no assignment history required."""
    task = get_task_profile_row(task_id)
    if task is None:
        raise ValueError(f"Unknown task_id: {task_id!r}")

    emp = get_employee_profile_row(employee_id)
    if emp is None:
        raise ValueError(f"Unknown employee_id: {employee_id!r}")

    proj = get_project_profile_row(task.get("project_id"))

    regressor = get_task_assignment_model()
    row = _build_pair_row(task, emp, proj)
    cols = list(regressor.feature_names_in_)
    X = pd.DataFrame([{c: row.get(c, 0) for c in cols}])
    predicted_delay = float(regressor.predict(X)[0])

    scores = _composite(row, predicted_delay)
    return {
        "task_id": task_id,
        "employee_id": employee_id,
        "predicted_delay_risk": round(predicted_delay, 1),
        "real_skill_match": row["real_skill_match"],
        **scores,
    }


def recommend_top_n(task_id: str, top_n: int = 3, candidate_pool: list[str] | None = None) -> list[dict]:
    """Rank employees for a task in one batched regressor call instead of
    one predict() per employee (the N+1 pattern the teammate's Layer 1/2
    implementation had)."""
    task = get_task_profile_row(task_id)
    if task is None:
        raise ValueError(f"Unknown task_id: {task_id!r}")

    proj = get_project_profile_row(task.get("project_id"))
    profiles = get_all_employee_profiles(candidate_pool)
    if not profiles:
        if candidate_pool is not None:
            raise ValueError(f"None of the given candidate_pool employee_ids were found: {candidate_pool}")
        raise ValueError("No employees found to score.")

    regressor = get_task_assignment_model()
    cols = list(regressor.feature_names_in_)

    rows = [_build_pair_row(task, emp, proj) for emp in profiles]
    X = pd.DataFrame([{c: r.get(c, 0) for c in cols} for r in rows])
    predicted_delay = regressor.predict(X)

    results = []
    for emp, row, delay in zip(profiles, rows, predicted_delay):
        scores = _composite(row, float(delay))
        results.append({
            "task_id": task_id,
            "employee_id": emp["employee_id"],
            "predicted_delay_risk": round(float(delay), 1),
            "real_skill_match": row["real_skill_match"],
            **scores,
        })

    results.sort(key=lambda r: r["composite_score"], reverse=True)
    return results[:top_n]
