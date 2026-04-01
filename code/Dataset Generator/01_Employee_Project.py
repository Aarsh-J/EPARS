"""
Part 1: Generate employees.csv and projects.csv
Dependencies: numpy, pandas (standard in most envs); no Faker needed
Usage: python generate_part1.py
Output: employees.csv, projects.csv in current directory
"""

import random
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta

random.seed(42)
np.random.seed(42)

# ─── Config ───────────────────────────────────────────────────────────────────
NUM_EMPLOYEES = 100
NUM_PROJECTS  = 80
OUT_DIR       = "./trial_dataset_generation"   # change if needed

# ─── Lookup tables ────────────────────────────────────────────────────────────
FIRST_NAMES = [
    "Aarna","Aarsh","Advaith","Ahana","Arjun","Priya","Rohan","Sneha","Vikram","Meera",
    "Kiran","Divya","Rajan","Ananya","Siddharth","Pooja","Neel","Isha","Rahul","Kavya",
    "John","Sarah","Michael","Emily","David","Jessica","Chris","Ashley","Daniel","Amanda",
    "James","Jennifer","Robert","Lisa","William","Karen","Richard","Nancy","Thomas","Betty",
    "Carlos","Maria","Jose","Ana","Miguel","Carmen","Luis","Rosa","Jorge","Isabel",
    "Raj","Priti","Amit","Sunita","Nikhil","Swati","Gaurav","Deepa","Vishal","Rekha",
    "Lena","Hans","Anna","Klaus","Ingrid","Erik","Astrid","Lars","Freya","Magnus",
    "Wei","Li","Fang","Jun","Mei","Hao","Xiu","Ping","Jing","Yang",
    "Alex","Jordan","Taylor","Morgan","Casey","Riley","Jamie","Avery","Quinn","Reese"
]
LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Martinez","Wilson",
    "Kumar","Sharma","Patel","Singh","Nair","Menon","Iyer","Reddy","Gupta","Shah",
    "Anderson","Taylor","Thomas","Jackson","White","Harris","Martin","Thompson","Young","Lewis",
    "Walker","Hall","Allen","Wright","Scott","Torres","Nguyen","Hill","Flores","Green",
    "Jain","Nambiar","Acharya","Bose","Chatterjee","Das","Ghosh","Mukherjee","Roy","Sen",
    "Muller","Schmidt","Fischer","Weber","Meyer","Wagner","Becker","Hoffman","Koch","Bauer",
    "Chen","Wang","Zhang","Liu","Yang","Huang","Zhao","Wu","Zhou","Sun"
]

DEPARTMENTS = ["Engineering","Sales","Marketing","HR","Finance","Design","Operations"]

# Role per department
DEPT_ROLES = {
    "Engineering":  ["Software Engineer","Senior Engineer","Team Lead","Developer","Principal Engineer"],
    "Sales":        ["Sales Representative","Account Manager","Sales Manager","Business Developer"],
    "Marketing":    ["Marketing Analyst","Content Strategist","Marketing Manager","SEO Specialist"],
    "HR":           ["HR Analyst","HR Manager","Recruiter","L&D Specialist"],
    "Finance":      ["Financial Analyst","Accountant","Finance Manager","Controller"],
    "Design":       ["UI/UX Designer","Graphic Designer","Design Lead","Product Designer"],
    "Operations":   ["Operations Analyst","Project Coordinator","Operations Manager","Scrum Master"],
}

SENIORITY = ["Junior","Mid","Senior","Lead","Principal"]
SENIORITY_WEIGHTS = [0.25, 0.30, 0.25, 0.15, 0.05]

EMP_TYPE = ["Full-time","Part-time","Contract"]
EMP_TYPE_WEIGHTS = [0.80, 0.10, 0.10]

