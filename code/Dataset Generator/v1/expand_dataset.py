# =============================================================================
# CAPSTONE PROJECT – Full Dataset Expansion (All 10 CSVs)
# =============================================================================
# PURPOSE : Generate expanded synthetic versions of all 10 CSVs that:
#           1. Preserve original statistical distributions
#           2. Maintain referential integrity (foreign keys stay valid)
#           3. Reach ML-ideal row counts for model training
#
# INPUT   : employee_performance_dataset_fixed/ (original CSVs)
# OUTPUT  : employee_performance_dataset_expanded/ (expanded CSVs)
#
# RUN     : python expand_dataset.py
# =============================================================================

import os
import warnings
import numpy as np
import pandas as pd
from datetime import timedelta

warnings.filterwarnings("ignore")
np.random.seed(42)

# ── Paths ─────────────────────────────────────────────────────────────────────
SRC_DIR = "employee_performance_dataset_fixed"
DST_DIR = "employee_performance_dataset_expanded"
os.makedirs(DST_DIR, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def sample_like(series, n, lo=None, hi=None):
    """Sample n values from a normal dist fitted to series, clipped to [lo, hi]."""
    mu, sigma = series.mean(), series.std()
    vals = np.random.normal(mu, sigma, n)
    if lo is not None:
        vals = np.clip(vals, lo, hi)
    return vals

def sample_cat(series, n):
    """Sample n values preserving the original category distribution."""
    counts = series.value_counts(normalize=True)
    return np.random.choice(counts.index, size=n, p=counts.values)

def next_id(prefix, start, n, pad):
    """Generate sequential IDs like EMP201, EMP202 ..."""
    return [f"{prefix}{str(i).zfill(pad)}" for i in range(start, start + n)]

def jitter_date(date_series, max_days=365):
    """Shift dates randomly by up to max_days in either direction."""
    dates = pd.to_datetime(date_series)
    deltas = np.random.randint(-max_days, max_days, len(dates))
    return [(d + timedelta(days=int(delta))).strftime("%Y-%m-%d")
            for d, delta in zip(dates, deltas)]

def expand_by_sampling(df, n_new):
    """
    Generate n_new rows by sampling with replacement from df,
    then jittering numeric columns slightly to avoid exact duplicates.
    """
    sampled = df.sample(n=n_new, replace=True, random_state=42).copy()
    sampled = sampled.reset_index(drop=True)

    # Jitter numeric columns slightly (±5% noise)
    num_cols = sampled.select_dtypes(include=[np.number]).columns
    for col in num_cols:
        noise = np.random.normal(0, sampled[col].std() * 0.05, n_new)
        sampled[col] = sampled[col] + noise
        # Clip to original min/max
        sampled[col] = sampled[col].clip(df[col].min(), df[col].max())

    return sampled


print("=" * 65)
print("CAPSTONE – FULL DATASET EXPANSION")
print("=" * 65)


# =============================================================================
# 1. EMPLOYEES  (200 → 1000)
# =============================================================================

print("\n[1/10] Expanding employees.csv ...")

emp_orig = pd.read_csv(os.path.join(SRC_DIR, "employees.csv"))
N_NEW_EMP = 1800   # 200 + 1800 = 2000 total

new_emp = expand_by_sampling(emp_orig, N_NEW_EMP)

# Assign new unique employee IDs
new_emp["employee_id"] = next_id("EMP", 201, N_NEW_EMP, 4)

# Regenerate emails to match new IDs
new_emp["email"] = [
    f"emp{i}@company.com" for i in range(201, 201 + N_NEW_EMP)
]

# Jitter hire_date
new_emp["hire_date"] = jitter_date(new_emp["hire_date"], max_days=500)
new_emp["last_updated"] = jitter_date(new_emp["last_updated"], max_days=100)
new_emp["created_at"]   = new_emp["hire_date"]

emp_expanded = pd.concat([emp_orig, new_emp], ignore_index=True)
emp_expanded.to_csv(os.path.join(DST_DIR, "employees.csv"), index=False)
print(f"  employees : {len(emp_orig)} → {len(emp_expanded)} rows")

# All valid employee IDs (used by other tables)
ALL_EMP_IDS = emp_expanded["employee_id"].tolist()


# =============================================================================
# 2. PROJECTS  (100 → 500)
# =============================================================================

print("[2/10] Expanding projects.csv ...")

proj_orig = pd.read_csv(os.path.join(SRC_DIR, "projects.csv"))
N_NEW_PROJ = 900   # 100 + 900 = 1000 total

new_proj = expand_by_sampling(proj_orig, N_NEW_PROJ)
new_proj["project_id"]         = next_id("PRJ", 101, N_NEW_PROJ, 3)
new_proj["project_manager_id"] = np.random.choice(ALL_EMP_IDS, N_NEW_PROJ)
new_proj["start_date"]         = jitter_date(new_proj["start_date"], 300)
new_proj["planned_end_date"]   = jitter_date(new_proj["planned_end_date"], 300)
new_proj["created_at"]         = new_proj["start_date"]
new_proj["last_updated"]       = jitter_date(new_proj["last_updated"], 100)

proj_expanded = pd.concat([proj_orig, new_proj], ignore_index=True)
proj_expanded.to_csv(os.path.join(DST_DIR, "projects.csv"), index=False)
print(f"  projects  : {len(proj_orig)} → {len(proj_expanded)} rows")

ALL_PROJ_IDS = proj_expanded["project_id"].tolist()


# =============================================================================
# 3. TASKS  (2000 → 10000)
# =============================================================================

print("[3/10] Expanding tasks.csv ...")

tasks_orig = pd.read_csv(os.path.join(SRC_DIR, "tasks.csv"))
N_NEW_TASKS = 18000  # 2000 + 18000 = 20000 total

new_tasks = expand_by_sampling(tasks_orig, N_NEW_TASKS)
new_tasks["task_id"]    = next_id("TSK", 2001, N_NEW_TASKS, 4)
new_tasks["project_id"] = np.random.choice(ALL_PROJ_IDS, N_NEW_TASKS)
new_tasks["assigned_to"]= np.random.choice(ALL_EMP_IDS, N_NEW_TASKS)
new_tasks["start_date"] = jitter_date(new_tasks["start_date"], 300)
new_tasks["due_date"]   = jitter_date(new_tasks["due_date"], 300)
new_tasks["created_at"] = new_tasks["start_date"]
new_tasks["last_updated"]= jitter_date(new_tasks["last_updated"], 100)
# Clear dependency columns to avoid broken references
new_tasks["dependent_task_ids"] = np.nan
new_tasks["blocking_task_ids"]  = np.nan
new_tasks["related_tasks"]      = np.nan
new_tasks["parent_task_id"]     = np.nan

tasks_expanded = pd.concat([tasks_orig, new_tasks], ignore_index=True)
tasks_expanded.to_csv(os.path.join(DST_DIR, "tasks.csv"), index=False)
print(f"  tasks     : {len(tasks_orig)} → {len(tasks_expanded)} rows")

ALL_TASK_IDS = tasks_expanded["task_id"].tolist()


# =============================================================================
# 4. TASK ASSIGNMENTS  (3000 → 15000)
# =============================================================================

print("[4/10] Expanding task_assignments.csv ...")

ta_orig = pd.read_csv(os.path.join(SRC_DIR, "task_assignments.csv"))
N_NEW_TA = 27000   # 3000 + 27000 = 30000 total

new_ta = expand_by_sampling(ta_orig, N_NEW_TA)
new_ta["assignment_id"] = next_id("ASG", 3001, N_NEW_TA, 4)
new_ta["task_id"]       = np.random.choice(ALL_TASK_IDS, N_NEW_TA)
new_ta["employee_id"]   = np.random.choice(ALL_EMP_IDS, N_NEW_TA)
new_ta["project_id"]    = np.random.choice(ALL_PROJ_IDS, N_NEW_TA)
new_ta["assigned_by"]   = np.random.choice(ALL_EMP_IDS, N_NEW_TA)
new_ta["assignment_date"]= jitter_date(new_ta["assignment_date"], 300)
new_ta["created_at"]    = new_ta["assignment_date"]
new_ta["last_updated"]  = jitter_date(new_ta["last_updated"], 100)

ta_expanded = pd.concat([ta_orig, new_ta], ignore_index=True)
ta_expanded.to_csv(os.path.join(DST_DIR, "task_assignments.csv"), index=False)
print(f"  task_assignments : {len(ta_orig)} → {len(ta_expanded)} rows")


# =============================================================================
# 5. TEAM FORMATIONS  (150 → 750)
# =============================================================================

print("[5/10] Expanding team_formations.csv ...")

tf_orig = pd.read_csv(os.path.join(SRC_DIR, "team_formations.csv"))
N_NEW_TF = 1350   # 150 + 1350 = 1500 total

new_tf = expand_by_sampling(tf_orig, N_NEW_TF)
new_tf["team_id"]       = next_id("TEAM", 151, N_NEW_TF, 3)
new_tf["project_id"]    = np.random.choice(ALL_PROJ_IDS, N_NEW_TF)
new_tf["team_lead_id"]  = np.random.choice(ALL_EMP_IDS, N_NEW_TF)
new_tf["formation_date"]= jitter_date(new_tf["formation_date"], 300)
new_tf["created_at"]    = new_tf["formation_date"]
new_tf["last_updated"]  = jitter_date(new_tf["last_updated"], 100)

tf_expanded = pd.concat([tf_orig, new_tf], ignore_index=True)
tf_expanded.to_csv(os.path.join(DST_DIR, "team_formations.csv"), index=False)
print(f"  team_formations : {len(tf_orig)} → {len(tf_expanded)} rows")


# =============================================================================
# 6. PERFORMANCE REVIEWS  (400 → 2000)
# =============================================================================

print("[6/10] Expanding performance_reviews.csv ...")

perf_orig = pd.read_csv(os.path.join(SRC_DIR, "performance_reviews.csv"))
N_NEW_PERF = 3600  # 400 + 3600 = 4000 total

# Rating bands with score ranges
RATING_BANDS = {
    "Exceptional":          (90, 100),
    "Exceeds Expectations": (75, 89.9),
    "Meets Expectations":   (60, 74.9),
    "Below Expectations":   (45, 59.9),
    "Unsatisfactory":       (31, 44.9),
}
rating_probs = perf_orig["performance_rating"].value_counts(normalize=True)
review_probs = perf_orig["review_type"].value_counts(normalize=True)

rows = []
last_rev = int(perf_orig["review_id"].str.extract(r"(\d+)")[0].astype(int).max())

for i in range(N_NEW_PERF):
    emp_id  = np.random.choice(ALL_EMP_IDS)
    rating  = np.random.choice(rating_probs.index, p=rating_probs.values)
    rev_type= np.random.choice(review_probs.index, p=review_probs.values)
    lo, hi  = RATING_BANDS[rating]
    norm_score = round(float(np.random.uniform(lo, hi)), 2)

    # Boost = how far above/below average this employee is
    boost = (norm_score - 65) / 35

    def skill(mu, sigma, lo=2.0, hi=10.0):
        return round(float(np.clip(np.random.normal(
            mu + boost * sigma * 0.6, sigma * 0.8), lo, hi)), 2)

    rev_date     = pd.to_datetime("2023-01-01") + timedelta(
        days=int(np.random.randint(0, 900)))
    period_end   = rev_date
    period_start = rev_date - timedelta(days=90)

    rows.append({
        "review_id":                    f"REV{last_rev + i + 1:03d}",
        "employee_id":                  emp_id,
        "reviewer_id":                  np.random.choice(ALL_EMP_IDS),
        "review_period_start":          period_start.strftime("%Y-%m-%d"),
        "review_period_end":            period_end.strftime("%Y-%m-%d"),
        "review_date":                  rev_date.strftime("%Y-%m-%d"),
        "review_type":                  rev_type,
        "overall_performance_score":    round(norm_score * 0.1, 2),
        "normalized_performance_score": norm_score,
        "technical_competence_score":   skill(5.78, 1.48),
        "domain_knowledge_score":       skill(5.50, 1.66),
        "problem_solving_score":        skill(7.19, 1.25, 3.3),
        "innovation_score":             skill(6.74, 1.43),
        "quality_of_work_score":        skill(7.53, 1.13, 4.2),
        "productivity_score":           skill(7.28, 1.30, 3.2),
        "communication_score":          skill(6.99, 1.53, 3.1),
        "collaboration_score":          skill(6.99, 1.60, 2.1),
        "leadership_score":             skill(5.34, 1.86),
        "initiative_score":             skill(6.70, 1.38),
        "adaptability_score":           skill(6.99, 1.29, 2.9),
        "reliability_score":            skill(7.46, 1.26, 3.2),
        "time_management_score":        skill(7.02, 1.29, 2.9),
        "tasks_completed":              int(np.clip(np.random.normal(84 + boost*20, 30), 20, 150)),
        "projects_completed":           int(np.clip(np.random.normal(4.5 + boost*1.5, 2), 1, 8)),
        "average_task_quality":         skill(7.45, 1.17, 4.4),
        "on_time_delivery_rate":        round(float(np.clip(np.random.normal(82 + boost*10, 10), 52, 100)), 2),
        "productivity_vs_peers":        round(float(np.random.normal(-1.2 + boost*12, 14)), 2),
        "total_hours_worked":           round(float(np.clip(np.random.normal(993, 150), 600, 1500)), 1),
        "overtime_hours":               round(float(np.clip(np.random.normal(32 + boost*5, 20), 0, 113)), 1),
        "utilization_rate":             round(float(np.clip(np.random.normal(85 + boost*6, 9), 56, 110)), 2),
        "self_assessment_score":        skill(7.26, 1.31, 3.5),
        "performance_rating":           rating,
        "promotion_recommended":        norm_score >= 80,
        "salary_increase_recommended":  norm_score >= 70,
        "training_recommended":         norm_score < 65,
        "follow_up_required":           norm_score < 50,
        "created_at":                   rev_date.strftime("%Y-%m-%d"),
        "last_updated":                 rev_date.strftime("%Y-%m-%d"),
    })

new_perf = pd.DataFrame(rows)
# Align columns to original
for col in perf_orig.columns:
    if col not in new_perf.columns:
        new_perf[col] = np.nan
new_perf = new_perf[perf_orig.columns]

perf_expanded = pd.concat([perf_orig, new_perf], ignore_index=True)
perf_expanded.to_csv(os.path.join(DST_DIR, "performance_reviews.csv"), index=False)
print(f"  performance_reviews : {len(perf_orig)} → {len(perf_expanded)} rows")


# =============================================================================
# 7. BURNOUT INDICATORS  (2000 → 10000)
# =============================================================================

print("[7/10] Expanding burnout_indicators.csv ...")

bi_orig = pd.read_csv(os.path.join(SRC_DIR, "burnout_indicators.csv"))
N_NEW_BI = 18000   # 2000 + 18000 = 20000 total

new_bi = expand_by_sampling(bi_orig, N_NEW_BI)
new_bi["indicator_id"] = next_id("BI", 2001, N_NEW_BI, 4)
new_bi["employee_id"]  = np.random.choice(ALL_EMP_IDS, N_NEW_BI)
new_bi["assessment_date"]     = jitter_date(new_bi["assessment_date"], 300)
new_bi["last_intervention_date"] = jitter_date(
    new_bi["last_intervention_date"].fillna("2024-01-01"), 300)
new_bi["created_at"]   = new_bi["assessment_date"]
new_bi["last_updated"] = jitter_date(new_bi["last_updated"], 100)

bi_expanded = pd.concat([bi_orig, new_bi], ignore_index=True)
bi_expanded.to_csv(os.path.join(DST_DIR, "burnout_indicators.csv"), index=False)
print(f"  burnout_indicators : {len(bi_orig)} → {len(bi_expanded)} rows")


# =============================================================================
# 8. FEEDBACK  (2000 → 10000)
# =============================================================================

print("[8/10] Expanding feedback.csv ...")

fb_orig = pd.read_csv(os.path.join(SRC_DIR, "feedback.csv"))
N_NEW_FB = 18000   # 2000 + 18000 = 20000 total

new_fb = expand_by_sampling(fb_orig, N_NEW_FB)
new_fb["feedback_id"]   = next_id("FDB", 2001, N_NEW_FB, 4)
new_fb["provider_id"]   = np.random.choice(ALL_EMP_IDS, N_NEW_FB)
new_fb["recipient_id"]  = np.random.choice(ALL_EMP_IDS, N_NEW_FB)
new_fb["related_task_id"]   = np.random.choice(ALL_TASK_IDS, N_NEW_FB)
new_fb["related_project_id"]= np.random.choice(ALL_PROJ_IDS, N_NEW_FB)
new_fb["feedback_date"] = jitter_date(new_fb["feedback_date"], 300)
new_fb["created_at"]    = new_fb["feedback_date"]
new_fb["last_updated"]  = jitter_date(new_fb["last_updated"], 100)

fb_expanded = pd.concat([fb_orig, new_fb], ignore_index=True)
fb_expanded.to_csv(os.path.join(DST_DIR, "feedback.csv"), index=False)
print(f"  feedback : {len(fb_orig)} → {len(fb_expanded)} rows")


# =============================================================================
# 9. SCHEDULES  (6000 → 30000)
# =============================================================================

print("[9/10] Expanding schedules.csv ...")

sc_orig = pd.read_csv(os.path.join(SRC_DIR, "schedules.csv"))
N_NEW_SC = 54000   # 6000 + 54000 = 60000 total

new_sc = expand_by_sampling(sc_orig, N_NEW_SC)
new_sc["schedule_id"] = next_id("SCH", 6001, N_NEW_SC, 5)
new_sc["employee_id"] = np.random.choice(ALL_EMP_IDS, N_NEW_SC)
new_sc["date"]        = jitter_date(new_sc["date"], 300)
new_sc["created_at"]  = new_sc["date"]
new_sc["last_updated"]= jitter_date(new_sc["last_updated"], 100)

sc_expanded = pd.concat([sc_orig, new_sc], ignore_index=True)
sc_expanded.to_csv(os.path.join(DST_DIR, "schedules.csv"), index=False)
print(f"  schedules : {len(sc_orig)} → {len(sc_expanded)} rows")


# =============================================================================
# 10. WORKLOAD HISTORY  (11369 → ~55000)
# =============================================================================

print("[10/10] Expanding workload_history.csv ...")

wh_orig = pd.read_csv(os.path.join(SRC_DIR, "workload_history.csv"))
N_NEW_WH = 99000   # 11369 + 99000 = ~110000 total

new_wh = expand_by_sampling(wh_orig, N_NEW_WH)
last_wh = int(wh_orig["record_id"].str.extract(r"(\d+)")[0].astype(int).max())
new_wh["record_id"]   = next_id("WH", last_wh + 1, N_NEW_WH, 6)
new_wh["employee_id"] = np.random.choice(ALL_EMP_IDS, N_NEW_WH)
new_wh["date"]        = jitter_date(new_wh["date"], 500)
new_wh["created_at"]  = new_wh["date"] if "created_at" in new_wh.columns else new_wh["date"]

wh_expanded = pd.concat([wh_orig, new_wh], ignore_index=True)
wh_expanded.to_csv(os.path.join(DST_DIR, "workload_history.csv"), index=False)
print(f"  workload_history : {len(wh_orig)} → {len(wh_expanded)} rows")


# =============================================================================
# SUMMARY
# =============================================================================

print("\n" + "=" * 65)
print("EXPANSION COMPLETE")
print("=" * 65)
originals = {
    "employees": 200, "projects": 100, "tasks": 2000,
    "task_assignments": 3000, "team_formations": 150,
    "performance_reviews": 400, "burnout_indicators": 2000,
    "feedback": 2000, "schedules": 6000, "workload_history": 11369,
}
expanded = {
    "employees": 2000, "projects": 1000, "tasks": 20000,
    "task_assignments": 30000, "team_formations": 1500,
    "performance_reviews": 4000, "burnout_indicators": 20000,
    "feedback": 20000, "schedules": 60000, "workload_history": 110369,
}
print(f"  {'File':<25} {'Original':>10} {'Expanded':>10} {'Multiplier':>12}")
print(f"  {'-'*57}")
for name in originals:
    mult = expanded[name] / originals[name]
    print(f"  {name:<25} {originals[name]:>10} {expanded[name]:>10} {mult:>11.1f}x")

print(f"\n  All files saved to : ./{DST_DIR}/")
print(f"\n  Next step : update DATA_DIR in preprocessing.py to point")
print(f"  to '{DST_DIR}' and re-run the full pipeline.")
print("=" * 65)
