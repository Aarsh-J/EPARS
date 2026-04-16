"""
02_tasks_assignments.py — Generate tasks.csv and task_assignments.csv
- Assignment dates clamped to >= employee hire_date
- Assignees drawn from the project's team pool (from team_formations)
"""

import os, random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config import (
    TASK_TYPES, TASK_NAMES_BY_TYPE, ROLE_BY_TASK_TYPE,
    TASK_STATUS, TASK_COMPLEXITY, TASK_COMPLEXITY_W,
    RISK_LEVEL, BIZ_IMPACT, COMM_FREQ,
    SKILLS_BY_TASK_TYPE,
    COMPLEXITY_EST_HOURS, COMPLEXITY_STORY_PTS, COMPLEXITY_TECH_SCORE,
    PRIORITY, PRIORITY_W,
    clamp, rand_date, rand_datetime, pick,
)

random.seed(42)
np.random.seed(42)

NUM_TASKS       = int(os.environ.get("NUM_TASKS",       800))
NUM_ASSIGNMENTS = int(os.environ.get("NUM_ASSIGNMENTS", 500))
OUT_DIR         = os.environ.get("OUT_DIR", "./output")


# ─── TASKS ────────────────────────────────────────────────────────────────────
def generate_tasks(employees_df: pd.DataFrame,
                   projects_df: pd.DataFrame,
                   n: int) -> pd.DataFrame:
    proj_ids = projects_df["project_id"].tolist()
    emp_ids  = employees_df["employee_id"].tolist()

    proj_windows = {}
    for _, row in projects_df.iterrows():
        start   = date.fromisoformat(row["start_date"])
        end_str = row["actual_end_date"] if pd.notna(row.get("actual_end_date")) \
                  else row["planned_end_date"]
        end = date.fromisoformat(end_str)
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
        tech_score   = round(random.uniform(*COMPLEXITY_TECH_SCORE[complexity]), 1)

        task_start = rand_date(p_start, p_end - timedelta(days=7))
        buffer     = random.randint(1, 7)
        duration   = int(est_hours / 8) + buffer + 1
        due_date   = min(task_start + timedelta(days=duration), p_end)

        proj_row    = projects_df[projects_df["project_id"] == proj_id].iloc[0]
        proj_status = proj_row["current_status"]

        if proj_status == "Completed":
            status = np.random.choice(TASK_STATUS, p=[0.02, 0.03, 0.05, 0.88, 0.02])
        elif proj_status == "Planning":
            status = np.random.choice(TASK_STATUS, p=[0.70, 0.15, 0.05, 0.05, 0.05])
        elif proj_status == "Cancelled":
            status = np.random.choice(TASK_STATUS, p=[0.20, 0.10, 0.05, 0.40, 0.25])
        else:
            status = np.random.choice(TASK_STATUS, p=[0.10, 0.35, 0.15, 0.30, 0.10])

        completed  = status == "Completed"
        comp_pct   = 100.0 if completed else \
                     (0.0 if status == "Not Started" else round(random.uniform(5, 90), 1))

        actual_comp  = None
        days_overdue = 0
        is_overdue   = False
        if completed:
            actual_comp  = rand_date(task_start, due_date + timedelta(days=15))
            days_overdue = max(0, (actual_comp - due_date).days)
            is_overdue   = days_overdue > 0
        elif status != "Not Started" and date.today() > due_date:
            is_overdue   = True
            days_overdue = (date.today() - due_date).days

        actual_hours = round(est_hours * random.uniform(0.7, 1.4), 1) if completed else None

        assigned_to   = random.choice(emp_ids) if random.random() > 0.2 else None
        assigned_date = rand_date(p_start, task_start).isoformat() if assigned_to else None

        skill_pool  = SKILLS_BY_TASK_TYPE[task_type]
        req_skills  = pick(skill_pool, k=random.randint(1, 3))
        req_role    = ROLE_BY_TASK_TYPE[task_type]
        req_seniority = np.random.choice(["Junior", "Mid", "Senior"], p=[0.30, 0.45, 0.25])

        dep_ids = rel_ids = block_ids = ""
        if i > 5 and random.random() < 0.30:
            dep_count = random.randint(1, 2)
            dep_ids   = ",".join(random.sample(task_ids[:i], min(dep_count, i)))
        if i < n - 5 and random.random() < 0.20:
            block_ids = ",".join(
                random.sample(task_ids[i+1:min(i+20, n)], min(2, n - i - 1))
            )
        if random.random() < 0.25:
            rel_pool  = task_ids[max(0, i-10):i] + task_ids[i+1:min(i+10, n)]
            rel_ids   = ",".join(random.sample(rel_pool, min(2, len(rel_pool))))

        has_subtasks = random.random() < 0.20
        parent_id    = random.choice(task_ids[:max(1, i)]) \
                       if i > 0 and random.random() < 0.15 else None

        quality_score    = None
        review_rating    = None
        stakeholder_sat  = None
        rework_required  = False
        rework_count     = 0
        if completed:
            quality_score   = clamp(round(np.random.normal(7.5, 1.2), 1), 3.0, 10.0)
            review_rating   = clamp(round(np.random.normal(7.8, 1.1), 1), 3.0, 10.0)
            stakeholder_sat = clamp(round(np.random.normal(7.5, 1.2), 1), 3.0, 10.0)
            rework_required = quality_score < 6.5
            rework_count    = random.randint(1, 3) if rework_required else 0

        tech_debt  = completed and random.random() < 0.25
        needs_collab = random.random() > 0.4
        team_size_req= random.randint(1, 5) if needs_collab else 1

        created_at   = rand_datetime(p_start - timedelta(days=7), task_start)
        last_updated = rand_datetime(task_start, date(2025, 3, 1))

        rows.append({
            "task_id":                task_id,
            "task_name":              random.choice(TASK_NAMES_BY_TYPE[task_type]) + f" #{i+1}",
            "task_description":       f"{task_type} task — {complexity} complexity.",
            "task_type":              task_type,
            "project_id":             proj_id,
            "priority":               priority,
            "complexity":             complexity,
            "estimated_hours":        est_hours,
            "actual_hours":           actual_hours,
            "story_points":           story_points,
            "required_skills":        req_skills,
            "required_role":          req_role,
            "required_seniority":     req_seniority,
            "required_certifications":None,
            "technical_complexity_score": tech_score,
            "assigned_to":            assigned_to,
            "assigned_date":          assigned_date,
            "status":                 status,
            "completion_percentage":  comp_pct,
            "start_date":             task_start.isoformat(),
            "due_date":               due_date.isoformat(),
            "actual_completion_date": actual_comp.isoformat() if actual_comp else None,
            "is_overdue":             is_overdue,
            "days_overdue":           days_overdue,
            "buffer_days":            buffer,
            "dependent_task_ids":     dep_ids or None,
            "blocking_task_ids":      block_ids or None,
            "related_tasks":          rel_ids or None,
            "parent_task_id":         parent_id,
            "has_subtasks":           has_subtasks,
            "quality_score":          quality_score,
            "rework_required":        rework_required,
            "rework_count":           rework_count,
            "review_rating":          review_rating,
            "stakeholder_satisfaction": stakeholder_sat,
            "risk_level":             np.random.choice(RISK_LEVEL, p=[0.40, 0.40, 0.20]),
            "business_impact":        np.random.choice(BIZ_IMPACT, p=[0.15, 0.35, 0.35, 0.15]),
            "delay_risk_score":       clamp(round(np.random.normal(35, 20), 1), 5.0, 95.0),
            "technical_debt_added":   tech_debt,
            "requires_collaboration": needs_collab,
            "team_size_required":     team_size_req,
            "communication_frequency":random.choice(COMM_FREQ),
            "meeting_hours_required": round(random.uniform(0, 5), 1),
            "created_at":             created_at,
            "last_updated":           last_updated,
        })

    return pd.DataFrame(rows)


