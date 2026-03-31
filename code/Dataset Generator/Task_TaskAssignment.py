"""
Part 2: Generate tasks.csv and task_assignments.csv
Dependencies: numpy, pandas
Requires: employees.csv, projects.csv (from Part 1) in same directory
Usage: python generate_part2.py
Output: tasks.csv, task_assignments.csv
"""

import random
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta

random.seed(42)
np.random.seed(42)

# ─── Config ───────────────────────────────────────────────────────────────────
NUM_TASKS       = 2000
NUM_ASSIGNMENTS = 3000
OUT_DIR         = "."

# ─── Lookup tables ────────────────────────────────────────────────────────────
TASK_TYPES = ["Development","Design","Testing","Research","Documentation","Meeting","DevOps","Review"]

TASK_NAMES_BY_TYPE = {
    "Development":   ["Implement user authentication","Build REST API endpoint","Develop payment gateway",
                      "Create database schema","Refactor legacy module","Build notification service",
                      "Implement caching layer","Develop admin dashboard","Create data pipeline","Build search feature"],
    "Design":        ["Design landing page","Create wireframes","Build design system","Design onboarding flow",
                      "Create icon set","Design email templates","Prototype user journey","Redesign settings page"],
    "Testing":       ["Write unit tests","Perform integration testing","Conduct load testing","Run regression suite",
                      "Security vulnerability scan","Accessibility audit","API contract testing","E2E test automation"],
    "Research":      ["Evaluate third-party libraries","Conduct user research","Benchmark database options",
                      "Research ML frameworks","Competitive analysis","Technology feasibility study"],
    "Documentation": ["Write API documentation","Update onboarding guide","Create runbook","Document architecture",
                      "Write release notes","Update README","Create user manual"],
    "Meeting":       ["Sprint planning","Retrospective","Stakeholder review","Design critique",
                      "Architecture discussion","Incident post-mortem","Team sync"],
    "DevOps":        ["Setup CI/CD pipeline","Configure monitoring","Deploy to staging","Optimize Docker images",
                      "Setup alerting rules","Database backup automation","Infrastructure as code"],
    "Review":        ["Code review","Design review","Architecture review","PR review","Document review"],
}

PRIORITY      = ["Low","Medium","High","Critical"]
COMPLEXITY    = ["Simple","Moderate","Complex","Very Complex"]
STATUS        = ["Not Started","In Progress","In Review","Completed","Blocked"]
RISK_LEVEL    = ["Low","Medium","High"]
BIZ_IMPACT    = ["Low","Medium","High","Critical"]
COMM_FREQ     = ["Daily","Weekly","As needed"]

# Skills needed per task type
SKILLS_BY_TYPE = {
    "Development":   ["Python","Java","Go","React","Node.js","SQL","TypeScript","C++","REST APIs","Docker"],
    "Design":        ["Figma","Adobe XD","UI/UX","Prototyping","Sketch","Illustrator","CSS","HTML"],
    "Testing":       ["Selenium","Jest","PyTest","JMeter","Postman","Cypress","TestRail"],
    "Research":      ["Data Analysis","Python","R","Excel","Literature Review","Statistics"],
    "Documentation": ["Technical Writing","Confluence","Markdown","Git"],
    "Meeting":       ["Communication","Facilitation","Agile","Scrum"],
    "DevOps":        ["Docker","Kubernetes","AWS","Terraform","Jenkins","GitHub Actions","Linux"],
    "Review":        ["Code Review","Git","Python","Java","React"],
}

