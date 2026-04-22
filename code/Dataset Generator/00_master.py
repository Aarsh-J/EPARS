"""
00_master.py — Master runner for V3 dataset generation.
Edit row counts here, then run this file.

Run:  python 00_master.py
"""

import subprocess
import sys
import os

# ─── Master Row / Table Counts ────────────────────────────────────────────────
CONFIG = {
    "NUM_EMPLOYEES":     2000,
    "NUM_PROJECTS":      1200,
    "NUM_TEAMS":         2500,
    "NUM_TASKS":         15000,
    "NUM_ASSIGNMENTS":   22000,
    "NUM_SCHEDULE_ROWS": 60000,
    "NUM_WORKLOAD_ROWS": 60000,
    "NUM_BURNOUT_ROWS":  25000,
    "NUM_REVIEWS":       6000,
    "NUM_FEEDBACK":      25000,
    "OUT_DIR": "./output",
}

# ─── Run Order (matches schema dependency chain) ───────────────────────────────
SCRIPTS = [
    "01_employees_projects.py",   # employees + projects (seeds)
    "02_team_formations.py",      # team_formations → backfills projects
    "03_tasks_assignments.py",    # tasks + task_assignments (uses team pools)
    "04_schedules_workload.py",   # schedules + workload_history
    "05_burnout_reviews_feedback.py",  # burnout + reviews + feedback
    "06_backfill.py",             # backfill employees + team_formations
]


