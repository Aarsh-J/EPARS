"""
03_tasks_assignments.py — Generate tasks.csv and task_assignments.csv (V3 schema).
- Task dates clamped within project windows
- Assignment dates clamped >= employee hire_date AND >= project start
- Assignees drawn from the project's team member pool
"""

import os, random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config import (
    TASK_TYPES, TASK_NAMES_BY_TYPE, ROLE_BY_TASK_TYPE,
    TASK_STATUS, TASK_COMPLEXITY, TASK_COMPLEXITY_W,
    RISK_LEVEL, BIZ_IMPACT, SKILLS_BY_TASK_TYPE,
    COMPLEXITY_EST_HOURS, COMPLEXITY_STORY_PTS,
    PRIORITY, PRIORITY_W, SENIORITY_ORDER,
    clamp, rand_date, rand_datetime, pick, normal_score,
)

random.seed(42)
np.random.seed(42)

NUM_TASKS       = int(os.environ.get("NUM_TASKS",       800))
NUM_ASSIGNMENTS = int(os.environ.get("NUM_ASSIGNMENTS", 500))
OUT_DIR         = os.environ.get("OUT_DIR", "./output")

TODAY = date(2025, 4, 16)


# ─── Task score helpers ───────────────────────────────────────────────────────

def calc_task_delay_risk(days_overdue: int, blocking_count: int,
                          is_overdue: bool, priority: str) -> float:
    """
    delay_risk_score:
      = overdue_pressure + blocking_pressure + priority_pressure + Normal(0, 8)
    """
    overdue_pressure   = min(days_overdue * 3.0, 50.0) if is_overdue else 0.0
    blocking_pressure  = min(blocking_count * 12.0, 30.0)
    priority_pressure  = {"Low": 0, "Medium": 5, "High": 15, "Critical": 25}[priority]
    base = overdue_pressure + blocking_pressure + priority_pressure
    return clamp(round(base + np.random.normal(0, 8), 1), 5.0, 95.0)


