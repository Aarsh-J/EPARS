"""
modules/ml/performance_features.py
=======================================
Assembles the 2-feature vector (formula_score, historical_performance_score)
for performance_ridge_model.pkl from real DB data, and separately exposes
get_score_signals() for the UI's real-data-only display. formula_score's 9
raw inputs are all sourced live — 8 from performance_reviews, plus
collaboration_score from employees (not performance_reviews — both tables have
a same-named column, and the model was trained specifically on the employees.csv
one; see ml_models/performance_feature_list.json). Formulas recovered verbatim
from UI_v2:code/Model2_Performance/train.py (commit 811254b3, "updated model").
"""

from db import get_connection

from .feature_specs import PERFORMANCE_FEATURES, PERFORMANCE_RAW_MEDIANS, REVIEW_TYPE_ENCODING

NUMERIC_REVIEW_FEATURES = [
    "technical_competence_score", "domain_knowledge_score", "problem_solving_score",
    "innovation_score", "quality_of_work_score", "productivity_score",
    "communication_score", "collaboration_score", "leadership_score",
    "initiative_score", "adaptability_score", "reliability_score",
    "time_management_score", "tasks_completed", "projects_completed",
    "average_task_quality", "on_time_delivery_rate", "productivity_vs_peers",
    "total_hours_worked", "overtime_hours", "utilization_rate", "self_assessment_score",
]

NUMERIC_EMP_FEATURES = [
    "years_of_experience", "technical_proficiency_score", "domain_expertise_score",
    "historical_performance_score", "average_task_completion_rate",
    "work_life_balance_score", "burnout_risk_score", "collaboration_score",
]


_REVIEW_COLS_NOT_LIVE = {"innovation_score", "adaptability_score", "reliability_score", "utilization_rate"}


def _fetch_review_row(employee_id: str, review_id: str | None) -> dict:
    cols = [c for c in NUMERIC_REVIEW_FEATURES if c not in _REVIEW_COLS_NOT_LIVE]
    sql = f"""
        SELECT {", ".join(cols)}, review_type
        FROM performance_reviews
        WHERE employee_id = %s {"AND review_id = %s" if review_id else ""}
        ORDER BY review_date DESC
        LIMIT 1
    """
    params = (employee_id, review_id) if review_id else (employee_id,)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
    return dict(row) if row else {}


def _fetch_employee_row(employee_id: str) -> dict:
    cols = [c for c in NUMERIC_EMP_FEATURES if c != "work_life_balance_score"]  # not a live column
    sql = f"SELECT {', '.join(cols)} FROM employees WHERE employee_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
    return dict(row) if row else {}


def _fetch_feedback_agg(employee_id: str) -> dict:
    sql = """
        SELECT
            AVG(overall_rating)       AS fb_overall_rating,
            AVG(quality_rating)       AS fb_quality_rating,
            AVG(timeliness_rating)    AS fb_timeliness_rating,
            AVG(collaboration_rating) AS fb_collaboration_rating,
            AVG(communication_rating) AS fb_communication_rating,
            COUNT(*)                  AS fb_count
        FROM feedback
        WHERE recipient_id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
    return dict(row) if row else {}


def _fetch_workload_agg(employee_id: str) -> dict:
    sql = """
        SELECT
            AVG(productivity_score)   AS wh_avg_productivity,
            AVG(efficiency_ratio)     AS wh_avg_efficiency,
            AVG(task_completion_rate) AS wh_avg_task_completion,
            AVG(quality_of_work)      AS wh_avg_quality,
            SUM(overtime_hours)       AS wh_overtime_days,
            AVG(focused_work_hours)   AS wh_avg_focus_hours,
            AVG(burnout_risk_today)   AS wh_avg_burnout_risk
        FROM workload_history
        WHERE employee_id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
    return dict(row) if row else {}


_FORMULA_RAW_NAMES = [
    "technical_competence_score", "domain_knowledge_score", "problem_solving_score",
    "communication_score", "leadership_score", "initiative_score", "time_management_score",
    "quality_of_work_score", "productivity_score",
]


