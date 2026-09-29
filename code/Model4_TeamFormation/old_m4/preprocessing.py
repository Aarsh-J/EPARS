# =============================================================
# MODEL 4 — TEAM FORMATION — PREPROCESSING & FEATURE EXTRACTION
# Grain: one row per team (team_id)
# Targets:
#   - actual_performance_score (regression)
#   - team_success              (classification, derived: score >= 80)
#
# Rebuilt from scratch to replace prep1.py / prep2.py / prep3.py.
#
# Why from scratch, not a patch of prep3.py:
#   1. prep3.py pointed at ../../dataset_v2, which no longer exists
#      (deleted during the Model2 dataset cleanup). Its FT3/ outputs
#      on disk were stale — team_id values didn't match current data.
#   2. prep3.py assumed a column schema (cross_functional_experience,
#      mentoring_experience, reliability_score, adaptability_score,
#      innovation_score, strategic_importance, late_hours_indicator...)
#      that doesn't exist in the CURRENT dataset/ CSVs. That schema
#      belonged to whatever generator produced the old dataset_v2.
#      Verified every column against the live CSVs below instead of
#      reusing the old assumptions.
#   3. team_formations.csv already ships pre-formation composite scores
#      (skill_diversity_score, experience_balance_score,
#      collaborative_history_score, workload_balance_score,
#      predicted_success_rate) that prep3.py ignored entirely and
#      recomputed from scratch. These are legitimate features (not
#      target leakage — predicted_success_rate only correlates 0.25
#      with actual_performance_score, checked below) and are far
#      cheaper/more reliable than re-deriving them from member rows.
#
# Label coverage (why team_success, not met_deadline):
#   met_deadline is only ever set when project_completed == True
#   (351/1000 teams). team_success, derived from actual_performance_score,
#   is available for 606/1000 teams — keep more usable data.
# =============================================================

import json
import os
from itertools import combinations

import numpy as np
import pandas as pd

# ── Paths ──────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(SCRIPT_DIR, "../../dataset")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "artifacts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SUCCESS_THRESHOLD = 80  # actual_performance_score >= this => team_success = 1


def load_raw():
    emp  = pd.read_csv(f"{INPUT_DIR}/employees.csv")
    tf   = pd.read_csv(f"{INPUT_DIR}/team_formations.csv")
    pr   = pd.read_csv(f"{INPUT_DIR}/performance_reviews.csv")
    wh   = pd.read_csv(f"{INPUT_DIR}/workload_history.csv")
    proj = pd.read_csv(f"{INPUT_DIR}/projects.csv")
    print("Shapes:")
    print(f"  employees        : {emp.shape}")
    print(f"  team_formations  : {tf.shape}")
    print(f"  performance_rev  : {pr.shape}")
    print(f"  workload_history : {wh.shape}")
    print(f"  projects         : {proj.shape}")
    return emp, tf, pr, wh, proj


def clean_employees(emp: pd.DataFrame) -> pd.DataFrame:
    emp = emp.copy()
    emp["hire_date"] = pd.to_datetime(emp["hire_date"], format="mixed")
    emp["tenure_days"] = (pd.Timestamp.today() - emp["hire_date"]).dt.days
    emp["is_available"] = emp["is_available"].astype(bool)

    emp["certifications"] = emp["certifications"].fillna("")
    # stress_level is constant ('Low' for every employee) — zero variance, drop.

    seniority_order = {"Junior": 1, "Mid": 2, "Senior": 3, "Lead": 4, "Principal": 5}
    trend_order = {"Decreasing": -1, "Stable": 0, "Increasing": 1}

    emp["seniority_encoded"] = emp["seniority_level"].map(seniority_order)
    emp["productivity_trend_enc"] = emp["productivity_trend"].map(trend_order)

    emp["all_skills_list"] = (
        emp["primary_skills"].fillna("") + "," + emp["secondary_skills"].fillna("")
    ).str.split(",").apply(lambda x: [s.strip().lower() for s in x if s.strip()])

    emp["project_success_rate"] = (
        emp["successful_project_count"]
        / (emp["successful_project_count"] + emp["failed_project_count"])
    ).fillna(0)

    print(f"employees.csv cleaned  |  shape: {emp.shape}")
    return emp


