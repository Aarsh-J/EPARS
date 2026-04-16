"""
01_employees_projects.py — Generate employees.csv and projects.csv (V3 schema).

Calculated columns seeded here; precise values backfilled in 06_backfill.py after
all other tables exist.
"""

import os, random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config import (
    DEPARTMENTS, DEPT_ROLES, SENIORITY_LEVELS, SENIORITY_WEIGHTS,
    SENIORITY_EXP_RANGE, SENIORITY_SAL_RANGE, DEPT_SAL_MULTIPLIER,
    SENIORITY_BOOST, SENIORITY_TECH_BASE, SENIORITY_DOMAIN_BASE, SENIORITY_LP_BASE,
    EMP_TYPES, EMP_TYPE_WEIGHTS, EMP_TYPE_CAPACITY,
    REMOTE_STATUS, WORK_HOURS, TEAM_SIZE_PREF, PROD_TREND, PROD_TREND_W,
    DEPT_SKILLS, CERTS_BY_DEPT, FIRST_NAMES, LAST_NAMES,
    PROJECT_TYPES, PROJ_STATUS, PROJ_STATUS_W, COMPLEXITY, PRIORITY, PRIORITY_W,
    COMPLEXITY_BUDGET, COMPLEXITY_DURATION, COMPLEXITY_RISK_BASE, PROJECT_NAMES,
    clamp, rand_date, rand_datetime, pick, normal_pct,
)

random.seed(42)
np.random.seed(42)

NUM_EMPLOYEES = int(os.environ.get("NUM_EMPLOYEES", 100))
NUM_PROJECTS  = int(os.environ.get("NUM_PROJECTS",  80))
OUT_DIR       = os.environ.get("OUT_DIR", "./output")

TODAY = date(2025, 4, 16)


# ─── Derived score helpers ────────────────────────────────────────────────────

def calc_technical_proficiency(seniority: str, primary_skills: str,
                                certifications: str) -> float:
    """
    technical_proficiency_score:
      = seniority_base(55%) + skill_count_factor(35%) + cert_bonus(10%)
      + Normal(0, 6) noise, clamped 5-100
    """
    seniority_base  = SENIORITY_TECH_BASE[seniority]
    skill_count     = len([s for s in primary_skills.split(",") if s.strip()])
    skill_factor    = min(skill_count / 5.0, 1.0) * 100   # max at 5 skills
    has_certs       = certifications and certifications.lower() not in ("none", "nan", "")
    cert_count      = len([c for c in certifications.split(",") if c.strip()]) if has_certs else 0
    cert_bonus      = min(cert_count * 8, 20)
    base = seniority_base * 0.55 + skill_factor * 0.35 + cert_bonus * 0.10
    return clamp(round(base + np.random.normal(0, 6), 1), 5.0, 100.0)


def calc_domain_expertise(seniority: str, yoe: float,
                           hist_perf: float) -> float:
    """
    domain_expertise_score:
      = yoe_factor(50%) + seniority_base(35%) + hist_perf_scaled(15%)
      + Normal(0, 6) noise, clamped 5-100
    """
    yoe_factor      = min(yoe / 20.0, 1.0) * 100
    seniority_base  = SENIORITY_DOMAIN_BASE[seniority]
    perf_contrib    = hist_perf * 0.15
    base = yoe_factor * 0.50 + seniority_base * 0.35 + perf_contrib
    return clamp(round(base + np.random.normal(0, 6), 1), 5.0, 100.0)


def calc_leadership_potential(seniority: str, successful_projects: int,
                               collaboration_score: int) -> float:
    """
    leadership_potential:
      = seniority_base(45%) + success_norm(30%) + collab_norm(25%)
      + Normal(0, 7) noise, clamped 5-100
    """
    seniority_base  = SENIORITY_LP_BASE[seniority]
    success_norm    = min(successful_projects / 20.0, 1.0) * 100
    collab_norm     = (collaboration_score / 10.0) * 100
    base = seniority_base * 0.45 + success_norm * 0.30 + collab_norm * 0.25
    return clamp(round(base + np.random.normal(0, 7), 1), 5.0, 100.0)