def run_script(script_name: str, config: dict):
    env = os.environ.copy()
    for k, v in config.items():
        env[k] = str(v)

    print(f"\n{'─'*60}")
    print(f"  Running: {script_name}")
    print(f"{'─'*60}")

    result = subprocess.run(
        [sys.executable, script_name],
        env=env,
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"\n[ERROR] {script_name} failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def _chk(label: str, bad_count: int, issues: list):
    if bad_count == 0:
        print(f"  OK  {label}")
    else:
        print(f"  XX  {label}: {bad_count} violations")
        issues.append(f"{label}: {bad_count}")


def validate(out_dir: str):
    import pandas as pd

    print(f"\n{'='*60}")
    print("  POST-GENERATION VALIDATION")
    print(f"{'='*60}")

    files = {
        "employees":           "employees.csv",
        "projects":            "projects.csv",
        "team_formations":     "team_formations.csv",
        "tasks":               "tasks.csv",
        "task_assignments":    "task_assignments.csv",
        "schedules":           "schedules.csv",
        "workload_history":    "workload_history.csv",
        "burnout_indicators":  "burnout_indicators.csv",
        "performance_reviews": "performance_reviews.csv",
        "feedback":            "feedback.csv",
    }

    dfs, issues = {}, []
    print("\n── Row Counts ──")
    for name, fname in files.items():
        path = os.path.join(out_dir, fname)
        if os.path.exists(path):
            dfs[name] = pd.read_csv(path)
            print(f"  {name:<25} {len(dfs[name]):>6} rows")
        else:
            print(f"  {name:<25} MISSING")

    if len(dfs) < len(files):
        print("\n  Some files missing — skipping detailed checks.")
        return

    emp_ids  = set(dfs["employees"]["employee_id"])
    proj_ids = set(dfs["projects"]["project_id"])
    task_ids = set(dfs["tasks"]["task_id"])
    team_ids = set(dfs["team_formations"]["team_id"])

    print("\n── Referential Integrity ──")

    ta = dfs["task_assignments"]
    _chk("task_assignments.employee_id",
         (~ta["employee_id"].isin(emp_ids)).sum(), issues)
    _chk("task_assignments.project_id",
         (~ta["project_id"].isin(proj_ids)).sum(), issues)
    _chk("task_assignments.task_id",
         (~ta["task_id"].isin(task_ids)).sum(), issues)

    tf = dfs["team_formations"]
    _chk("team_formations.project_id",
         (~tf["project_id"].isin(proj_ids)).sum(), issues)
    _chk("team_formations.team_lead_id",
         (~tf["team_lead_id"].isin(emp_ids)).sum(), issues)
    all_members = [m.strip() for cell in tf["member_ids"].dropna()
                   for m in str(cell).split(",") if m.strip()]
    _chk("team_formations.member_ids",
         sum(1 for m in all_members if m not in emp_ids), issues)

    _chk("projects.project_manager_id",
         (~dfs["projects"]["project_manager_id"].isin(emp_ids)).sum(), issues)
    _chk("tasks.project_id",
         (~dfs["tasks"]["project_id"].isin(proj_ids)).sum(), issues)

    pr = dfs["performance_reviews"]
    _chk("performance_reviews.employee_id",
         (~pr["employee_id"].isin(emp_ids)).sum(), issues)
    _chk("performance_reviews.reviewer_id",
         (~pr["reviewer_id"].isin(emp_ids)).sum(), issues)

    for tname in ["burnout_indicators", "workload_history", "schedules"]:
        _chk(f"{tname}.employee_id",
             (~dfs[tname]["employee_id"].isin(emp_ids)).sum(), issues)

    print("\n── Temporal Integrity ──")
    hire_map = dict(zip(dfs["employees"]["employee_id"],
                        pd.to_datetime(dfs["employees"]["hire_date"])))
    checks = [
        ("task_assignments",    "employee_id", "assignment_date"),
        ("workload_history",    "employee_id", "date"),
        ("schedules",           "employee_id", "date"),
        ("burnout_indicators",  "employee_id", "assessment_date"),
        ("performance_reviews", "employee_id", "review_period_start"),
    ]
    for tname, id_col, date_col in checks:
        df = dfs[tname].copy()
        df["_hire"] = pd.to_datetime(df[id_col].map(hire_map), errors="coerce")
        df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
        _chk(f"{tname}.{date_col} >= hire_date",
             (df["_date"] < df["_hire"]).sum(), issues)

    print("\n── Logic Checks ──")

    emp = dfs["employees"]
    burn_by_stress = emp.groupby("stress_level")["burnout_risk_score"].mean()
    if "Low" in burn_by_stress and "High" in burn_by_stress:
        ok = burn_by_stress["Low"] < burn_by_stress["High"]
        _chk("employees: Low stress < High stress burnout", 0 if ok else 1, issues)

    p = dfs["projects"]
    _chk("projects: Completed => pct=100",
         ((p["current_status"] == "Completed") & (p["completion_percentage"] < 100)).sum(), issues)
    _chk("projects: Planning => pct=0",
         ((p["current_status"] == "Planning") & (p["completion_percentage"] > 0)).sum(), issues)

    t = dfs["tasks"]
    _chk("tasks: Completed => pct=100",
         ((t["status"] == "Completed") & (t["completion_percentage"] < 100)).sum(), issues)

    if "performance_rating" in pr.columns:
        order = ["Needs Improvement", "Meets Expectations", "Exceeds Expectations", "Outstanding"]
        avgs  = pr.groupby("performance_rating")["overall_performance_score"].mean()
        vals  = [avgs.get(r, 0) for r in order if r in avgs]
        ok    = all(vals[i] <= vals[i+1] for i in range(len(vals)-1))
        _chk("performance_reviews: rating monotone with score", 0 if ok else 1, issues)

    tf_done = tf[tf["actual_performance_score"].notna()]
    if len(tf_done) > 10:
        corr = tf_done["predicted_success_rate"].corr(tf_done["actual_performance_score"])
        ok   = corr >= 0.30
        label = f"team_formations: pred/actual corr={corr:.2f} (need >=0.30)"
        print(f"  {'OK' if ok else 'XX'}  {label}")
        if not ok:
            issues.append(label)

    print(f"\n── Summary ──")
    if issues:
        print(f"  {len(issues)} issue(s) found — see above")
    else:
        print(f"  All checks passed — dataset looks clean!")


if __name__ == "__main__":
    out_dir = CONFIG["OUT_DIR"]
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("  V3 DATASET GENERATION — MASTER RUNNER")
    print("=" * 60)
    print(f"\n  Output directory : {os.path.abspath(out_dir)}")
    for k, v in CONFIG.items():
        if k != "OUT_DIR":
            print(f"  {k:<24}: {v}")

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    for script in SCRIPTS:
        run_script(script, CONFIG)

    validate(out_dir)

    print(f"\n{'='*60}")
    print("  DONE")
    print(f"{'='*60}\n")