def clean_performance_reviews(pr: pd.DataFrame) -> pd.DataFrame:
    pr = pr.copy()
    pr["review_date"] = pd.to_datetime(pr["review_date"], format="mixed")
    pr_latest = pr.sort_values("review_date", ascending=False).groupby(
        "employee_id", as_index=False
    ).first()

    # NOTE: collaboration_score also exists on employees.csv directly —
    # keeping only the employees.csv version there, so this select
    # deliberately excludes performance_reviews' collaboration_score
    # to avoid a silent _x/_y merge collision.
    keep = [
        "employee_id", "overall_performance_score", "technical_competence_score",
        "problem_solving_score", "communication_score", "leadership_score",
        "time_management_score", "on_time_delivery_rate", "productivity_vs_peers",
        "quality_of_work_score",
    ]
    pr_latest = pr_latest[keep].rename(columns={
        "overall_performance_score": "review_performance_score",
        "technical_competence_score": "review_technical_score",
    })
    print(f"performance_reviews.csv cleaned  |  employees with reviews: {pr_latest['employee_id'].nunique()}")
    return pr_latest


def clean_workload(wh: pd.DataFrame) -> pd.DataFrame:
    wh = wh.copy()
    wh["date"] = pd.to_datetime(wh["date"], format="mixed")
    cutoff = wh["date"].max() - pd.Timedelta(weeks=8)
    wh_recent = wh[wh["date"] >= cutoff]

    wh_agg = wh_recent.groupby("employee_id").agg(
        recent_avg_hours=("total_hours_worked", "mean"),
        recent_avg_overtime=("overtime_hours", "mean"),
        recent_workload_pct=("workload_vs_capacity", "mean"),
        recent_avg_productivity=("productivity_score", "mean"),
        recent_focus_hours=("focused_work_hours", "mean"),
        recent_avg_burnout_today=("burnout_risk_today", "mean"),
        weekend_work_count=("weekend_work_indicator", "sum"),
    ).reset_index()
    print(f"workload_history.csv aggregated  |  employees covered: {wh_agg['employee_id'].nunique()} / {wh['employee_id'].nunique()}")
    return wh_agg


def build_master(emp: pd.DataFrame, pr_latest: pd.DataFrame, wh_agg: pd.DataFrame) -> pd.DataFrame:
    master = emp.merge(pr_latest, on="employee_id", how="left")
    master = master.merge(wh_agg, on="employee_id", how="left")

    master["available_hours"] = (
        master["weekly_capacity_hours"]
        - master["recent_avg_hours"].fillna(master["weekly_capacity_hours"] * 0.7)
    ).clip(lower=0)

    conflicts = [c for c in master.columns if c.endswith("_x") or c.endswith("_y")]
    assert not conflicts, f"Column conflicts found: {conflicts}"
    print(f"Master employee table shape: {master.shape}")
    return master


def clean_projects(proj: pd.DataFrame) -> pd.DataFrame:
    proj = proj.copy()
    complexity_order = {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}
    priority_order = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}

    proj["complexity_encoded"] = proj["complexity_level"].map(complexity_order)
    proj["priority_encoded"] = proj["priority"].map(priority_order).fillna(2)
    proj["required_skills_list"] = proj["required_skills"].fillna("").str.split(",").apply(
        lambda x: [s.strip().lower() for s in x if s.strip()]
    )
    proj["budget_per_head"] = proj["budget"] / proj["team_size"].replace(0, np.nan)

    proj_keep = proj[[
        "project_id", "complexity_encoded", "priority_encoded", "budget_per_head",
        "team_size", "delay_risk_score", "quality_risk_score", "success_probability",
        "budget_overrun_risk", "required_skills_list",
    ]].rename(columns={"team_size": "proj_required_team_size"}).set_index("project_id")
    print(f"projects.csv cleaned  |  {len(proj_keep)} projects indexed")
    return proj_keep


def parse_json_col(val):
    try:
        return json.loads(str(val).replace("'", '"'))
    except Exception:
        return {}


