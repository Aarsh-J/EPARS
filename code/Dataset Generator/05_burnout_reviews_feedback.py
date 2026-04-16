"""
05_burnout_reviews_feedback.py — Generate burnout_indicators.csv,
performance_reviews.csv, and feedback.csv (V3 schema).
"""

import os, random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config import (
    HISTORY_START, HISTORY_END,
    BURNOUT_TREND, INTERV_URGENCY, ASSESS_TYPE, ASSESS_WEIGHTS,
    REVIEW_TYPES, REVIEW_WEIGHTS, PROMO_READINESS, PERF_RATING_BANDS,
    STRENGTHS_POOL, WEAKNESS_POOL, TRAINING_POOL,
    MANAGER_COMMENTS, PEER_FEEDBACK, ACHIEVEMENTS_POOL,
    FB_TYPES, FB_TYPES_W, FB_CATEGORY, VISIBILITY, VISIBILITY_W,
    POSITIVE_ASPECTS_POOL, IMPROVE_AREAS_POOL, SUGGESTIONS_POOL,
    FB_TEXT_POOL, ACTION_ITEMS_POOL, RECIPIENT_RESPONSES,
    clamp, rand_date, rand_datetime, normal_score, normal_pct,
    perf_rating_from_score,
)

random.seed(42)
np.random.seed(42)

NUM_BURNOUT_ROWS = int(os.environ.get("NUM_BURNOUT_ROWS",  600))
NUM_REVIEWS      = int(os.environ.get("NUM_REVIEWS",       300))
NUM_FEEDBACK     = int(os.environ.get("NUM_FEEDBACK",     1500))
OUT_DIR          = os.environ.get("OUT_DIR", "./output")

TODAY = date(2025, 4, 16)


# ─── BURNOUT INDICATORS ───────────────────────────────────────────────────────

def calc_overall_burnout(exhaust: int, deperson: int, reduced_acc: int) -> float:
    """
    overall_burnout_risk (Maslach):
      emotional_exhaustion × 40% + depersonalization × 30% + reduced_accomplishment × 30%
      Each dimension scaled from 0-10 → 0-100, then combined.
    """
    exhaust_norm   = exhaust   * 10
    deperson_norm  = deperson  * 10
    reduced_norm   = reduced_acc * 10
    base = exhaust_norm * 0.40 + deperson_norm * 0.30 + reduced_norm * 0.30
    return clamp(round(base + np.random.normal(0, 5), 1), 0.0, 100.0)


def predict_burnout(current: float, trend: str, horizon: str) -> float:
    """
    predicted_burnout_30days / 90days:
      trend_adj_30d: Decreasing -5, Stable 0, Increasing +8, Rapidly Increasing +15
      trend_adj_90d: 2.5× the 30-day adjustment
    """
    trend_30 = {"Decreasing": -5, "Stable": 0,
                "Increasing": 8, "Rapidly Increasing": 15}[trend]
    adj = trend_30 if horizon == "30d" else round(trend_30 * 2.5)
    noise = 4 if horizon == "30d" else 7
    return clamp(round(current + adj + np.random.normal(0, noise), 1), 0.0, 100.0)