ROLE_BY_TYPE = {
    "Development":   "Developer",
    "Design":        "Designer",
    "Testing":       "Developer",
    "Research":      "Analyst",
    "Documentation": "Developer",
    "Meeting":       "Manager",
    "DevOps":        "Developer",
    "Review":        "Senior Engineer",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────
def rand_date(start: date, end: date) -> date:
    if start >= end:
        return start
    return start + timedelta(days=random.randint(0, (end - start).days))

def rand_datetime(start: date, end: date) -> str:
    d = rand_date(start, end)
    h, m = random.randint(8, 18), random.choice([0, 15, 30, 45])
    return f"{d} {h:02d}:{m:02d}:00"

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def pick_skills(pool, k):
    return ",".join(random.sample(pool, min(k, len(pool))))

# ─── TASKS ────────────────────────────────────────────────────────────────────
def generate_tasks(employees_df, projects_df, n=NUM_TASKS):
    proj_ids = projects_df["project_id"].tolist()
    emp_ids  = employees_df["employee_id"].tolist()

    # Build project date windows for temporal consistency
    proj_windows = {}
    for _, row in projects_df.iterrows():
        start = date.fromisoformat(row["start_date"])
        end_str = row["actual_end_date"] if pd.notna(row["actual_end_date"]) else row["planned_end_date"]
        end = date.fromisoformat(end_str)
        proj_windows[row["project_id"]] = (start, max(end, start + timedelta(days=7)))

    task_ids = [f"TSK{i:04d}" for i in range(1, n + 1)]
    rows = []

    for i, task_id in enumerate(task_ids):
        task_type  = random.choice(TASK_TYPES)
        proj_id    = random.choice(proj_ids)
        p_start, p_end = proj_windows[proj_id]

        priority   = np.random.choice(PRIORITY,   p=[0.15, 0.35, 0.35, 0.15])
        complexity = np.random.choice(COMPLEXITY, p=[0.20, 0.35, 0.30, 0.15])

        # Estimated hours aligned to complexity
        est_map = {"Simple":(1,8),"Moderate":(8,24),"Complex":(24,80),"Very Complex":(80,200)}
        est_hours = round(random.uniform(*est_map[complexity]), 1)

        # Story points aligned to complexity
        sp_map = {"Simple":[1,2,3],"Moderate":[3,5,8],"Complex":[8,13],"Very Complex":[13,21]}
        story_points = random.choice(sp_map[complexity])

        # Technical complexity score
        tc_map = {"Simple":(1,4),"Moderate":(4,7),"Complex":(7,9),"Very Complex":(8,10)}
        tech_score = round(random.uniform(*tc_map[complexity]), 1)

        # Timeline
        task_start = rand_date(p_start, p_end - timedelta(days=7))
        buffer     = random.randint(1, 7)
        duration   = int(est_hours / 8) + buffer + 1
        due_date   = task_start + timedelta(days=duration)
        due_date   = min(due_date, p_end)

        # Status — weight toward completion for older projects
        proj_row   = projects_df[projects_df["project_id"] == proj_id].iloc[0]
        proj_status= proj_row["current_status"]
        if proj_status == "Completed":
            status = np.random.choice(STATUS, p=[0.02, 0.03, 0.05, 0.88, 0.02])
        elif proj_status == "Planning":
            status = np.random.choice(STATUS, p=[0.70, 0.15, 0.05, 0.05, 0.05])
        elif proj_status == "Cancelled":
            status = np.random.choice(STATUS, p=[0.20, 0.10, 0.05, 0.40, 0.25])
        else:
            status = np.random.choice(STATUS, p=[0.10, 0.35, 0.15, 0.30, 0.10])

        completed  = status == "Completed"
        comp_pct   = 100.0 if completed else (0.0 if status == "Not Started" else round(random.uniform(5, 90), 1))

        # Actual completion date only if completed
        actual_comp = None
        days_overdue = 0
        is_overdue   = False
        if completed:
            actual_comp  = rand_date(task_start, due_date + timedelta(days=15))
            days_overdue = (actual_comp - due_date).days
            is_overdue   = days_overdue > 0
        elif status not in ["Not Started"] and date.today() > due_date:
            is_overdue   = True
            days_overdue = (date.today() - due_date).days

        # Actual hours — null if not complete
        actual_hours = None
        if completed:
            variance = random.uniform(0.7, 1.4)
            actual_hours = round(est_hours * variance, 1)

        # Assignee — 80% chance assigned
        assigned_to   = random.choice(emp_ids) if random.random() > 0.2 else None
        assigned_date = rand_date(p_start, task_start).isoformat() if assigned_to else None

        # Skills & requirements
        skill_pool   = SKILLS_BY_TYPE[task_type]
        req_skills   = pick_skills(skill_pool, k=random.randint(1, 3))
        req_role     = ROLE_BY_TYPE[task_type]
        req_seniority= np.random.choice(["Junior","Mid","Senior"], p=[0.30, 0.45, 0.25])

        # Dependencies — 30% of tasks have dependencies on prior tasks
        dep_ids = ""
        block_ids = ""
        related_ids = ""
        if i > 5 and random.random() < 0.30:
            dep_count = random.randint(1, 2)
            dep_ids   = ",".join(random.sample(task_ids[:i], min(dep_count, i)))
        if i < n - 5 and random.random() < 0.20:
            block_count = random.randint(1, 2)
            block_ids   = ",".join(random.sample(task_ids[i+1:min(i+20, n)], min(block_count, 5)))
        if random.random() < 0.25:
            rel_pool  = task_ids[max(0, i-10):i] + task_ids[i+1:min(i+10, n)]
            related_ids = ",".join(random.sample(rel_pool, min(2, len(rel_pool))))

        has_subtasks = random.random() < 0.20
        parent_id    = random.choice(task_ids[:max(1, i)]) if i > 0 and random.random() < 0.15 else None

        # Quality metrics — only for completed tasks
        quality_score = None
        review_rating = None
        stakeholder_sat = None
        rework_required = False
        rework_count = 0
        if completed:
            quality_score   = clamp(round(np.random.normal(7.5, 1.2), 1), 3.0, 10.0)
            review_rating   = clamp(round(np.random.normal(7.5, 1.2), 1), 3.0, 10.0)
            stakeholder_sat = clamp(round(np.random.normal(7.5, 1.3), 1), 3.0, 10.0)
            rework_required = random.random() < 0.25
            rework_count    = random.randint(1, 3) if rework_required else 0

        # Risk
        delay_risk = clamp(round(np.random.normal(
            {"Low":20,"Medium":45,"High":65,"Critical":80}[priority], 15), 1), 5.0, 95.0)
        tech_debt  = random.random() < 0.20

        # Collaboration
        req_collab  = random.random() > 0.4
        team_needed = random.randint(2, 5) if req_collab else 1
        mtg_hrs     = round(random.uniform(0, 6), 1) if req_collab else 0.0

        created_at   = rand_datetime(p_start - timedelta(days=10), task_start)
        last_updated = rand_datetime(task_start, date(2025, 3, 1))

        rows.append({
            "task_id":               task_id,
            "task_name":             random.choice(TASK_NAMES_BY_TYPE[task_type]),
            "task_description":      f"{task_type} task for project {proj_id} — {complexity} complexity.",
            "task_type":             task_type,
            "project_id":            proj_id,
            "priority":              priority,
            "complexity":            complexity,
            "estimated_hours":       est_hours,
            "actual_hours":          actual_hours,
            "story_points":          story_points,
            "required_skills":       req_skills,
            "required_role":         req_role,
            "required_seniority":    req_seniority,
            "required_certifications": None,
            "technical_complexity_score": tech_score,
            "assigned_to":           assigned_to,
            "assigned_date":         assigned_date,
            "status":                status,
            "completion_percentage": comp_pct,
            "start_date":            task_start.isoformat(),
            "due_date":              due_date.isoformat(),
            "actual_completion_date":actual_comp.isoformat() if actual_comp else None,
            "is_overdue":            is_overdue,
            "days_overdue":          days_overdue,
            "buffer_days":           buffer,
            "dependent_task_ids":    dep_ids if dep_ids else None,
            "blocking_task_ids":     block_ids if block_ids else None,
            "related_tasks":         related_ids if related_ids else None,
            "parent_task_id":        parent_id,
            "has_subtasks":          has_subtasks,
            "quality_score":         quality_score,
            "rework_required":       rework_required,
            "rework_count":          rework_count,
            "review_rating":         review_rating,
            "stakeholder_satisfaction": stakeholder_sat,
            "risk_level":            np.random.choice(RISK_LEVEL, p=[0.40, 0.40, 0.20]),
            "business_impact":       np.random.choice(BIZ_IMPACT,  p=[0.15, 0.35, 0.35, 0.15]),
            "delay_risk_score":      delay_risk,
            "technical_debt_added":  tech_debt,
            "requires_collaboration":req_collab,
            "team_size_required":    team_needed,
            "communication_frequency": random.choice(COMM_FREQ),
            "meeting_hours_required":mtg_hrs,
            "created_at":            created_at,
            "last_updated":          last_updated,
        })

    return pd.DataFrame(rows)


# ─── TASK ASSIGNMENTS ─────────────────────────────────────────────────────────
ASSIGN_METHOD  = ["Manual","AI-Recommended","Auto-Scheduled"]
ACCEPT_STATUS  = ["Pending","Accepted","Declined","Renegotiated"]
COMPLETE_STATUS= ["Completed","Reassigned","Cancelled","In Progress"]
REASSIGN_REASON= ["Overload","Skill Mismatch","Leave","Priority Change"]

EMP_FEEDBACK_POOL = [
    "Good match for my skills","Enjoyed the challenge","Task was well-defined",
    "Too complex for timeline","Great learning opportunity","Straightforward assignment",
    "Could use more context","Well scoped task","Interesting problem to solve", None
]
MGR_FEEDBACK_POOL = [
    "Excellent work delivered","Met all requirements","Needs improvement on documentation",
    "Good quality output","Completed ahead of schedule","Minor issues but acceptable",
    "Strong technical execution","Communication could be better","Solid performance", None
]

def generate_task_assignments(employees_df, tasks_df, projects_df, n=NUM_ASSIGNMENTS):
    emp_ids  = employees_df["employee_id"].tolist()
    task_ids = tasks_df["task_id"].tolist()

    # Build task → project mapping for FK
    task_proj = dict(zip(tasks_df["task_id"], tasks_df["project_id"]))
    task_status= dict(zip(tasks_df["task_id"], tasks_df["status"]))
    task_start = dict(zip(tasks_df["task_id"], tasks_df["start_date"]))
    task_due   = dict(zip(tasks_df["task_id"], tasks_df["due_date"]))
    task_est   = dict(zip(tasks_df["task_id"], tasks_df["estimated_hours"]))

    # Managers for assigned_by
    managers = employees_df[
        employees_df["seniority_level"].isin(["Senior","Lead","Principal"])
    ]["employee_id"].tolist()

    rows = []

    # Ensure each assigned task gets at least one assignment
    assigned_tasks = tasks_df[tasks_df["assigned_to"].notna()]["task_id"].tolist()
    # Pad remaining randomly
    extra_needed = max(0, n - len(assigned_tasks))
    pool = assigned_tasks + random.choices(task_ids, k=extra_needed)
    random.shuffle(pool)
    pool = pool[:n]

    seen_pairs = set()  # avoid duplicate (task, employee) on same assignment

    for i, task_id in enumerate(pool):
        asg_id   = f"ASG{i+1:04d}"
        proj_id  = task_proj[task_id]
        t_status = task_status[task_id]
        t_start  = date.fromisoformat(task_start[task_id])
        t_due    = date.fromisoformat(task_due[task_id])
        t_est    = task_est[task_id]

        # Pick employee — avoid repeat (task, emp) pairs where possible
        for _ in range(10):
            emp_id = random.choice(emp_ids)
            if (task_id, emp_id) not in seen_pairs:
                break
        seen_pairs.add((task_id, emp_id))

        assign_date = rand_date(t_start - timedelta(days=5), t_start + timedelta(days=2))

        # Suitability scores
        skill_match    = clamp(round(np.random.normal(75, 15), 1), 20.0, 100.0)
        avail_match    = clamp(round(np.random.normal(78, 13), 1), 20.0, 100.0)
        workload_compat= clamp(round(np.random.normal(72, 15), 1), 20.0, 100.0)
        exp_match      = clamp(round(np.random.normal(76, 14), 1), 20.0, 100.0)
        team_compat    = clamp(round(np.random.normal(78, 13), 1), 20.0, 100.0)
        overall        = clamp(round(np.mean([skill_match, avail_match, workload_compat, exp_match, team_compat]) +
                                     np.random.normal(0, 3), 1), 20.0, 100.0)

        # Acceptance — mostly accepted
        accept_status = np.random.choice(ACCEPT_STATUS, p=[0.10, 0.75, 0.08, 0.07])
        accept_date   = (assign_date + timedelta(days=random.randint(0, 3))).isoformat() \
                        if accept_status != "Pending" else None

        # Completion outcome
        is_completed  = t_status == "Completed" and accept_status == "Accepted"
        comp_status   = "Completed" if is_completed else \
                        ("In Progress" if t_status == "In Progress" else \
                         np.random.choice(["Reassigned","Cancelled","In Progress"], p=[0.15, 0.10, 0.75]))

        reassign_count  = random.randint(0, 2) if comp_status == "Reassigned" else 0
        reassign_reason = random.choice(REASSIGN_REASON) if reassign_count > 0 else None

        # Performance metrics — only if completed
        time_to_complete = None
        quality_rating   = None
        on_time          = None
        efficiency       = None
        asg_success      = None
        asg_satisfaction = None
        would_recommend  = None

        if is_completed:
            variance         = random.uniform(0.7, 1.5)
            time_to_complete = round(t_est * variance, 1)
            quality_rating   = clamp(round(np.random.normal(7.5, 1.2), 1), 3.0, 10.0)
            on_time          = random.random() > 0.20   # 80% on time
            efficiency       = clamp(round(t_est / time_to_complete, 2), 0.5, 1.8)
            asg_success      = True
            asg_satisfaction = clamp(round(np.random.normal(7.5, 1.3), 1), 3.0, 10.0)
            would_recommend  = random.random() > 0.20
        elif comp_status in ["Reassigned","Cancelled"]:
            asg_success = False

        rows.append({
            "assignment_id":            asg_id,
            "task_id":                  task_id,
            "employee_id":              emp_id,
            "project_id":               proj_id,
            "assignment_date":          assign_date.isoformat(),
            "assignment_method":        np.random.choice(ASSIGN_METHOD, p=[0.40, 0.40, 0.20]),
            "assigned_by":              random.choice(managers + ["SYSTEM"]),
            "acceptance_status":        accept_status,
            "acceptance_date":          accept_date,
            "skill_match_score":        skill_match,
            "availability_match_score": avail_match,
            "workload_compatibility_score": workload_compat,
            "experience_match_score":   exp_match,
            "overall_suitability_score":overall,
            "team_compatibility_score": team_compat,
            "assignment_success":       asg_success,
            "completion_status":        comp_status,
            "reassignment_count":       reassign_count,
            "reassignment_reason":      reassign_reason,
            "time_to_complete":         time_to_complete,
            "quality_rating":           quality_rating,
            "on_time_completion":       on_time,
            "efficiency_score":         efficiency,
            "employee_feedback":        random.choice(EMP_FEEDBACK_POOL),
            "manager_feedback":         random.choice(MGR_FEEDBACK_POOL),
            "assignment_satisfaction":  asg_satisfaction,
            "would_recommend_again":    would_recommend,
            "created_at":               rand_datetime(assign_date, assign_date + timedelta(days=1)),
            "last_updated":             rand_datetime(assign_date, date(2025, 3, 1)),
        })

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading Part 1 data...")
    emp_df  = pd.read_csv(f"{OUT_DIR}/employees.csv")
    proj_df = pd.read_csv(f"{OUT_DIR}/projects.csv")
    print(f"  Loaded {len(emp_df)} employees, {len(proj_df)} projects")

    print("Generating tasks...")
    tasks_df = generate_tasks(emp_df, proj_df, NUM_TASKS)
    tasks_df.to_csv(f"{OUT_DIR}/tasks.csv", index=False)
    print(f"  ✓ {len(tasks_df)} rows → tasks.csv")

    print("Generating task assignments...")
    asg_df = generate_task_assignments(emp_df, tasks_df, proj_df, NUM_ASSIGNMENTS)
    asg_df.to_csv(f"{OUT_DIR}/task_assignments.csv", index=False)
    print(f"  ✓ {len(asg_df)} rows → task_assignments.csv")

    # Sanity checks
    print("\nSanity checks:")
    print(f"  Tasks — status distribution:\n{tasks_df['status'].value_counts().to_string()}")
    print(f"  Tasks — all project_ids valid: {tasks_df['project_id'].isin(proj_df['project_id']).all()}")
    assigned_emps = tasks_df['assigned_to'].dropna()
    print(f"  Tasks — all assigned employee_ids valid: {assigned_emps.isin(emp_df['employee_id']).all()}")
    print(f"  Assignments — status distribution:\n{asg_df['completion_status'].value_counts().to_string()}")
    print(f"  Assignments — all task_ids valid: {asg_df['task_id'].isin(tasks_df['task_id']).all()}")
    print(f"  Assignments — all employee_ids valid: {asg_df['employee_id'].isin(emp_df['employee_id']).all()}")
    print(f"  Assignments — on-time rate (completed): "
          f"{asg_df[asg_df['on_time_completion'].notna()]['on_time_completion'].mean():.1%}")
    print("\nDone.")