TIMEZONES = ["IST","UTC","EST","PST","CST","GMT"]
REMOTE = ["Remote","Hybrid","Office"]
WORK_HOURS = ["9am-5pm","10am-6pm","8am-4pm","Flexible"]
TEAM_SIZE_PREF = ["Small (2-4)","Medium (5-8)","Large (9+)"]
PROD_TREND = ["Increasing","Stable","Decreasing"]
STRESS = ["Low","Medium","High"]

# Skills per department
DEPT_SKILLS = {
    "Engineering":  (["Python","Java","Go","C++","React","Node.js","AWS","Docker","Kubernetes","SQL","TypeScript","Rust"],
                     ["Git","Linux","Agile","REST APIs","Microservices"]),
    "Sales":        (["CRM","Salesforce","Negotiation","Lead Generation","B2B Sales"],
                     ["Excel","PowerPoint","Communication","Networking"]),
    "Marketing":    (["Google Analytics","SEO","Content Marketing","Social Media","HubSpot","Copywriting"],
                     ["Canva","Excel","Analytics","Email Marketing"]),
    "HR":           (["Recruitment","HRIS","Performance Management","Employee Relations","Training"],
                     ["Excel","Communication","Conflict Resolution","Onboarding"]),
    "Finance":      (["Financial Modeling","Excel","SAP","Accounting","Budgeting","Forecasting"],
                     ["SQL","PowerBI","Tableau","Communication"]),
    "Design":       (["Figma","Adobe XD","Sketch","Photoshop","Illustrator","UI/UX","Prototyping"],
                     ["CSS","HTML","User Research","Wireframing"]),
    "Operations":   (["Project Management","Jira","Process Improvement","Supply Chain","Lean","Six Sigma"],
                     ["Excel","Agile","Communication","Risk Management"]),
}

CERTS_BY_DEPT = {
    "Engineering":  ["AWS Certified","GCP Professional","Azure Certified","Kubernetes CKA","Scrum Master"],
    "Sales":        ["Salesforce Certified","HubSpot Certified","Sales Bootcamp"],
    "Marketing":    ["Google Analytics","Google Ads","HubSpot Marketing","Facebook Blueprint"],
    "HR":           ["SHRM-CP","PHR","CIPD","Talent Management"],
    "Finance":      ["CPA","CFA","FRM","CMA","ACCA"],
    "Design":       ["Google UX Design","Figma Certified","Adobe Certified"],
    "Operations":   ["PMP","Scrum Master","Six Sigma Green Belt","ITIL"],
}

LANGUAGES = ["English","Hindi","Spanish","French","German","Mandarin","Tamil","Telugu","Kannada","Arabic"]

# ─── Helpers ──────────────────────────────────────────────────────────────────
def rand_date(start: date, end: date) -> date:
    return start + timedelta(days=random.randint(0, (end - start).days))

def rand_datetime(start: date, end: date) -> str:
    d = rand_date(start, end)
    h, m = random.randint(8,18), random.choice([0,15,30,45])
    return f"{d} {h:02d}:{m:02d}:00"

def pick(lst, k=1, sep=","):
    k = max(1, k)  # ensure at least 1
    sample = random.sample(lst, min(k, len(lst)))
    return sep.join(sample) if len(sample) > 1 else sample[0]

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

