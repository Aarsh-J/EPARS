"""
modules/performance/routes.py
================================
FastAPI router exposing performance data to the frontend. Reuses the existing
DB connection helper and tool functions from src/epars_agent — no new DB logic
is duplicated beyond the two list/history queries tools.py doesn't already have
(there is no existing "all employees" or "review history" tool).

/analyse returns both the DB-stored `predicted_score` and a `live_predicted_score`
from performance_model.pkl (see modules/ml/), plus `score_signals` — real
per-review-dimension scores and engineered composites for the UI. See
ml_models/README.md for what's real vs. mean-imputed in the live model, and
docs/performance_scoring.md / docs/API-Contracts.md for the full contract.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import get_connection
from tools import get_employee_profile, get_employee_ml_scores, _to_list

from ..ml.performance_features import get_score_signals
from ..ml.predict import predict_performance

router = APIRouter(prefix="/performance", tags=["performance"])


def _rating(score: float) -> tuple[str, str]:
    """Same thresholds Performance.jsx already uses client-side for score-pill colors."""
    if score is None:
        return "Unrated", "#94a3b8"
    if score >= 85:
        return "Exceptional", "#065f46"
    if score >= 70:
        return "High Performer", "#1e40af"
    if score >= 55:
        return "Meets Expectations", "#92400e"
    return "Needs Improvement", "#991b1b"


@router.get("/employees")
def list_employees():
    """
    Latest performance score per employee, for the employee-selector table.
    """
    sql = """
        SELECT DISTINCT ON (e.employee_id)
            e.employee_id,
            e.department,
            e.role,
            e.seniority_level AS seniority,
            pr.overall_performance_score AS score
        FROM employees e
        LEFT JOIN performance_reviews pr ON pr.employee_id = e.employee_id
        ORDER BY e.employee_id, pr.review_date DESC
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = _to_list(cur.fetchall())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    for row in rows:
        row["score"] = round(float(row["score"]), 1) if row["score"] is not None else None
    return rows


def _review_history(employee_id: str) -> list[dict]:
    sql = """
        SELECT
            review_id,
            review_type,
            review_date,
            overall_performance_score AS overall_score
        FROM performance_reviews
        WHERE employee_id = %s
        ORDER BY review_date DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            rows = _to_list(cur.fetchall())
    for row in rows:
        row["review_date"] = row["review_date"].isoformat() if row["review_date"] else None
        row["overall_score"] = round(float(row["overall_score"]), 1) if row["overall_score"] is not None else None
    return rows


class AnalyseRequest(BaseModel):
    employee_id: str
    review_id: str | None = None


@router.post("/analyse")
def analyse_employee(body: AnalyseRequest):
    profile = get_employee_profile(body.employee_id)
    if "error" in profile:
        raise HTTPException(status_code=404, detail=profile["error"])

    ml_scores = get_employee_ml_scores(body.employee_id)
    try:
        reviews = _review_history(body.employee_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        live = predict_performance(body.employee_id, body.review_id)
        signals = get_score_signals(body.employee_id, body.review_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    pem_score = ml_scores.get("pem_score")
    predicted_score = round(float(pem_score), 1) if pem_score is not None else None
    rating_label, rating_color = _rating(predicted_score)

    return {
        "employee": {
            "employee_id": profile["employee_id"],
            "role": profile["role"],
            "department": profile["department"],
            "seniority": profile["seniority_level"],
            "review_type": ml_scores.get("performance_rating"),
            "review_date": ml_scores.get("pem_review_date"),
        },
        "predicted_score": predicted_score,
        "rating_label": rating_label,
        "rating_color": rating_color,
        "live_predicted_score": live["predicted_score"],
        "live_confidence": live["confidence"],
        "live_real_feature_count": live["real_feature_count"],
        "live_total_feature_count": live["total_feature_count"],
        "score_signals": signals,
        "all_reviews": reviews,
    }