def assemble_performance_features(employee_id: str, review_id: str | None = None):
    """
    Returns (vector: dict[str, float], imputed: list[str]) for
    performance_ridge_model.pkl. `vector` has exactly PERFORMANCE_FEATURES
    ("formula_score", "historical_performance_score") as keys.
    """
    review = _fetch_review_row(employee_id, review_id)
    emp = _fetch_employee_row(employee_id)

    raw: dict[str, float] = {}
    imputed: list[str] = []
    for name in _FORMULA_RAW_NAMES:
        val = review.get(name)
        if val is not None:
            raw[name] = float(val)
        else:
            raw[name] = PERFORMANCE_RAW_MEDIANS[name]
            imputed.append(name)

    for name in ("historical_performance_score", "collaboration_score"):
        val = emp.get(name)
        if val is not None:
            raw[name] = float(val)
        else:
            raw[name] = PERFORMANCE_RAW_MEDIANS[name]
            imputed.append(name)
    historical_performance_score = raw["historical_performance_score"]

    technical_cluster = (
        raw["technical_competence_score"] + raw["domain_knowledge_score"] + raw["problem_solving_score"]
    ) / 3 * 10
    # collaboration_score comes from `employees`, not performance_reviews — see module docstring.
    behavioral_cluster = (
        raw["communication_score"] + raw["collaboration_score"] + raw["leadership_score"]
        + raw["initiative_score"] + raw["time_management_score"]
    ) / 5 * 10
    quality_norm = raw["quality_of_work_score"] * 10
    productivity_norm = raw["productivity_score"] * 10

    formula_score = (
        technical_cluster * 0.30 + behavioral_cluster * 0.25 + quality_norm * 0.20 + productivity_norm * 0.25
    )

    vector = {
        "formula_score": formula_score,
        "historical_performance_score": historical_performance_score,
    }
    return vector, imputed


REVIEW_DIMENSION_COLS = [
    "technical_competence", "domain_knowledge", "problem_solving", "quality_of_work",
    "productivity", "communication", "collaboration", "leadership", "initiative",
    "time_management",
]


def get_score_signals(employee_id: str, review_id: str | None = None) -> dict:
    """
    Real-data-only view for the API/UI (as opposed to predict.py's mean-imputed
    vector, which exists purely to feed the Ridge model). Composites are only
    computed when every one of their raw inputs is real; otherwise they're
    reported as None so the frontend can show "not enough data" instead of a
    number derived from a training-mean placeholder.
    """
    review = _fetch_review_row(employee_id, review_id)
    fb = _fetch_feedback_agg(employee_id)

    review_dimensions = {
        dim: float(review[f"{dim}_score"])
        for dim in REVIEW_DIMENSION_COLS
        if review.get(f"{dim}_score") is not None
    }

    # output_quality_composite always omitted here: one of its 3 training
    # inputs (utilization_rate) has no live source, so it can never be fully
    # real-data-backed — reporting it from 2-of-3 real inputs would silently
    # bake in a training-mean placeholder without saying so.
    signals = {"output_quality_composite": None}

    if review.get("overtime_hours") is not None and review.get("total_hours_worked") is not None:
        signals["overtime_ratio"] = round(
            float(review["overtime_hours"]) / (float(review["total_hours_worked"]) + 1e-6), 4
        )
    else:
        signals["overtime_ratio"] = None

    if review.get("productivity_vs_peers") is not None and review.get("productivity_score") is not None:
        signals["peer_productivity_gap"] = round(
            float(review["productivity_vs_peers"]) - float(review["productivity_score"]), 2
        )
    else:
        signals["peer_productivity_gap"] = None

    fb_cols = ["fb_overall_rating", "fb_quality_rating", "fb_timeliness_rating",
               "fb_collaboration_rating", "fb_communication_rating"]
    fb_vals = [fb[c] for c in fb_cols if fb.get(c) is not None]
    # fb_innovation_rating has no live source, so this is a partial (5-of-6) real average.
    signals["fb_composite_rating"] = round(sum(float(v) for v in fb_vals) / len(fb_vals), 2) if fb_vals else None

    return {"review_dimensions": review_dimensions, **signals}
