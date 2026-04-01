"""
04b_reviews_feedback.py — Generate performance_reviews.csv and feedback.csv
- performance_rating derived from score bands (not random)
- review_period_start clamped to >= hire_date
"""

import os, random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config import (
    REVIEW_TYPES, REVIEW_WEIGHTS, PROMO_READINESS,
    STRENGTHS_POOL, WEAKNESS_POOL, TRAINING_POOL,
    MANAGER_COMMENTS, PEER_FEEDBACK, ACHIEVEMENTS_POOL,
    FB_TYPES, FB_TYPES_W, FB_CATEGORY, SENTIMENT, SENTIMENT_W,
    TONE, TONE_W, VISIBILITY, VISIBILITY_W,
    POSITIVE_ASPECTS_POOL, IMPROVE_AREAS_POOL, SUGGESTIONS_POOL,
    FB_TEXT_POOL, ACTION_ITEMS_POOL, RECIPIENT_RESPONSES,
    clamp, rand_date, rand_datetime, normal_score, normal_pct,
    perf_rating_from_score,
)

random.seed(42)
np.random.seed(42)

NUM_REVIEWS  = int(os.environ.get("NUM_REVIEWS",  400))
NUM_FEEDBACK = int(os.environ.get("NUM_FEEDBACK", 2000))
OUT_DIR      = os.environ.get("OUT_DIR", "./output")


# ─── PERFORMANCE REVIEWS ──────────────────────────────────────────────────────
def generate_performance_reviews(employees_df: pd.DataFrame,
                                   n: int) -> pd.DataFrame:
    emp_ids   = employees_df["employee_id"].tolist()
    reviewers = employees_df[
        employees_df["seniority_level"].isin(["Senior", "Lead", "Principal"])
    ]["employee_id"].tolist() or emp_ids

    hire_map = {row["employee_id"]: date.fromisoformat(row["hire_date"])
                for _, row in employees_df.iterrows()}
    perf_map = {row["employee_id"]: row["historical_performance_score"]
                for _, row in employees_df.iterrows()}

    rows = []
    for i in range(1, n + 1):
        rev_id   = f"REV{i:04d}"
        emp_id   = random.choice(emp_ids)
        reviewer = random.choice([r for r in reviewers if r != emp_id] or reviewers)

        hire_dt  = hire_map[emp_id]
        base_perf= perf_map[emp_id]

        rev_type = np.random.choice(REVIEW_TYPES, p=REVIEW_WEIGHTS)
        period_months = {"Annual": 12, "Quarterly": 3, "Project-based": 3, "Probationary": 3}[rev_type]

        # period_end: after at least 6 months employment, and within data range
        min_period_end = max(hire_dt + timedelta(days=180), date(2023, 6, 1))
        if min_period_end >= date(2025, 1, 1):
            min_period_end = hire_dt + timedelta(days=90)
        period_end   = rand_date(min_period_end, date(2025, 1, 1))

        # period_start clamped to >= hire_date
        raw_start    = period_end - timedelta(days=period_months * 30)
        period_start = max(raw_start, hire_dt)

        review_date  = period_end + timedelta(days=random.randint(5, 20))

        # Scores anchored to employee historical performance
        overall   = normal_pct(base_perf, 10)
        norm_perf = normal_pct(base_perf - 2, 10)

        # performance_rating derived from score band (not random)
        perf_rating = perf_rating_from_score(overall)

        tech_comp   = normal_score(overall / 11, 0.9)
        domain_kn   = normal_score(overall / 11, 0.9)
        prob_solv   = normal_score(overall / 11, 1.0)
        innovation  = normal_score(overall / 12, 1.1)
        quality_wk  = normal_score(overall / 11, 0.8)
        prod_score  = normal_score(overall / 11, 0.9)
        comm_score  = normal_score(7.0, 1.2)
        collab_sc   = normal_score(7.2, 1.1)
        lead_score  = normal_score(6.5, 1.4)
        init_score  = normal_score(6.8, 1.2)
        adapt_score = normal_score(7.0, 1.1)
        reli_score  = normal_score(7.5, 1.0)
        time_score  = normal_score(7.0, 1.2)

        tasks_done   = random.randint(15, 150)
        projs_done   = random.randint(1, 8)
        avg_quality  = normal_score(7.5, 1.0)
        otd_rate     = normal_pct(82, 12)
        prod_vs_peers= clamp(round(np.random.normal(0, 12), 1), -30, 40)
        total_hrs    = round(random.uniform(600, 1400), 0)
        ot_hrs       = round(max(0, np.random.exponential(25)), 1)
        util_rate    = normal_pct(85, 10)

        strengths    = ",".join(random.sample(STRENGTHS_POOL, k=random.randint(2, 4)))
        weaknesses   = ",".join(random.sample(WEAKNESS_POOL,  k=random.randint(1, 3)))
        achievements = random.choice(ACHIEVEMENTS_POOL)
        exceeded_areas = ",".join(random.sample(STRENGTHS_POOL, k=random.randint(1, 3)))
        improve_areas  = ",".join(random.sample(WEAKNESS_POOL,  k=random.randint(1, 3)))
        dev_goals    = f"Complete {random.choice(TRAINING_POOL)}, improve {random.choice(WEAKNESS_POOL).lower()}"
        training_recs= ",".join(random.sample(TRAINING_POOL, k=random.randint(1, 3)))
        next_review  = (review_date + timedelta(
                            days=90 if rev_type == "Quarterly" else 365
                        )).isoformat()
        follow_up    = random.random() > 0.65

        promo_ready  = np.random.choice(
            PROMO_READINESS,
            p=[0.45, 0.35, 0.20] if overall >= 75 else [0.70, 0.25, 0.05]
        )
        promo_rec    = promo_ready == "Ready Now"
        sal_inc_rec  = overall >= 70
        sal_inc_pct  = round(random.choice([0, 3, 5, 7, 10, 15]) if sal_inc_rec else 0, 1)
        bonus_rec    = round(random.choice([0, 1000, 2000, 5000, 10000]) if overall >= 75 else 0, 1)
        training_rec = random.random() > 0.3
        self_assess  = normal_score(overall / 11, 0.8)

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
            "collaboration_score":          collab_sc,
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


