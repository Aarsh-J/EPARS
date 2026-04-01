"""
01_employees_projects.py — Generate employees.csv and projects.csv
Reads config from environment (set by 00_master.py) or uses defaults.
"""

import os, random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config import (
    DEPARTMENTS, DEPT_ROLES, SENIORITY_LEVELS, SENIORITY_WEIGHTS,
    SENIORITY_EXP_RANGE, SENIORITY_SAL_RANGE, SENIORITY_BOOST,
    EMP_TYPES, EMP_TYPE_WEIGHTS, EMP_TYPE_CAPACITY,
    TIMEZONES, REMOTE_STATUS, WORK_HOURS, TEAM_SIZE_PREF,
    PROD_TREND, PROD_TREND_W, STRESS_LEVELS, STRESS_WEIGHTS, LANGUAGES,
    DEPT_SKILLS, CERTS_BY_DEPT, FIRST_NAMES, LAST_NAMES,
    PROJECT_TYPES, PROJ_STATUS, PROJ_STATUS_W, COMPLEXITY, PRIORITY, PRIORITY_W,
    BIZ_VALUE, BIZ_VALUE_W, CUST_IMPACT, CUST_IMPACT_W, COMM_FREQ,
    COLLAB_TOOLS, COMPLEXITY_BUDGET, COMPLEXITY_DURATION, COMPLEXITY_RISK_BASE,
    PROJECT_NAMES, DEPT_SKILLS,
    clamp, rand_date, rand_datetime, pick, normal_score, normal_pct,
)

random.seed(42)
np.random.seed(42)

NUM_EMPLOYEES = int(os.environ.get("NUM_EMPLOYEES", 100))
NUM_PROJECTS  = int(os.environ.get("NUM_PROJECTS",  80))
OUT_DIR       = os.environ.get("OUT_DIR", "./output")


# ─── EMPLOYEES ────────────────────────────────────────────────────────────────
def generate_employees(n: int) -> pd.DataFrame:
    rows = []
    used_emails: set = set()

    for i in range(1, n + 1):
        emp_id = f"EMP{i:03d}"
        first  = random.choice(FIRST_NAMES)
        last   = random.choice(LAST_NAMES)

        # unique email
        base = f"{first.lower()}.{last.lower()}@company.com"
        email, suffix = base, 1
        while email in used_emails:
            email = f"{first.lower()}.{last.lower()}{suffix}@company.com"
            suffix += 1
        used_emails.add(email)

        dept      = random.choice(DEPARTMENTS)
        role      = random.choice(DEPT_ROLES[dept])
        seniority = np.random.choice(SENIORITY_LEVELS, p=SENIORITY_WEIGHTS)
        emp_type  = np.random.choice(EMP_TYPES, p=EMP_TYPE_WEIGHTS)

        lo, hi = SENIORITY_EXP_RANGE[seniority]
        yoe    = round(random.uniform(lo, hi), 1)

        # hire_date: roughly (yoe * 0.6) years ago, not before 2015
        days_ago  = int(yoe * 0.6 * 365)
        hire_date = max(date.today() - timedelta(days=max(days_ago, 90)), date(2015, 1, 1))

        salary = random.randint(*SENIORITY_SAL_RANGE[seniority])

        # Skills
        pri_pool, sec_pool = DEPT_SKILLS[dept]
        primary_skills   = pick(pri_pool,         k=random.randint(2, 4))
        secondary_skills = pick(sec_pool,         k=random.randint(1, 3))
        certifications   = pick(CERTS_BY_DEPT[dept], k=random.randint(1, 2)) \
                           if random.random() > 0.3 else "None"
        languages        = pick(LANGUAGES, k=random.randint(1, 3))

        # Scores anchored to seniority
        boost      = SENIORITY_BOOST[seniority]
        tech_score = clamp(round(np.random.normal(6.0 + boost * 4, 1.2), 1), 2.0, 10.0)
        dom_score  = clamp(round(np.random.normal(6.0 + boost * 4, 1.2), 1), 2.0, 10.0)

        capacity   = EMP_TYPE_CAPACITY[emp_type]
        is_avail   = True   # backfilled in 01b after task assignments exist

        hist_perf  = clamp(round(np.random.normal(73, 12), 1), 30.0, 100.0)
        task_comp  = clamp(round(np.random.normal(82, 10), 1), 40.0, 100.0)
        collab     = clamp(round(np.random.normal(7.2, 1.2), 1), 2.0, 10.0)
        comm       = clamp(round(np.random.normal(7.0, 1.2), 1), 2.0, 10.0)
        leadership = clamp(round(np.random.normal(6.0 + boost * 3, 1.5), 1), 1.0, 10.0)

        stress_val = np.random.choice(STRESS_LEVELS, p=STRESS_WEIGHTS)
        burnout_mu = {"Low": 20, "Medium": 45, "High": 70}[stress_val]
        burnout    = clamp(round(np.random.normal(burnout_mu, 12), 1), 0.0, 100.0)
        overtime   = round(max(0, np.random.exponential(5)), 1) \
                     if stress_val != "Low" else round(random.uniform(0, 3), 1)
        days_leave = random.choices(
            [random.randint(1, 30), random.randint(30, 120), random.randint(120, 365)],
            weights=[0.5, 0.3, 0.2],
        )[0]
        wlb = clamp(round(np.random.normal(7.0 - (burnout / 30), 1.2), 1), 1.0, 10.0)

        cross_func = random.random() > 0.4
        # mentoring backfilled in 01b; placeholder False
        mentoring  = False

        created_at   = rand_datetime(hire_date, hire_date + timedelta(days=5))
        last_updated = rand_datetime(date(2024, 1, 1), date(2025, 3, 1))

        rows.append({
            "employee_id":                emp_id,
            "first_name":                 first,
            "last_name":                  last,
            "email":                      email,
            "department":                 dept,
            "role":                       role,
            "seniority_level":            seniority,
            "employment_type":            emp_type,
            "hire_date":                  hire_date.isoformat(),
            "years_of_experience":        yoe,
            "current_salary":             salary,
            "primary_skills":             primary_skills,
            "secondary_skills":           secondary_skills,
            "certifications":             certifications,
            "languages_known":            languages,
            "technical_proficiency_score":tech_score,
            "domain_expertise_score":     dom_score,
            "weekly_capacity_hours":      capacity,
            "is_available":               is_avail,
            "preferred_work_hours":       random.choice(WORK_HOURS),
            "timezone":                   random.choice(TIMEZONES),
            "remote_work_status":         random.choice(REMOTE_STATUS),
            "historical_performance_score": hist_perf,
            "productivity_trend":         np.random.choice(PROD_TREND, p=PROD_TREND_W),
            "average_task_completion_rate": task_comp,
            "collaboration_score":        collab,
            "communication_effectiveness":comm,
            "leadership_potential":       leadership,
            "stress_level":               stress_val,
            "burnout_risk_score":         burnout,
            "recent_overtime_hours":      overtime,
            "days_since_last_leave":      days_leave,
            "work_life_balance_score":    wlb,
            "preferred_team_size":        random.choice(TEAM_SIZE_PREF),
            "cross_functional_experience":cross_func,
            "mentoring_experience":       mentoring,
            "last_updated":               last_updated,
            "created_at":                 created_at,
        })

    return pd.DataFrame(rows)


