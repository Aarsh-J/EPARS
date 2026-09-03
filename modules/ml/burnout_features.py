"""
modules/ml/burnout_features.py
===================================
Assembles the 17-feature vector for burnout_model_bundle.pkl from real DB
data. Unlike the previous 135-feature model, every one of these features is
sourceable live — from `employees` plus the employee's LATEST `burnout_indicators`
row (the training script used one row per employee, not an aggregate across
history) — so there's no live-data gap here. Missing values (e.g. an employee
with no burnout_indicators row yet) are filled with BURNOUT_LIVE_MEDIANS, since
this model (a bare GradientBoostingRegressor, not a Pipeline with an imputer)
does not impute on its own. Formulas recovered verbatim from
UI_v2:code/Model1/WBP-pp.py — see ml_models/README.md.
"""

from db import get_connection

from .feature_specs import BURNOUT_FEATURES, BURNOUT_LIVE_MEDIANS

_EMPLOYEE_COLS = [
    "technical_proficiency_score", "domain_expertise_score", "leadership_potential",
    "collaboration_score", "years_of_experience", "historical_performance_score",
    "average_task_completion_rate", "successful_project_count",
    "weekly_capacity_hours", "current_project_count", "is_available",
]

_BURNOUT_INDICATOR_COLS = [
    "late_hours_frequency", "vacation_days_unused", "job_satisfaction",
    "role_ambiguity", "job_control",
]

PROJECT_HOURS = 15  # justified constant, ported from WBP-pp.py


def _fetch_employee_row(employee_id: str) -> dict:
    sql = f"SELECT {', '.join(_EMPLOYEE_COLS)} FROM employees WHERE employee_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
    return dict(row) if row else {}


def _fetch_latest_burnout_row(employee_id: str) -> dict:
    """Latest row only — matches training's `bi_latest` (sorted by assessment_date, last())."""
    sql = f"""
        SELECT {", ".join(_BURNOUT_INDICATOR_COLS)}
        FROM burnout_indicators
        WHERE employee_id = %s
        ORDER BY assessment_date DESC
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
    return dict(row) if row else {}


def _workload_compatibility_score(emp: dict) -> float | None:
    cap = emp.get("weekly_capacity_hours")
    current_projects = emp.get("current_project_count")
    if cap is None or current_projects is None:
        return None
    cap = cap if cap else 40
    remaining_cap = max(0.0, (cap - current_projects * PROJECT_HOURS) / cap) * 100
    # Training added Gaussian noise here for synthetic-data realism; omitted
    # for deterministic live inference (see ml_models/burnout_model_metadata.json).
    return max(0.0, min(100.0, remaining_cap))


def _availability_score(emp: dict) -> float | None:
    is_avail = emp.get("is_available")
    current_projects = emp.get("current_project_count")
    if is_avail is None or current_projects is None:
        return None
    if (not is_avail) or current_projects >= 3:
        base = 25
    elif current_projects == 0:
        base = 95
    elif current_projects == 1:
        base = 78
    else:
        base = 58
    return float(base)


def assemble_burnout_features(employee_id: str):
    """
    Returns (vector: dict[str, float], imputed: list[str]).
    `vector` has exactly BURNOUT_FEATURES as keys, always fully populated
    (imputed with BURNOUT_LIVE_MEDIANS where live data is missing).
    """
    emp = _fetch_employee_row(employee_id)
    bi = _fetch_latest_burnout_row(employee_id)

    raw: dict[str, float | None] = {}
    for name in ("technical_proficiency_score", "domain_expertise_score", "leadership_potential",
                 "collaboration_score", "years_of_experience", "historical_performance_score",
                 "average_task_completion_rate", "successful_project_count"):
        val = emp.get(name)
        raw[name] = float(val) if val is not None else None

    for name in _BURNOUT_INDICATOR_COLS:
        val = bi.get(name)
        raw[name] = float(val) if val is not None else None

    raw["workload_compatibility_score"] = _workload_compatibility_score(emp)
    raw["availability_score"] = _availability_score(emp)

    late_hours = raw["late_hours_frequency"]
    vacation_days = raw["vacation_days_unused"]
    role_ambiguity = raw["role_ambiguity"]
    raw["stress_load"] = (
        (late_hours * vacation_days) / 10 if late_hours is not None and vacation_days is not None else None
    )
    raw["pressure_index"] = (
        late_hours + role_ambiguity if late_hours is not None and role_ambiguity is not None else None
    )

    imputed = [name for name in BURNOUT_FEATURES if raw.get(name) is None]
    vector = {name: (raw[name] if raw.get(name) is not None else BURNOUT_LIVE_MEDIANS[name]) for name in BURNOUT_FEATURES}

    return vector, imputed