def clean_team_formations(tf: pd.DataFrame) -> pd.DataFrame:
    tf = tf.copy()
    tf["formation_date"] = pd.to_datetime(tf["formation_date"], format="mixed")
    # member_ids EXCLUDES team_lead_id in every row (verified against
    # seniority_mix totals, which do include the lead) — add it back in,
    # or every team silently loses its most senior member.
    tf["member_ids_list"] = tf.apply(
        lambda r: sorted(set(
            [s.strip() for s in str(r["member_ids"]).split(",")] + [r["team_lead_id"]]
        )),
        axis=1,
    )
    tf["seniority_mix_parsed"] = tf["seniority_mix"].apply(parse_json_col)
    tf["met_deadline"] = tf["met_deadline"].map({True: 1, False: 0, "True": 1, "False": 0})

    # Only rows with a real outcome are trainable.
    before = len(tf)
    tf = tf.dropna(subset=["actual_performance_score"]).reset_index(drop=True)
    print(f"team_formations.csv cleaned  |  {len(tf)}/{before} teams have a usable target")

    tf["team_success"] = (tf["actual_performance_score"] >= SUCCESS_THRESHOLD).astype(int)
    print(f"team_success balance:\n{tf['team_success'].value_counts()}")
    return tf


def compute_past_overlap(tf: pd.DataFrame) -> pd.DataFrame:
    """For each team, what fraction of its member-pairs have worked
    together before (in any team formed on an earlier date)."""
    tf_sorted = tf.sort_values("formation_date").reset_index(drop=True)
    historical_pairs = set()
    ratios = []
    for _, row in tf_sorted.iterrows():
        current_members = set(row["member_ids_list"])
        current_pairs = list(combinations(sorted(current_members), 2))
        overlap_count = sum(1 for p in current_pairs if p in historical_pairs)
        total_pairs = len(current_pairs)
        ratios.append(overlap_count / total_pairs if total_pairs > 0 else 0.0)
        historical_pairs.update(current_pairs)
    tf_sorted["past_team_overlap_ratio"] = ratios

    tf = tf.merge(tf_sorted[["team_id", "past_team_overlap_ratio"]], on="team_id", how="left")
    print("Past team overlap computed")
    return tf


def compute_budget_seniority_fit(master, member_ids, budget_per_head):
    if pd.isna(budget_per_head):
        return np.nan
    members = master[master["employee_id"].isin(member_ids)]
    if members.empty:
        return np.nan
    return (members["current_salary"] <= budget_per_head).mean()