# ─── TASK ASSIGNMENTS ─────────────────────────────────────────────────────────
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

    # Build project → team member pool from team_formations
    proj_team_pool: dict[str, list[str]] = {}
    for _, row in teams_df.iterrows():
        pid     = row["project_id"]
        members = [m.strip() for m in str(row["member_ids"]).split(",") if m.strip()]
        members.append(row["team_lead_id"])
        proj_team_pool.setdefault(pid, [])
        proj_team_pool[pid].extend(members)
    # deduplicate
    proj_team_pool = {pid: list(set(members)) for pid, members in proj_team_pool.items()}

    ASSIGN_METHOD = ["Manual", "AI-Recommended", "Skill-Based", "Availability-Based"]
    ACCEPT_STATUS = ["Accepted", "Pending", "Declined"]
    ACCEPT_W      = [0.80, 0.15, 0.05]
    COMPLETE_STATUS = ["Completed", "In Progress", "Reassigned", "Cancelled"]
    COMPLETE_W      = [0.55, 0.25, 0.12, 0.08]
    REASSIGN_REASON = ["Overload", "Skill Mismatch", "Leave", None]

    # Index tasks by project for realistic pairing
    tasks_by_proj: dict[str, list] = {}
    for _, row in tasks_df.iterrows():
        tasks_by_proj.setdefault(row["project_id"], []).append(row)

    rows = []
    used_task_emp_pairs: set = set()

    for i in range(1, n + 1):
        asgn_id = f"ASG{i:04d}"

        # Pick a project that has tasks
        proj_id = random.choice([p for p in tasks_by_proj if tasks_by_proj[p]])
        task_row = random.choice(tasks_by_proj[proj_id])
        task_id  = task_row["task_id"]

        # Pick employee from team pool weighted by skill match — fallback to any employee
        pool = proj_team_pool.get(proj_id, emp_ids)
        if not pool:
            pool = emp_ids

        task_req_skills = {s.strip() for s in str(task_row.get("required_skills", "")).split(",") if s.strip()}

        def _skill_weight(eid):
            row = employees_df[employees_df["employee_id"] == eid]
            if row.empty:
                return 1.0
            row = row.iloc[0]
            e_skills = set()
            for col in ["primary_skills", "secondary_skills"]:
                if pd.notna(row.get(col)):
                    e_skills.update(s.strip() for s in str(row[col]).split(","))
            overlap = len(e_skills & task_req_skills)
            # Base weight 1.0 even with no match; strong boost for matching skills
            return 1.0 + overlap * 4.0

        pool_weights = np.array([_skill_weight(e) for e in pool], dtype=float)
        pool_weights /= pool_weights.sum()
        emp_id = np.random.choice(pool, p=pool_weights)

        # Avoid duplicate (task, employee) pairs
        pair = (task_id, emp_id)
        if pair in used_task_emp_pairs:
            emp_id = random.choice(emp_ids)
            pair   = (task_id, emp_id)
        used_task_emp_pairs.add(pair)

        hire_dt    = hire_map.get(emp_id, date(2015, 1, 1))
        proj_start = proj_start_map.get(proj_id, date(2023, 1, 1))
        # Assignment date must be >= hire_date AND >= project_start
        earliest   = max(hire_dt, proj_start)
        task_start = date.fromisoformat(str(task_row["start_date"]))
        latest     = max(task_start, earliest + timedelta(days=1))
        assign_date= rand_date(earliest, latest)

        # Match scores
        emp_row = employees_df[employees_df["employee_id"] == emp_id].iloc[0]
        task_skills = {s.strip() for s in str(task_row.get("required_skills", "")).split(",") if s.strip()}
        emp_skills  = set()
        for col in ["primary_skills", "secondary_skills"]:
            if pd.notna(emp_row.get(col)):
                emp_skills.update(s.strip() for s in str(emp_row[col]).split(","))
        skill_match = round(
            (len(emp_skills & task_skills) / max(len(task_skills), 1)) * 100, 1
        )
        avail_match  = round(np.random.normal(75, 15), 1)
        wl_compat    = round(np.random.normal(72, 15), 1)
        exp_match    = round(np.random.normal(70, 15), 1)
        overall_suit = clamp(round(
            skill_match * 0.35 + avail_match * 0.25 + wl_compat * 0.20 + exp_match * 0.20
            + np.random.normal(0, 5), 1
        ), 10.0, 100.0)
        team_compat  = round(np.random.normal(74, 13), 1)

        method   = random.choice(ASSIGN_METHOD)
        assigned_by = random.choice(
            employees_df[employees_df["seniority_level"].isin(["Senior", "Lead", "Principal"])
            ]["employee_id"].tolist() or emp_ids
        )
        accept = np.random.choice(ACCEPT_STATUS, p=ACCEPT_W)
        accept_date = (assign_date + timedelta(days=random.randint(0, 3))).isoformat() \
                      if accept == "Accepted" else None

        comp_status = np.random.choice(COMPLETE_STATUS, p=COMPLETE_W)
        completed   = comp_status == "Completed"
        reassign_cnt= random.randint(0, 2) if comp_status == "Reassigned" else 0
        reassign_rsn= random.choice(REASSIGN_REASON) if reassign_cnt > 0 else None

        time_to_comp = round(task_row["estimated_hours"] * random.uniform(0.7, 1.5), 1) \
                       if completed else None
        quality_rat  = clamp(round(np.random.normal(7.5, 1.2), 1), 3.0, 10.0) \
                       if completed else None
        on_time      = (random.random() > 0.20) if completed else None
        efficiency   = clamp(round(
            task_row["estimated_hours"] / time_to_comp, 2
        ), 0.4, 2.0) if completed and time_to_comp else None

        satisfaction = clamp(round(np.random.normal(7.2, 1.3), 1), 2.0, 10.0)
        would_rec    = (random.random() > 0.25) if completed else None

        success_val  = completed
        emp_fb_pool  = ["Good match for my skills", "Task was well-scoped",
                        "Enjoyed the challenge", "Too complex for current workload",
                        "Great team support throughout", None]
        mgr_fb_pool  = ["Excellent work delivered", "Met expectations",
                        "Needs improvement on timelines", "Strong technical execution", None]

        created_at   = rand_datetime(assign_date)
        last_updated = rand_datetime(assign_date + timedelta(days=random.randint(1, 30)))

        rows.append({
            "assignment_id":            asgn_id,
            "task_id":                  task_id,
            "employee_id":              emp_id,
            "project_id":               proj_id,
            "assignment_date":          assign_date.isoformat(),
            "assignment_method":        method,
            "assigned_by":              assigned_by,
            "acceptance_status":        accept,
            "acceptance_date":          accept_date,
            "skill_match_score":        clamp(skill_match, 0.0, 100.0),
            "availability_match_score": clamp(avail_match, 0.0, 100.0),
            "workload_compatibility_score": clamp(wl_compat, 0.0, 100.0),
            "experience_match_score":   clamp(exp_match, 0.0, 100.0),
            "overall_suitability_score":overall_suit,
            "team_compatibility_score": clamp(team_compat, 0.0, 100.0),
            "assignment_success":       success_val,
            "completion_status":        comp_status,
            "reassignment_count":       reassign_cnt,
            "reassignment_reason":      reassign_rsn,
            "time_to_complete":         time_to_comp,
            "quality_rating":           quality_rat,
            "on_time_completion":       on_time,
            "efficiency_score":         efficiency,
            "employee_feedback":        random.choice(emp_fb_pool),
            "manager_feedback":         random.choice(mgr_fb_pool),
            "assignment_satisfaction":  satisfaction,
            "would_recommend_again":    would_rec,
            "created_at":               created_at,
            "last_updated":             last_updated,
        })

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading prior data...")
    emp_df   = pd.read_csv(f"{OUT_DIR}/employees.csv")
    proj_df  = pd.read_csv(f"{OUT_DIR}/projects.csv")
    teams_df = pd.read_csv(f"{OUT_DIR}/team_formations.csv")
    print(f"  Loaded {len(emp_df)} employees | {len(proj_df)} projects | {len(teams_df)} teams")

    print(f"Generating {NUM_TASKS} tasks...")
    tasks_df = generate_tasks(emp_df, proj_df, NUM_TASKS)
    tasks_df.to_csv(f"{OUT_DIR}/tasks.csv", index=False)
    print(f"  ✓ {len(tasks_df)} rows → tasks.csv")

    print(f"Generating {NUM_ASSIGNMENTS} task assignments...")
    ta_df = generate_task_assignments(emp_df, proj_df, tasks_df, teams_df, NUM_ASSIGNMENTS)
    ta_df.to_csv(f"{OUT_DIR}/task_assignments.csv", index=False)
    print(f"  ✓ {len(ta_df)} rows → task_assignments.csv")

    print("\nSanity checks:")
    print(f"  all task project_ids valid: {tasks_df['project_id'].isin(proj_df['project_id']).all()}")
    print(f"  all assignment employee_ids valid: {ta_df['employee_id'].isin(emp_df['employee_id']).all()}")
    print(f"  all assignment project_ids valid: {ta_df['project_id'].isin(proj_df['project_id']).all()}")
    print(f"  all assignment task_ids valid: {ta_df['task_id'].isin(tasks_df['task_id']).all()}")

    hire_map = dict(zip(emp_df["employee_id"], pd.to_datetime(emp_df["hire_date"])))
    ta_df["_hire"] = pd.to_datetime(ta_df["employee_id"].map(hire_map))
    ta_df["_adate"] = pd.to_datetime(ta_df["assignment_date"])
    before_hire = (ta_df["_adate"] < ta_df["_hire"]).sum()
    print(f"  assignment_date before hire_date: {before_hire}  (should be 0)")
    print(f"  on-time rate (completed): {ta_df[ta_df['completion_status']=='Completed']['on_time_completion'].mean():.1%}")
