"""
modules/ml/task_assignment_features.py
==========================================
Live-DB feature assembly for Model3's Layer 3 (task_assignment_regressor.pkl,
the novel_pair_regressor from preprocessor:code/Model3_TaskAssignment/). Ported
from that branch's preprocessing.py + profiles.py, which built these same
profiles from CSVs — here every value comes straight from Postgres, since the
live schema (tasks/projects/employees/burnout_indicators/schedules) mirrors
those CSVs column-for-column. See ml_models/README.md for feature provenance.

Only the columns scheduler.py's _build_pair_features() actually reads are
assembled — aggregate_reviews()'s output on the preprocessor branch is
computed but never consumed by Layer 3, so it's intentionally not ported here.
"""

from db import get_connection

from .loader import get_task_assignment_encoders

_EMPLOYEE_COLS = [
    "technical_proficiency_score", "domain_expertise_score",
    "historical_performance_score", "average_task_completion_rate",
    "collaboration_score", "burnout_risk_score", "recent_overtime_hours",
    "weekly_capacity_hours", "primary_skills",
]

_TASK_COLS = [
    "task_id", "task_name", "task_type", "priority", "complexity",
    "estimated_hours", "story_points", "required_skills", "required_certifications",
    "required_role", "required_seniority", "start_date", "due_date",
    "dependent_task_ids", "days_overdue", "buffer_days", "rework_count",
    "risk_level", "business_impact", "requires_collaboration", "project_id",
    "status", "assigned_to",
]

_PROJECT_COLS = ["success_probability", "budget_overrun_risk", "scope_creep_indicator", "days_ahead_behind"]

_CATEGORICAL_COLS = ["task_type", "priority", "complexity", "required_role", "required_seniority", "risk_level", "business_impact"]


def _split_count(value: str | None) -> int:
    if not value:
        return 0
    return len([v for v in str(value).split(",") if v.strip()])


def _encode(column: str, value) -> int:
    """Same fallback policy as preprocessing.py::encode_categoricals(fit=False):
    unseen values fall back to the encoder's first known class."""
    encoders = get_task_assignment_encoders()
    le = encoders.get(column)
    if le is None:
        return 0
    text = str(value) if value is not None else "Unknown"
    known = set(le.classes_)
    if text not in known:
        text = le.classes_[0]
    return int(le.transform([text])[0])


def compute_skill_match(task_skills: str | None, emp_skills: str | None) -> float:
    """Fraction of a task's required_skills an employee's primary_skills covers, 0-100.
    Ported verbatim from preprocessing.py::compute_skill_match()."""
    required = set(s.strip().lower() for s in str(task_skills or "").split(",") if s.strip())
    available = set(s.strip().lower() for s in str(emp_skills or "").split(",") if s.strip())
    if not required:
        return 100.0
    return round(len(required & available) / len(required) * 100, 2)


def _fetch_employee_row(employee_id: str) -> dict:
    sql = f"SELECT {', '.join(_EMPLOYEE_COLS)} FROM employees WHERE employee_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
    return dict(row) if row else {}

def _fetch_all_employee_rows() -> list[dict]:
    sql = f"SELECT employee_id, {', '.join(_EMPLOYEE_COLS)} FROM employees"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def _fetch_latest_burnout_row(employee_id: str) -> dict:
    sql = """
        SELECT overall_burnout_risk, predicted_burnout_30days
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


def _fetch_all_latest_burnout_rows() -> dict[str, dict]:
    sql = """
        SELECT DISTINCT ON (employee_id) employee_id, overall_burnout_risk, predicted_burnout_30days
        FROM burnout_indicators
        ORDER BY employee_id, assessment_date DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return {r["employee_id"]: dict(r) for r in rows}


def _fetch_scheduled_hours(employee_id: str) -> float:
    sql = "SELECT COALESCE(SUM(duration_minutes), 0) AS total_minutes FROM schedules WHERE employee_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
    return float(row["total_minutes"]) / 60 if row else 0.0


def _fetch_all_scheduled_hours() -> dict[str, float]:
    sql = "SELECT employee_id, COALESCE(SUM(duration_minutes), 0) AS total_minutes FROM schedules GROUP BY employee_id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return {r["employee_id"]: float(r["total_minutes"]) / 60 for r in rows}


