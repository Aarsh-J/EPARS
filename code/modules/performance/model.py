"""
modules/performance/model.py
Loads the trained Ridge model and runs predictions.
"""

import os
import pickle
import numpy as np
import pandas as pd

# ── Paths — resolve from modules/performance/ to code/ ────────────────────
# __file__ = code/modules/performance/model.py
# dirname(__file__) = code/modules/performance/
# dirname(dirname(__file__)) = code/modules/
# dirname(dirname(dirname(__file__))) = code/
CODE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
EPARS_ROOT = os.path.dirname(CODE_DIR)

# Artifacts are in code/Model2_Performance/
MODEL2_PERF = os.path.join(CODE_DIR, "Model2_Performance")
MODEL_PATH  = os.path.join(MODEL2_PERF, "ridge_model.pkl")
SCALER_PATH = os.path.join(MODEL2_PERF, "scaler.pkl")
DATA_PATH   = os.path.join(MODEL2_PERF, "processed_data.csv")

# Raw CSVs are in EPARS/dataset/ (one level up from code/)
DATASET_DIR = os.path.join(EPARS_ROOT, "dataset")
REVIEWS_PATH    = os.path.join(DATASET_DIR, "performance_reviews.csv")
EMPLOYEES_PATH  = os.path.join(DATASET_DIR, "employees.csv")

# ── Debug: Print paths on import ───────────────────────────────────────────
print(f"[EPARS] CODE_DIR: {CODE_DIR}")
print(f"[EPARS] EPARS_ROOT: {EPARS_ROOT}")
print(f"[EPARS] MODEL2_PERF: {MODEL2_PERF}")
print(f"[EPARS] DATASET_DIR: {DATASET_DIR}")
print()
print(f"[EPARS] Checking artifact paths:")
print(f"  MODEL_PATH exists: {os.path.exists(MODEL_PATH)}")
print(f"  SCALER_PATH exists: {os.path.exists(SCALER_PATH)}")
print(f"  DATA_PATH exists: {os.path.exists(DATA_PATH)}")
print()
print(f"[EPARS] Checking dataset paths:")
print(f"  REVIEWS_PATH exists: {os.path.exists(REVIEWS_PATH)}")
print(f"  EMPLOYEES_PATH exists: {os.path.exists(EMPLOYEES_PATH)}")
print()

# ── Load artifacts once at import time ────────────────────────────────────
model = None
scaler = None
df_proc = None

# Try loading model
try:
    model = pickle.load(open(MODEL_PATH, "rb"))
    print(f"[EPARS] ✓ Model loaded")
except Exception as e:
    print(f"[EPARS] ✗ Error loading model: {e}")
    raise

# Try loading scaler
try:
    scaler = pickle.load(open(SCALER_PATH, "rb"))
    print(f"[EPARS] ✓ Scaler loaded")
except Exception as e:
    print(f"[EPARS] ✗ Error loading scaler: {e}")
    raise

# Try loading processed data
try:
    df_proc = pd.read_csv(DATA_PATH)
    print(f"[EPARS] ✓ Processed data loaded")
except Exception as e:
    print(f"[EPARS] ✗ Error loading processed data: {e}")
    raise

# Load original unencoded data for display
try:
    df_reviews  = pd.read_csv(REVIEWS_PATH)
    df_employees = pd.read_csv(EMPLOYEES_PATH)
    df_display  = df_reviews.merge(
        df_employees[["employee_id","first_name","last_name","department","role","seniority_level"]],
        on="employee_id", how="left"
    )
    print(f"[EPARS] ✓ Loaded {len(df_display)} review records")
except Exception as e:
    print(f"[EPARS] ✗ Error loading data: {e}")
    raise

# ── Rating thresholds ──────────────────────────────────────────────────────
def score_to_rating(score: float) -> dict:
    if score >= 85:
        return {"label": "Exceptional",          "color": "#059669"}
    elif score >= 70:
        return {"label": "Exceeds Expectations", "color": "#0284c7"}
    elif score >= 55:
        return {"label": "Meets Expectations",   "color": "#d97706"}
    elif score >= 40:
        return {"label": "Below Expectations",   "color": "#dc2626"}
    else:
        return {"label": "Unsatisfactory",       "color": "#7c3aed"}


def get_employee_list() -> list[dict]:
    """
    Return a list of unique employees with their latest review scores
    for the employee selector dropdown.
    """
    latest = (
        df_display.sort_values("review_date", ascending=False)
        .drop_duplicates(subset="employee_id")
    )
    employees = []
    for _, row in latest.iterrows():
        employees.append({
            "employee_id":  row["employee_id"],
            "name":         f"{row['first_name']} {row['last_name']}",
            "department":   row["department"],
            "role":         row["role"],
            "seniority":    row["seniority_level"],
            "score":        round(float(row["overall_performance_score"]), 1),
        })
    return sorted(employees, key=lambda x: x["name"])