def generate_burnout_indicators(employees_df: pd.DataFrame,
                                 n: int) -> pd.DataFrame:
    emp_ids  = employees_df["employee_id"].tolist()
    hire_map = {row["employee_id"]: date.fromisoformat(row["hire_date"])
                for _, row in employees_df.iterrows()}
    stress_map = dict(zip(employees_df["employee_id"],
                          employees_df["stress_level"]))
    burnout_map= dict(zip(employees_df["employee_id"],
                          employees_df["burnout_risk_score"]))

    hist_start = date.fromisoformat(HISTORY_START)
    hist_end   = date.fromisoformat(HISTORY_END)

    # Weight employees with higher stress for more assessments
    stress_w = np.array([
        {"Low": 1, "Medium": 2, "High": 4}.get(stress_map.get(e, "Low"), 1)
        for e in emp_ids
    ], dtype=float)
    stress_w /= stress_w.sum()
    sampled_emps = np.random.choice(emp_ids, size=n, replace=True, p=stress_w)

    rows = []
    for i, emp_id in enumerate(sampled_emps):
        ind_id    = f"BI{i+1:04d}"
        hire_dt   = hire_map[emp_id]
        base_burn = float(burnout_map.get(emp_id, 30))
        base_stress_lv = stress_map.get(emp_id, "Low")

        days_avail = max((hist_end - max(hire_dt, hist_start)).days, 1)
        assess_date= max(hire_dt, hist_start) + timedelta(days=random.randint(0, days_avail))
        assess_type= np.random.choice(ASSESS_TYPE, p=ASSESS_WEIGHTS)

        # Slight trend drift
        days_elapsed = (assess_date - hist_start).days
        total_days   = max((hist_end - hist_start).days, 1)
        drift_factor = days_elapsed / total_days
        trend_dir    = np.random.choice(["stable", "increasing", "decreasing"],
                                         p=[0.55, 0.25, 0.20])
        drift = {"stable": 0,
                 "increasing":  20 * drift_factor,
                 "decreasing": -15 * drift_factor}[trend_dir]
        burnout = clamp(base_burn + drift + np.random.normal(0, 8), 5, 98)

        # Maslach dimensions — seeded to be consistent with overall burnout
        exhaust_mu  = burnout / 10 * 0.90
        deperson_mu = burnout / 10 * 0.75
        reduced_mu  = burnout / 10 * 0.65
        emo_exhaust  = int(clamp(round(exhaust_mu  + np.random.normal(0, 0.8)), 0, 10))
        deperson     = int(clamp(round(deperson_mu + np.random.normal(0, 0.8)), 0, 10))
        reduced_acc  = int(clamp(round(reduced_mu  + np.random.normal(0, 0.8)), 0, 10))

        overall_burnout = calc_overall_burnout(emo_exhaust, deperson, reduced_acc)

        burnout_cat = ("Critical"      if overall_burnout >= 75
                       else "High Risk"    if overall_burnout >= 55
                       else "Moderate Risk"if overall_burnout >= 30
                       else "Low Risk")

        # Work environment factors (self-reported)
        role_amb   = int(clamp(round(np.random.normal(overall_burnout / 15, 1.5)), 0, 10))
        job_ctrl   = int(clamp(round(10 - overall_burnout / 14 + np.random.normal(0, 1)), 0, 10))

        # Behavioral indicators — calculated from workload proxy
        late_freq   = int(clamp(overall_burnout / 6  + np.random.normal(0, 2),  0, 20))
        wknd_work   = int(clamp(overall_burnout / 15 + np.random.normal(0, 1),  0,  8))
        missed_brks = int(clamp(overall_burnout / 12 + np.random.normal(0, 1),  0, 10))
        vac_unused  = int(clamp(overall_burnout / 6  + np.random.normal(0, 2),  0, 20))
        sick_days   = int(clamp(overall_burnout / 12 + np.random.normal(0, 1.5),0, 12))
        absence_rate= clamp(round(sick_days / 130 * 100, 1), 0.0, 15.0)

        # Support factors (self-reported)
        job_sat    = int(clamp(round(9.5 - overall_burnout / 12 + np.random.normal(0, 0.8)), 1, 10))
        soc_support= int(clamp(round(np.random.normal(6.5, 1.5)), 1, 10))
        mgr_support= int(clamp(round(np.random.normal(6.5, 1.5)), 1, 10))
        mh_support = overall_burnout > 65 and random.random() > 0.40

        # Burnout trend string
        b_trend = ("Rapidly Increasing" if trend_dir == "increasing" and burnout > 60
                   else "Increasing"    if trend_dir == "increasing"
                   else "Decreasing"    if trend_dir == "decreasing"
                   else "Stable")

        pred_30d = predict_burnout(overall_burnout, b_trend, "30d")
        pred_90d = predict_burnout(overall_burnout, b_trend, "90d")

        urgency = ("Immediate"  if overall_burnout >= 78
                   else "Recommend" if overall_burnout >= 58
                   else "Monitor"   if overall_burnout >= 38
                   else "None")

        n_interv = int(clamp(overall_burnout / 30 + np.random.normal(0, 0.5), 0, 4))
        last_interv = (assess_date - timedelta(days=random.randint(5, 60))).isoformat() \
                      if n_interv > 0 else None
        interv_eff  = int(clamp(round(np.random.normal(6.5, 1.5)), 1, 10)) \
                      if n_interv > 0 else None

        rows.append({
            "indicator_id":                 ind_id,
            "employee_id":                  emp_id,
            "assessment_date":              assess_date.isoformat(),
            "assessment_type":              assess_type,
            # Core dimensions
            "overall_burnout_risk":         overall_burnout,
            "emotional_exhaustion_score":   emo_exhaust,
            "depersonalization_score":      deperson,
            "reduced_accomplishment_score": reduced_acc,
            "burnout_category":             burnout_cat,
            # Work environment
            "role_ambiguity":               role_amb,
            "job_control":                  job_ctrl,
            # Behavioral indicators
            "late_hours_frequency":         late_freq,
            "weekend_work_frequency":       wknd_work,
            "missed_breaks_count":          missed_brks,
            "vacation_days_unused":         vac_unused,
            "sick_days_taken":              sick_days,
            "absence_rate":                 absence_rate,
            # Support factors
            "job_satisfaction":             job_sat,
            "social_support_score":         soc_support,
            "manager_support_score":        mgr_support,
            "mental_health_support_needed": mh_support,
            # Predictive
            "burnout_trend":                b_trend,
            "predicted_burnout_30days":     pred_30d,
            "predicted_burnout_90days":     pred_90d,
            "intervention_urgency":         urgency,
            # Intervention history
            "interventions_received":       n_interv,
            "last_intervention_date":       last_interv,
            "intervention_effectiveness":   interv_eff,
            # Timestamps
            "created_at":                   f"{assess_date} 09:00:00",
            "last_updated":                 rand_datetime(assess_date),
        })

    return pd.DataFrame(rows)


