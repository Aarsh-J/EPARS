# =============================================================================
# Performance Evaluation Model
# =============================================================================
# What were doing: Load data, aggregate, merge, feature engineering
# Input CSV  : performance_reviews.csv, employees.csv, feedback.csv, workload_history.csv
# Outputs in PEM folder  : processed_data.csv, feature_list.pkl, label_encoder_review_type.pkl
# ============================================================================
import os
import pickle
import warnings
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
warnings.filterwarnings("ignore")

DATA_DIR = "dataset"
ARTIFACTS_DIR = "PEM"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

TARGET = "normalized_performance_score"

# LOADING DATA -----------------------------------
perf_df = pd.read_csv(os.path.join(DATA_DIR, "performance_reviews.csv"))
emp_df  = pd.read_csv(os.path.join(DATA_DIR, "employees.csv"))
fb_df   = pd.read_csv(os.path.join(DATA_DIR, "feedback.csv"))
wh_df   = pd.read_csv(os.path.join(DATA_DIR, "workload_history.csv"))
print("LOADED DATA SUCCESSFULLY \n")

# AGGREGATING -----------------------------------
# Each employee has multiple feedback entries — take the mean per employee
fb_agg = fb_df.groupby("recipient_id").agg(
    fb_overall_rating       = ("overall_rating", "mean"),
    fb_quality_rating       = ("quality_rating", "mean"),
    fb_timeliness_rating    = ("timeliness_rating", "mean"),
    fb_collaboration_rating = ("collaboration_rating", "mean"),
    fb_communication_rating = ("communication_rating", "mean"),
    fb_innovation_rating    = ("innovation_rating", "mean"),
    fb_sentiment_score      = ("sentiment_score", "mean"),
    fb_count                = ("feedback_id", "count")
).reset_index().rename(columns={"recipient_id": "employee_id"})
print("Aggregrated the feedback records")

# Each employee has many daily records — take mean per employee
wh_agg = wh_df.groupby("employee_id").agg(
    wh_avg_productivity    = ("productivity_score", "mean"),
    wh_avg_efficiency      = ("efficiency_ratio", "mean"),
    wh_avg_task_completion = ("task_completion_rate", "mean"),
    wh_avg_quality         = ("quality_of_work", "mean"),
    wh_avg_engagement      = ("engagement_score", "mean"),
    wh_avg_stress          = ("stress_score", "mean"),
    wh_avg_cognitive_load  = ("cognitive_load_estimate", "mean"),
    wh_overtime_days       = ("overtime_hours", "sum"),
    wh_avg_focus_hours     = ("focused_work_hours", "mean"),
    wh_avg_burnout_risk    = ("burnout_risk_today", "mean")
).reset_index()
print("Aggregrated workload records\n")

# MERGE AND FEATURE SELECTION -----------------------------------

# Features from performance_reviews
NUMERIC_REVIEW_FEATURES = [
    "technical_competence_score", "domain_knowledge_score",
    "problem_solving_score", "innovation_score", "quality_of_work_score",
    "productivity_score", "communication_score", "collaboration_score",
    "leadership_score", "initiative_score", "adaptability_score",
    "reliability_score", "time_management_score", "tasks_completed",
    "projects_completed", "average_task_quality", "on_time_delivery_rate",
    "productivity_vs_peers", "total_hours_worked", "overtime_hours",
    "utilization_rate", "self_assessment_score"]

# Features from employees
NUMERIC_EMP_FEATURES = [
    "years_of_experience", "technical_proficiency_score",
    "domain_expertise_score", "historical_performance_score",
    "average_task_completion_rate", "work_life_balance_score",
    "burnout_risk_score"]

# Build base dataframe from performance reviews
df = perf_df[["employee_id", TARGET] + NUMERIC_REVIEW_FEATURES + ["review_type"]].copy()
# Merge employee profile features
df = df.merge(emp_df[["employee_id"] + NUMERIC_EMP_FEATURES], on="employee_id", how="left")
# Merge aggregated feedback features
df = df.merge(fb_agg, on="employee_id", how="left")
# Merge aggregated workload features
df = df.merge(wh_agg, on="employee_id", how="left")
print(f"Merged dataset size : {df.shape}")

# ENCODE CATEGORICALS -----------------------------------

# Encode review_type (Annual, Quarterly, etc.) as integers
le = LabelEncoder()
df["review_type_enc"] = le.fit_transform(df["review_type"].astype(str))
#print(f"review_type classes : {list(le.classes_)}")

