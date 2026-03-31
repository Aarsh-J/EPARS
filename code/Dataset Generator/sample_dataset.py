import pandas as pd
import random
import os

# ── Config ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(SCRIPT_DIR, "../../dataset")  # folder containing your CSVs
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "../../sampled_dataset")  # output folder
N_EMPLOYEES = 100          # anchor: pick 40 employees → pulls related rows from all tables

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Load tables ──────────────────────────────────────────────────────────────
print("Loading tables...")
employees          = pd.read_csv(f"{INPUT_DIR}/employees.csv")
tasks              = pd.read_csv(f"{INPUT_DIR}/tasks.csv")
projects           = pd.read_csv(f"{INPUT_DIR}/projects.csv")
workload_history   = pd.read_csv(f"{INPUT_DIR}/workload_history.csv")
task_assignments   = pd.read_csv(f"{INPUT_DIR}/task_assignments.csv")
team_formations    = pd.read_csv(f"{INPUT_DIR}/team_formations.csv")
performance_reviews= pd.read_csv(f"{INPUT_DIR}/performance_reviews.csv")
schedules          = pd.read_csv(f"{INPUT_DIR}/schedules.csv")
burnout_indicators = pd.read_csv(f"{INPUT_DIR}/burnout_indicators.csv")
feedback           = pd.read_csv(f"{INPUT_DIR}/feedback.csv")

# ── Step 1: Sample anchor employees ──────────────────────────────────────────
sampled_emp = employees.sample(n=N_EMPLOYEES, random_state=43)
emp_ids = set(sampled_emp["employee_id"])
print(f"Anchored on {len(emp_ids)} employees: {sorted(emp_ids)[:5]} ...")

# ── Step 2: Filter each table by employee linkage ────────────────────────────

# Direct employee_id filter
sampled_wl   = workload_history[workload_history["employee_id"].isin(emp_ids)]
sampled_bi   = burnout_indicators[burnout_indicators["employee_id"].isin(emp_ids)]
sampled_pr   = performance_reviews[performance_reviews["employee_id"].isin(emp_ids)]
sampled_sch  = schedules[schedules["employee_id"].isin(emp_ids)]

# task_assignments: get tasks assigned to sampled employees
sampled_ta   = task_assignments[task_assignments["employee_id"].isin(emp_ids)]
task_ids     = set(sampled_ta["task_id"].dropna())
proj_ids_ta  = set(sampled_ta["project_id"].dropna())

# tasks: filter by task_ids found above
sampled_tasks = tasks[tasks["task_id"].isin(task_ids)]

# feedback: provider OR recipient in sampled employees
sampled_fb = feedback[
    feedback["recipient_id"].isin(emp_ids) | feedback["provider_id"].isin(emp_ids)
]

# projects: linked via task_assignments OR manager OR team_member_ids
def members_overlap(member_str, emp_set):
    if pd.isna(member_str):
        return False
    return bool(emp_set & set(str(member_str).split(",")))

proj_mask = (
    projects["project_id"].isin(proj_ids_ta) |
    projects["project_manager_id"].isin(emp_ids) |
    projects["team_member_ids"].apply(lambda x: members_overlap(x, emp_ids))
)
sampled_proj = projects[proj_mask]

# team_formations: teams where member_ids overlap with sampled employees
tf_mask = team_formations["member_ids"].apply(lambda x: members_overlap(x, emp_ids))
sampled_tf = team_formations[tf_mask]

# ── Step 3: Cap large tables to avoid huge outputs ───────────────────────────
def cap(df, n=2000, label=""):
    if len(df) > n:
        df = df.sample(n=n, random_state=43)
        print(f"  {label}: capped to {n} rows")
    else:
        print(f"  {label}: {len(df)} rows")
    return df

print("\nRow counts after filtering:")
sampled_emp    = cap(sampled_emp,    200,  "employees")
sampled_tasks  = cap(sampled_tasks,  500,  "tasks")
sampled_proj   = cap(sampled_proj,   100,  "projects")
sampled_wl     = cap(sampled_wl,     500,  "workload_history")
sampled_ta     = cap(sampled_ta,     500,  "task_assignments")
sampled_tf     = cap(sampled_tf,     150,  "team_formations")
sampled_pr     = cap(sampled_pr,     200,  "performance_reviews")
sampled_sch    = cap(sampled_sch,    500,  "schedules")
sampled_bi     = cap(sampled_bi,     500,  "burnout_indicators")
sampled_fb     = cap(sampled_fb,     500,  "feedback")

# ── Step 4: Save ──────────────────────────────────────────────────────────────
print("\nSaving...")
sampled_emp.to_csv(   f"{OUTPUT_DIR}/employees.csv",           index=False)
sampled_tasks.to_csv( f"{OUTPUT_DIR}/tasks.csv",               index=False)
sampled_proj.to_csv(  f"{OUTPUT_DIR}/projects.csv",            index=False)
sampled_wl.to_csv(    f"{OUTPUT_DIR}/workload_history.csv",    index=False)
sampled_ta.to_csv(    f"{OUTPUT_DIR}/task_assignments.csv",    index=False)
sampled_tf.to_csv(    f"{OUTPUT_DIR}/team_formations.csv",     index=False)
sampled_pr.to_csv(    f"{OUTPUT_DIR}/performance_reviews.csv", index=False)
sampled_sch.to_csv(   f"{OUTPUT_DIR}/schedules.csv",           index=False)
sampled_bi.to_csv(    f"{OUTPUT_DIR}/burnout_indicators.csv",  index=False)
sampled_fb.to_csv(    f"{OUTPUT_DIR}/feedback.csv",            index=False)

print(f"\nDone. Sampled CSVs saved to '{OUTPUT_DIR}/' folder.")