def get_employee_reviews(employee_id: str) -> list[dict]:
    """Return all review records for one employee, newest first."""
    rows = df_display[df_display["employee_id"] == employee_id].sort_values(
        "review_date", ascending=False
    )
    reviews = []
    for _, row in rows.iterrows():
        reviews.append({
            "review_id":     row.get("review_id", ""),
            "review_date":   row.get("review_date", ""),
            "review_type":   row.get("review_type", ""),
            "overall_score": round(float(row["overall_performance_score"]), 1),
        })
    return reviews


def predict_from_row(row: pd.Series) -> dict:
    """
    Run the Ridge model on one review row and return a full result dict.
    """
    # ── Helper: safely get value from row with optional fallback ──────────
    def g(col_name, fallback_col_name=None, default=0):
        """
        Get value from row. If not found, try fallback column.
        If still not found, return default.
        Handles NaN values.
        """
        # Try primary column
        if col_name in row.index:
            val = row[col_name]
            if pd.notna(val):
                return float(val)
        
        # Try fallback column
        if fallback_col_name and fallback_col_name in row.index:
            val = row[fallback_col_name]
            if pd.notna(val):
                return float(val)
        
        # Return default
        return default

    # ── Build formula features (mirrors train.py) ──────────────────────────
    technical_cluster = (
        g("technical_competence_score") +
        g("domain_knowledge_score") +
        g("problem_solving_score")
    ) / 3 * 10

    behavioral_cluster = (
        g("communication_score") +
        g("collaboration_score") +  # Try collaboration_score, fall back to _x or _y variants
        g("leadership_score") +
        g("initiative_score") +
        g("time_management_score")
    ) / 5 * 10

    quality_norm = g("quality_of_work_score") * 10

    # Handle productivity_score variants
    productivity_raw = g("productivity_score", "productivity_score_x", 0)
    if productivity_raw == 0:
        productivity_raw = g("productivity_score_x", "productivity_score_y", 0)
    productivity_norm = productivity_raw * 10

    formula_score = (
        technical_cluster  * 0.30 +
        behavioral_cluster * 0.25 +
        quality_norm       * 0.20 +
        productivity_norm  * 0.25
    )

    hist_score = g("historical_performance_score")

    # Predict
    X = np.array([[formula_score, hist_score]])
    X_scaled = scaler.transform(X)
    predicted = float(np.clip(model.predict(X_scaled)[0], 0, 100))
    rating = score_to_rating(predicted)

    return {
        "predicted_score":   round(predicted, 1),
        "rating_label":      rating["label"],
        "rating_color":      rating["color"],
        "formula_score":     round(formula_score, 1),
        "historical_score":  round(hist_score, 1),
        "breakdown": {
            "technical":    round(technical_cluster, 1),
            "behavioral":   round(behavioral_cluster, 1),
            "quality":      round(quality_norm, 1),
            "productivity": round(productivity_norm, 1),
        },
        "sub_scores": {
            "technical_competence": g("technical_competence_score"),
            "domain_knowledge":     g("domain_knowledge_score"),
            "problem_solving":      g("problem_solving_score"),
            "quality_of_work":      g("quality_of_work_score"),
            "productivity":         productivity_raw,
            "communication":        g("communication_score"),
            "collaboration":        g("collaboration_score"),
            "leadership":           g("leadership_score"),
            "initiative":           g("initiative_score"),
            "time_management":      g("time_management_score"),
        },
        "extras": {
            "on_time_delivery":    round(g("on_time_delivery_rate"), 1),
            "task_completion":     round(g("average_task_completion_rate"), 1),
            "burnout_risk":        round(g("burnout_risk_score"), 1),
            "promotion_recommended": bool(g("promotion_recommended")),
        }
    }


def analyse_employee(employee_id: str, review_id: str = None) -> dict:
    """
    Main entry point called by the Flask route.
    Returns full analysis for one employee review.
    """
    try:
        rows = df_display[df_display["employee_id"] == employee_id]
        if rows.empty:
            return {"error": f"Employee {employee_id} not found."}

        # Use specified review or latest
        if review_id:
            row = rows[rows["review_id"] == review_id]
            if row.empty:
                row = rows.sort_values("review_date", ascending=False).iloc[0]
            else:
                row = row.iloc[0]
        else:
            row = rows.sort_values("review_date", ascending=False).iloc[0]

        # Run prediction
        result = predict_from_row(row)

        # Build employee info
        result["employee"] = {
            "employee_id": employee_id,
            "name":        f"{row.get('first_name', 'Unknown')} {row.get('last_name', 'Employee')}",
            "department":  row.get("department", "N/A"),
            "role":        row.get("role", "N/A"),
            "seniority":   row.get("seniority_level", "N/A"),
            "review_date": row.get("review_date", ""),
            "review_type": row.get("review_type", ""),
        }

        result["all_reviews"] = get_employee_reviews(employee_id)

        return result
    
    except Exception as e:
        print(f"[EPARS] ERROR in analyse_employee({employee_id}): {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Failed to analyse employee: {str(e)}"}