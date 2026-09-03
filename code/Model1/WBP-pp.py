import pandas as pd
import numpy as np
import json
import warnings

warnings.filterwarnings("ignore")
np.random.seed(42)

# ==============================
# LOAD DATA
# ==============================
emp = pd.read_csv("employees.csv")
emp.columns = emp.columns.str.lower().str.strip()

bi = pd.read_csv("burnout_indicators.csv")
bi.columns = bi.columns.str.lower().str.strip()

# latest burnout record per employee
bi_latest = (
    bi.sort_values("assessment_date")
      .groupby("employee_id", as_index=False)
      .last()
)

# ==============================
# SAFE MIN-MAX SCALING
# ==============================
def minmax_scale(series):
    denom = (series.max() - series.min())
    if denom == 0:
        return pd.Series(50, index=series.index)
    return (series - series.min()) / denom * 100

# ==============================
# TARGET CREATION (NO LEAKAGE)
# ==============================
exhaust  = minmax_scale(bi_latest["emotional_exhaustion_score"])
deperson = minmax_scale(bi_latest["depersonalization_score"])
reduced  = minmax_scale(bi_latest["reduced_accomplishment_score"])

# Maslach core burnout
core = exhaust * 0.40 + deperson * 0.30 + reduced * 0.30

# Behavioral signals
behavior = (
    bi_latest["late_hours_frequency"] * 5 +
    bi_latest["vacation_days_unused"] * 1.5 +
    (10 - bi_latest["job_satisfaction"]) * 4 +
    bi_latest["role_ambiguity"] * 3
)

behavior = minmax_scale(behavior)

# Final target (with small noise for realism)
bi_latest["burnout_risk_computed"] = np.clip(
    core * 0.75 + behavior * 0.25 +
    np.random.normal(0, 2, len(bi_latest)),  # reduced noise
    0, 100
)

# ==============================
# MERGE
# ==============================
df = emp.merge(bi_latest, on="employee_id", how="inner")

# ==============================
# FEATURE ENGINEERING
# ==============================

PROJECT_HOURS = 15  # justified constant

cap = df["weekly_capacity_hours"].replace(0, 40)

remaining_cap = np.maximum(
    0,
    (cap - df["current_project_count"] * PROJECT_HOURS) / cap
) * 100

df["workload_compatibility_score"] = np.clip(
    remaining_cap + np.random.normal(0, 2, len(df)),
    0, 100
)

# availability score
df["is_available"] = df["is_available"].astype(str).str.strip().str.lower()

is_avail = df["is_available"].isin(["true", "1", "yes"])

avail_base = np.where(
    (~is_avail) | (df["current_project_count"] >= 3), 25,
    np.where(df["current_project_count"] == 0, 95,
    np.where(df["current_project_count"] == 1, 78, 58))
)

df["availability_score"] = np.clip(
    avail_base + np.random.normal(0, 2, len(df)),
    0, 100
)

# ==============================
# FINAL FEATURES
# ==============================
FEATURES = [
    "technical_proficiency_score",
    "domain_expertise_score",
    "leadership_potential",
    "workload_compatibility_score",
    "availability_score",
    "collaboration_score",
    "years_of_experience",
    "historical_performance_score",
    "average_task_completion_rate",
    "successful_project_count",
    "late_hours_frequency",
    "vacation_days_unused",
    "job_satisfaction",
    "role_ambiguity",
    "job_control",
]

TARGET = "burnout_risk_computed"

df_final = df[FEATURES + [TARGET]].dropna()

# ==============================
# THRESHOLDS (FROM FULL DATA)
# ==============================
p50 = df_final[TARGET].quantile(0.50)
p80 = df_final[TARGET].quantile(0.80)

thresholds = {
    "low_max": float(p50),
    "medium_max": float(p80)
}

# ==============================
# SAVE
# ==============================
df_final.to_csv("processed.csv", index=False)

with open("selected_features.json", "w") as f:
    json.dump(FEATURES, f, indent=2)

with open("thresholds.json", "w") as f:
    json.dump(thresholds, f, indent=2)

print("✅ processed.csv saved")
print("✅ selected_features.json saved")
print("✅ thresholds.json saved")