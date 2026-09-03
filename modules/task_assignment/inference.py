"""
modules/task_assignment/inference.py
────────────────────────────────────────────────────────────────────────────────
Task Assignment — Inference
────────────────────────────────────────────────────────────────────────────────
Scores a (task_id, employee_id) pair by:
  1. Fetching employee + task + project features from Supabase
  2. Building a feature vector matching what the model was trained on
  3. Running the classifier (assignment_success) and regressor (delay_risk_score)
  4. Returning a JSON-serializable result dict

No CSV files are read at inference time — all data comes from the DB.
"""

import os
import joblib
import numpy as np
import pandas as pd

from db import get_connection

# ─────────────────────────────────────────────────────────────────────────────
# 0. Paths
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
ML_MODELS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "ml_models"))

CLF_PATH = os.path.join(ML_MODELS_DIR, "best_classifier.pkl")
REG_PATH = os.path.join(ML_MODELS_DIR, "best_regressor.pkl")
LE_PATH  = os.path.join(ML_MODELS_DIR, "task_assignment_encoders.joblib")

# ─────────────────────────────────────────────────────────────────────────────
# 1. Load models once at startup
# ─────────────────────────────────────────────────────────────────────────────
_clf = None
_reg = None
_le  = None


def _load_models():
    global _clf, _reg, _le
    if _clf is None:
        if not os.path.isfile(CLF_PATH):
            raise FileNotFoundError(f"Classifier not found at {CLF_PATH}")
        _clf = joblib.load(CLF_PATH)
    if _reg is None:
        if not os.path.isfile(REG_PATH):
            raise FileNotFoundError(f"Regressor not found at {REG_PATH}")
        _reg = joblib.load(REG_PATH)
    if _le is None:
        if os.path.isfile(LE_PATH):
            _le = joblib.load(LE_PATH)
    return _clf, _reg, _le


# ─────────────────────────────────────────────────────────────────────────────
# 2. DB Queries
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_employee(employee_id: str) -> dict:
    """Fetch employee features from Supabase."""
    sql = """
        SELECT
            e.employee_id,
            e.technical_proficiency_score,
            e.domain_expertise_score,
            e.historical_performance_score,
            e.average_task_completion_rate,
            e.collaboration_score,
            e.burnout_risk_score,
            e.recent_overtime_hours,
            e.primary_skills,
            b.overall_burnout_risk,
            b.emotional_exhaustion_score,
            b.job_control,
            b.late_hours_frequency,
            b.weekend_work_frequency,
            b.job_satisfaction,
            AVG(pr.overall_performance_score) AS avg_perf_score,
            AVG(pr.quality_of_work_score)     AS avg_quality,
            AVG(pr.productivity_score)         AS avg_productivity,
            AVG(pr.time_management_score)      AS avg_timeliness,
            AVG(pr.on_time_delivery_rate)      AS on_time_rate
        FROM employees e
        LEFT JOIN LATERAL (
            SELECT *
            FROM burnout_indicators
            WHERE employee_id = e.employee_id
            ORDER BY assessment_date DESC
            LIMIT 1
        ) b ON true
        LEFT JOIN LATERAL (
            SELECT *
            FROM performance_reviews
            WHERE employee_id = e.employee_id
            ORDER BY review_date DESC
            LIMIT 2
        ) pr ON true
        WHERE e.employee_id = %s
        GROUP BY
            e.employee_id, e.technical_proficiency_score, e.domain_expertise_score,
            e.historical_performance_score, e.average_task_completion_rate,
            e.collaboration_score, e.burnout_risk_score, e.recent_overtime_hours,
            e.primary_skills,
            b.overall_burnout_risk, b.emotional_exhaustion_score, b.job_control,
            b.late_hours_frequency, b.weekend_work_frequency, b.job_satisfaction
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
    if not row:
        raise ValueError(f"No employee found with employee_id='{employee_id}'.")
    return dict(row)


def _fetch_task(task_id: str) -> dict:
    """Fetch task features from Supabase."""
    sql = """
        SELECT
            task_id,
            task_type,
            priority,
            complexity,
            estimated_hours,
            story_points,
            required_skills,
            required_role,
            required_seniority,
            required_certifications,
            technical_complexity_score,
            dependent_task_ids,
            days_overdue,
            buffer_days,
            rework_count,
            risk_level,
            business_impact,
            requires_collaboration,
            has_subtasks,
            technical_debt_added,
            delay_risk_score,
            start_date,
            due_date
        FROM tasks
        WHERE task_id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (task_id,))
            row = cur.fetchone()
    if not row:
        raise ValueError(f"No task found with task_id='{task_id}'.")
    return dict(row)


