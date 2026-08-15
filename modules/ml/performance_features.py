"""
modules/ml/performance_features.py
=======================================
Assembles a 53-feature vector for performance_model.pkl from real DB data,
mean-imputing whatever isn't available live. Aggregation/composite formulas
recovered verbatim from code/Model2_Performance/performance_preprocessing.py
(commit 8d893c0a) — see ml_models/README.md.
"""

from db import get_connection

from .feature_specs import PERFORMANCE_FEATURES, REVIEW_TYPE_ENCODING

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
    "work_life_balance_score", "burnout_risk_score",
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


def assemble_performance_features(employee_id: str, review_id: str | None = None):
    """
    Returns (vector: dict[str, float | None], imputed: list[str]).
    `vector` has exactly PERFORMANCE_FEATURES as keys; a value of None means
    "not sourced from real data — caller must mean-impute before scaling".
    """
    review = _fetch_review_row(employee_id, review_id)
    emp = _fetch_employee_row(employee_id)
    fb = _fetch_feedback_agg(employee_id)
    wh = _fetch_workload_agg(employee_id)

    raw: dict[str, float | None] = {name: None for name in PERFORMANCE_FEATURES}

    for name in NUMERIC_REVIEW_FEATURES:
        if name in review and review[name] is not None:
            raw[name] = float(review[name])

    review_type = review.get("review_type")
    if review_type in REVIEW_TYPE_ENCODING:
        raw["review_type_enc"] = float(REVIEW_TYPE_ENCODING[review_type])

    for name in NUMERIC_EMP_FEATURES:
        if name in emp and emp[name] is not None:
            raw[name] = float(emp[name])

    fb_map = {
        "fb_overall_rating": fb.get("fb_overall_rating"),
        "fb_quality_rating": fb.get("fb_quality_rating"),
        "fb_timeliness_rating": fb.get("fb_timeliness_rating"),
        "fb_collaboration_rating": fb.get("fb_collaboration_rating"),
        "fb_communication_rating": fb.get("fb_communication_rating"),
    }
    for name, val in fb_map.items():
        if val is not None:
            raw[name] = float(val)
    if fb.get("fb_count") is not None:
        raw["fb_count"] = float(fb["fb_count"])

    wh_map = {
        "wh_avg_productivity": wh.get("wh_avg_productivity"),
        "wh_avg_efficiency": wh.get("wh_avg_efficiency"),
        "wh_avg_task_completion": wh.get("wh_avg_task_completion"),
        "wh_avg_quality": wh.get("wh_avg_quality"),
        "wh_overtime_days": wh.get("wh_overtime_days"),
        "wh_avg_focus_hours": wh.get("wh_avg_focus_hours"),
        "wh_avg_burnout_risk": wh.get("wh_avg_burnout_risk"),
    }
    for name, val in wh_map.items():
        if val is not None:
            raw[name] = float(val)

    return raw, [name for name, val in raw.items() if val is None]


def compute_composites(raw: dict[str, float]) -> None:
    """
    Fills 4 of the 5 engineered composite features in-place, using whatever's
    in `raw` at call time (real values and/or already-mean-imputed ones — see
    predict.py, which imputes raw inputs before calling this). Formulas
    recovered verbatim from performance_preprocessing.py.

    wh_health_score is deliberately NOT computed here: the live
    workload_history.efficiency_ratio column ranges ~0-75, not the ~0-1.2
    ratio the recovered formula's `* 20` term assumes (a genuine scale drift
    between the training CSVs and the live seeded DB), and wh_avg_stress has
    no live source at all. Computing it from that mix produced predictions
    >300 before clipping. It's left as None so predict.py mean-imputes it
    like any other unavailable feature instead.
    """
    raw["output_quality_composite"] = (
        raw["average_task_quality"] * 0.4
        + raw["on_time_delivery_rate"] * 0.3
        + raw["utilization_rate"] * 0.3
    )
    raw["overtime_ratio"] = raw["overtime_hours"] / (raw["total_hours_worked"] + 1e-6)
    raw["peer_productivity_gap"] = raw["productivity_vs_peers"] - raw["productivity_score"]
    fb_cols = [
        "fb_overall_rating", "fb_quality_rating", "fb_timeliness_rating",
        "fb_collaboration_rating", "fb_communication_rating", "fb_innovation_rating",
    ]
    raw["fb_composite_rating"] = sum(raw[c] for c in fb_cols) / len(fb_cols)


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