# Encode ordinal stress_level from employees (Low=0, Medium=1, High=2)
stress_map = {"Low": 0, "Medium": 1, "High": 2}
if "stress_level" in df.columns:
    df["stress_level"] = df["stress_level"].map(stress_map).fillna(1)
    #print("stress_level encoded as ordinal (Low=0, Medium=1, High=2)")

# ENGINEER COMPOSITE FEATURES -----------------------------------

print("\nENGINEERING FEATURES")
# Composite output quality score (task quality + delivery rate + utilization)
df["output_quality_composite"] = (df["average_task_quality"] * 0.4 + df["on_time_delivery_rate"] * 0.3 + df["utilization_rate"] * 0.3)
# Overtime ratio (how much of total hours were overtime)
df["overtime_ratio"] = (df["overtime_hours"] / (df["total_hours_worked"] + 1e-6))
# How far above/below peers this employee is in productivity
df["peer_productivity_gap"] = (df["productivity_vs_peers"] - df["productivity_score"])
# Average of all feedback rating dimensions
fb_rating_cols = ["fb_overall_rating", "fb_quality_rating", "fb_timeliness_rating", "fb_collaboration_rating", "fb_communication_rating", "fb_innovation_rating"]
df["fb_composite_rating"] = df[fb_rating_cols].mean(axis=1)
# Workload health score (high productivity + efficiency, low stress)
df["wh_health_score"] = (df["wh_avg_productivity"] * 0.4 + df["wh_avg_efficiency"] * 20 + (100 - df["wh_avg_stress"]) * 0.2)
print("Created: output_quality_composite, overtime_ratio, peer_productivity_gap, fb_composite_rating, wh_health_score")

# HANDLE MISSING VALUES -----------------------------------

print("\nHANDLING MISSING VALUES")
# Drop rows where target is missing
before = len(df)
df = df.dropna(subset=[TARGET])
print(f"Dropped {before - len(df)} rows with missing target")
# Fill remaining numeric nulls with column median
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
null_counts   = df[numeric_cols].isnull().sum()
filled_cols   = null_counts[null_counts > 0]
if len(filled_cols) > 0:
    print(f"Filling nulls with median in {len(filled_cols)} columns:")
    for col, cnt in filled_cols.items():
        print(f"  {col}: {cnt} nulls")
    df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
else:
    print("No missing values found in numeric columns.")

# SAVE FEATURE LIST -----------------------------------

print("\nFINAL FEATURE LIST")
FB_FEATURES  = list(fb_agg.columns.drop("employee_id")) + ["fb_composite_rating"]
WH_FEATURES  = list(wh_agg.columns.drop("employee_id")) + ["wh_health_score"]
ENGINEERED   = ["output_quality_composite", "overtime_ratio", "peer_productivity_gap"]
ALL_FEATURES = (
    NUMERIC_REVIEW_FEATURES
    + ["review_type_enc"]
    + NUMERIC_EMP_FEATURES
    + FB_FEATURES
    + WH_FEATURES
    + ENGINEERED
)
# Deduplicate and keep only columns that exist in df
seen = set()
ALL_FEATURES = [
    f for f in ALL_FEATURES
    if f in df.columns and not (f in seen or seen.add(f))
]
print(f"Total number of features : {len(ALL_FEATURES)}")

# SAVE PROCESSED CSV OUTPUTS -----------------------------------
print("\nOUTPUTS SAVED")
# Save processed dataset (features + target + employee_id)
processed_path = os.path.join(ARTIFACTS_DIR, "processed_data.csv")
cols_to_save   = ["employee_id"] + ALL_FEATURES + [TARGET]
df[cols_to_save].to_csv(processed_path, index=False)
print(f"[Saved] processed_data.csv  ({df.shape[0]} rows × {len(cols_to_save)} cols)")

# Save feature list
with open(os.path.join(ARTIFACTS_DIR, "feature_list.pkl"), "wb") as f:
    pickle.dump(ALL_FEATURES, f)
print(f"[Saved] feature_list.pkl  ({len(ALL_FEATURES)} features)")

# Save label encoder
with open(os.path.join(ARTIFACTS_DIR, "label_encoder_review_type.pkl"), "wb") as f:
    pickle.dump(le, f)
print(f"[Saved] label_encoder_review_type.pkl")

print(f"\nAll data saved to : ./{ARTIFACTS_DIR}/")