def _fetch_assignment_scores(task_id: str, employee_id: str) -> dict:
    """Fetch pre-computed match scores from task_assignments if they exist."""
    sql = """
        SELECT
            skill_match_score,
            availability_match_score,
            workload_compatibility_score,
            experience_match_score,
            reassignment_count,
            assignment_method,
            acceptance_status
        FROM task_assignments
        WHERE task_id = %s AND employee_id = %s
        ORDER BY assignment_date DESC
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (task_id, employee_id))
            row = cur.fetchone()
    return dict(row) if row else {}


def _fetch_project(task_id: str) -> dict:
    """Fetch project features linked to this task."""
    sql = """
        SELECT
            p.project_id,
            p.success_probability,
            p.budget_overrun_risk,
            p.scope_creep_indicator,
            p.days_ahead_behind,
            p.stakeholder_satisfaction
        FROM projects p
        JOIN task_assignments ta ON ta.project_id = p.project_id
        WHERE ta.task_id = %s
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (task_id,))
            row = cur.fetchone()
    return dict(row) if row else {}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Feature Engineering
# ─────────────────────────────────────────────────────────────────────────────

def _count_skills(skills_str: str) -> int:
    if not skills_str:
        return 0
    return len([s for s in str(skills_str).split(",") if s.strip()])


def _build_features(employee: dict, task: dict, assignment: dict, project: dict) -> pd.DataFrame:
    """
    Build the feature vector matching what the model was trained on.
    Mirrors the feature engineering in preprocessing.py.
    """
    # Skill counts
    n_required_skills = _count_skills(task.get("required_skills", ""))
    n_primary_skills  = _count_skills(employee.get("primary_skills", ""))

    # Planned duration
    start = pd.to_datetime(task.get("start_date"), errors="coerce")
    due   = pd.to_datetime(task.get("due_date"),   errors="coerce")
    planned_duration_days = max((due - start).days, 0) if pd.notna(start) and pd.notna(due) else 0

    # Assignment match scores — use DB values if available, else neutral 50
    skill_match_score            = assignment.get("skill_match_score",            50) or 50
    availability_match_score     = assignment.get("availability_match_score",     50) or 50
    workload_compatibility_score = assignment.get("workload_compatibility_score", 50) or 50
    experience_match_score       = assignment.get("experience_match_score",       50) or 50

    # Engineered interaction features
    skill_gap    = max(n_required_skills - n_primary_skills, 0)
    emp_fitness  = (
        skill_match_score            * 0.30 +
        experience_match_score       * 0.25 +
        availability_match_score     * 0.20 +
        workload_compatibility_score * 0.15 +
        50                           * 0.10   # team_compatibility_score default
    )
    buffer_days   = task.get("buffer_days") or 1
    days_overdue  = task.get("days_overdue") or 0
    urgency_ratio = float(np.clip(days_overdue / max(buffer_days, 1), -10, 10))

    health_risk = (
        float(employee.get("burnout_risk_score")   or 0) * 0.5 +
        float(employee.get("overall_burnout_risk") or 0) * 0.3
    )

    # Bool columns
    def _bool(val):
        if isinstance(val, bool):  return int(val)
        if isinstance(val, str):   return 1 if val.lower() in ("true", "1", "yes") else 0
        return int(val) if val is not None else 0

    features = {
        # Task features
        "task_type":                    task.get("task_type",                   "Unknown"),
        "priority":                     task.get("priority",                    "Medium"),
        "complexity":                   task.get("complexity",                  "Medium"),
        "estimated_hours":              float(task.get("estimated_hours")       or 0),
        "story_points":                 float(task.get("story_points")          or 0),
        "n_required_skills":            n_required_skills,
        "has_cert_req":                 1 if task.get("required_certifications") else 0,
        "required_certifications":      task.get("required_certifications",     "None"),
        "required_role":                task.get("required_role",               "Unknown"),
        "required_seniority":           task.get("required_seniority",          "Unknown"),
        "technical_complexity_score":   float(task.get("technical_complexity_score") or 0),
        "planned_duration_days":        planned_duration_days,
        "n_dependencies":               _count_skills(task.get("dependent_task_ids", "")),
        "days_overdue":                 float(days_overdue),
        "buffer_days":                  float(buffer_days),
        "rework_count":                 float(task.get("rework_count")          or 0),
        "risk_level":                   task.get("risk_level",                  "Medium"),
        "business_impact":              task.get("business_impact",             "Medium"),
        "requires_collaboration":       _bool(task.get("requires_collaboration")),
        "has_subtasks":                 _bool(task.get("has_subtasks")),
        "technical_debt_added":         _bool(task.get("technical_debt_added")),
        "delay_risk_score":             float(task.get("delay_risk_score")      or 0),

        # Assignment match scores
        "skill_match_score":            float(skill_match_score),
        "availability_match_score":     float(availability_match_score),
        "workload_compatibility_score": float(workload_compatibility_score),
        "experience_match_score":       float(experience_match_score),
        "reassignment_count":           float(assignment.get("reassignment_count") or 0),
        "assignment_method":            assignment.get("assignment_method",     "Manual"),
        "acceptance_status":            assignment.get("acceptance_status",     "Pending"),

        # Employee features
        "technical_proficiency_score":  float(employee.get("technical_proficiency_score") or 0),
        "domain_expertise_score":       float(employee.get("domain_expertise_score")      or 0),
        "historical_performance_score": float(employee.get("historical_performance_score")or 0),
        "average_task_completion_rate": float(employee.get("average_task_completion_rate")or 0),
        "collaboration_score":          float(employee.get("collaboration_score")         or 0),
        "burnout_risk_score":           float(employee.get("burnout_risk_score")          or 0),
        "recent_overtime_hours":        float(employee.get("recent_overtime_hours")       or 0),
        "avg_perf_score":               float(employee.get("avg_perf_score")              or 0),
        "avg_quality":                  float(employee.get("avg_quality")                 or 0),
        "avg_productivity":             float(employee.get("avg_productivity")            or 0),
        "avg_timeliness":               float(employee.get("avg_timeliness")              or 0),
        "on_time_rate":                 float(employee.get("on_time_rate")                or 0),

        # Project features
        "success_probability":          float(project.get("success_probability")    or 0),
        "budget_overrun_risk":          float(project.get("budget_overrun_risk")    or 0),
        "scope_creep_indicator":        float(project.get("scope_creep_indicator")  or 0),
        "days_ahead_behind":            float(project.get("days_ahead_behind")      or 0),
        "stakeholder_satisfaction_proj":float(project.get("stakeholder_satisfaction") or 0),

        # Engineered features
        "skill_gap":            skill_gap,
        "emp_fitness":          emp_fitness,
        "urgency_ratio":        urgency_ratio,
        "health_risk":          health_risk,
        "schedule_load_ratio":  0.0,
    }

    return pd.DataFrame([features])