# ─── PERFORMANCE REVIEWS ──────────────────────────────────────────────────────

def calc_overall_performance(tech: int, domain: int, prob_solve: int,
                              quality_wk: int, prod: int,
                              comm: int, collab: int, leadership: int,
                              initiative: int, time_mgmt: int) -> float:
    """
    overall_performance_score:
      technical_cluster(30%) + behavioral_cluster(25%)
      + quality_of_work(20%) + productivity(25%)
    technical_cluster = avg(technical_competence, domain_knowledge, problem_solving)
    behavioral_cluster = avg(communication, collaboration, leadership, initiative, time_management)
    All inputs are 0-10 integers, scaled to 0-100.
    """
    tech_cluster = (tech + domain + prob_solve) / 3 * 10
    behav_cluster= (comm + collab + leadership + initiative + time_mgmt) / 5 * 10
    qual_norm    = quality_wk  * 10
    prod_norm    = prod        * 10
    base = (tech_cluster * 0.30 + behav_cluster * 0.25
            + qual_norm   * 0.20 + prod_norm     * 0.25)
    return clamp(round(base + np.random.normal(0, 4), 1), 0.0, 100.0)


def calc_salary_increase(overall_perf: float, prod_vs_peers: float) -> float:
    """
    salary_increase_percentage:
      base = max(0, (overall_perf - 60) / 40 × 12)  → 0-12% range
      × peer_adjustment = 1 + (prod_vs_peers / 100)
      clamped 0-15
    """
    base_pct      = max(0.0, (overall_perf - 60) / 40 * 12)
    peer_adj      = 1 + (prod_vs_peers / 100)
    return clamp(round(base_pct * peer_adj, 1), 0.0, 15.0)


