# ===============================================================
# pre_processing.py
# Input: performance_reviews.csv, employees.csv
# Output: processed_data.csv
# ===============================================================

import os
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

DATA_DIR = "../dataset"
OUT_FILE = "processed_data.csv"

# ===============================================================
# LOAD FILES
# ===============================================================

perf_df = pd.read_csv(os.path.join(DATA_DIR, "performance_reviews.csv"))
emp_df  = pd.read_csv(os.path.join(DATA_DIR, "employees.csv"))

print("Loaded:")
print("1. performance_reviews.csv")
print("2. employees.csv")

# ===============================================================
# MERGE TABLES
# ===============================================================

df = perf_df.merge(emp_df, on="employee_id", how="left")

# ===============================================================
# REQUIRED FEATURES
# ===============================================================

required_cols = [

    # ID
    "employee_id",

    # Technical Cluster
    "technical_competence_score",
    "domain_knowledge_score",
    "problem_solving_score",

    # Behavioural Cluster
    "communication_score",
    "collaboration_score_y",
    "leadership_score",
    "initiative_score",
    "time_management_score",

    # Quality
    "quality_of_work_score",

    # Productivity 
    "productivity_score",

    # Historical Feature
    "historical_performance_score",

    # Target
    "overall_performance_score"
]

available = [c for c in required_cols if c in df.columns]
df = df[available]

# ===============================================================
# HANDLE MISSING VALUES
# ===============================================================

num_cols = df.select_dtypes(include=np.number).columns
df[num_cols] = df[num_cols].fillna(df[num_cols].median())

# ===============================================================
# SAVE
# ===============================================================

df.to_csv(OUT_FILE, index=False)

print("\nSaved:", OUT_FILE)
print("Rows :", len(df))
print("Cols :", len(df.columns))

print("\nColumns:")
for c in df.columns:
    print("-", c)

print("PREPROCESSING COMPLETE")
