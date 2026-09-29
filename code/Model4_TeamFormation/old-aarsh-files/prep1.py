# --- Code Cell 1 ---
# ============================================================
# Cell 1 — Imports & Setup
# ============================================================

import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.preprocessing import MultiLabelBinarizer
import os

import warnings
warnings.filterwarnings('ignore')

pd.set_option('display.max_columns', None)

# Path configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(SCRIPT_DIR, "../../dataset")

print("Libraries loaded ✅")


# --- Code Cell 2 ---
# ============================================================
# Cell 2 — Load All Datasets
# ============================================================

emp  = pd.read_csv(f"{INPUT_DIR}/employees.csv")
tf   = pd.read_csv(f"{INPUT_DIR}/team_formations.csv")
pr   = pd.read_csv(f"{INPUT_DIR}/performance_reviews.csv")
# ta   = pd.read_csv(f"{INPUT_DIR}/task_assignments.csv")
wh   = pd.read_csv(f"{INPUT_DIR}/workload_history.csv")
proj = pd.read_csv(f"{INPUT_DIR}/projects.csv")
# tasks = pd.read_csv(f"{INPUT_DIR}/tasks.csv")

print("Shapes:")
print(f"  employees        : {emp.shape}")
print(f"  team_formations  : {tf.shape}")
print(f"  performance_rev  : {pr.shape}")
# print(f"  task_assignments : {ta.shape}")  # FIXED (was error)
print(f"  workload_history : {wh.shape}")
print(f"  projects         : {proj.shape}")


# --- Code Cell 3 ---
# ============================================================
# Cell 3 — Clean employees.csv
# ============================================================

# --- Datetime parsing ---
emp['hire_date']    = pd.to_datetime(emp['hire_date'], format='mixed')
emp['last_updated'] = pd.to_datetime(emp['last_updated'], format='mixed')
emp['created_at']   = pd.to_datetime(emp['created_at'], format='mixed')

# Derive tenure in days from today
emp['tenure_days'] = (pd.Timestamp.today() - emp['hire_date']).dt.days

# --- Boolean fix ---
emp['is_available']                = emp['is_available'].astype(bool)
emp['cross_functional_experience'] = emp['cross_functional_experience'].astype(bool)

print("Employees cleaned ✅")


# --- Code Cell 4 ---
# ============================================================
# Cell 4 — Clean performance_reviews.csv
# ============================================================

pr['review_date'] = pd.to_datetime(pr['review_date'], format='mixed')

# Aggregate metrics per employee
pr_agg = pr.groupby('employee_id').agg({
    'overall_performance_score': ['mean', 'std'],
    'review_id': 'count'
}).reset_index()

pr_agg.columns = ['employee_id', 'rating_mean', 'rating_std', 'review_count']

# Fill NaN std (single review case)
pr_agg['rating_std'] = pr_agg['rating_std'].fillna(0)

print("Performance reviews aggregated ✅")


# --- Code Cell 5 ---
# ============================================================
# Cell 5 — Clean workload_history.csv
# ============================================================

wh['date'] = pd.to_datetime(wh['date'], format='mixed')

# Aggregate workload stats
wh_agg = wh.groupby('employee_id').agg({
    'active_tasks_count': 'mean',
    'total_hours_worked': 'mean'
}).reset_index()

wh_agg.columns = ['employee_id', 'avg_tasks', 'avg_hours']

print("Workload aggregated ✅")


# --- Code Cell 6 ---
# ============================================================
# Cell 6 — Merge All Features
# ============================================================

df = emp.merge(pr_agg, on='employee_id', how='left')
df = df.merge(wh_agg, on='employee_id', how='left')

# Fill missing values
df.fillna(0, inplace=True)

print("Merged feature table shape:", df.shape)


# --- Code Cell 7 ---
# ============================================================
# Cell 7 — Encode Skills (MultiLabel)
# ============================================================

# Assuming skills column is comma-separated
df['skills'] = df['skills'].fillna('')
df['skills_list'] = df['skills'].apply(lambda x: x.split(','))

mlb = MultiLabelBinarizer()
skills_encoded = pd.DataFrame(
    mlb.fit_transform(df['skills_list']),
    columns=mlb.classes_
)

df = pd.concat([df, skills_encoded], axis=1)

print("Skills encoded ✅")


# --- Code Cell 8 ---
# ============================================================
# Cell 8 — Normalize Numerical Features
# ============================================================

scaler = MinMaxScaler()

num_cols = [
    'tenure_days',
    'rating_mean',
    'rating_std',
    'review_count',
    'avg_tasks',
    'avg_hours'
]

df[num_cols] = scaler.fit_transform(df[num_cols])

print("Normalization done ✅")


# --- Code Cell 9 ---
# ============================================================
# Cell 9 — Final Feature Table
# ============================================================

# Drop unused columns
drop_cols = [
    'hire_date',
    'last_updated',
    'created_at',
    'skills',
    'skills_list'
]

df.drop(columns=drop_cols, inplace=True, errors='ignore')

print("Final feature table ready ✅")
print(df.head())


# --- Code Cell 10 ---
# ============================================================
# Cell 10 — Save Feature Table
# ============================================================

df.to_csv('../../dataset/final_feature_table.csv', index=False)

print("Feature table saved ✅")