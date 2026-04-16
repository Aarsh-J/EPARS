"""
00_master.py — Master runner. Edit row counts here, then run this file.
Calls all generation scripts in correct dependency order and prints
a final validation summary.

Run:  python 00_master.py
"""

import subprocess
import sys
import os

# ─── Master Row / Table Counts ────────────────────────────────────────────────
# Edit these to scale the dataset up or down.

CONFIG = {
    # Core tables
    "NUM_EMPLOYEES":        100,
    "NUM_PROJECTS":         80,

    # Team formations (run before tasks/assignments)
    "NUM_TEAMS":            100,

    # Tasks & assignments
    "NUM_TASKS":            800,
    "NUM_ASSIGNMENTS":      500,

    # Time-series
    "NUM_WORKLOAD_ROWS":    1000,   # sampled daily records total
    "NUM_SCHEDULE_ROWS":    6000,
    "NUM_BURNOUT_ROWS":     2000,

    # Reviews & feedback
    "NUM_REVIEWS":          400,
    "NUM_FEEDBACK":         2000,

    # Output directory (relative to this file's location)
    "OUT_DIR": "./output",
}

# ─── Run Order ────────────────────────────────────────────────────────────────
SCRIPTS = [
    "01_employees_projects.py",
    "04a_team_formations.py",
    "02_tasks_assignments.py",
    "03a_workload.py",
    "03b_schedules_burnout.py",
    "04b_reviews_feedback.py",
    "01b_backfill.py",
]