# ─── TASKS ────────────────────────────────────────────────────────────────────
def generate_tasks(employees_df: pd.DataFrame,
                   projects_df: pd.DataFrame,
                   n: int) -> pd.DataFrame:
    proj_ids = projects_df["project_id"].tolist()

    proj_windows = {}
    for _, row in projects_df.iterrows():
        start   = date.fromisoformat(row["start_date"])
        end_str = row["actual_end_date"] if pd.notna(row.get("actual_end_date")) \
                  else row["planned_end_date"]
        end = date.fromisoformat(str(end_str))
        proj_windows[row["project_id"]] = (start, max(end, start + timedelta(days=7)))

    task_ids = [f"TSK{i:04d}" for i in range(1, n + 1)]
    rows = []

    for i, task_id in enumerate(task_ids):
        task_type  = random.choice(TASK_TYPES)
        proj_id    = random.choice(proj_ids)
        p_start, p_end = proj_windows[proj_id]

        priority   = np.random.choice(PRIORITY, p=PRIORITY_W)
        complexity = np.random.choice(TASK_COMPLEXITY, p=TASK_COMPLEXITY_W)

        est_hours    = round(random.uniform(*COMPLEXITY_EST_HOURS[complexity]), 1)
        story_points = random.choice(COMPLEXITY_STORY_PTS[complexity])

        task_start = rand_date(p_start, p_end - timedelta(days=7))
        buffer     = random.randint(1, 7)
        duration   = int(est_hours / 8) + buffer + 1
        due_date   = min(task_start + timedelta(days=duration), p_end)

        # Status weighted by project status
        proj_status = projects_df.loc[projects_df["project_id"] == proj_id,
                                      "current_status"].values[0]
        if proj_status == "Completed":
            status = np.random.choice(TASK_STATUS, p=[0.02, 0.03, 0.05, 0.88, 0.02])
        elif proj_status == "Planning":
            status = np.random.choice(TASK_STATUS, p=[0.70, 0.15, 0.05, 0.05, 0.05])
        elif proj_status == "Cancelled":
            status = np.random.choice(TASK_STATUS, p=[0.20, 0.10, 0.05, 0.40, 0.25])
        else:
            status = np.random.choice(TASK_STATUS, p=[0.10, 0.35, 0.15, 0.30, 0.10])

        completed = status == "Completed"

        # completion_percentage from status
        if completed:
            comp_pct = 100.0
        elif status == "Not Started":
            comp_pct = 0.0
        elif status == "In Review":
            comp_pct = round(random.uniform(75, 90), 1)
        elif status == "In Progress":
            comp_pct = round(random.uniform(10, 74), 1)
        else:  # Blocked
            comp_pct = round(random.uniform(5, 50), 1)

        actual_comp  = None
        days_overdue = 0
        is_overdue   = False
        if completed:
            actual_comp  = rand_date(task_start, due_date + timedelta(days=15))
            days_overdue = max(0, (actual_comp - due_date).days)
            is_overdue   = days_overdue > 0
        elif status not in ("Not Started",) and TODAY > due_date:
            is_overdue   = True
            days_overdue = (TODAY - due_date).days

        actual_hours = round(est_hours * random.uniform(0.7, 1.40), 1) if completed else None

        assigned_to   = None
        assigned_date = None
        if random.random() > 0.15:
            assigned_to   = random.choice(employees_df["employee_id"].tolist())
            assigned_date = rand_date(p_start, task_start).isoformat()

        skill_pool    = SKILLS_BY_TASK_TYPE[task_type]
        req_skills    = pick(skill_pool, k=random.randint(1, 3))
        req_role      = ROLE_BY_TASK_TYPE[task_type]
        req_seniority = np.random.choice(
            ["Junior", "Mid", "Senior"],
            p=[0.30, 0.45, 0.25]
            if complexity in ("Simple", "Moderate")
            else [0.10, 0.35, 0.55]
        )

        # Dependencies (avoid self-reference)
        dep_ids = block_ids = ""
        if i > 5 and random.random() < 0.28:
            dep_count = random.randint(1, 2)
            dep_ids   = ",".join(random.sample(task_ids[:i], min(dep_count, i)))
        if i < n - 5 and random.random() < 0.18:
            block_ids = ",".join(
                random.sample(task_ids[i+1:min(i+20, n)], min(2, n - i - 1))
            )
        blocking_count = len(block_ids.split(",")) if block_ids else 0

        parent_id = random.choice(task_ids[:max(1, i)]) \
                    if i > 0 and random.random() < 0.15 else None

        # Quality fields (only for completed tasks)
        quality_score   = None
        review_rating   = None
        stkh_sat        = None
        rework_required = False
        rework_count    = 0
        if completed:
            quality_score   = int(clamp(round(np.random.normal(7.5, 1.2)), 1, 10))
            review_rating   = int(clamp(round(np.random.normal(7.8, 1.0)), 1, 10))
            stkh_sat        = int(clamp(round(np.random.normal(7.5, 1.2)), 1, 10))
            rework_required = quality_score < 6
            rework_count    = random.randint(1, 3) if rework_required else 0

        # risk_level from complexity + overdue + blocking
        if complexity in ("Very Complex", "Complex") or is_overdue or blocking_count >= 2:
            risk_lv = np.random.choice(RISK_LEVEL, p=[0.10, 0.40, 0.50])
        elif complexity == "Moderate":
            risk_lv = np.random.choice(RISK_LEVEL, p=[0.30, 0.50, 0.20])
        else:
            risk_lv = np.random.choice(RISK_LEVEL, p=[0.60, 0.30, 0.10])

        delay_risk = calc_task_delay_risk(days_overdue, blocking_count,
                                          is_overdue, priority)

        needs_collab   = random.random() > 0.40
        team_size_req  = random.randint(2, 5) if needs_collab else 1

        created_at   = rand_datetime(p_start - timedelta(days=7), task_start)
        last_updated = rand_datetime(task_start, TODAY)

        rows.append({
            # Core
            "task_id":                  task_id,
            "task_name":                random.choice(TASK_NAMES_BY_TYPE[task_type]) + f" #{i+1}",
            "task_description":         f"{task_type} task — {complexity} complexity.",
            "task_type":                task_type,
            "project_id":               proj_id,
            "priority":                 priority,
            "complexity":               complexity,
            "estimated_hours":          est_hours,
            "actual_hours":             actual_hours,
            "story_points":             story_points,
            # Skills & requirements
            "required_skills":          req_skills,
            "required_role":            req_role,
            "required_seniority":       req_seniority,
            # Assignment
            "assigned_to":              assigned_to,
            "assigned_date":            assigned_date,
            "status":                   status,
            "completion_percentage":    comp_pct,
            # Timeline
            "start_date":               task_start.isoformat(),
            "due_date":                 due_date.isoformat(),
            "actual_completion_date":   actual_comp.isoformat() if actual_comp else None,
            "is_overdue":               is_overdue,
            "days_overdue":             days_overdue,
            "buffer_days":              buffer,
            # Dependencies
            "dependent_task_ids":       dep_ids or None,
            "blocking_task_ids":        block_ids or None,
            "parent_task_id":           parent_id,
            # Quality
            "quality_score":            quality_score,
            "rework_required":          rework_required,
            "rework_count":             rework_count,
            "review_rating":            review_rating,
            "stakeholder_satisfaction": stkh_sat,
            # Risk
            "risk_level":               risk_lv,
            "business_impact":          np.random.choice(BIZ_IMPACT, p=[0.15, 0.35, 0.35, 0.15]),
            "delay_risk_score":         delay_risk,
            # Collaboration
            "requires_collaboration":   needs_collab,
            "team_size_required":       team_size_req,
            # Timestamps
            "created_at":               created_at,
            "last_updated":             last_updated,
        })

    return pd.DataFrame(rows)