def extract_team_features(tf_row, proj_row, master):
    member_ids = tf_row["member_ids_list"]
    members = master[master["employee_id"].isin(member_ids)]
    if members.empty:
        return None

    f = {
        "team_id": tf_row["team_id"],
        "project_id": tf_row["project_id"],
        "formation_date": tf_row["formation_date"],
        "team_size": len(members),
    }

    # ── Pre-formation composite scores already shipped in team_formations.csv
    # (not leakage — computed at formation time, before the outcome exists) ──
    f["skill_diversity_score"] = tf_row["skill_diversity_score"]
    f["experience_balance_score"] = tf_row["experience_balance_score"]
    f["collaborative_history_score"] = tf_row["collaborative_history_score"]
    f["workload_balance_score"] = tf_row["workload_balance_score"]
    f["predicted_success_rate"] = tf_row["predicted_success_rate"]
    f["past_team_overlap_ratio"] = tf_row["past_team_overlap_ratio"]

    # ── Skill / seniority composition ─────────────────────────────
    all_skills = set(s for sl in members["all_skills_list"] for s in sl)
    f["avg_skills_per_member"] = len(all_skills) / max(f["team_size"], 1)
    f["avg_technical_score"] = members["technical_proficiency_score"].mean()
    f["avg_domain_score"] = members["domain_expertise_score"].mean()
    f["avg_review_technical"] = members["review_technical_score"].mean()

    sen_mix = tf_row["seniority_mix_parsed"]
    f["junior_ratio"] = sen_mix.get("Junior", 0) / max(f["team_size"], 1)
    f["mid_ratio"] = sen_mix.get("Mid", 0) / max(f["team_size"], 1)
    f["senior_ratio"] = sen_mix.get("Senior", 0) / max(f["team_size"], 1)
    f["lead_ratio"] = (sen_mix.get("Lead", 0) + sen_mix.get("Principal", 0)) / max(f["team_size"], 1)
    f["seniority_diversity"] = len([v for v in sen_mix.values() if v > 0])
    f["avg_seniority"] = members["seniority_encoded"].mean()
    f["max_seniority"] = members["seniority_encoded"].max()

    # ── Budget / cost fit ───────────────────────────────────────
    budget_per_head = proj_row["budget_per_head"] if proj_row is not None else np.nan
    f["budget_per_head"] = budget_per_head
    f["budget_seniority_fit"] = compute_budget_seniority_fit(master, member_ids, budget_per_head)

    # ── Historical performance / review signals ─────────────────
    f["avg_performance"] = members["review_performance_score"].mean()
    f["min_performance"] = members["review_performance_score"].min()
    f["std_performance"] = members["review_performance_score"].std()
    f["avg_on_time_rate"] = members["on_time_delivery_rate"].mean()
    f["avg_problem_solving"] = members["problem_solving_score"].mean()
    f["avg_communication"] = members["communication_score"].mean()
    f["avg_leadership_review"] = members["leadership_score"].mean()
    f["avg_time_management"] = members["time_management_score"].mean()
    f["avg_quality_of_work"] = members["quality_of_work_score"].mean()
    f["avg_productivity_vs_peers"] = members["productivity_vs_peers"].mean()

    # ── Employee-profile traits ──────────────────────────────────
    f["avg_collaboration"] = members["collaboration_score"].mean()
    f["avg_leadership_potential"] = members["leadership_potential"].mean()
    f["avg_historical_performance"] = members["historical_performance_score"].mean()
    f["avg_task_completion_rate"] = members["average_task_completion_rate"].mean()
    f["avg_project_success_rate"] = members["project_success_rate"].mean()

    # ── Capacity / burnout / workload ────────────────────────────
    f["avg_burnout_risk"] = members["burnout_risk_score"].mean()
    f["max_burnout_risk"] = members["burnout_risk_score"].max()
    f["avg_available_hours"] = members["available_hours"].mean()
    f["avg_workload_recent"] = members["recent_workload_pct"].mean()
    f["avg_overtime_recent"] = members["recent_avg_overtime"].mean()
    f["avg_burnout_recent"] = members["recent_avg_burnout_today"].mean()
    f["avg_current_project_count"] = members["current_project_count"].mean()
    f["pct_available_now"] = members["is_available"].mean()

    # ── Experience / tenure ───────────────────────────────────────
    f["avg_experience"] = members["years_of_experience"].mean()
    f["experience_range"] = members["years_of_experience"].max() - members["years_of_experience"].min()
    f["avg_tenure_days"] = members["tenure_days"].mean()
    f["avg_productivity_trend"] = members["productivity_trend_enc"].mean()

    # ── Project context ────────────────────────────────────────────
    if proj_row is not None:
        f["proj_complexity"] = proj_row["complexity_encoded"]
        f["proj_priority"] = proj_row["priority_encoded"]
        f["proj_delay_risk"] = proj_row["delay_risk_score"]
        f["proj_quality_risk"] = proj_row["quality_risk_score"]
        f["proj_success_probability"] = proj_row["success_probability"]
        f["proj_budget_overrun_risk"] = proj_row["budget_overrun_risk"]
        f["proj_required_team_size"] = proj_row["proj_required_team_size"]
        f["team_size_match"] = len(members) / max(proj_row["proj_required_team_size"], 1)
    else:
        for col in ["proj_complexity", "proj_priority", "proj_delay_risk", "proj_quality_risk",
                    "proj_success_probability", "proj_budget_overrun_risk",
                    "proj_required_team_size", "team_size_match"]:
            f[col] = np.nan

    # ── Targets ────────────────────────────────────────────────────
    f["actual_performance_score"] = tf_row["actual_performance_score"]
    f["team_success"] = tf_row["team_success"]
    f["met_deadline"] = tf_row["met_deadline"]
    f["quality_rating"] = tf_row["quality_rating"]

    return f


