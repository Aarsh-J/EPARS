"""
Part 4: Generate team_formations.csv, performance_reviews.csv, feedback.csv
Dependencies: numpy, pandas
Requires: employees.csv, projects.csv, tasks.csv, task_assignments.csv (Parts 1 & 2)
Usage: python generate_part4.py
Output: team_formations.csv, performance_reviews.csv, feedback.csv
"""

import random
import numpy as np
import pandas as pd
from datetime import date, timedelta

random.seed(42)
np.random.seed(42)

OUT_DIR = "."

# ─── Helpers ──────────────────────────────────────────────────────────────────
def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def rand_date(start: date, end: date) -> date:
    if start >= end:
        return start
    return start + timedelta(days=random.randint(0, (end - start).days))

def rand_datetime(d: date) -> str:
    h, m = random.randint(8, 18), random.choice([0, 15, 30, 45])
    return f"{d} {h:02d}:{m:02d}:00"

def normal_score(mu, sigma, lo=1.0, hi=10.0):
    return clamp(round(np.random.normal(mu, sigma), 1), lo, hi)

def normal_pct(mu, sigma, lo=0.0, hi=100.0):
    return clamp(round(np.random.normal(mu, sigma), 1), lo, hi)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TEAM FORMATIONS
# ═══════════════════════════════════════════════════════════════════════════════
NUM_TEAMS = 150

FORMATION_METHOD  = ["Manual", "AI-Recommended", "Hybrid"]
FORMATION_WEIGHTS = [0.35, 0.40, 0.25]
TEAM_STATUS       = ["Active", "Completed", "Disbanded", "On Hold"]
TEAM_STATUS_W     = [0.30, 0.45, 0.15, 0.10]
DISSOLVE_REASON   = ["Project Complete", "Reorganization", "Budget Cut", None]

TEAM_NAMES = [
    "Alpha Squad", "Beta Crew", "Delta Force", "Gamma Team", "Omega Unit",
    "Phoenix Team", "Nexus Crew", "Titan Squad", "Vortex Team", "Apex Unit",
    "Backend Crew", "Frontend Force", "Data Squad", "Design Dream Team",
    "DevOps Warriors", "QA Guardians", "Platform Team", "Growth Squad",
    "Research Collective", "Strategy Unit", "Innovation Lab", "Core Team",
    "Velocity Squad", "Agile Avengers", "Sprint Masters", "Cloud Ninjas",
    "Security Squad", "AI Task Force", "Analytics Crew", "Mobile Team",
]

FEEDBACK_SUMMARIES = [
    "Great collaboration and clear communication throughout",
    "Strong technical execution but documentation needs improvement",
    "Team worked well under pressure, met all major milestones",
    "Communication gaps slowed progress in early sprints",
    "Excellent cross-functional coordination and knowledge sharing",
    "Skill balance was ideal for the project requirements",
    "Some workload imbalance noted, but team adapted quickly",
    "High cohesion team, delivered above expectations",
    None,
]

LESSONS_LEARNED = [
    "Need daily standups for better alignment",
    "Clear role definitions improved efficiency significantly",
    "Earlier risk identification would have prevented delays",
    "Async communication tools reduced meeting overhead",
    "Pair programming improved code quality noticeably",
    "Regular retrospectives helped resolve conflicts early",
    "Cross-training team members reduced single points of failure",
    None,
]

