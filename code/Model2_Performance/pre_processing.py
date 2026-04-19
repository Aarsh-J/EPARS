# ===============================================================
# preprocessing.py
# FINAL VERSION (Feedback Table Removed)
# Uses:
# 1. performance_reviews.csv
# 2. employees.csv
# 3. workload_history.csv
# ===============================================================

import os
import pickle
import warnings
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

# ===============================================================
# SETTINGS
# ===============================================================

DATA_DIR = "../dataset"
OUT_DIR = "."
TARGET = "overall_performance_score"

os.makedirs(OUT_DIR, exist_ok=True)

print("=" * 70)
print("PREPROCESSING STARTED (NO FEEDBACK DATA)")
print("=" * 70)

# ===============================================================
# LOAD FILES
# ===============================================================

perf_df = pd.read_csv(os.path.join(DATA_DIR, "performance_reviews.csv"))
emp_df  = pd.read_csv(os.path.join(DATA_DIR, "employees.csv"))
wh_df   = pd.read_csv(os.path.join(DATA_DIR, "workload_history.csv"))

print("Loaded:")
print("1. performance_reviews.csv")
print("2. employees.csv")
print("3. workload_history.csv")

# ===============================================================
# AGGREGATE WORKLOAD HISTORY
# ===============================================================

wh_num_cols = wh_df.select_dtypes(include=np.number).columns.tolist()
wh_num_cols = [c for c in wh_num_cols if c != "employee_id"]

wh_agg = wh_df.groupby("employee_id")[wh_num_cols].mean().reset_index()

# ===============================================================
# MERGE TABLES
# ===============================================================

df = perf_df.merge(emp_df, on="employee_id", how="left")
df = df.merge(wh_agg, on="employee_id", how="left")

print("\nMerged Shape:", df.shape)

# ===============================================================
# ENCODE CATEGORICAL COLUMNS
# ===============================================================

encoders = {}

cat_cols = df.select_dtypes(include="object").columns.tolist()

for col in cat_cols:
    le = LabelEncoder()
    df[col] = df[col].astype(str)
    df[col] = le.fit_transform(df[col])
    encoders[col] = le

# ===============================================================
# HANDLE MISSING VALUES
# ===============================================================

num_cols = df.select_dtypes(include=np.number).columns
df[num_cols] = df[num_cols].fillna(df[num_cols].median())

# ===============================================================
# SAVE OUTPUTS
# ===============================================================

df.to_csv("processed_data.csv", index=False)

with open("encoders.pkl", "wb") as f:
    pickle.dump(encoders, f)

print("\nSaved Files:")
print("processed_data.csv")
print("encoders.pkl")

print("\nRows :", len(df))
print("Cols :", len(df.columns))

print("=" * 70)
print("PREPROCESSING COMPLETE")
print("=" * 70)