# ─── EMPLOYEES ────────────────────────────────────────────────────────────────
def generate_employees(n=NUM_EMPLOYEES):
    rows = []
    used_emails = set()

    for i in range(1, n+1):
        emp_id = f"EMP{i:03d}"
        first  = random.choice(FIRST_NAMES)
        last   = random.choice(LAST_NAMES)

        # unique email
        base_email = f"{first.lower()}.{last.lower()}@company.com"
        email = base_email
        suffix = 1
        while email in used_emails:
            email = f"{first.lower()}.{last.lower()}{suffix}@company.com"
            suffix += 1
        used_emails.add(email)

        dept       = random.choice(DEPARTMENTS)
        role       = random.choice(DEPT_ROLES[dept])
        seniority  = np.random.choice(SENIORITY, p=SENIORITY_WEIGHTS)
        emp_type   = np.random.choice(EMP_TYPE, p=EMP_TYPE_WEIGHTS)

        # Experience aligned to seniority
        exp_range = {"Junior":(0.5,2.5),"Mid":(2.5,6),"Senior":(6,12),"Lead":(8,18),"Principal":(12,25)}
        lo, hi = exp_range[seniority]
        yoe = round(random.uniform(lo, hi), 1)

        # Hire date: roughly (yoe * 0.6) years ago, capped at 2015
        days_ago   = int(yoe * 0.6 * 365)
        hire_date  = date.today() - timedelta(days=max(days_ago, 90))
        hire_date  = max(hire_date, date(2015, 1, 1))

        # Salary aligned to seniority
        sal_range  = {"Junior":(40000,65000),"Mid":(60000,90000),"Senior":(85000,130000),
                      "Lead":(110000,160000),"Principal":(140000,200000)}
        salary     = random.randint(*sal_range[seniority])

        # Skills
        pri_pool, sec_pool = DEPT_SKILLS[dept]
        primary_skills   = pick(pri_pool, k=random.randint(2,4))
        secondary_skills = pick(sec_pool, k=random.randint(1,3))
        certs_pool       = CERTS_BY_DEPT[dept]
        certifications   = pick(certs_pool, k=random.randint(0,2)) if random.random() > 0.3 else "None"
        languages        = pick(LANGUAGES, k=random.randint(1,3))

        # Scores — senior = higher scores on average
        seniority_boost = {"Junior":0,"Mid":0.1,"Senior":0.2,"Lead":0.25,"Principal":0.3}[seniority]
        tech_score  = clamp(round(np.random.normal(6.0 + seniority_boost*4, 1.2), 1), 2.0, 10.0)
        domain_score= clamp(round(np.random.normal(6.0 + seniority_boost*4, 1.2), 1), 2.0, 10.0)

        # Capacity
        capacity = 40.0 if emp_type == "Full-time" else (20.0 if emp_type == "Part-time" else 35.0)
        proj_count  = random.randint(0, 3)
        is_available= proj_count < 3

        # Performance metrics — normal dist centred ~73
        hist_perf  = clamp(round(np.random.normal(73, 12), 1), 30.0, 100.0)
        task_comp  = clamp(round(np.random.normal(82, 10), 1), 40.0, 100.0)
        collab     = clamp(round(np.random.normal(7.2, 1.2), 1), 2.0, 10.0)
        comm       = clamp(round(np.random.normal(7.0, 1.2), 1), 2.0, 10.0)
        leadership = clamp(round(np.random.normal(6.0 + seniority_boost*3, 1.5), 1), 1.0, 10.0)

        # Stress & burnout — skewed low (most employees OK)
        stress_val = np.random.choice(STRESS, p=[0.45, 0.35, 0.20])
        burnout_mu = {"Low":20,"Medium":45,"High":70}[stress_val]
        burnout    = clamp(round(np.random.normal(burnout_mu, 12), 1), 0.0, 100.0)
        overtime   = round(max(0, np.random.exponential(5)), 1) if stress_val != "Low" else round(random.uniform(0,3),1)
        days_leave = random.choices(
            [random.randint(1,30), random.randint(30,120), random.randint(120,365)],
            weights=[0.5, 0.3, 0.2])[0]
        wlb        = clamp(round(np.random.normal(7.0 - (burnout/30), 1.2), 1), 1.0, 10.0)

        # Team history
        succ_proj  = random.randint(1, 20) if yoe > 1 else random.randint(0, 3)
        fail_proj  = random.randint(0, max(1, succ_proj // 5))
        cross_func = random.random() > 0.4
        mentoring  = random.random() > 0.5 if seniority in ["Senior","Lead","Principal"] else random.random() > 0.85

        # Timestamps
        created_at  = rand_datetime(hire_date, hire_date + timedelta(days=5))
        last_updated= rand_datetime(date(2024,1,1), date(2025,3,1))

        rows.append({
            "employee_id": emp_id,
            "first_name": first,
            "last_name": last,
            "email": email,
            "department": dept,
            "role": role,
            "seniority_level": seniority,
            "employment_type": emp_type,
            "hire_date": hire_date.isoformat(),
            "years_of_experience": yoe,
            "current_salary": salary,
            "primary_skills": primary_skills,
            "secondary_skills": secondary_skills,
            "certifications": certifications,
            "languages_known": languages,
            "technical_proficiency_score": tech_score,
            "domain_expertise_score": domain_score,
            "weekly_capacity_hours": capacity,
            "is_available": is_available,
            "current_project_count": proj_count,
            "preferred_work_hours": random.choice(WORK_HOURS),
            "timezone": random.choice(TIMEZONES),
            "remote_work_status": random.choice(REMOTE),
            "historical_performance_score": hist_perf,
            "productivity_trend": np.random.choice(PROD_TREND, p=[0.3,0.5,0.2]),
            "average_task_completion_rate": task_comp,
            "collaboration_score": collab,
            "communication_effectiveness": comm,
            "leadership_potential": leadership,
            "stress_level": stress_val,
            "burnout_risk_score": burnout,
            "recent_overtime_hours": overtime,
            "days_since_last_leave": days_leave,
            "work_life_balance_score": wlb,
            "preferred_team_size": random.choice(TEAM_SIZE_PREF),
            "past_team_members": None,   # filled after team_formations
            "successful_project_count": succ_proj,
            "failed_project_count": fail_proj,
            "cross_functional_experience": cross_func,
            "mentoring_experience": mentoring,
            "last_updated": last_updated,
            "created_at": created_at,
        })

    return pd.DataFrame(rows)


# ─── PROJECTS ─────────────────────────────────────────────────────────────────
PROJECT_TYPES = ["Product Development","Marketing","Internal","Research","Client Project"]
PROJ_STATUS   = ["Planning","Active","On Hold","Completed","Cancelled"]
COMPLEXITY    = ["Low","Medium","High","Very High"]
PRIORITY      = ["Low","Medium","High","Critical"]
BIZ_VALUE     = ["Low","Medium","High","Critical"]
CUST_IMPACT   = ["None","Minor","Moderate","Major"]
COMM_FREQ     = ["Daily","Weekly","Bi-weekly"]
COLLAB_TOOLS  = ["Slack,Jira,Confluence","Teams,Azure DevOps","Slack,Trello","Jira,Confluence,Zoom","Asana,Slack"]

PROJECT_NAMES = [
    "Mobile App Redesign","Customer Portal Upgrade","Data Warehouse Migration","AI Chatbot Integration",
    "Sales Automation Pipeline","HR Self-Service Portal","Security Compliance Audit","Cloud Infrastructure Overhaul",
    "Marketing Analytics Dashboard","Employee Onboarding System","Real-Time Monitoring Platform","API Gateway Modernization",
    "Recommendation Engine","Fraud Detection System","Supply Chain Optimizer","Digital Twin Prototype",
    "Q1 Marketing Campaign","Brand Refresh Initiative","SEO Content Strategy","Lead Generation Funnel",
    "Financial Reporting Automation","Budget Forecasting Tool","Expense Management System","Payroll Integration",
    "Design System Library","User Research Study","Accessibility Compliance Project","Prototype Testing Sprint",
    "Process Automation Initiative","Vendor Management Portal","Capacity Planning Tool","Incident Response Framework",
    "Performance Review Overhaul","Learning Management System","Internal Knowledge Base","Code Quality Initiative",
    "DevOps Transformation","Microservices Migration","Data Privacy Compliance","Customer Feedback Platform"
]

def generate_projects(employees_df, n=NUM_PROJECTS):
    emp_ids = employees_df["employee_id"].tolist()
    # Managers: Senior / Lead / Principal employees
    managers = employees_df[
        employees_df["seniority_level"].isin(["Senior","Lead","Principal"])
    ]["employee_id"].tolist()
    if not managers:
        managers = emp_ids[:20]

    rows = []
    proj_start_base = date(2023, 1, 1)

    for i in range(1, n+1):
        proj_id = f"PRJ{i:03d}"
        dept    = random.choice(DEPARTMENTS)
        p_type  = random.choice(PROJECT_TYPES)
        priority= np.random.choice(PRIORITY, p=[0.10,0.35,0.35,0.20])
        complexity = np.random.choice(COMPLEXITY, p=[0.15,0.35,0.35,0.15])

        # Budget aligned to complexity
        budgets = {"Low":(20000,80000),"Medium":(80000,300000),"High":(300000,800000),"Very High":(800000,2000000)}
        budget  = round(random.uniform(*budgets[complexity]), 2)

        # Timeline
        start_date  = rand_date(proj_start_base, date(2024, 6, 1))
        duration    = {"Low":30,"Medium":90,"High":180,"Very High":270}[complexity]
        duration   += random.randint(-20, 40)
        planned_end = start_date + timedelta(days=max(duration, 20))

        # Status probabilities
        status = np.random.choice(
            PROJ_STATUS, p=[0.10, 0.40, 0.10, 0.35, 0.05]
        )

        completed   = status == "Completed"
        actual_end  = (start_date + timedelta(days=duration + random.randint(-15,30))).isoformat() if completed else None
        comp_pct    = 100.0 if completed else (0.0 if status == "Planning" else round(random.uniform(5,95),1))

        # Schedule variance
        days_var    = random.randint(-20, 20) if status == "Active" else (random.randint(0,10) if completed else 0)
        is_on_sched = days_var >= -5

        # Team
        team_size   = random.randint(3, 15)
        pm_id       = random.choice(managers)
        members     = random.sample([e for e in emp_ids if e != pm_id], min(team_size-1, len(emp_ids)-1))
        members_str = ",".join(members)

        # Resource usage
        alloc  = round(random.uniform(500, 5000), 0)
        consumed_pct = {"Planning":0.05,"Active":random.uniform(0.3,0.7),"On Hold":random.uniform(0.2,0.5),
                        "Completed":random.uniform(0.9,1.15),"Cancelled":random.uniform(0.1,0.4)}[status]
        consumed = round(alloc * consumed_pct, 0)

        # Risk scores — higher complexity = higher risk
        risk_base = {"Low":20,"Medium":40,"High":60,"Very High":75}[complexity]
        success_prob    = clamp(round(np.random.normal(100 - risk_base, 15), 1), 10.0, 98.0)
        delay_risk      = clamp(round(np.random.normal(risk_base, 15), 1), 5.0, 95.0)
        budget_risk     = clamp(round(np.random.normal(risk_base * 0.7, 12), 1), 5.0, 90.0)
        quality_risk    = clamp(round(np.random.normal(risk_base * 0.6, 12), 1), 5.0, 90.0)
        scope_creep     = clamp(round(np.random.normal(risk_base * 0.5, 10), 1), 0.0, 80.0)
        stakeholder_sat = clamp(round(np.random.normal(7.5, 1.2), 1), 3.0, 10.0)

        # Milestones
        total_ms    = random.randint(3, 12)
        comp_ms     = int(total_ms * comp_pct / 100)
        overdue_ms  = random.randint(0, max(0, total_ms - comp_ms - 1)) if not completed else 0
        next_ms     = (start_date + timedelta(days=int(duration * (comp_ms+1)/total_ms))).isoformat() \
                      if not completed and comp_ms < total_ms else None
        next_ms_risk= clamp(round(np.random.normal(delay_risk, 10), 1), 5.0, 95.0) if next_ms else None

        # Skills from dept
        pri_pool, _ = DEPT_SKILLS[dept]
        req_skills  = pick(pri_pool, k=random.randint(2,5))

        # Misc
        client_id   = f"CLT{random.randint(1,30):03d}" if p_type == "Client Project" else None
        biz_value   = np.random.choice(BIZ_VALUE, p=[0.10,0.30,0.40,0.20])
        roi_est     = round(random.uniform(20, 400), 1)
        strat_imp   = clamp(round(np.random.normal(6.5, 1.5), 1), 1.0, 10.0)
        cust_impact = np.random.choice(CUST_IMPACT, p=[0.20,0.25,0.35,0.20])
        doc_quality = clamp(round(np.random.normal(7.0, 1.3), 1), 2.0, 10.0)
        mtg_hrs     = round(random.uniform(1, 12), 1)

        created_at   = rand_datetime(start_date - timedelta(days=30), start_date)
        last_updated = rand_datetime(start_date, date(2025, 3, 1))

        rows.append({
            "project_id": proj_id,
            "project_name": random.choice(PROJECT_NAMES) + f" {i}",
            "project_description": f"{p_type} project for {dept} department — {complexity} complexity.",
            "project_type": p_type,
            "client_id": client_id,
            "department": dept,
            "priority": priority,
            "budget": budget,
            "complexity_level": complexity,
            "start_date": start_date.isoformat(),
            "planned_end_date": planned_end.isoformat(),
            "actual_end_date": actual_end,
            "current_status": status,
            "completion_percentage": comp_pct,
            "is_on_schedule": is_on_sched,
            "days_ahead_behind": days_var,
            "project_manager_id": pm_id,
            "team_member_ids": members_str,
            "team_size": team_size,
            "required_skills": req_skills,
            "allocated_resources": int(alloc),
            "consumed_resources": int(consumed),
            "success_probability": success_prob,
            "delay_risk_score": delay_risk,
            "budget_overrun_risk": budget_risk,
            "quality_risk_score": quality_risk,
            "scope_creep_indicator": scope_creep,
            "stakeholder_satisfaction": stakeholder_sat,
            "total_milestones": total_ms,
            "completed_milestones": comp_ms,
            "overdue_milestones": overdue_ms,
            "next_milestone_date": next_ms,
            "next_milestone_risk": next_ms_risk,
            "communication_frequency": random.choice(COMM_FREQ),
            "meeting_hours_per_week": mtg_hrs,
            "collaboration_tools": random.choice(COLLAB_TOOLS),
            "documentation_quality": doc_quality,
            "business_value": biz_value,
            "roi_estimate": roi_est,
            "strategic_importance": strat_imp,
            "customer_impact": cust_impact,
            "created_at": created_at,
            "last_updated": last_updated,
        })

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating employees...")
    emp_df = generate_employees(NUM_EMPLOYEES)
    emp_path = f"{OUT_DIR}/employees.csv"
    emp_df.to_csv(emp_path, index=False)
    print(f"  ✓ {len(emp_df)} rows → {emp_path}")

    print("Generating projects...")
    proj_df = generate_projects(emp_df, NUM_PROJECTS)
    proj_path = f"{OUT_DIR}/projects.csv"
    proj_df.to_csv(proj_path, index=False)
    print(f"  ✓ {len(proj_df)} rows → {proj_path}")

    # Quick sanity checks
    print("\nSanity checks:")
    print(f"  Employees — dept distribution:\n{emp_df['department'].value_counts().to_string()}")
    print(f"  Employees — seniority distribution:\n{emp_df['seniority_level'].value_counts().to_string()}")
    print(f"  Projects  — status distribution:\n{proj_df['current_status'].value_counts().to_string()}")
    print(f"  Projects  — all manager IDs valid: "
          f"{proj_df['project_manager_id'].isin(emp_df['employee_id']).all()}")
    print("\nDone. Files saved.")