# ─── Helpers ──────────────────────────────────────────────────────────────────
def run_script(script_name: str, config: dict):
    """Run a generation script, passing CONFIG as env variables."""
    env = os.environ.copy()
    for k, v in config.items():
        env[k] = str(v)

    print(f"\n{'─'*60}")
    print(f"  Running: {script_name}")
    print(f"{'─'*60}")

    result = subprocess.run(
        [sys.executable, script_name],
        env=env,
        capture_output=False,   # stream output directly
    )
    if result.returncode != 0:
        print(f"\n[ERROR] {script_name} failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def validate(out_dir: str):
    """Post-generation validation: FK checks, row counts, key correlations."""
    import pandas as pd
    import numpy as np

    print(f"\n{'='*60}")
    print("  POST-GENERATION VALIDATION")
    print(f"{'='*60}")

    files = {
        "employees":          "employees.csv",
        "projects":           "projects.csv",
        "team_formations":    "team_formations.csv",
        "tasks":              "tasks.csv",
        "task_assignments":   "task_assignments.csv",
        "workload_history":   "workload_history.csv",
        "schedules":          "schedules.csv",
        "burnout_indicators": "burnout_indicators.csv",
        "performance_reviews":"performance_reviews.csv",
        "feedback":           "feedback.csv",
    }

    dfs = {}
    print("\n── Row Counts ──")
    for name, fname in files.items():
        path = os.path.join(out_dir, fname)
        if os.path.exists(path):
            dfs[name] = pd.read_csv(path)
            print(f"  {name:<22} {len(dfs[name]):>6} rows")
        else:
            print(f"  {name:<22} MISSING")

    emp_ids  = set(dfs["employees"]["employee_id"])
    proj_ids = set(dfs["projects"]["project_id"])
    task_ids = set(dfs["tasks"]["task_id"])
    team_ids = set(dfs["team_formations"]["team_id"])

    issues = []

    print("\n── Referential Integrity ──")

    # task_assignments → employees, projects, tasks
    ta = dfs["task_assignments"]
    bad = (~ta["employee_id"].isin(emp_ids)).sum()
    _chk("task_assignments.employee_id", bad, issues)
    bad = (~ta["project_id"].isin(proj_ids)).sum()
    _chk("task_assignments.project_id", bad, issues)
    bad = (~ta["task_id"].isin(task_ids)).sum()
    _chk("task_assignments.task_id", bad, issues)

    # team_formations → projects, employees (lead + members)
    tf = dfs["team_formations"]
    bad = (~tf["project_id"].isin(proj_ids)).sum()
    _chk("team_formations.project_id", bad, issues)
    bad = (~tf["team_lead_id"].isin(emp_ids)).sum()
    _chk("team_formations.team_lead_id", bad, issues)
    all_members = [m.strip() for cell in tf["member_ids"].dropna()
                   for m in str(cell).split(",") if m.strip()]
    bad = sum(1 for m in all_members if m not in emp_ids)
    _chk("team_formations.member_ids (all)", bad, issues)

    # projects → employees (manager)
    bad = (~dfs["projects"]["project_manager_id"].isin(emp_ids)).sum()
    _chk("projects.project_manager_id", bad, issues)

    # tasks → projects
    bad = (~dfs["tasks"]["project_id"].isin(proj_ids)).sum()
    _chk("tasks.project_id", bad, issues)

    # performance_reviews → employees
    pr = dfs["performance_reviews"]
    bad = (~pr["employee_id"].isin(emp_ids)).sum()
    _chk("performance_reviews.employee_id", bad, issues)
    bad = (~pr["reviewer_id"].isin(emp_ids)).sum()
    _chk("performance_reviews.reviewer_id", bad, issues)

    # burnout/workload/schedules → employees
    for tname in ["burnout_indicators", "workload_history", "schedules"]:
        bad = (~dfs[tname]["employee_id"].isin(emp_ids)).sum()
        _chk(f"{tname}.employee_id", bad, issues)

    print("\n── Temporal Integrity (hire_date violations) ──")
    hire_map = dict(zip(dfs["employees"]["employee_id"],
                        pd.to_datetime(dfs["employees"]["hire_date"])))

    date_checks = [
        ("task_assignments", "employee_id", "assignment_date"),
        ("workload_history",  "employee_id", "date"),
        ("schedules",         "employee_id", "date"),
        ("burnout_indicators","employee_id", "assessment_date"),
        ("performance_reviews","employee_id","review_period_start"),
    ]
    for tname, id_col, date_col in date_checks:
        df = dfs[tname].copy()
        df["_hire"] = pd.to_datetime(df[id_col].map(hire_map), errors="coerce")
        df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
        bad = (df["_date"] < df["_hire"]).sum()
        _chk(f"{tname}.{date_col} >= hire_date", bad, issues)

    print("\n── Logic Checks ──")

    # Employees: stress vs burnout direction
    emp = dfs["employees"]
    burn_by_stress = emp.groupby("stress_level")["burnout_risk_score"].mean()
    if "Low" in burn_by_stress and "High" in burn_by_stress:
        ok = burn_by_stress["Low"] < burn_by_stress["High"]
        _chk("employees: Low stress < High stress burnout", 0 if ok else 1, issues)

    # Projects: completion % vs status
    p = dfs["projects"]
    bad = ((p["current_status"] == "Completed") & (p["completion_percentage"] < 100)).sum()
    _chk("projects: Completed => pct=100", bad, issues)
    bad = ((p["current_status"] == "Planning") & (p["completion_percentage"] > 0)).sum()
    _chk("projects: Planning => pct=0", bad, issues)

    # Tasks: Completed => pct=100
    t = dfs["tasks"]
    bad = ((t["status"] == "Completed") & (t["completion_percentage"] < 100)).sum()
    _chk("tasks: Completed => pct=100", bad, issues)

    # Team formations: predicted vs actual correlation
    tf_done = tf[tf["actual_performance_score"].notna()]
    if len(tf_done) > 10:
        corr = tf_done["predicted_success_rate"].corr(tf_done["actual_performance_score"])
        ok = corr >= 0.35
        label = f"team_formations: predicted/actual corr={corr:.2f} (need >=0.35)"
        if ok:
            print(f"  ✓  {label}")
        else:
            print(f"  ✗  {label}")
            issues.append(label)

    # Skill coverage
    proj_skills = dict(zip(p["project_id"], p["required_skills"]))
    emp_skill_map = {}
    for _, row in emp.iterrows():
        skills = set()
        for col in ["primary_skills", "secondary_skills"]:
            if pd.notna(row.get(col)):
                skills.update(s.strip() for s in str(row[col]).split(","))
        emp_skill_map[row["employee_id"]] = skills

    coverages = []
    for _, row in tf.iterrows():
        req = {s.strip() for s in str(proj_skills.get(row["project_id"], "")).split(",") if s.strip()}
        members = [m.strip() for m in str(row["member_ids"]).split(",") if m.strip()]
        members.append(row["team_lead_id"])
        covered = set()
        for m in members:
            covered |= emp_skill_map.get(m, set()) & req
        if req:
            coverages.append(len(covered) / len(req) * 100)
    avg_cov = sum(coverages) / len(coverages) if coverages else 0
    ok = avg_cov >= 70
    label = f"team_formations: avg skill coverage={avg_cov:.1f}% (need >=70%)"
    print(f"  {'✓' if ok else '✗'}  {label}")
    if not ok:
        issues.append(label)

    # Performance rating monotone
    if "performance_rating" in pr.columns:
        order = ["Needs Improvement", "Meets Expectations", "Exceeds Expectations", "Outstanding"]
        avgs = pr.groupby("performance_rating")["overall_performance_score"].mean()
        vals = [avgs.get(r, 0) for r in order if r in avgs]
        ok = all(vals[i] <= vals[i+1] for i in range(len(vals)-1))
        _chk("performance_reviews: rating monotone with score", 0 if ok else 1, issues)

    print(f"\n── Summary ──")
    if issues:
        print(f"  ✗  {len(issues)} issue(s) found — review above")
    else:
        print(f"  ✓  All checks passed — dataset looks clean!")


def _chk(label: str, bad_count: int, issues: list):
    if bad_count == 0:
        print(f"  ✓  {label}")
    else:
        print(f"  ✗  {label}: {bad_count} violations")
        issues.append(f"{label}: {bad_count} violations")


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    out_dir = CONFIG["OUT_DIR"]
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("  DATASET GENERATION — MASTER RUNNER")
    print("=" * 60)
    print(f"\n  Output directory : {os.path.abspath(out_dir)}")
    print(f"  Employees        : {CONFIG['NUM_EMPLOYEES']}")
    print(f"  Projects         : {CONFIG['NUM_PROJECTS']}")
    print(f"  Teams            : {CONFIG['NUM_TEAMS']}")
    print(f"  Tasks            : {CONFIG['NUM_TASKS']}")
    print(f"  Assignments      : {CONFIG['NUM_ASSIGNMENTS']}")
    print(f"  Workload rows    : {CONFIG['NUM_WORKLOAD_ROWS']}")
    print(f"  Schedule rows    : {CONFIG['NUM_SCHEDULE_ROWS']}")
    print(f"  Burnout rows     : {CONFIG['NUM_BURNOUT_ROWS']}")
    print(f"  Reviews          : {CONFIG['NUM_REVIEWS']}")
    print(f"  Feedback         : {CONFIG['NUM_FEEDBACK']}")

    # Change to script directory so relative imports work
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    for script in SCRIPTS:
        run_script(script, CONFIG)

    validate(out_dir)

    print(f"\n{'='*60}")
    print("  DONE")
    print(f"{'='*60}\n")