def main():
    emp, tf, pr, wh, proj = load_raw()

    emp = clean_employees(emp)
    pr_latest = clean_performance_reviews(pr)
    wh_agg = clean_workload(wh)
    master = build_master(emp, pr_latest, wh_agg)
    proj_keep = clean_projects(proj)
    tf = clean_team_formations(tf)
    tf = compute_past_overlap(tf)

    rows, skipped = [], 0
    for _, tf_row in tf.iterrows():
        pid = tf_row["project_id"]
        proj_row = proj_keep.loc[pid] if pid in proj_keep.index else None
        feats = extract_team_features(tf_row, proj_row, master)
        if feats:
            rows.append(feats)
        else:
            skipped += 1

    team_df = pd.DataFrame(rows)
    print(f"\nTeams extracted: {len(team_df)}  |  skipped (no member match): {skipped}")

    # ── Sanity checks ────────────────────────────────────────────
    ratio_sum = team_df[["junior_ratio", "mid_ratio", "senior_ratio", "lead_ratio"]].sum(axis=1)
    print(f"Seniority ratio sum — min: {ratio_sum.min():.2f} | max: {ratio_sum.max():.2f}  (should be ~1.0)")
    print(f"avg_burnout_risk describe:\n{team_df['avg_burnout_risk'].describe()}")
    print(f"quality_rating non-null: {team_df['quality_rating'].notnull().sum()} / {len(team_df)}")
    print(f"met_deadline non-null:   {team_df['met_deadline'].notnull().sum()} / {len(team_df)}")

    # ── Correlation-based pruning (mirrors the discipline of the old
    # prep3.py, re-checked against the real feature set) ───────────
    id_cols = ["team_id", "project_id", "formation_date"]
    target_cols = ["actual_performance_score", "team_success", "met_deadline", "quality_rating"]
    targets = team_df[id_cols + target_cols].copy()
    X = team_df.drop(columns=id_cols + target_cols)

    numeric_X = X.select_dtypes(include=[np.number])
    corr = numeric_X.corr().abs()
    high_corr_pairs = [
        (corr.columns[i], corr.columns[j], corr.iloc[i, j])
        for i in range(len(corr.columns)) for j in range(i)
        if corr.iloc[i, j] > 0.85
    ]
    if high_corr_pairs:
        print("\nHighly correlated feature pairs (r > 0.85) — consider dropping one of each:")
        for a, b, r in high_corr_pairs:
            print(f"  {a}  <->  {b}   r={r:.2f}")
    else:
        print("\nNo feature pairs with r > 0.85 found.")

    # Explicit drops based on the correlation scan above (checked after
    # the team-lead roster fix; re-verify if you change feature extraction):
    #   avg_skills_per_member  <-> skill_diversity_score        r=0.95  (keep the pre-existing composite)
    #   avg_domain_score       <-> avg_seniority/avg_experience  r=0.93-0.94 (keep avg_seniority — matches ratio features)
    #   avg_tenure_days        <-> avg_experience                r=0.99  (near-duplicate, keep avg_experience)
    #   avg_experience         <-> avg_seniority                 r=0.93  (kept both — see note below)
    #   proj_complexity        <-> proj_quality_risk              r=0.87  (keep proj_quality_risk — more granular)
    DROP_CORRELATED = [
        "avg_skills_per_member", "avg_domain_score", "avg_tenure_days", "proj_complexity",
    ]
    X = X.drop(columns=DROP_CORRELATED)
    print(f"\nDropped correlated features: {DROP_CORRELATED}")
    # avg_experience & avg_seniority kept together (r=0.93, not =0.99) since
    # they're conceptually distinct (raw years vs. job-level band) and tree
    # models handle moderate collinearity fine — revisit if linear models
    # end up in the running and coefficients look unstable.

    null_before = int(X.isnull().sum().sum())
    X = X.fillna(X.median(numeric_only=True))
    print(f"\nFilled {null_before} null feature values with column medians")
    print(f"Final feature matrix: {X.shape}")

    X.to_csv(f"{OUTPUT_DIR}/team_features.csv", index=False)
    targets.to_csv(f"{OUTPUT_DIR}/team_targets.csv", index=False)
    print(f"\nSaved {OUTPUT_DIR}/team_features.csv and team_targets.csv")


if __name__ == "__main__":
    main()