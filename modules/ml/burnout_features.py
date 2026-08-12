"""
modules/ml/burnout_features.py
===================================
Assembles a 135-feature vector for burnout_gbm_model.pkl from real DB data.
Anything not sourceable live is left as None/NaN — the pipeline's own
SimpleImputer(strategy="median") fills it at predict time, which is the
correct behavior for this model (unlike the Ridge performance model, which
has no built-in imputer). Aggregation/encoding logic recovered verbatim from
code/workload_preprocessing.py (commit 9126e7e1) — see ml_models/README.md.
"""

import statistics

from db import get_connection

from .feature_specs import (
    BURNOUT_EMP_COLS_LIVE,
    BURNOUT_EMP_STRESS_MAP,
    BURNOUT_FEATURES,
    BURNOUT_PROD_MAP,
    BURNOUT_SENIORITY_MAP,
    BURNOUT_SYMPTOM_COLS_LIVE,
    BURNOUT_TREND_MAP,
)

_LIVE_SYMPTOM_SQL_COLS = [c for c in BURNOUT_SYMPTOM_COLS_LIVE if c not in ("mental_supp", "trend_enc")]


def _fetch_burnout_rows(employee_id: str) -> list[dict]:
    sql = f"""
        SELECT {", ".join(_LIVE_SYMPTOM_SQL_COLS)}, mental_health_support_needed, burnout_trend
        FROM burnout_indicators
        WHERE employee_id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            return [dict(r) for r in cur.fetchall()]


def _fetch_employee_row(employee_id: str) -> dict:
    cols = [c for c in BURNOUT_EMP_COLS_LIVE if c != "is_available"]
    sql = f"SELECT {', '.join(cols)}, is_available, seniority_level, productivity_trend, stress_level FROM employees WHERE employee_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
    return dict(row) if row else {}


def _fetch_task_agg(employee_id: str) -> dict:
    sql = """
        SELECT
            AVG(skill_match_score)            AS ta_skill_match,
            AVG(overall_suitability_score)     AS ta_suitability,
            AVG(workload_compatibility_score)  AS ta_wl_compat,
            SUM(reassignment_count)            AS ta_reassign,
            AVG(CASE WHEN completion_status = 'Completed' THEN 1.0 ELSE 0.0 END) AS ta_complete
        FROM task_assignments
        WHERE employee_id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
    return dict(row) if row else {}


def assemble_burnout_features(employee_id: str):
    """
    Returns (vector: dict[str, float | None], imputed: list[str]).
    `vector` has exactly BURNOUT_FEATURES as keys; None means "left for the
    model's own SimpleImputer to fill with its training median".
    """
    rows = _fetch_burnout_rows(employee_id)
    emp = _fetch_employee_row(employee_id)
    ta = _fetch_task_agg(employee_id)

    vector: dict[str, float | None] = {name: None for name in BURNOUT_FEATURES}

    if rows:
        for col in _LIVE_SYMPTOM_SQL_COLS:
            values = [float(r[col]) for r in rows if r.get(col) is not None]
            if values:
                vector[f"{col}_mean"] = statistics.mean(values)
                vector[f"{col}_max"] = max(values)
                vector[f"{col}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0

        mental_vals = [float(bool(r["mental_health_support_needed"])) for r in rows if r.get("mental_health_support_needed") is not None]
        if mental_vals:
            vector["mental_supp_mean"] = statistics.mean(mental_vals)
            vector["mental_supp_max"] = max(mental_vals)
            vector["mental_supp_std"] = statistics.stdev(mental_vals) if len(mental_vals) > 1 else 0.0

        trend_vals = [BURNOUT_TREND_MAP[r["burnout_trend"]] for r in rows if r.get("burnout_trend") in BURNOUT_TREND_MAP]
        if trend_vals:
            vector["trend_enc_mean"] = statistics.mean(trend_vals)
            vector["trend_enc_max"] = max(trend_vals)
            vector["trend_enc_std"] = statistics.stdev(trend_vals) if len(trend_vals) > 1 else 0.0

    for name in BURNOUT_EMP_COLS_LIVE:
        if name == "is_available":
            continue
        if emp.get(name) is not None:
            vector[name] = float(emp[name])
    if emp.get("is_available") is not None:
        vector["is_available"] = float(bool(emp["is_available"]))
    if emp.get("seniority_level") in BURNOUT_SENIORITY_MAP:
        vector["seniority_enc"] = float(BURNOUT_SENIORITY_MAP[emp["seniority_level"]])
    if emp.get("productivity_trend") in BURNOUT_PROD_MAP:
        vector["prod_enc"] = float(BURNOUT_PROD_MAP[emp["productivity_trend"]])
    if emp.get("stress_level") in BURNOUT_EMP_STRESS_MAP:
        vector["stress_emp_enc"] = float(BURNOUT_EMP_STRESS_MAP[emp["stress_level"]])

    for name in ("ta_skill_match", "ta_suitability", "ta_wl_compat", "ta_reassign", "ta_complete"):
        if ta.get(name) is not None:
            vector[name] = float(ta[name])

    return vector, [name for name, val in vector.items() if val is None]
