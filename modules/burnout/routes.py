"""
modules/burnout/routes.py
==============================
Confidence-gated burnout assessment + manager-confirmed task reassignment.
See modules/ml/reassignment.py for the assess/execute split and the
high/medium/low confidence policy, and ml_models/README.md for the burnout
model's known live-data gap (most predictions land in "low confidence" today).

Score propagation mirrors modules/performance/routes.py: burnout_indicators
is never written to directly. /employees and /analyse both prefer the latest
"current" burnout_ai_assessments row (status IN ('applied', 'verified')) over
the stored burnout_indicators.burnout_category.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import get_connection
from tools import get_employee_profile, _to_list

from ..ml.reassignment import assess_and_recommend, execute_recommendation

router = APIRouter(prefix="/burnout", tags=["burnout"])

_CLASS_COLOR = {
    "Low": "#065f46",
    "Moderate": "#92400e",
    "High": "#c2410c",
    # "Critical" is no longer produced by the current model (see modules/ml/predict.py)
    # but is kept so older stored assessments/DB rows from the previous model still render.
    "Critical": "#991b1b",
}


@router.get("/employees")
def list_employees():
    """
    Latest burnout category per employee (the AI assessment if one has been
    applied or verified, otherwise the stored DB value).
    """
    sql = """
        SELECT DISTINCT ON (e.employee_id)
            e.employee_id,
            e.department,
            e.role,
            e.seniority_level AS seniority,
            bi.overall_burnout_risk AS stored_score,
            COALESCE(ai.ai_predicted_class, bi.burnout_category) AS stored_category
        FROM employees e
        LEFT JOIN burnout_indicators bi ON bi.employee_id = e.employee_id
        LEFT JOIN LATERAL (
            SELECT ai_predicted_class
            FROM burnout_ai_assessments
            WHERE employee_id = e.employee_id AND status IN ('applied', 'verified')
            ORDER BY created_at DESC
            LIMIT 1
        ) ai ON true
        ORDER BY e.employee_id, bi.assessment_date DESC
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = _to_list(cur.fetchall())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    for row in rows:
        row["stored_score"] = round(float(row["stored_score"]), 1) if row["stored_score"] is not None else None
    return rows


class AnalyseRequest(BaseModel):
    employee_id: str


@router.post("/analyse")
def analyse_employee(body: AnalyseRequest):
    profile = get_employee_profile(body.employee_id)
    if "error" in profile:
        raise HTTPException(status_code=404, detail=profile["error"])

    try:
        result = assess_and_recommend(body.employee_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    stored_sql = """
        SELECT overall_burnout_risk AS stored_score, burnout_category AS stored_category
        FROM burnout_indicators
        WHERE employee_id = %s
        ORDER BY assessment_date DESC
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(stored_sql, (body.employee_id,))
            stored = cur.fetchone()

    return {
        "employee": {
            "employee_id": profile["employee_id"],
            "role": profile["role"],
            "department": profile["department"],
            "seniority": profile["seniority_level"],
        },
        "assessment_id": result["assessment_id"],
        "predicted_class": result["predicted_class"],
        "predicted_class_color": _CLASS_COLOR.get(result["predicted_class"], "#64748b"),
        "predicted_probabilities": result["predicted_probabilities"],
        "confidence": result["confidence"],
        "real_feature_count": result["real_feature_count"],
        "total_feature_count": result["total_feature_count"],
        "justification": result["justification"],
        "policy_citation": result["policy_citation"],
        "status": result["status"],
        "recommendations": result["recommendations"],
        "stored_score": round(float(stored["stored_score"]), 1) if stored and stored["stored_score"] is not None else None,
        "stored_category": stored["stored_category"] if stored else None,
    }


@router.post("/assessments/{assessment_id}/verify")
def verify_assessment(assessment_id: str):
    """
    Manager verifies a 'pending_review' (medium-confidence) assessment,
    promoting it to 'verified' so it becomes the employee's current status.
    """
    sql = """
        UPDATE burnout_ai_assessments
        SET status = 'verified', reviewed_at = %s
        WHERE assessment_id = %s AND status = 'pending_review'
        RETURNING *
    """
    now = datetime.now()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (now, assessment_id))
                row = cur.fetchone()
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not row:
        raise HTTPException(status_code=404, detail="Assessment not found or not pending review.")

    row = dict(row)
    row["reviewed_at"] = row["reviewed_at"].isoformat() if row["reviewed_at"] else None
    row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None
    return row


class RecommendationDecision(BaseModel):
    decision: str  # "confirmed" | "rejected"


@router.post("/recommendations/{recommendation_id}/decide")
def decide_recommendation(recommendation_id: str, body: RecommendationDecision):
    if body.decision not in ("confirmed", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'confirmed' or 'rejected'")

    check_sql = "SELECT manager_decision FROM task_reassignment_recommendations WHERE recommendation_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(check_sql, (recommendation_id,))
            existing = cur.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    if existing["manager_decision"] is not None:
        raise HTTPException(status_code=400, detail="This recommendation has already been decided.")

    execution_result = None
    if body.decision == "confirmed":
        try:
            execution_result = execute_recommendation(recommendation_id)
        except Exception as e:
            execution_result = {"success": False, "error": str(e)}

        if not execution_result.get("success"):
            # Don't persist manager_decision on a failed execution — the
            # manager's "confirm" intent didn't actually take effect, and
            # locking the row to 'confirmed' here (with no successful
            # execution behind it) would permanently block retrying once
            # whatever failed (e.g. Google Calendar not configured) is fixed.
            return {
                "recommendation_id": recommendation_id,
                "manager_decision": None,
                "execution_result": execution_result,
            }

    update_sql = """
        UPDATE task_reassignment_recommendations
        SET manager_decision = %s, executed_at = %s
        WHERE recommendation_id = %s
        RETURNING *
    """
    now = datetime.now() if body.decision == "confirmed" else None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(update_sql, (body.decision, now, recommendation_id))
                row = dict(cur.fetchone())
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    row["new_start_time"] = row["new_start_time"].isoformat() if row["new_start_time"] else None
    row["new_end_time"] = row["new_end_time"].isoformat() if row["new_end_time"] else None
    row["executed_at"] = row["executed_at"].isoformat() if row["executed_at"] else None
    row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None
    row["execution_result"] = execution_result
    return row
