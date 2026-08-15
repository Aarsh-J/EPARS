"""
modules/performance/routes.py
================================
FastAPI router exposing performance data to the frontend. Reuses the existing
DB connection helper and tool functions from src/epars_agent — no new DB logic
is duplicated beyond the list/history/evaluation queries tools.py doesn't
already have.

/analyse returns the DB-stored `recorded_score` alongside an `ai_predicted_score`
from performance_model.pkl (see modules/ml/) plus `score_signals` (real
per-review-dimension scores and engineered composites) and a written
`justification` (see modules/ml/justification.py). A manager then finalizes a
score via /finalize — see docs/performance_scoring.md / docs/API-Contracts.md
for the full contract.

Score propagation: performance_reviews is never written to (keeps model
training data clean). Instead, `recorded_score` here and the list in
/employees both prefer the *latest* performance_ai_evaluations.final_score for
an employee, falling back to performance_reviews.overall_performance_score if
no decision has been made yet — so a manager's decision visibly "sticks."
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import get_connection
from tools import get_employee_profile, get_employee_ml_scores, _to_list

from ..ml.performance_features import get_score_signals
from ..ml.predict import predict_performance
from ..ml.justification import generate_justification

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
    Latest performance score per employee (the manager's last decision if one
    exists, otherwise the raw review score), for the employee-selector table.
    """
    sql = """
        SELECT DISTINCT ON (e.employee_id)
            e.employee_id,
            e.department,
            e.role,
            e.seniority_level AS seniority,
            COALESCE(ai.final_score, pr.overall_performance_score) AS score
        FROM employees e
        LEFT JOIN performance_reviews pr ON pr.employee_id = e.employee_id
        LEFT JOIN LATERAL (
            SELECT final_score
            FROM performance_ai_evaluations
            WHERE employee_id = e.employee_id
            ORDER BY decided_at DESC
            LIMIT 1
        ) ai ON true
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


def _latest_ai_evaluation(employee_id: str) -> dict | None:
    sql = """
        SELECT * FROM performance_ai_evaluations
        WHERE employee_id = %s
        ORDER BY decided_at DESC
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
    return dict(row) if row else None


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
        latest_eval = _latest_ai_evaluation(body.employee_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        live = predict_performance(body.employee_id, body.review_id)
        signals = get_score_signals(body.employee_id, body.review_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if latest_eval is not None:
        recorded_score = round(float(latest_eval["final_score"]), 1)
    else:
        pem_score = ml_scores.get("pem_score")
        recorded_score = round(float(pem_score), 1) if pem_score is not None else None
    rating_label, rating_color = _rating(recorded_score)

    employee_summary = {
        "employee_id": profile["employee_id"],
        "role": profile["role"],
        "department": profile["department"],
        "seniority": profile["seniority_level"],
    }

    justification = generate_justification(
        employee_profile=employee_summary,
        ai_predicted_score=live["predicted_score"],
        ai_confidence=live["confidence"],
        score_signals=signals,
    )

    return {
        "employee": {
            **employee_summary,
            "review_type": ml_scores.get("performance_rating"),
            "review_date": ml_scores.get("pem_review_date"),
        },
        "recorded_score": recorded_score,
        "rating_label": rating_label,
        "rating_color": rating_color,
        "ai_predicted_score": live["predicted_score"],
        "ai_confidence": live["confidence"],
        "ai_real_feature_count": live["real_feature_count"],
        "ai_total_feature_count": live["total_feature_count"],
        "score_signals": signals,
        "justification": justification["justification"],
        "policy_citation": justification["policy_citation"],
        "last_decision": {
            "decision": latest_eval["manager_decision"],
            "final_score": round(float(latest_eval["final_score"]), 1),
            "decided_at": latest_eval["decided_at"].isoformat() if latest_eval["decided_at"] else None,
        } if latest_eval else None,
        "all_reviews": reviews,
    }


class FinalizeRequest(BaseModel):
    employee_id: str
    review_id: str | None = None
    decision: str  # "accepted" | "edited"
    final_score: float | None = None
    ai_predicted_score: float | None = None
    ai_confidence: str | None = None
    ai_justification: str | None = None
    policy_citation: str | None = None
    manager_note: str | None = None


@router.post("/finalize")
def finalize_score(body: FinalizeRequest):
    if body.decision not in ("accepted", "edited"):
        raise HTTPException(status_code=400, detail="decision must be 'accepted' or 'edited'")

    final_score = body.final_score
    if body.decision == "accepted":
        final_score = final_score if final_score is not None else body.ai_predicted_score
    if final_score is None:
        raise HTTPException(status_code=400, detail="final_score is required")

    next_id_sql = """
        SELECT COALESCE(MAX(CAST(SUBSTRING(evaluation_id FROM 7) AS INTEGER)), 0) AS max_num
        FROM performance_ai_evaluations
    """
    insert_sql = """
        INSERT INTO performance_ai_evaluations (
            evaluation_id, employee_id, review_id, ai_predicted_score, ai_confidence,
            ai_justification, policy_citation, manager_decision, final_score,
            manager_note, decided_at, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    now = datetime.now()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(next_id_sql)
                next_num = cur.fetchone()["max_num"] + 1
                evaluation_id = f"AIEVAL{next_num:04d}"
                cur.execute(insert_sql, (
                    evaluation_id, body.employee_id, body.review_id, body.ai_predicted_score,
                    body.ai_confidence, body.ai_justification, body.policy_citation,
                    body.decision, final_score, body.manager_note, now, now,
                ))
                row = dict(cur.fetchone())
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    row["decided_at"] = row["decided_at"].isoformat() if row["decided_at"] else None
    row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None
    return row


@router.get("/evaluations/{employee_id}")
def get_evaluations(employee_id: str):
    sql = """
        SELECT * FROM performance_ai_evaluations
        WHERE employee_id = %s
        ORDER BY decided_at DESC
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (employee_id,))
                rows = _to_list(cur.fetchall())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    for row in rows:
        row["decided_at"] = row["decided_at"].isoformat() if row["decided_at"] else None
        row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None
    return rows