# ─── FEEDBACK ─────────────────────────────────────────────────────────────────
def generate_feedback(employees_df: pd.DataFrame,
                       tasks_df: pd.DataFrame,
                       projects_df: pd.DataFrame,
                       teams_df: pd.DataFrame,
                       n: int) -> pd.DataFrame:
    emp_ids  = employees_df["employee_id"].tolist()
    task_ids = tasks_df["task_id"].tolist()
    proj_ids = projects_df["project_id"].tolist()
    team_ids = teams_df["team_id"].tolist()

    rows = []
    for i in range(1, n + 1):
        fb_id     = f"FDB{i:04d}"
        fb_type   = np.random.choice(FB_TYPES, p=FB_TYPES_W)
        recipient = random.choice(emp_ids)
        provider  = random.choice([e for e in emp_ids if e != recipient] + ["SYSTEM"])

        fb_date   = rand_date(date(2023, 6, 1), date(2025, 2, 28))

        rel_task  = random.choice(task_ids) if fb_type == "Task Completion" else None
        rel_proj  = random.choice(proj_ids) if fb_type in ["Project Review", "Task Completion"] else None
        rel_team  = random.choice(team_ids) if fb_type == "Project Review" else None

        sentiment_cat = np.random.choice(SENTIMENT, p=SENTIMENT_W)
        base_rating   = {"Very Negative": 3.0, "Negative": 4.5, "Neutral": 6.0,
                         "Positive": 7.8, "Very Positive": 9.0}[sentiment_cat]

        overall_rat    = normal_score(base_rating, 0.8)
        quality_rat    = normal_score(base_rating, 0.9)
        timeliness_rat = normal_score(base_rating, 1.0)
        collab_rat     = normal_score(base_rating, 0.9)
        comm_rat       = normal_score(base_rating, 1.0)
        innov_rat      = normal_score(base_rating, 1.1)

        sent_score = clamp(round(
            {"Very Negative": -70, "Negative": -35, "Neutral": 5,
             "Positive": 55, "Very Positive": 82}[sentiment_cat]
            + np.random.normal(0, 10), 1), -100, 100)

        tone       = np.random.choice(TONE, p=TONE_W)
        actionable = random.random() > 0.35
        action_items = random.choice(ACTION_ITEMS_POOL) if actionable else None
        priority   = np.random.choice(["Low", "Medium", "High"], p=[0.30, 0.45, 0.25])
        follow_up  = actionable and random.random() > 0.5
        fu_date    = (fb_date + timedelta(days=random.randint(7, 30))).isoformat() \
                     if follow_up else None

        acknowledged = random.random() > 0.25
        ack_date     = (fb_date + timedelta(days=random.randint(1, 5))).isoformat() \
                       if acknowledged else None
        has_response = acknowledged and random.random() > 0.55
        resp_text    = random.choice(RECIPIENT_RESPONSES) if has_response else None
        # response_date chained off ack_date so it's always after acknowledgement
        _ack_dt   = date.fromisoformat(ack_date) if ack_date else fb_date
        resp_date    = (_ack_dt + timedelta(days=random.randint(1, 5))).isoformat() \
                       if has_response and resp_text else None

        rows.append({
            "feedback_id":              fb_id,
            "feedback_type":            fb_type,
            "provider_id":              provider,
            "recipient_id":             recipient,
            "feedback_date":            fb_date.isoformat(),
            "related_task_id":          rel_task,
            "related_project_id":       rel_proj,
            "related_team_id":          rel_team,
            "feedback_category":        random.choice(FB_CATEGORY),
            "feedback_text":            random.choice(FB_TEXT_POOL),
            "positive_aspects":         ",".join(random.sample(POSITIVE_ASPECTS_POOL, k=random.randint(1, 3))),
            "improvement_areas":        ",".join(random.sample(IMPROVE_AREAS_POOL,   k=random.randint(1, 2))),
            "specific_suggestions":     random.choice(SUGGESTIONS_POOL),
            "overall_rating":           overall_rat,
            "quality_rating":           quality_rat,
            "timeliness_rating":        timeliness_rat,
            "collaboration_rating":     collab_rat,
            "communication_rating":     comm_rat,
            "innovation_rating":        innov_rat,
            "sentiment":                sentiment_cat,
            "sentiment_score":          sent_score,
            "tone":                     tone,
            "actionable":               actionable,
            "action_items":             action_items,
            "priority_level":           priority,
            "follow_up_required":       follow_up,
            "follow_up_date":           fu_date,
            "acknowledged":             acknowledged,
            "acknowledged_date":        ack_date,
            "recipient_response":       resp_text,
            "response_date":            resp_date,
            "used_for_training":        random.random() > 0.6,
            "used_for_performance_review": random.random() > 0.5,
            "visibility":               np.random.choice(VISIBILITY, p=VISIBILITY_W),
            "created_at":               rand_datetime(fb_date),
            "last_updated":             rand_datetime(fb_date + timedelta(days=random.randint(0, 10))),
        })

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading prior data...")
    emp_df   = pd.read_csv(f"{OUT_DIR}/employees.csv")
    tasks_df = pd.read_csv(f"{OUT_DIR}/tasks.csv")
    proj_df  = pd.read_csv(f"{OUT_DIR}/projects.csv")
    teams_df = pd.read_csv(f"{OUT_DIR}/team_formations.csv")

    print(f"Generating {NUM_REVIEWS} performance reviews...")
    rev_df = generate_performance_reviews(emp_df, NUM_REVIEWS)
    rev_df.to_csv(f"{OUT_DIR}/performance_reviews.csv", index=False)
    print(f"  ✓ {len(rev_df)} rows → performance_reviews.csv")

    print(f"Generating {NUM_FEEDBACK} feedback records...")
    fb_df = generate_feedback(emp_df, tasks_df, proj_df, teams_df, NUM_FEEDBACK)
    fb_df.to_csv(f"{OUT_DIR}/feedback.csv", index=False)
    print(f"  ✓ {len(fb_df)} rows → feedback.csv")

    print("\nSanity checks:")
    hire_map = dict(zip(emp_df["employee_id"], pd.to_datetime(emp_df["hire_date"])))
    rev_df["_hire"]  = pd.to_datetime(rev_df["employee_id"].map(hire_map))
    rev_df["_start"] = pd.to_datetime(rev_df["review_period_start"])
    before_hire = (rev_df["_start"] < rev_df["_hire"]).sum()
    print(f"  review_period_start before hire_date: {before_hire}  (should be 0)")

    order = ["Needs Improvement", "Meets Expectations", "Exceeds Expectations", "Outstanding"]
    avgs  = rev_df.groupby("performance_rating")["overall_performance_score"].mean()
    print(f"  Avg score by rating (should be monotone):")
    for r in order:
        if r in avgs.index:
            print(f"    {r}: {avgs[r]:.1f}")

    print(f"  feedback acknowledgement rate: {fb_df['acknowledged'].mean():.1%}")
    print(f"  feedback avg overall rating: {fb_df['overall_rating'].mean():.2f}")