# ─── TASK ASSIGNMENTS ─────────────────────────────────────────────────────────

def calc_availability_match(emp_row) -> float:
    """
    availability_match_score:
      is_available + project_count proxy → 0-100
    """
    is_avail  = bool(emp_row.get("is_available", True))
    proj_cnt  = int(emp_row.get("current_project_count", 1))
    if not is_avail or proj_cnt >= 3:
        base = 25.0
    elif proj_cnt == 0:
        base = 95.0
    elif proj_cnt == 1:
        base = 78.0
    else:
        base = 58.0
    return clamp(round(base + np.random.normal(0, 8), 1), 0.0, 100.0)


def calc_workload_compat(emp_row) -> float:
    """
    workload_compatibility_score:
      remaining capacity fraction × 70% + (1 - burnout_norm) × 30%
    """
    capacity    = float(emp_row.get("weekly_capacity_hours", 40))
    proj_cnt    = int(emp_row.get("current_project_count", 1))
    burnout     = float(emp_row.get("burnout_risk_score", 30))
    remaining   = max(0.0, capacity - proj_cnt * 15) / max(capacity, 1) * 100
    antiBurnout = (100 - burnout)
    base = remaining * 0.70 + antiBurnout * 0.30
    return clamp(round(base + np.random.normal(0, 8), 1), 0.0, 100.0)


def calc_experience_match(emp_seniority: str, req_seniority: str) -> float:
    """
    experience_match_score:
      delta = emp_seniority_num - required_seniority_num
      delta >= 0 → 80 + delta × 5 (max 100)
      delta == -1 → 50 (slightly underqualified)
      delta <= -2 → 20 (significantly underqualified)
    """
    emp_num = SENIORITY_ORDER.get(emp_seniority, 2)
    req_map = {"Junior": 1, "Mid": 2, "Senior": 3}
    req_num = req_map.get(req_seniority, 2)
    delta   = emp_num - req_num
    if delta >= 0:
        base = min(80 + delta * 5, 100)
    elif delta == -1:
        base = 50
    else:
        base = 20
    return clamp(round(base + np.random.normal(0, 7), 1), 5.0, 100.0)


def calc_team_compat(emp_row) -> float:
    """
    team_compatibility_score:
      (collaboration_score / 10) × 100 × 65% + random team history proxy × 35%
    """
    collab = float(emp_row.get("collaboration_score", 5))
    collab_norm = (collab / 10) * 100
    history_proxy = normal_pct(70, 15)
    base = collab_norm * 0.65 + history_proxy * 0.35
    return clamp(round(base + np.random.normal(0, 6), 1), 5.0, 100.0)