def generate_team_formations(employees_df, projects_df):
    emp_ids  = employees_df["employee_id"].tolist()
    proj_ids = projects_df["project_id"].tolist()

    # Leads: Senior / Lead / Principal
    leads = employees_df[
        employees_df["seniority_level"].isin(["Senior", "Lead", "Principal"])
    ]["employee_id"].tolist()
    if not leads:
        leads = emp_ids[:20]

    # Map project → dates & status
    proj_meta = {
        row["project_id"]: {
            "start":  date.fromisoformat(row["start_date"]),
            "end":    date.fromisoformat(row["planned_end_date"]),
            "status": row["current_status"],
        }
        for _, row in projects_df.iterrows()
    }

    rows = []
    used_team_names = []

    for i in range(1, NUM_TEAMS + 1):
        team_id  = f"TEAM{i:03d}"
        proj_id  = random.choice(proj_ids)
        meta     = proj_meta[proj_id]
        p_start  = meta["start"]
        p_end    = meta["end"]
        p_status = meta["status"]

        form_date = rand_date(p_start, p_start + timedelta(days=14))
        method    = np.random.choice(FORMATION_METHOD, p=FORMATION_WEIGHTS)

        # Team composition
        team_size  = random.randint(3, 12)
        lead_id    = random.choice(leads)
        candidates = [e for e in emp_ids if e != lead_id]
        members    = random.sample(candidates, min(team_size - 1, len(candidates)))
        all_members= [lead_id] + members
        member_str = ",".join(members)

        # Role & seniority distribution (simplified JSON strings)
        roles_avail = ["Developer", "Designer", "QA", "Analyst", "Manager", "DevOps"]
        role_dist   = {r: random.randint(0, max(1, team_size // len(roles_avail)))
                       for r in random.sample(roles_avail, min(4, team_size))}
        # Ensure total matches team_size roughly
        role_dist_str = str(role_dist).replace("'", '"')

        sen_dist   = {"Junior": random.randint(0,2), "Mid": random.randint(1,3),
                      "Senior": random.randint(1,2), "Lead": random.randint(0,1)}
        sen_dist_str = str(sen_dist).replace("'", '"')

        # Team characteristic scores
        skill_div   = normal_pct(70, 15)
        exp_balance = normal_pct(72, 14)
        collab_hist = normal_pct(65, 18)
        comm_compat = normal_pct(75, 13)
        wl_balance  = normal_pct(72, 15)
        tz_compat   = normal_pct(80, 15)

        pred_success = normal_pct(72, 14)

        # Outcomes — depends on project status
        completed    = p_status == "Completed" and random.random() > 0.15
        actual_perf  = normal_pct(73, 14) if completed else None
        team_prod    = normal_pct(74, 13) if completed else normal_pct(68, 14)
        cohesion     = normal_score(7.2, 1.3)
        conflicts    = random.choices([0, 1, 2, 3], weights=[0.55, 0.28, 0.12, 0.05])[0]
        collab_eff   = normal_score(7.3, 1.2)

        # Project outcome metrics
        proj_done    = completed
        comp_days    = round((p_end - form_date).days * random.uniform(0.85, 1.20), 1) if completed else None
        met_deadline = (random.random() > 0.25) if completed else None
        quality_rat  = normal_score(7.6, 1.2) if completed else None
        budget_adh   = clamp(round(np.random.normal(100, 12), 1), 70, 140) if completed else None
        stkh_sat     = normal_score(7.5, 1.2) if completed else None

        # Optimization
        eff_ratio    = clamp(round(np.random.normal(1.0, 0.15), 2), 0.6, 1.5)
        res_util     = normal_pct(82, 12)
        skill_util   = normal_pct(78, 13)
        improve_ops  = random.randint(0, 5)

        # Status & lifecycle
        status = np.random.choice(TEAM_STATUS, p=TEAM_STATUS_W)
        if p_status == "Completed":
            status = "Completed"
        dissolve_date = p_end.isoformat() if status in ["Completed", "Disbanded"] else None
        dissolve_rsn  = random.choice(DISSOLVE_REASON[:2]) if status in ["Completed", "Disbanded"] else None

        # Name — allow repeats with suffix if exhausted
        base_name = random.choice(TEAM_NAMES)
        used_team_names.append(base_name)
        count = used_team_names.count(base_name)
        team_name = base_name if count == 1 else f"{base_name} {count}"

        would_reform = (random.random() > 0.3) if completed else None

        rows.append({
            "team_id":                   team_id,
            "team_name":                 team_name,
            "project_id":                proj_id,
            "formation_date":            form_date.isoformat(),
            "formation_method":          method,
            "team_lead_id":              lead_id,
            "member_ids":                member_str,
            "team_size":                 team_size,
            "role_distribution":         role_dist_str,
            "seniority_mix":             sen_dist_str,
            "skill_diversity_score":     skill_div,
            "experience_balance_score":  exp_balance,
            "collaborative_history_score": collab_hist,
            "communication_compatibility": comm_compat,
            "workload_balance_score":    wl_balance,
            "timezone_compatibility":    tz_compat,
            "predicted_success_rate":    pred_success,
            "actual_performance_score":  actual_perf,
            "team_productivity_score":   team_prod,
            "team_cohesion_score":       cohesion,
            "conflict_incidents":        conflicts,
            "collaboration_effectiveness": collab_eff,
            "project_completed":         proj_done,
            "completion_time_days":      comp_days,
            "met_deadline":              met_deadline,
            "quality_rating":            quality_rat,
            "budget_adherence":          budget_adh,
            "stakeholder_satisfaction":  stkh_sat,
            "team_efficiency_ratio":     eff_ratio,
            "resource_utilization":      res_util,
            "skill_utilization_rate":    skill_util,
            "improvement_opportunities": improve_ops,
            "team_feedback_summary":     random.choice(FEEDBACK_SUMMARIES),
            "lessons_learned":           random.choice(LESSONS_LEARNED),
            "would_reform_team":         would_reform,
            "team_status":               status,
            "dissolution_date":          dissolve_date,
            "dissolution_reason":        dissolve_rsn,
            "created_at":                rand_datetime(form_date),
            "last_updated":              rand_datetime(
                                             rand_date(form_date, date(2025, 3, 1))
                                         ),
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PERFORMANCE REVIEWS
# ═══════════════════════════════════════════════════════════════════════════════
NUM_REVIEWS = 400

REVIEW_TYPES   = ["Annual", "Quarterly", "Project-based", "Probationary"]
REVIEW_WEIGHTS = [0.40, 0.35, 0.15, 0.10]
PROMO_READINESS= ["Not Ready", "Ready in 6-12 months", "Ready Now"]
PERF_RATING    = ["Needs Improvement", "Meets Expectations", "Exceeds Expectations", "Outstanding"]
PERF_RATING_W  = [0.10, 0.40, 0.35, 0.15]

STRENGTHS_POOL = [
    "Technical expertise", "Problem solving", "Communication", "Leadership",
    "Collaboration", "Time management", "Innovation", "Mentoring",
    "Attention to detail", "Adaptability", "Reliability", "Initiative",
]
WEAKNESS_POOL = [
    "Documentation", "Public speaking", "Time estimation", "Delegation",
    "Conflict resolution", "Strategic thinking", "Cross-team communication",
    "Process adherence", "Work-life balance", "Stakeholder management",
]
TRAINING_POOL = [
    "Leadership Training", "AWS Certification", "Agile Course", "Communication Workshop",
    "Data Analysis Bootcamp", "PMP Certification", "Scrum Master Training",
    "Technical Writing", "Python Advanced", "Cloud Architecture",
]
MANAGER_COMMENTS = [
    "Strong performer who consistently delivers high-quality work.",
    "Shows great initiative and is a reliable team member.",
    "Has significant potential for growth with focused development.",
    "Excellent collaborator who elevates the entire team.",
    "Demonstrates strong technical skills with room for soft-skill growth.",
    "A dependable contributor who meets expectations consistently.",
    "Outstanding performance this period — exceeds on all fronts.",
    "Needs to focus on delivery timelines and communication.",
]
PEER_FEEDBACK = [
    "Great collaborator, always willing to help the team.",
    "Brings strong expertise and shares knowledge freely.",
    "Reliable and communicates blockers early.",
    "Could improve on proactively sharing updates.",
    "A pleasure to work with — highly recommended for future teams.",
    "Strong technical contributor, great pair-programming partner.",
]
ACHIEVEMENTS_POOL = [
    "Led successful product launch ahead of schedule",
    "Mentored 2 junior team members",
    "Reduced system latency by 40%",
    "Delivered critical feature with zero post-release bugs",
    "Improved test coverage from 45% to 82%",
    "Automated deployment pipeline saving 5hrs/week",
    "Won internal hackathon with innovative prototype",
    "Resolved major production incident within SLA",
]

def generate_performance_reviews(employees_df, projects_df, tasks_asg_df):
    emp_ids   = employees_df["employee_id"].tolist()
    reviewers = employees_df[
        employees_df["seniority_level"].isin(["Senior", "Lead", "Principal"])
    ]["employee_id"].tolist()

    # Map employee → hire_date for realistic period windows
    hire_map = {row["employee_id"]: date.fromisoformat(row["hire_date"])
                for _, row in employees_df.iterrows()}
    perf_map = {row["employee_id"]: row["historical_performance_score"]
                for _, row in employees_df.iterrows()}

    rows = []
    for i in range(1, NUM_REVIEWS + 1):
        rev_id   = f"REV{i:04d}"
        emp_id   = random.choice(emp_ids)
        reviewer = random.choice([r for r in reviewers if r != emp_id] or reviewers)

        hire_dt  = hire_map[emp_id]
        base_perf= perf_map[emp_id]

        # Review period
        rev_type = np.random.choice(REVIEW_TYPES, p=REVIEW_WEIGHTS)
        period_months = {"Annual": 12, "Quarterly": 3,
                         "Project-based": 3, "Probationary": 3}[rev_type]
        period_end   = rand_date(max(hire_dt + timedelta(days=180), date(2023, 6, 1)),
                                 date(2025, 1, 1))
        period_start = period_end - timedelta(days=period_months * 30)
        review_date  = period_end + timedelta(days=random.randint(5, 20))

        # Core performance scores — anchored to employee's historical score
        perf_mu = base_perf
        overall  = normal_pct(perf_mu, 10)
        norm_perf= normal_pct(perf_mu - 2, 10)   # peer-adjusted slightly lower

        # Skill scores (0-10)
        tech_comp  = normal_score(overall / 11, 0.9)
        domain_kn  = normal_score(overall / 11, 0.9)
        prob_solv  = normal_score(overall / 11, 1.0)
        innovation = normal_score(overall / 12, 1.1)
        quality_wk = normal_score(overall / 11, 0.8)
        prod_score = normal_score(overall / 11, 0.9)

        # Soft skills
        comm_score  = normal_score(7.0, 1.2)
        collab_score= normal_score(7.2, 1.1)
        lead_score  = normal_score(6.5, 1.4)
        init_score  = normal_score(6.8, 1.2)
        adapt_score = normal_score(7.0, 1.1)
        reli_score  = normal_score(7.5, 1.0)
        time_score  = normal_score(7.0, 1.2)

        # Quantitative
        tasks_done  = random.randint(15, 150)
        projs_done  = random.randint(1, 8)
        avg_quality = normal_score(7.5, 1.0)
        otd_rate    = normal_pct(82, 12)
        prod_vs_peers= clamp(round(np.random.normal(0, 12), 1), -30, 40)
        total_hrs   = round(random.uniform(600, 1400), 0)
        ot_hrs      = round(max(0, np.random.exponential(25)), 1)
        util_rate   = normal_pct(85, 10)

        # Areas
        strengths   = ",".join(random.sample(STRENGTHS_POOL, k=random.randint(2, 4)))
        weaknesses  = ",".join(random.sample(WEAKNESS_POOL,  k=random.randint(1, 3)))
        achievements= random.choice(ACHIEVEMENTS_POOL)
        exceeded_areas = ",".join(random.sample(STRENGTHS_POOL, k=random.randint(1, 3)))
        improve_areas  = ",".join(random.sample(WEAKNESS_POOL, k=random.randint(1, 3)))
        dev_goals   = f"Complete {random.choice(TRAINING_POOL)}, improve {random.choice(WEAKNESS_POOL).lower()}"

        # Recommendations
        training_recs  = ",".join(random.sample(TRAINING_POOL, k=random.randint(1, 3)))
        next_review    = (review_date + timedelta(days=90 if rev_type == "Quarterly" else 365)).isoformat()
        follow_up      = random.random() > 0.65

        # Promotion & salary
        promo_ready    = np.random.choice(PROMO_READINESS,
                            p=[0.45, 0.35, 0.20] if overall >= 75 else [0.70, 0.25, 0.05])
        promo_rec      = promo_ready == "Ready Now"
        sal_inc_rec    = overall >= 70
        sal_inc_pct    = round(random.choice([0, 3, 5, 7, 10, 15])
                               if sal_inc_rec else 0, 1)
        bonus_rec      = round(random.choice([0, 1000, 2000, 5000, 10000])
                               if overall >= 75 else 0, 1)
        training_rec   = random.random() > 0.3

        perf_rating    = np.random.choice(PERF_RATING, p=PERF_RATING_W)
        self_assess    = normal_score(overall / 11, 0.8)

        rows.append({
            "review_id":                    rev_id,
            "employee_id":                  emp_id,
            "reviewer_id":                  reviewer,
            "review_period_start":          period_start.isoformat(),
            "review_period_end":            period_end.isoformat(),
            "review_date":                  review_date.isoformat(),
            "review_type":                  rev_type,
            "overall_performance_score":    overall,
            "normalized_performance_score": norm_perf,
            "technical_competence_score":   tech_comp,
            "domain_knowledge_score":       domain_kn,
            "problem_solving_score":        prob_solv,
            "innovation_score":             innovation,
            "quality_of_work_score":        quality_wk,
            "productivity_score":           prod_score,
            "communication_score":          comm_score,
            "collaboration_score":          collab_score,
            "leadership_score":             lead_score,
            "initiative_score":             init_score,
            "adaptability_score":           adapt_score,
            "reliability_score":            reli_score,
            "time_management_score":        time_score,
            "tasks_completed":              tasks_done,
            "projects_completed":           projs_done,
            "average_task_quality":         avg_quality,
            "on_time_delivery_rate":        otd_rate,
            "productivity_vs_peers":        prod_vs_peers,
            "total_hours_worked":           total_hrs,
            "overtime_hours":               ot_hrs,
            "utilization_rate":             util_rate,
            "strengths":                    strengths,
            "achievements":                 achievements,
            "exceeded_expectations_areas":  exceeded_areas,
            "weaknesses":                   weaknesses,
            "improvement_areas":            improve_areas,
            "development_goals":            dev_goals,
            "reviewer_comments":            random.choice(MANAGER_COMMENTS),
            "recommended_actions":          f"Focus on {random.choice(WEAKNESS_POOL).lower()}",
            "promotion_recommended":        promo_rec,
            "salary_increase_recommended":  sal_inc_rec,
            "salary_increase_percentage":   sal_inc_pct,
            "training_recommended":         training_rec,
            "training_areas":               training_recs,
            "performance_rating":           perf_rating,
            "manager_comments":             random.choice(MANAGER_COMMENTS),
            "self_assessment_score":        self_assess,
            "peer_feedback_summary":        random.choice(PEER_FEEDBACK),
            "promotion_readiness":          promo_ready,
            "salary_adjustment_recommendation": sal_inc_pct,
            "bonus_recommendation":         bonus_rec,
            "training_recommendations":     training_recs,
            "next_review_date":             next_review,
            "follow_up_required":           follow_up,
            "created_at":                   rand_datetime(review_date),
            "last_updated":                 rand_datetime(review_date),
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. FEEDBACK
# ═══════════════════════════════════════════════════════════════════════════════
NUM_FEEDBACK = 2000

FB_TYPES     = ["Task Completion", "Project Review", "Peer Feedback", "Self Assessment"]
FB_TYPES_W   = [0.35, 0.25, 0.30, 0.10]
FB_CATEGORY  = ["Technical Skills", "Communication", "Leadership", "Quality", "Teamwork"]
SENTIMENT    = ["Very Negative", "Negative", "Neutral", "Positive", "Very Positive"]
SENTIMENT_W  = [0.05, 0.10, 0.15, 0.45, 0.25]
TONE         = ["Constructive", "Critical", "Encouraging", "Mixed"]
TONE_W       = [0.40, 0.15, 0.30, 0.15]
PRIORITY_LVL = ["Low", "Medium", "High"]
VISIBILITY   = ["Private", "Team", "Manager Only", "Public"]
VISIBILITY_W = [0.25, 0.30, 0.30, 0.15]

POSITIVE_ASPECTS_POOL = [
    "Clear communication", "On-time delivery", "High quality output",
    "Proactive problem solving", "Strong collaboration", "Attention to detail",
    "Technical depth", "Team support", "Initiative shown", "Reliable execution",
]
IMPROVE_AREAS_POOL = [
    "Documentation quality", "Testing coverage", "Time estimation accuracy",
    "Stakeholder updates", "Code readability", "Proactive communication",
    "Deadline adherence", "Cross-team alignment", "Technical depth", "Process adherence",
]
SUGGESTIONS_POOL = [
    "Consider adding more unit tests to improve coverage",
    "Document API endpoints before handoff",
    "Schedule earlier check-ins with stakeholders",
    "Break large tasks into smaller trackable subtasks",
    "Improve commit message quality for better traceability",
    "Set up automated alerts for deployment issues",
    "Conduct a brief knowledge-sharing session with the team",
    "Request early feedback instead of waiting until delivery",
    None,
]
FB_TEXT_POOL = [
    "Delivered the task with great attention to detail and minimal rework needed.",
    "Strong collaboration throughout the sprint, kept the team unblocked.",
    "Quality of deliverables was high, stakeholders were satisfied.",
    "Communication was proactive and clear during the entire project phase.",
    "Technical execution was excellent but documentation was lacking.",
    "Showed great initiative in identifying and resolving blockers early.",
    "Met all deadlines and maintained consistent quality standards.",
    "Good work overall, with some areas to improve in cross-team coordination.",
    "Exceeded expectations on the technical front, peer feedback is very positive.",
    "Delivery was slightly delayed but final output quality was strong.",
]
ACTION_ITEMS_POOL = [
    "Complete training,Review documentation",
    "Improve test coverage,Update runbook",
    "Schedule 1:1 with manager,Review goals",
    "Enroll in leadership course,Improve delegation",
    "Attend communication workshop",
    None,
]
RECIPIENT_RESPONSES = [
    "Thank you for the feedback, will work on documentation.",
    "Appreciate the recognition, will continue improving.",
    "Acknowledged — will focus on the suggested areas.",
    "Feedback received and noted, will discuss with manager.",
    None, None,
]

def generate_feedback(employees_df, tasks_df, projects_df, teams_df):
    emp_ids  = employees_df["employee_id"].tolist()
    task_ids = tasks_df["task_id"].tolist()
    proj_ids = projects_df["project_id"].tolist()
    team_ids = teams_df["team_id"].tolist()

    rows = []
    for i in range(1, NUM_FEEDBACK + 1):
        fb_id    = f"FDB{i:04d}"
        fb_type  = np.random.choice(FB_TYPES, p=FB_TYPES_W)
        recipient= random.choice(emp_ids)
        provider = random.choice([e for e in emp_ids if e != recipient] + ["SYSTEM"])

        fb_date  = rand_date(date(2023, 6, 1), date(2025, 2, 28))

        # Context IDs based on type
        rel_task = random.choice(task_ids) if fb_type == "Task Completion" else None
        rel_proj = random.choice(proj_ids) if fb_type in ["Project Review", "Task Completion"] else None
        rel_team = random.choice(team_ids) if fb_type == "Project Review" else None

        # Ratings — correlated with each other
        sentiment_cat = np.random.choice(SENTIMENT, p=SENTIMENT_W)
        base_rating   = {"Very Negative": 3.0, "Negative": 4.5, "Neutral": 6.0,
                         "Positive": 7.8, "Very Positive": 9.0}[sentiment_cat]
        overall_rat   = normal_score(base_rating, 0.8)
        quality_rat   = normal_score(base_rating, 0.9)
        timeliness_rat= normal_score(base_rating, 1.0)
        collab_rat    = normal_score(base_rating, 0.9)
        comm_rat      = normal_score(base_rating, 1.0)
        innov_rat     = normal_score(base_rating, 1.1)

        # Sentiment score (-100 to 100)
        sent_score = clamp(round(
            {"Very Negative": -70, "Negative": -35, "Neutral": 5,
             "Positive": 55, "Very Positive": 82}[sentiment_cat]
            + np.random.normal(0, 10), 1), -100, 100)

        tone       = np.random.choice(TONE, p=TONE_W)
        actionable = random.random() > 0.35
        action_items = random.choice(ACTION_ITEMS_POOL) if actionable else None
        priority   = np.random.choice(PRIORITY_LVL, p=[0.30, 0.45, 0.25])
        follow_up  = actionable and random.random() > 0.5
        fu_date    = (fb_date + timedelta(days=random.randint(7, 30))).isoformat() \
                     if follow_up else None

        acknowledged   = random.random() > 0.25
        ack_date       = (fb_date + timedelta(days=random.randint(1, 5))).isoformat() \
                         if acknowledged else None
        has_response   = acknowledged and random.random() > 0.55
        resp_text      = random.choice(RECIPIENT_RESPONSES) if has_response else None
        resp_date      = (fb_date + timedelta(days=random.randint(2, 7))).isoformat() \
                         if has_response and resp_text else None

        rows.append({
            "feedback_id":             fb_id,
            "feedback_type":           fb_type,
            "provider_id":             provider,
            "recipient_id":            recipient,
            "feedback_date":           fb_date.isoformat(),
            "related_task_id":         rel_task,
            "related_project_id":      rel_proj,
            "related_team_id":         rel_team,
            "feedback_category":       random.choice(FB_CATEGORY),
            "feedback_text":           random.choice(FB_TEXT_POOL),
            "positive_aspects":        ",".join(random.sample(POSITIVE_ASPECTS_POOL, k=random.randint(1, 3))),
            "improvement_areas":       ",".join(random.sample(IMPROVE_AREAS_POOL, k=random.randint(1, 2))),
            "specific_suggestions":    random.choice(SUGGESTIONS_POOL),
            "overall_rating":          overall_rat,
            "quality_rating":          quality_rat,
            "timeliness_rating":       timeliness_rat,
            "collaboration_rating":    collab_rat,
            "communication_rating":    comm_rat,
            "innovation_rating":       innov_rat,
            "sentiment":               sentiment_cat,
            "sentiment_score":         sent_score,
            "tone":                    tone,
            "actionable":              actionable,
            "action_items":            action_items,
            "priority_level":          priority,
            "follow_up_required":      follow_up,
            "follow_up_date":          fu_date,
            "acknowledged":            acknowledged,
            "acknowledged_date":       ack_date,
            "recipient_response":      resp_text,
            "response_date":           resp_date,
            "used_for_training":       random.random() > 0.6,
            "used_for_performance_review": random.random() > 0.5,
            "visibility":              np.random.choice(VISIBILITY, p=VISIBILITY_W),
            "created_at":              rand_datetime(fb_date),
            "last_updated":            rand_datetime(
                                           fb_date + timedelta(days=random.randint(0, 10))
                                       ),
        })

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading prior data...")
    emp_df   = pd.read_csv(f"{OUT_DIR}/employees.csv")
    proj_df  = pd.read_csv(f"{OUT_DIR}/projects.csv")
    tasks_df = pd.read_csv(f"{OUT_DIR}/tasks.csv")
    asg_df   = pd.read_csv(f"{OUT_DIR}/task_assignments.csv")
    print(f"  Loaded {len(emp_df)} employees | {len(proj_df)} projects | "
          f"{len(tasks_df)} tasks | {len(asg_df)} assignments")

    print("Generating team_formations...")
    teams_df = generate_team_formations(emp_df, proj_df)
    teams_df.to_csv(f"{OUT_DIR}/team_formations.csv", index=False)
    print(f"  ✓ {len(teams_df)} rows → team_formations.csv")

    print("Generating performance_reviews...")
    rev_df = generate_performance_reviews(emp_df, proj_df, asg_df)
    rev_df.to_csv(f"{OUT_DIR}/performance_reviews.csv", index=False)
    print(f"  ✓ {len(rev_df)} rows → performance_reviews.csv")

    print("Generating feedback...")
    fb_df = generate_feedback(emp_df, tasks_df, proj_df, teams_df)
    fb_df.to_csv(f"{OUT_DIR}/feedback.csv", index=False)
    print(f"  ✓ {len(fb_df)} rows → feedback.csv")

    # ── Sanity checks ──────────────────────────────────────────────────────────
    print("\nSanity checks:")

    print(f"  TEAMS — all project_ids valid    : {teams_df['project_id'].isin(proj_df['project_id']).all()}")
    print(f"  TEAMS — all lead_ids valid       : {teams_df['team_lead_id'].isin(emp_df['employee_id']).all()}")
    print(f"  TEAMS — status distribution:\n{teams_df['team_status'].value_counts().to_string()}")
    print(f"  TEAMS — formation method dist:\n{teams_df['formation_method'].value_counts().to_string()}")

    print(f"  REVIEWS — all employee_ids valid : {rev_df['employee_id'].isin(emp_df['employee_id']).all()}")
    print(f"  REVIEWS — all reviewer_ids valid : {rev_df['reviewer_id'].isin(emp_df['employee_id']).all()}")
    print(f"  REVIEWS — avg overall perf score : {rev_df['overall_performance_score'].mean():.1f}")
    print(f"  REVIEWS — rating distribution:\n{rev_df['performance_rating'].value_counts().to_string()}")
    print(f"  REVIEWS — promotion ready pct    : {(rev_df['promotion_recommended']).mean():.1%}")

    print(f"  FEEDBACK — all recipient_ids valid: {fb_df['recipient_id'].isin(emp_df['employee_id']).all()}")
    print(f"  FEEDBACK — sentiment distribution:\n{fb_df['sentiment'].value_counts().to_string()}")
    print(f"  FEEDBACK — avg overall rating    : {fb_df['overall_rating'].mean():.2f}")
    print(f"  FEEDBACK — acknowledgement rate  : {fb_df['acknowledged'].mean():.1%}")

    print("\nAll 10 tables generated. Done.")