def _derive_profile(emp: dict, burnout: dict, scheduled_hours: float) -> dict:
    cap = emp.get("weekly_capacity_hours") or 40
    schedule_load_ratio = min(10.0, max(0.0, scheduled_hours / cap))

    burnout_risk_score = float(emp.get("burnout_risk_score") or 0)
    overall_burnout_risk = float(burnout.get("overall_burnout_risk") or 0)
    predicted_30d = float(burnout.get("predicted_burnout_30days") or 0)
    health_risk = burnout_risk_score * 0.5 + overall_burnout_risk * 0.3 + predicted_30d * 0.2

    primary_skills = emp.get("primary_skills") or ""
    return {
        "technical_proficiency_score": float(emp.get("technical_proficiency_score") or 50),
        "domain_expertise_score": float(emp.get("domain_expertise_score") or 50),
        "historical_performance_score": float(emp.get("historical_performance_score") or 50),
        "average_task_completion_rate": float(emp.get("average_task_completion_rate") or 70),
        "collaboration_score": float(emp.get("collaboration_score") or 50),
        "burnout_risk_score": burnout_risk_score,
        "recent_overtime_hours": float(emp.get("recent_overtime_hours") or 0),
        "health_risk": round(health_risk, 2),
        "schedule_load_ratio": round(schedule_load_ratio, 3),
        "n_primary_skills": _split_count(primary_skills),
        "primary_skills": primary_skills,
    }


def get_employee_profile_row(employee_id: str) -> dict | None:
    emp = _fetch_employee_row(employee_id)
    if not emp:
        return None
    burnout = _fetch_latest_burnout_row(employee_id)
    scheduled_hours = _fetch_scheduled_hours(employee_id)
    profile = _derive_profile(emp, burnout, scheduled_hours)
    profile["employee_id"] = employee_id
    return profile


def get_all_employee_profiles(candidate_ids: list[str] | None = None) -> list[dict]:
    rows = _fetch_all_employee_rows()
    if candidate_ids is not None:
        wanted = set(candidate_ids)
        rows = [r for r in rows if r["employee_id"] in wanted]

    burnout_by_emp = _fetch_all_latest_burnout_rows()
    hours_by_emp = _fetch_all_scheduled_hours()

    profiles = []
    for emp in rows:
        emp_id = emp["employee_id"]
        profile = _derive_profile(emp, burnout_by_emp.get(emp_id, {}), hours_by_emp.get(emp_id, 0.0))
        profile["employee_id"] = emp_id
        profiles.append(profile)
    return profiles


def get_task_profile_row(task_id: str) -> dict | None:
    sql = f"SELECT {', '.join(_TASK_COLS)} FROM tasks WHERE task_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (task_id,))
            task = cur.fetchone()
    if not task:
        return None
    task = dict(task)

    start_date, due_date = task.get("start_date"), task.get("due_date")
    planned_duration_days = max(0, (due_date - start_date).days) if start_date and due_date else 0

    return {
        "task_id": task_id,
        "project_id": task.get("project_id"),
        "task_type": _encode("task_type", task.get("task_type")),
        "priority": _encode("priority", task.get("priority")),
        "complexity": _encode("complexity", task.get("complexity")),
        "estimated_hours": float(task.get("estimated_hours") or 8),
        "story_points": float(task.get("story_points") or 3),
        "n_required_skills": _split_count(task.get("required_skills")),
        "has_cert_req": 1 if task.get("required_certifications") else 0,
        "required_role": _encode("required_role", task.get("required_role")),
        "required_seniority": _encode("required_seniority", task.get("required_seniority")),
        "planned_duration_days": planned_duration_days,
        "n_dependencies": _split_count(task.get("dependent_task_ids")),
        "days_overdue": float(task.get("days_overdue") or 0),
        "buffer_days": float(task.get("buffer_days") or 1) or 1,
        "rework_count": float(task.get("rework_count") or 0),
        "risk_level": _encode("risk_level", task.get("risk_level")),
        "business_impact": _encode("business_impact", task.get("business_impact")),
        "requires_collaboration": 1 if task.get("requires_collaboration") else 0,
        "required_skills": task.get("required_skills") or "",
    }


def get_project_profile_row(project_id: str | None) -> dict:
    if not project_id:
        return {}
    sql = f"SELECT {', '.join(_PROJECT_COLS)} FROM projects WHERE project_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (project_id,))
            row = cur.fetchone()
    return dict(row) if row else {}


def get_open_tasks(limit: int = 200) -> list[dict]:
    """Tasks not yet completed/assigned — candidate pool for the selector UI."""
    sql = """
        SELECT task_id, task_name, task_type, priority, required_role, due_date, status
        FROM tasks
        WHERE status IS NULL OR status NOT IN ('Completed', 'Cancelled')
        ORDER BY due_date ASC NULLS LAST
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    return [dict(r) for r in rows]
