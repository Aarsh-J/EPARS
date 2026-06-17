# ===============================================================
# predict.py
# Input: employee_id
# Reads RAW files from dataset folder
# Output: json file of
#-----------------------------------------------------------------
# IMPORTANT NOTE: 
# In terminal run as: python Model2_Performance/pem_predict.py
# # ===============================================================

import os
import json
import pickle
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ===============================================================
# SETTINGS
# ===============================================================

DATA_DIR = "../dataset"
MODEL_FILE = "Model2_Performance/ridge_model.pkl"
SCALER_FILE = "Model2_Performance/scaler.pkl"

# ===============================================================
# LOAD MODEL
# ===============================================================

model = pickle.load(open(MODEL_FILE, "rb"))
scaler = pickle.load(open(SCALER_FILE, "rb"))

# ===============================================================
# LOAD RAW TABLES
# ===============================================================

perf_df = pd.read_csv(os.path.join(DATA_DIR, "performance_reviews.csv"))
emp_df  = pd.read_csv(os.path.join(DATA_DIR, "employees.csv"))

# ===============================================================
# HELPERS
# ===============================================================

def score_to_rating(score):
    if score >= 90:
        return "Exceptional"
    elif score >= 75:
        return "Exceeds Expectations"
    elif score >= 60:
        return "Meets Expectations"
    elif score >= 45:
        return "Below Expectations"
    else:
        return "Unsatisfactory"


def val(row, colname, default=0):
    if colname in row.index:
        x = row[colname]
        if pd.isna(x):
            return default
        return x
    return default

# ===============================================================
# MAIN FUNCTION
# ===============================================================

def predict_performance(employee_id):

    # FETCH EMPLOYEE ROWS

    emp_perf = perf_df[perf_df["employee_id"] == employee_id]

    if emp_perf.empty:
        return {"error": "Employee ID not found"}

    # latest record for prediction
    perf_row = emp_perf.iloc[-1]

    # employee table row
    emp_row = emp_df[emp_df["employee_id"] == employee_id]

    if not emp_row.empty:
        emp_row = emp_row.iloc[0]
    else:
        emp_row = pd.Series(dtype="object")

    # BUILD FEATURES
 
    prev_scores = emp_perf["overall_performance_score"].tail(5).tolist()

    tc = val(perf_row, "technical_competence_score")
    dk = val(perf_row, "domain_knowledge_score")
    ps = val(perf_row, "problem_solving_score")

    cs = val(perf_row, "communication_score")
    cb = val(perf_row, "collaboration_score")
    ls = val(perf_row, "leadership_score")
    ins = val(perf_row, "initiative_score")
    tm = val(perf_row, "time_management_score")

    q = val(perf_row, "quality_of_work_score")
    p = val(perf_row, "productivity_score")
    hist = val(emp_row, "historical_performance_score")

    # FORMULA SCORE
    technical_cluster = (tc + dk + ps) / 3 * 10
    behavioral_cluster = (cs + cb + ls + ins + tm) / 5 * 10
    quality_norm = q * 10
    productivity_norm = p * 10
    formula_score = (
        technical_cluster * 0.30 +
        behavioral_cluster * 0.25 +
        quality_norm * 0.20 +
        productivity_norm * 0.25
    )

    # -----------------------------------------------------------
    # MODEL INPUT
    # -----------------------------------------------------------

    X = pd.DataFrame([{
        "formula_score": formula_score,
        "historical_performance_score": hist
    }])

    X_scaled = scaler.transform(X)

    pred = float(model.predict(X_scaled)[0])
    pred = max(0, min(100, pred))

    actual = val(perf_row, "overall_performance_score", None)

    result = {
        "employee_id": employee_id,
        "predicted_score": round(pred, 2),
        "rating": score_to_rating(pred),
        "previous_performance_scores":
            [round(float(x), 2) for x in prev_scores]

    }

#    if actual is not None:
#        result["actual_score"] = round(float(actual), 2)

    file_name = f"{employee_id}.json"
    with open(file_name, "w") as f:
        json.dump(result, f, indent=4)
    return result

# ===============================================================
# QUICK TEST
# ===============================================================

if __name__ == "__main__":

    sample_emp_id = input("Enter Employee ID: ")
    output = predict_performance(sample_emp_id)

    print(json.dumps(output, indent=2))