# ─────────────────────────────────────────────────────────────────────────────
# 4. Label Encoding
# ─────────────────────────────────────────────────────────────────────────────

CATEGORICAL_COLS = [
    "task_type", "priority", "complexity",
    "required_role", "required_seniority", "required_certifications",
    "risk_level", "business_impact", "assignment_method", "acceptance_status",
]


def _encode(df: pd.DataFrame, le: dict) -> pd.DataFrame:
    df = df.copy()
    for col in CATEGORICAL_COLS:
        if col not in df.columns:
            continue
        df[col] = df[col].astype(str).fillna("Unknown")
        if le and col in le:
            encoder = le[col]
            known   = set(encoder.classes_)
            df[col] = df[col].apply(lambda x: x if x in known else encoder.classes_[0])
            df[col] = encoder.transform(df[col])
        else:
            df[col] = 0
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 5. Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _delay_risk_label(score: float) -> str:
    if score < 25:  return "Low"
    if score < 50:  return "Moderate"
    if score < 75:  return "High"
    return "Critical"


def _recommendation(success_prob: float, delay_score: float) -> str:
    if success_prob >= 70 and delay_score < 35:
        return "Strong match — recommend assigning."
    if success_prob >= 50 and delay_score < 60:
        return "Reasonable match — assign with normal monitoring."
    if success_prob < 50 and delay_score >= 60:
        return "Poor match — high risk of both failure and delay. Consider alternatives."
    return "Mixed signals — review manually before assigning."


def _align_features(df: pd.DataFrame, model) -> pd.DataFrame:
    """Align feature columns to exact order the model was trained on."""
    if hasattr(model, "feature_names_in_"):
        cols = list(model.feature_names_in_)
        for c in cols:
            if c not in df.columns:
                df[c] = 0
        return df[cols]
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 6. Public API
# ─────────────────────────────────────────────────────────────────────────────

def score_assignment(task_id: str, employee_id: str) -> dict:
    """
    Score a (task_id, employee_id) pair using live Supabase data.
    Returns a JSON-serializable dict with model predictions and verdict.
    """
    clf, reg, le = _load_models()

    employee   = _fetch_employee(employee_id)
    task       = _fetch_task(task_id)
    assignment = _fetch_assignment_scores(task_id, employee_id)
    project    = _fetch_project(task_id)

    df    = _build_features(employee, task, assignment, project)
    df    = _encode(df, le)

    clf_X = _align_features(df.copy(), clf)
    reg_X = _align_features(df.copy(), reg)

    pred_success = int(clf.predict(clf_X)[0])
    proba        = clf.predict_proba(clf_X)[0]
    success_prob = round(float(proba[1]) * 100, 1)

    delay_score  = round(float(np.clip(reg.predict(reg_X)[0], 0, 100)), 1)
    delay_label  = _delay_risk_label(delay_score)

    return {
        "task_id":             task_id,
        "employee_id":         employee_id,
        "assignment_success":  pred_success,
        "success_probability": success_prob,
        "delay_risk_score":    delay_score,
        "delay_risk_label":    delay_label,
        "recommendation":      _recommendation(success_prob, delay_score),
    }


def recommend_employees(task_id: str, top_n: int = 3) -> list:
    """
    Score all employees in the DB for a given task and return top N
    ranked by success_probability descending, then delay_risk_score ascending.
    """
    sql = "SELECT employee_id FROM employees"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    if not rows:
        raise ValueError("No employees found in the database.")

    scored = []
    for row in rows:
        try:
            result = score_assignment(task_id, row["employee_id"])
            scored.append(result)
        except Exception:
            continue

    if not scored:
        raise ValueError(f"Could not score any employees for task_id='{task_id}'.")

    scored.sort(key=lambda r: (-r["success_probability"], r["delay_risk_score"]))
    return scored[:top_n]