# ─── PROJECTS ─────────────────────────────────────────────────────────────────
def generate_projects(employees_df: pd.DataFrame, n: int) -> pd.DataFrame:
    emp_ids  = employees_df["employee_id"].tolist()
    managers = employees_df[
        employees_df["seniority_level"].isin(["Senior", "Lead", "Principal"])
    ]["employee_id"].tolist() or emp_ids[:20]

    rows = []
    proj_start_base = date(2023, 1, 1)

    for i in range(1, n + 1):
        proj_id    = f"PRJ{i:03d}"
        dept       = random.choice(DEPARTMENTS)
        p_type     = random.choice(PROJECT_TYPES)
        priority   = np.random.choice(PRIORITY, p=PRIORITY_W)
        complexity = np.random.choice(COMPLEXITY, p=[0.15, 0.35, 0.35, 0.15])

        budget     = round(random.uniform(*COMPLEXITY_BUDGET[complexity]), 2)

        start_date = rand_date(proj_start_base, date(2024, 6, 1))
        duration   = COMPLEXITY_DURATION[complexity] + random.randint(-20, 40)
        duration   = max(duration, 20)
        planned_end= start_date + timedelta(days=duration)

        status     = np.random.choice(PROJ_STATUS, p=PROJ_STATUS_W)
        completed  = status == "Completed"
        actual_end = (start_date + timedelta(days=duration + random.randint(-15, 30))).isoformat() \
                     if completed else None
        comp_pct   = 100.0 if completed else \
                     (0.0 if status == "Planning" else round(random.uniform(5, 95), 1))

        days_var   = random.randint(-20, 20) if status == "Active" \
                     else (random.randint(0, 10) if completed else 0)
        is_on_sched= days_var >= -5

        # Team — PM is the only one stored here; full team in team_formations
        # team_size stored as placeholder; backfilled in 04a
        pm_id      = random.choice(managers)

        alloc      = round(random.uniform(500, 5000), 0)
        consumed_pct = {
            "Planning":  0.05,
            "Active":    random.uniform(0.3, 0.7),
            "On Hold":   random.uniform(0.2, 0.5),
            "Completed": random.uniform(0.9, 1.15),
            "Cancelled": random.uniform(0.1, 0.4),
        }[status]
        consumed   = round(alloc * consumed_pct, 0)

        risk_base      = COMPLEXITY_RISK_BASE[complexity]
        success_prob   = clamp(round(np.random.normal(100 - risk_base, 15), 1), 10.0, 98.0)
        delay_risk     = clamp(round(np.random.normal(risk_base,        15), 1),  5.0, 95.0)
        budget_risk    = clamp(round(np.random.normal(risk_base * 0.7,  12), 1),  5.0, 90.0)
        quality_risk   = clamp(round(np.random.normal(risk_base * 0.6,  12), 1),  5.0, 90.0)
        scope_creep    = clamp(round(np.random.normal(risk_base * 0.5,  10), 1),  0.0, 80.0)
        stkh_sat       = clamp(round(np.random.normal(7.5, 1.2), 1), 3.0, 10.0)

        total_ms   = random.randint(3, 12)
        comp_ms    = int(total_ms * comp_pct / 100)
        overdue_ms = random.randint(0, max(0, total_ms - comp_ms - 1)) if not completed else 0
        next_ms    = (start_date + timedelta(
                          days=int(duration * (comp_ms + 1) / total_ms)
                      )).isoformat() if not completed and comp_ms < total_ms else None
        next_ms_risk = clamp(round(np.random.normal(delay_risk, 10), 1), 5.0, 95.0) \
                       if next_ms else None

        pri_pool, _ = DEPT_SKILLS[dept]
        req_skills  = pick(pri_pool, k=random.randint(2, 5))

        client_id  = f"CLT{random.randint(1, 30):03d}" if p_type == "Client Project" else None
        biz_value  = np.random.choice(BIZ_VALUE, p=BIZ_VALUE_W)
        roi_est    = round(random.uniform(20, 400), 1)
        strat_imp  = clamp(round(np.random.normal(6.5, 1.5), 1), 1.0, 10.0)
        cust_impact= np.random.choice(CUST_IMPACT, p=CUST_IMPACT_W)
        doc_quality= clamp(round(np.random.normal(7.0, 1.3), 1), 2.0, 10.0)
        mtg_hrs    = round(random.uniform(1, 12), 1)

        created_at   = rand_datetime(start_date - timedelta(days=30), start_date)
        last_updated = rand_datetime(start_date, date(2025, 3, 1))

        rows.append({
            "project_id":            proj_id,
            "project_name":          random.choice(PROJECT_NAMES) + f" {i}",
            "project_description":   f"{p_type} project for {dept} — {complexity} complexity.",
            "project_type":          p_type,
            "client_id":             client_id,
            "department":            dept,
            "priority":              priority,
            "budget":                budget,
            "complexity_level":      complexity,
            "start_date":            start_date.isoformat(),
            "planned_end_date":      planned_end.isoformat(),
            "actual_end_date":       actual_end,
            "current_status":        status,
            "completion_percentage": comp_pct,
            "is_on_schedule":        is_on_sched,
            "days_ahead_behind":     days_var,
            "project_manager_id":    pm_id,
            "allocated_resources":   int(alloc),
            "consumed_resources":    int(consumed),
            "success_probability":   success_prob,
            "delay_risk_score":      delay_risk,
            "budget_overrun_risk":   budget_risk,
            "quality_risk_score":    quality_risk,
            "scope_creep_indicator": scope_creep,
            "stakeholder_satisfaction": stkh_sat,
            "total_milestones":      total_ms,
            "completed_milestones":  comp_ms,
            "overdue_milestones":    overdue_ms,
            "next_milestone_date":   next_ms,
            "next_milestone_risk":   next_ms_risk,
            "communication_frequency": random.choice(COMM_FREQ),
            "meeting_hours_per_week":mtg_hrs,
            "collaboration_tools":   random.choice(COLLAB_TOOLS),
            "documentation_quality": doc_quality,
            "business_value":        biz_value,
            "roi_estimate":          roi_est,
            "strategic_importance":  strat_imp,
            "customer_impact":       cust_impact,
            "required_skills":       req_skills,
            "created_at":            created_at,
            "last_updated":          last_updated,
        })

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Generating employees...")
    emp_df = generate_employees(NUM_EMPLOYEES)
    emp_df.to_csv(f"{OUT_DIR}/employees.csv", index=False)
    print(f"  ✓ {len(emp_df)} rows → employees.csv")

    print("Generating projects...")
    proj_df = generate_projects(emp_df, NUM_PROJECTS)
    proj_df.to_csv(f"{OUT_DIR}/projects.csv", index=False)
    print(f"  ✓ {len(proj_df)} rows → projects.csv")

    print("\nSanity checks:")
    print(f"  dept distribution:\n{emp_df['department'].value_counts().to_string()}")
    print(f"  seniority distribution:\n{emp_df['seniority_level'].value_counts().to_string()}")
    print(f"  project status distribution:\n{proj_df['current_status'].value_counts().to_string()}")
    print(f"  all PM ids valid: {proj_df['project_manager_id'].isin(emp_df['employee_id']).all()}")