def calc_burnout_risk(recent_overtime_hours: float,
                      days_since_last_leave: int) -> float:
    """
    burnout_risk_score:
      = overtime_factor(55%) + leave_factor(45%)
      + Normal(0, 8) noise, clamped 0-100
    overtime_factor caps at 60 pts when overtime >= 20h/month
    leave_factor caps at 40 pts when days_since_last_leave >= 180
    """
    overtime_factor = min(recent_overtime_hours / 20.0, 1.0) * 60
    leave_factor    = min(days_since_last_leave / 180.0, 1.0) * 40
    base = overtime_factor * 0.55 + leave_factor * 0.45
    return clamp(round(base + np.random.normal(0, 8), 1), 0.0, 100.0)


def stress_from_burnout(burnout: float) -> str:
    if burnout >= 67:
        return "High"
    elif burnout >= 34:
        return "Medium"
    return "Low"


# ─── EMPLOYEES ────────────────────────────────────────────────────────────────
def generate_employees(n: int) -> pd.DataFrame:
    rows = []
    used_emails: set = set()

    for i in range(1, n + 1):
        emp_id = f"EMP{i:03d}"
        first  = random.choice(FIRST_NAMES)
        last   = random.choice(LAST_NAMES)

        # Unique email
        base   = f"{first.lower()}.{last.lower()}@company.com"
        email, suffix = base, 1
        while email in used_emails:
            email = f"{first.lower()}.{last.lower()}{suffix}@company.com"
            suffix += 1
        used_emails.add(email)

        dept      = random.choice(DEPARTMENTS)
        role      = random.choice(DEPT_ROLES[dept])
        seniority = np.random.choice(SENIORITY_LEVELS, p=SENIORITY_WEIGHTS)
        emp_type  = np.random.choice(EMP_TYPES, p=EMP_TYPE_WEIGHTS)

        yoe_lo, yoe_hi = SENIORITY_EXP_RANGE[seniority]
        yoe = round(random.uniform(yoe_lo, yoe_hi), 1)

        days_ago  = int(yoe * 0.6 * 365)
        hire_date = max(TODAY - timedelta(days=max(days_ago, 90)), date(2015, 1, 1))

        # Salary: seniority range × department multiplier
        sal_lo, sal_hi = SENIORITY_SAL_RANGE[seniority]
        mult   = DEPT_SAL_MULTIPLIER.get(dept, 1.0)
        salary = round(random.randint(sal_lo, sal_hi) * mult, -2)   # round to nearest 100

        # Skills
        pri_pool, sec_pool = DEPT_SKILLS[dept]
        primary_skills   = pick(pri_pool, k=random.randint(2, 4))
        secondary_skills = pick(sec_pool, k=random.randint(1, 3))
        certs_raw        = CERTS_BY_DEPT[dept]
        certifications   = pick(certs_raw, k=random.randint(1, 2)) \
                           if random.random() > 0.35 else None

        hist_perf = clamp(round(np.random.normal(73, 12), 1), 30.0, 100.0)

        # Computed scores
        tech_score = calc_technical_proficiency(seniority, primary_skills,
                                                certifications or "")
        dom_score  = calc_domain_expertise(seniority, yoe, hist_perf)

        capacity   = EMP_TYPE_CAPACITY[emp_type]

        # Seeded values — backfilled accurately in 06_backfill.py
        collab_score       = int(clamp(round(np.random.normal(7, 1.2)), 1, 10))
        days_since_leave   = random.choices(
            [random.randint(1, 30), random.randint(31, 120), random.randint(121, 365)],
            weights=[0.50, 0.30, 0.20]
        )[0]
        seed_overtime      = round(max(0.0, np.random.exponential(4)), 1)
        seed_proj_count    = random.choices([0, 1, 2, 3], weights=[0.25, 0.35, 0.25, 0.15])[0]
        seed_success_proj  = random.randint(1, 15) if seniority in ("Senior", "Lead", "Principal") \
                             else random.randint(0, 6)
        seed_failed_proj   = random.randint(0, max(1, seed_success_proj // 5))
        seed_avg_tcr       = clamp(round(np.random.normal(83, 10), 1), 40.0, 100.0)

        burnout     = calc_burnout_risk(seed_overtime, days_since_leave)
        stress_lv   = stress_from_burnout(burnout)
        leadership  = calc_leadership_potential(seniority, seed_success_proj, collab_score)

        prod_trend  = np.random.choice(PROD_TREND, p=PROD_TREND_W)
        is_avail    = seed_proj_count < 3

        created_at   = f"{hire_date} 09:00:00"
        last_updated = rand_datetime(date(2024, 6, 1), TODAY)

        rows.append({
            # Core identity
            "employee_id":                  emp_id,
            "first_name":                   first,
            "last_name":                    last,
            "email":                        email,
            "department":                   dept,
            "role":                         role,
            "seniority_level":              seniority,
            "employment_type":              emp_type,
            "hire_date":                    hire_date.isoformat(),
            "years_of_experience":          yoe,
            "current_salary":               salary,
            # Skills
            "primary_skills":               primary_skills,
            "secondary_skills":             secondary_skills,
            "certifications":               certifications,
            "technical_proficiency_score":  tech_score,
            "domain_expertise_score":       dom_score,
            # Availability
            "weekly_capacity_hours":        capacity,
            "is_available":                 is_avail,
            "current_project_count":        seed_proj_count,
            "preferred_work_hours":         random.choice(WORK_HOURS),
            "remote_work_status":           random.choice(REMOTE_STATUS),
            # Performance & well-being
            "historical_performance_score": hist_perf,
            "productivity_trend":           prod_trend,
            "average_task_completion_rate": seed_avg_tcr,
            "collaboration_score":          collab_score,
            "leadership_potential":         leadership,
            "stress_level":                 stress_lv,
            "burnout_risk_score":           burnout,
            "recent_overtime_hours":        seed_overtime,
            "days_since_last_leave":        days_since_leave,
            # Team history (backfilled)
            "preferred_team_size":          random.choice(TEAM_SIZE_PREF),
            "past_team_members":            "",          # backfilled in 06
            "successful_project_count":     seed_success_proj,
            "failed_project_count":         seed_failed_proj,
            # Timestamps
            "created_at":                   created_at,
            "last_updated":                 last_updated,
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
        start_date = rand_date(proj_start_base, date(2024, 9, 1))
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
                     else (random.randint(-5, 10) if completed else 0)
        is_on_sched= days_var >= 0

        pm_id      = random.choice(managers)

        # Resources — allocated from team capacity, consumed by status
        alloc      = round(random.uniform(400, 4000), 0)
        consumed_ratio = {
            "Planning":  random.uniform(0.02, 0.08),
            "Active":    random.uniform(0.30, 0.70),
            "On Hold":   random.uniform(0.20, 0.50),
            "Completed": random.uniform(0.88, 1.15),
            "Cancelled": random.uniform(0.10, 0.40),
        }[status]
        consumed   = round(alloc * consumed_ratio, 0)

        # Risk scores derived from complexity + schedule + milestones
        risk_base     = COMPLEXITY_RISK_BASE[complexity]

        total_ms   = random.randint(3, 12)
        comp_ms    = int(total_ms * comp_pct / 100)
        overdue_ms = random.randint(0, max(0, total_ms - comp_ms - 1)) if not completed else 0
        next_ms    = (start_date + timedelta(
                         days=int(duration * (comp_ms + 1) / max(total_ms, 1))
                     )).isoformat() if not completed and comp_ms < total_ms else None

        # scope_creep: ms growth + complexity rand
        ms_growth_factor = overdue_ms / max(total_ms, 1) * 100
        scope_creep = clamp(round(
            ms_growth_factor * 0.50 + risk_base * 0.40 + np.random.normal(0, 8), 1
        ), 0.0, 80.0)

        # delay_risk
        schedule_penalty = max(0, -days_var) * 1.5
        delay_risk = clamp(round(
            overdue_ms * 15 + schedule_penalty + scope_creep * 0.30
            + np.random.normal(0, 8), 1
        ), 5.0, 95.0)

        # budget_overrun_risk
        resource_excess = max(consumed_ratio - 0.50, 0) * 200
        budget_risk = clamp(round(
            resource_excess * 0.55 + scope_creep * 0.30 + np.random.normal(0, 8), 1
        ), 5.0, 90.0)

        # quality_risk: complexity + scope creep
        complexity_q = {"Low": 10, "Medium": 22, "High": 42, "Very High": 58}[complexity]
        quality_risk = clamp(round(
            complexity_q + scope_creep * 0.30 + np.random.normal(0, 10), 1
        ), 5.0, 90.0)

        # success_probability: inverse of risk
        complexity_penalty = {"Low": 5, "Medium": 15, "High": 28, "Very High": 42}[complexity]
        schedule_bonus     = 10 if is_on_sched else 0
        success_prob = clamp(round(
            90 - complexity_penalty + schedule_bonus + np.random.normal(0, 10), 1
        ), 10.0, 98.0)

        # next_milestone_risk: propagated from delay_risk
        next_ms_risk = clamp(round(
            delay_risk * 0.75 + overdue_ms * 5 + np.random.normal(0, 8), 1
        ), 5.0, 95.0) if next_ms else None

        stkh_sat  = clamp(round(np.random.normal(7.5, 1.2), 1), 3.0, 10.0) \
                    if completed else None
        roi_est   = round(random.uniform(20, 400), 1)

        pri_pool, _ = DEPT_SKILLS[dept]
        req_skills  = pick(pri_pool, k=random.randint(2, 5))

        created_at   = f"{start_date} 09:00:00"
        last_updated = rand_datetime(start_date, TODAY)

        rows.append({
            # Core
            "project_id":            proj_id,
            "project_name":          random.choice(PROJECT_NAMES) + f" {i}",
            "project_description":   f"{p_type} project for {dept} — {complexity} complexity.",
            "project_type":          p_type,
            "department":            dept,
            "priority":              priority,
            "budget":                budget,
            "complexity_level":      complexity,
            # Timeline
            "start_date":            start_date.isoformat(),
            "planned_end_date":      planned_end.isoformat(),
            "actual_end_date":       actual_end,
            "current_status":        status,
            "completion_percentage": comp_pct,
            "is_on_schedule":        is_on_sched,
            "days_ahead_behind":     days_var,
            # Team & resources (team_member_ids / team_size backfilled in 02)
            "project_manager_id":    pm_id,
            "team_member_ids":       "",         # backfilled
            "team_size":             0,          # backfilled
            "required_skills":       req_skills,
            "allocated_resources":   int(alloc),
            "consumed_resources":    int(consumed),
            # Risk
            "success_probability":   success_prob,
            "delay_risk_score":      delay_risk,
            "budget_overrun_risk":   budget_risk,
            "quality_risk_score":    quality_risk,
            "scope_creep_indicator": scope_creep,
            "stakeholder_satisfaction": stkh_sat,
            "roi_estimate":          roi_est,
            # Milestones
            "total_milestones":      total_ms,
            "completed_milestones":  comp_ms,
            "overdue_milestones":    overdue_ms,
            "next_milestone_date":   next_ms,
            "next_milestone_risk":   next_ms_risk,
            # Timestamps
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
    print(f"  OK {len(emp_df)} rows -> employees.csv")

    print("Generating projects...")
    proj_df = generate_projects(emp_df, NUM_PROJECTS)
    proj_df.to_csv(f"{OUT_DIR}/projects.csv", index=False)
    print(f"  OK {len(proj_df)} rows -> projects.csv")

    print("\nSanity checks:")
    print(f"  dept dist:\n{emp_df['department'].value_counts().to_string()}")
    print(f"  seniority dist:\n{emp_df['seniority_level'].value_counts().to_string()}")
    print(f"  project status dist:\n{proj_df['current_status'].value_counts().to_string()}")
    print(f"  PM ids valid: {proj_df['project_manager_id'].isin(emp_df['employee_id']).all()}")
    print(f"  tech_prof range: {emp_df['technical_proficiency_score'].min():.1f} - "
          f"{emp_df['technical_proficiency_score'].max():.1f}")
    print(f"  burnout_risk range: {emp_df['burnout_risk_score'].min():.1f} - "
          f"{emp_df['burnout_risk_score'].max():.1f}")