def generate_task_assignments(employees_df: pd.DataFrame,
                               projects_df: pd.DataFrame,
                               tasks_df: pd.DataFrame,
                               teams_df: pd.DataFrame,
                               n: int) -> pd.DataFrame:
    emp_ids  = employees_df["employee_id"].tolist()
    hire_map = {row["employee_id"]: date.fromisoformat(row["hire_date"])
                for _, row in employees_df.iterrows()}
    proj_start_map = {row["project_id"]: date.fromisoformat(row["start_date"])
                      for _, row in projects_df.iterrows()}

    emp_lookup = employees_df.set_index("employee_id").to_dict("index")

    # Build project → team member pool
    proj_team_pool: dict = {}
    for _, row in teams_df.iterrows():
        pid     = row["project_id"]
        members = [m.strip() for m in str(row["member_ids"]).split(",") if m.strip()]
        members.append(row["team_lead_id"])
        proj_team_pool.setdefault(pid, [])
        proj_team_pool[pid].extend(members)
    proj_team_pool = {pid: list(set(ms)) for pid, ms in proj_team_pool.items()}

    ASSIGN_METHOD  = ["Manual", "AI-Recommended", "Auto-Scheduled"]
    ACCEPT_STATUS  = ["Accepted", "Pending", "Declined", "Renegotiated"]
    ACCEPT_W       = [0.78, 0.14, 0.04, 0.04]
    COMPLETE_STATUS= ["Completed", "In Progress", "Reassigned", "Cancelled"]
    COMPLETE_W     = [0.55, 0.25, 0.12, 0.08]
    REASSIGN_REASON= ["Overload", "Skill Mismatch", "Leave", None]

    tasks_by_proj: dict = {}
    for _, row in tasks_df.iterrows():
        tasks_by_proj.setdefault(row["project_id"], []).append(row)

    rows = []
    used_pairs: set = set()

    # Filter projects that actually have tasks
    valid_projs = [p for p in tasks_by_proj if tasks_by_proj[p]]
    if not valid_projs:
        valid_projs = list(tasks_by_proj.keys())

    for i in range(1, n + 1):
        asgn_id = f"ASG{i:04d}"
        proj_id = random.choice(valid_projs)
        task_row= random.choice(tasks_by_proj[proj_id])
        task_id = task_row["task_id"]

        # Pick employee from team pool, weighted by skill match
        pool = proj_team_pool.get(proj_id, emp_ids)
        if not pool:
            pool = emp_ids

        task_req_skills = {s.strip() for s in
                           str(task_row.get("required_skills", "")).split(",") if s.strip()}

        def _skill_w(eid):
            erow = emp_lookup.get(eid, {})
            e_skills = set()
            for col in ("primary_skills", "secondary_skills"):
                v = erow.get(col, "")
                if v and str(v).lower() not in ("none", "nan", ""):
                    e_skills.update(s.strip() for s in str(v).split(","))
            overlap = len(e_skills & task_req_skills)
            return 1.0 + overlap * 4.0

        pool_w = np.array([_skill_w(e) for e in pool], dtype=float)
        pool_w /= pool_w.sum()
        emp_id  = np.random.choice(pool, p=pool_w)

        pair = (task_id, emp_id)
        if pair in used_pairs:
            emp_id = random.choice(emp_ids)
            pair   = (task_id, emp_id)
        used_pairs.add(pair)

        hire_dt    = hire_map.get(emp_id, date(2015, 1, 1))
        proj_start = proj_start_map.get(proj_id, date(2023, 1, 1))
        earliest   = max(hire_dt, proj_start)
        task_start = date.fromisoformat(str(task_row["start_date"]))
        latest     = max(task_start, earliest + timedelta(days=1))
        assign_date= rand_date(earliest, latest)

        emp_row    = emp_lookup.get(emp_id, {})
        emp_skills = set()
        for col in ("primary_skills", "secondary_skills"):
            v = emp_row.get(col, "")
            if v and str(v).lower() not in ("none", "nan", ""):
                emp_skills.update(s.strip() for s in str(v).split(","))
        skill_match = round(
            len(emp_skills & task_req_skills) / max(len(task_req_skills), 1) * 100, 1
        )

        avail_match  = calc_availability_match(emp_row)
        wl_compat    = calc_workload_compat(emp_row)
        exp_match    = calc_experience_match(
            emp_row.get("seniority_level", "Mid"),
            task_row.get("required_seniority", "Mid"),
        )
        overall_suit = clamp(round(
            skill_match * 0.35 + avail_match * 0.25
            + wl_compat  * 0.20 + exp_match   * 0.20
            + np.random.normal(0, 3), 1
        ), 5.0, 100.0)
        team_compat  = calc_team_compat(emp_row)

        # assignment_satisfaction correlates with skill + workload match (0-10 int)
        raw_sat      = (skill_match + wl_compat) / 20.0
        assignment_sat = int(clamp(round(raw_sat + np.random.normal(0, 1)), 1, 10))

        method   = random.choice(ASSIGN_METHOD)
        senior_pool = employees_df[employees_df["seniority_level"].isin(
            ["Senior", "Lead", "Principal"])]["employee_id"].tolist() or emp_ids
        assigned_by = random.choice([e for e in senior_pool if e != emp_id] or senior_pool)

        accept    = np.random.choice(ACCEPT_STATUS, p=ACCEPT_W)
        accept_dt = (assign_date + timedelta(days=random.randint(0, 2))).isoformat() \
                    if accept == "Accepted" else None

        comp_status = np.random.choice(COMPLETE_STATUS, p=COMPLETE_W)
        completed   = comp_status == "Completed"
        reassign_cnt= random.randint(0, 2) if comp_status == "Reassigned" else 0
        reassign_rsn= random.choice(REASSIGN_REASON) if reassign_cnt > 0 else None

        quality_rat = int(clamp(round(np.random.normal(7.5, 1.2)), 1, 10)) \
                      if completed else None
        on_time     = (random.random() > 0.20) if completed else None

        # efficiency_score = estimated_hours / actual_hours × 100
        est_h  = float(task_row.get("estimated_hours", 8))
        act_h  = float(task_row.get("actual_hours") or (est_h * random.uniform(0.7, 1.4)))
        efficiency_score = clamp(round(est_h / max(act_h, 0.5) * 100, 1), 30.0, 150.0) \
                           if completed else None

        success_val = completed and on_time

        created_at   = f"{assign_date} 09:00:00"
        last_updated = rand_datetime(assign_date + timedelta(days=random.randint(1, 30)))

        rows.append({
            # IDs
            "assignment_id":              asgn_id,
            "task_id":                    task_id,
            "employee_id":                emp_id,
            "project_id":                 proj_id,
            # Details
            "assignment_date":            assign_date.isoformat(),
            "assignment_method":          method,
            "assigned_by":                assigned_by,
            "acceptance_status":          accept,
            "acceptance_date":            accept_dt,
            # Suitability scores
            "skill_match_score":          clamp(skill_match, 0.0, 100.0),
            "availability_match_score":   avail_match,
            "workload_compatibility_score": wl_compat,
            "experience_match_score":     exp_match,
            "overall_suitability_score":  overall_suit,
            "team_compatibility_score":   team_compat,
            # Outcome
            "assignment_success":         success_val,
            "completion_status":          comp_status,
            "reassignment_count":         reassign_cnt,
            "reassignment_reason":        reassign_rsn,
            # Performance
            "quality_rating":             quality_rat,
            "on_time_completion":         on_time,
            "efficiency_score":           efficiency_score,
            # Feedback
            "assignment_satisfaction":    assignment_sat,
            # Timestamps
            "created_at":                 created_at,
            "last_updated":               last_updated,
        })

    return pd.DataFrame(rows)