def generate_performance_reviews(employees_df: pd.DataFrame,
                                   n: int) -> pd.DataFrame:
    emp_ids   = employees_df["employee_id"].tolist()
    reviewers = employees_df[
        employees_df["seniority_level"].isin(["Senior", "Lead", "Principal"])
    ]["employee_id"].tolist() or emp_ids

    hire_map = {row["employee_id"]: date.fromisoformat(row["hire_date"])
                for _, row in employees_df.iterrows()}
    perf_map = {row["employee_id"]: float(row["historical_performance_score"])
                for _, row in employees_df.iterrows()}

    rows = []
    for i in range(1, n + 1):
        rev_id   = f"REV{i:04d}"
        emp_id   = random.choice(emp_ids)
        reviewer = random.choice([r for r in reviewers if r != emp_id] or reviewers)

        hire_dt   = hire_map[emp_id]
        base_perf = perf_map[emp_id]

        rev_type     = np.random.choice(REVIEW_TYPES, p=REVIEW_WEIGHTS)
        period_months= {"Annual": 12, "Quarterly": 3, "Project-based": 3, "Probationary": 3}[rev_type]

        min_period_end = max(hire_dt + timedelta(days=180), date(2023, 6, 1))
        if min_period_end >= date(2025, 1, 1):
            min_period_end = hire_dt + timedelta(days=90)
        period_end   = rand_date(min_period_end, date(2025, 1, 1))
        raw_start    = period_end - timedelta(days=period_months * 30)
        period_start = max(raw_start, hire_dt)
        review_date  = period_end + timedelta(days=random.randint(5, 20))

        # Human-given scores (0-10 int), anchored to historical performance
        anchor = base_perf / 11  # ~7 for avg perf of 77
        tech_comp   = int(normal_score(anchor, 0.9))
        domain_kn   = int(normal_score(anchor, 0.9))
        prob_solv   = int(normal_score(anchor, 1.0))
        quality_wk  = int(normal_score(anchor, 0.8))
        prod_score  = int(normal_score(anchor, 0.9))
        comm_score  = int(normal_score(7.0, 1.2))
        collab_sc   = int(normal_score(7.2, 1.1))
        lead_score  = int(normal_score(6.5, 1.4))
        init_score  = int(normal_score(6.8, 1.2))
        time_score  = int(normal_score(7.0, 1.2))

        overall   = calc_overall_performance(
            tech_comp, domain_kn, prob_solv, quality_wk, prod_score,
            comm_score, collab_sc, lead_score, init_score, time_score
        )
        norm_perf = clamp(round(overall - abs(np.random.normal(2, 2)), 1), 0.0, 100.0)

        perf_rating = perf_rating_from_score(overall)

        # Quantitative metrics
        tasks_done  = random.randint(15, 120)
        projs_done  = random.randint(1, 7)
        avg_quality = clamp(round(np.random.normal(anchor * 10, 8), 1), 40.0, 100.0)
        otd_rate    = normal_pct(83, 12)
        prod_vs_peers = clamp(round(np.random.normal(0, 12), 1), -30, 40)
        total_hrs   = round(random.uniform(600, 1400), 0)
        ot_hrs      = round(max(0, np.random.exponential(20)), 1)

        # Narrative
        strengths    = ",".join(random.sample(STRENGTHS_POOL, k=random.randint(2, 4)))
        weaknesses   = ",".join(random.sample(WEAKNESS_POOL,  k=random.randint(1, 3)))
        achievements = random.choice(ACHIEVEMENTS_POOL)
        improve_areas= ",".join(random.sample(WEAKNESS_POOL,  k=random.randint(1, 3)))
        training_recs= ",".join(random.sample(TRAINING_POOL,  k=random.randint(1, 3)))

        # Promotion
        promo_ready = np.random.choice(
            PROMO_READINESS,
            p=[0.45, 0.35, 0.20] if overall >= 75 else [0.70, 0.25, 0.05]
        )
        promo_rec  = (promo_ready == "Ready Now") and (lead_score >= 7)
        sal_pct    = calc_salary_increase(overall, prod_vs_peers)
        sal_adj    = round(
            employees_df.loc[employees_df["employee_id"] == emp_id,
                             "current_salary"].values[0] * sal_pct / 100, 2
        ) if sal_pct > 0 else 0.0

        self_assess = int(normal_score(anchor, 0.8))

        rows.append({
            # Identification
            "review_id":                    rev_id,
            "employee_id":                  emp_id,
            "reviewer_id":                  reviewer,
            "review_period_start":          period_start.isoformat(),
            "review_period_end":            period_end.isoformat(),
            "review_date":                  review_date.isoformat(),
            "review_type":                  rev_type,
            # Performance scores
            "overall_performance_score":    overall,
            "normalized_performance_score": norm_perf,
            "technical_competence_score":   tech_comp,
            "domain_knowledge_score":       domain_kn,
            "problem_solving_score":        prob_solv,
            "quality_of_work_score":        quality_wk,
            "productivity_score":           prod_score,
            # Behavioral scores
            "communication_score":          comm_score,
            "collaboration_score":          collab_sc,
            "leadership_score":             lead_score,
            "initiative_score":             init_score,
            "time_management_score":        time_score,
            # Quantitative
            "tasks_completed":              tasks_done,
            "projects_completed":           projs_done,
            "average_task_quality":         avg_quality,
            "on_time_delivery_rate":        otd_rate,
            "productivity_vs_peers":        prod_vs_peers,
            "total_hours_worked":           total_hrs,
            "overtime_hours":               ot_hrs,
            # Narrative
            "strengths":                    strengths,
            "achievements":                 achievements,
            "weaknesses":                   weaknesses,
            "improvement_areas":            improve_areas,
            "reviewer_comments":            random.choice(MANAGER_COMMENTS),
            "recommended_actions":          f"Focus on {random.choice(WEAKNESS_POOL).lower()}",
            # Feedback & recommendations
            "self_assessment_score":        self_assess,
            "peer_feedback_summary":        random.choice(PEER_FEEDBACK),
            "promotion_recommended":        promo_rec,
            "salary_increase_percentage":   sal_pct,
            "salary_adjustment_recommendation": sal_adj,
            "training_recommendations":     training_recs,
            "performance_rating":           perf_rating,
            "promotion_readiness":          promo_ready,
            # Timestamps
            "created_at":                   f"{review_date} 09:00:00",
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
        rel_proj  = random.choice(proj_ids) if fb_type in ("Project Review", "Task Completion") else None
        rel_team  = random.choice(team_ids) if fb_type == "Project Review" else None

        # Base rating drives all human rating fields
        base_rating = clamp(round(np.random.normal(7.5, 1.5), 1), 3.0, 10.0)
        overall_rat = int(clamp(round(np.random.normal(base_rating, 0.8)), 1, 10))
        quality_rat = int(clamp(round(np.random.normal(base_rating, 0.9)), 1, 10))
        timely_rat  = int(clamp(round(np.random.normal(base_rating, 1.0)), 1, 10))
        collab_rat  = int(clamp(round(np.random.normal(base_rating, 0.9)), 1, 10))
        comm_rat    = int(clamp(round(np.random.normal(base_rating, 1.0)), 1, 10))

        priority   = np.random.choice(["Low", "Medium", "High"], p=[0.30, 0.45, 0.25])
        follow_up  = priority == "High" and random.random() > 0.40
        fu_date    = (fb_date + timedelta(days=30)).isoformat() if follow_up else None

        acknowledged = random.random() > 0.25
        ack_date     = (fb_date + timedelta(days=random.randint(1, 5))).isoformat() \
                       if acknowledged else None
        has_response = acknowledged and random.random() > 0.55
        resp_text    = random.choice(RECIPIENT_RESPONSES) if has_response else None
        _ack_dt      = date.fromisoformat(ack_date) if ack_date else fb_date
        resp_date    = (_ack_dt + timedelta(days=random.randint(1, 5))).isoformat() \
                       if has_response and resp_text else None

        rows.append({
            # Identification
            "feedback_id":          fb_id,
            "feedback_type":        fb_type,
            "provider_id":          provider,
            "recipient_id":         recipient,
            "feedback_date":        fb_date.isoformat(),
            # Context
            "related_task_id":      rel_task,
            "related_project_id":   rel_proj,
            "related_team_id":      rel_team,
            "feedback_category":    random.choice(FB_CATEGORY),
            # Content
            "feedback_text":        random.choice(FB_TEXT_POOL),
            "positive_aspects":     ",".join(random.sample(POSITIVE_ASPECTS_POOL,
                                                            k=random.randint(1, 3))),
            "improvement_areas":    ",".join(random.sample(IMPROVE_AREAS_POOL,
                                                            k=random.randint(1, 2))),
            "specific_suggestions": random.choice(SUGGESTIONS_POOL),
            "action_items":         random.choice(ACTION_ITEMS_POOL),
            # Ratings (human-given)
            "overall_rating":       overall_rat,
            "quality_rating":       quality_rat,
            "timeliness_rating":    timely_rat,
            "collaboration_rating": collab_rat,
            "communication_rating": comm_rat,
            # Impact & follow-up
            "priority_level":       priority,
            "follow_up_date":       fu_date,
            # Recipient response
            "acknowledged":         acknowledged,
            "acknowledged_date":    ack_date,
            "recipient_response":   resp_text,
            "response_date":        resp_date,
            # Access
            "visibility":           np.random.choice(VISIBILITY, p=VISIBILITY_W),
            # Timestamps
            "created_at":           f"{fb_date} 09:00:00",
            "last_updated":         rand_datetime(fb_date + timedelta(days=random.randint(0, 10))),
        })

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading prior data...")
    emp_df   = pd.read_csv(f"{OUT_DIR}/employees.csv")
    tasks_df = pd.read_csv(f"{OUT_DIR}/tasks.csv")
    proj_df  = pd.read_csv(f"{OUT_DIR}/projects.csv")
    teams_df = pd.read_csv(f"{OUT_DIR}/team_formations.csv")

    print(f"Generating {NUM_BURNOUT_ROWS} burnout indicators...")
    bi_df = generate_burnout_indicators(emp_df, NUM_BURNOUT_ROWS)
    bi_df.to_csv(f"{OUT_DIR}/burnout_indicators.csv", index=False)
    print(f"  OK {len(bi_df)} rows -> burnout_indicators.csv")

    print(f"Generating {NUM_REVIEWS} performance reviews...")
    rev_df = generate_performance_reviews(emp_df, NUM_REVIEWS)
    rev_df.to_csv(f"{OUT_DIR}/performance_reviews.csv", index=False)
    print(f"  OK {len(rev_df)} rows -> performance_reviews.csv")

    print(f"Generating {NUM_FEEDBACK} feedback records...")
    fb_df = generate_feedback(emp_df, tasks_df, proj_df, teams_df, NUM_FEEDBACK)
    fb_df.to_csv(f"{OUT_DIR}/feedback.csv", index=False)
    print(f"  OK {len(fb_df)} rows -> feedback.csv")

    print("\nSanity checks:")
    hire_map = dict(zip(emp_df["employee_id"], pd.to_datetime(emp_df["hire_date"])))
    bi_df["_hire"]  = pd.to_datetime(bi_df["employee_id"].map(hire_map))
    bi_df["_adate"] = pd.to_datetime(bi_df["assessment_date"])
    print(f"  burnout before hire: {(bi_df['_adate'] < bi_df['_hire']).sum()} (should be 0)")
    print(f"  burnout category dist:\n{bi_df['burnout_category'].value_counts().to_string()}")

    rev_df["_hire"]  = pd.to_datetime(rev_df["employee_id"].map(hire_map))
    rev_df["_start"] = pd.to_datetime(rev_df["review_period_start"])
    print(f"  review before hire: {(rev_df['_start'] < rev_df['_hire']).sum()} (should be 0)")

    order = ["Needs Improvement", "Meets Expectations", "Exceeds Expectations", "Outstanding"]
    avgs  = rev_df.groupby("performance_rating")["overall_performance_score"].mean()
    print("  Avg score by rating (should be monotone):")
    for r in order:
        if r in avgs.index:
            print(f"    {r}: {avgs[r]:.1f}")

    print(f"  feedback ack rate: {fb_df['acknowledged'].mean():.1%}")
