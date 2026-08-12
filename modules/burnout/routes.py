"""
modules/burnout/routes.py
==============================
Mirrors modules/performance/routes.py: a selector-table endpoint plus a
POST /analyse endpoint, but for burnout_gbm_model.pkl instead of the
performance Ridge model. See ml_models/README.md for the model's known
live-data gap (many top-weighted features aren't in the production DB) —
that's why every /analyse response carries a `confidence` + `imputed_features`
so the frontend can flag low-confidence predictions instead of presenting
them as authoritative.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import get_connection
from tools import get_employee_profile, _to_list

from ..ml.predict import predict_burnout

router = APIRouter(prefix="/burnout", tags=["burnout"])

_CLASS_COLOR = {
    "Low": "#065f46",
    "Moderate": "#92400e",
    "High": "#c2410c",
    "Critical": "#991b1b",
}


@router.get("/employees")
def list_employees():
    """
    Latest stored burnout assessment per employee, for the selector table.
    """
    sql = """
        SELECT DISTINCT ON (e.employee_id)
            e.employee_id,
            e.department,
            e.role,
            e.seniority_level AS seniority,
            bi.overall_burnout_risk AS stored_score,
            bi.burnout_category AS stored_category
        FROM employees e
        LEFT JOIN burnout_indicators bi ON bi.employee_id = e.employee_id
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
        prediction = predict_burnout(body.employee_id)
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
        "predicted_class": prediction["predicted_class"],
        "predicted_class_color": _CLASS_COLOR.get(prediction["predicted_class"], "#64748b"),
        "predicted_probabilities": prediction["predicted_probabilities"],
        "class_thresholds": prediction["class_thresholds"],
        "confidence": prediction["confidence"],
        "imputed_features": prediction["imputed_features"],
        "missing_top_features": prediction["missing_top_features"],
        "real_feature_count": prediction["real_feature_count"],
        "total_feature_count": prediction["total_feature_count"],
        "top_contributing_features": prediction["top_contributing_features"],
        "stored_score": round(float(stored["stored_score"]), 1) if stored and stored["stored_score"] is not None else None,
        "stored_category": stored["stored_category"] if stored else None,
    }