# ─── Helpers used in calc_team_compat ────────────────────────────────────────
def normal_pct(mu, sigma, lo=0.0, hi=100.0):
    from config import clamp
    return clamp(round(np.random.normal(mu, sigma), 1), lo, hi)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading prior data...")
    emp_df   = pd.read_csv(f"{OUT_DIR}/employees.csv")
    proj_df  = pd.read_csv(f"{OUT_DIR}/projects.csv")
    teams_df = pd.read_csv(f"{OUT_DIR}/team_formations.csv")
    print(f"  Loaded {len(emp_df)} emp | {len(proj_df)} proj | {len(teams_df)} teams")

    print(f"Generating {NUM_TASKS} tasks...")
    tasks_df = generate_tasks(emp_df, proj_df, NUM_TASKS)
    tasks_df.to_csv(f"{OUT_DIR}/tasks.csv", index=False)
    print(f"  OK {len(tasks_df)} rows -> tasks.csv")

    print(f"Generating {NUM_ASSIGNMENTS} task assignments...")
    ta_df = generate_task_assignments(emp_df, proj_df, tasks_df, teams_df, NUM_ASSIGNMENTS)
    ta_df.to_csv(f"{OUT_DIR}/task_assignments.csv", index=False)
    print(f"  OK {len(ta_df)} rows -> task_assignments.csv")

    print("\nSanity checks:")
    print(f"  tasks project_ids valid: {tasks_df['project_id'].isin(proj_df['project_id']).all()}")
    print(f"  assignments employee_ids valid: {ta_df['employee_id'].isin(emp_df['employee_id']).all()}")
    print(f"  Completed => comp_pct=100: {((tasks_df['status']=='Completed') & (tasks_df['completion_percentage']<100)).sum()} violations")

    hire_map = dict(zip(emp_df["employee_id"], pd.to_datetime(emp_df["hire_date"])))
    ta_df["_hire"]  = pd.to_datetime(ta_df["employee_id"].map(hire_map))
    ta_df["_adate"] = pd.to_datetime(ta_df["assignment_date"])
    print(f"  assignment before hire_date: {(ta_df['_adate'] < ta_df['_hire']).sum()} (should be 0)")
    completed_ta = ta_df[ta_df["completion_status"] == "Completed"]
    if len(completed_ta):
        print(f"  on-time rate (completed): {completed_ta['on_time_completion'].mean():.1%}")
