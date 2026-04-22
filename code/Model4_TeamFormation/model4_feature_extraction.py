# =============================================================
# MODEL 4 — TEAM FORMATION
# model4_feature_extraction.py
#
# Builds model4_features.csv  (one row per completed team).
# Features follow decisions.md spec: 45 formation-time-safe
# signals across 7 source tables.
#
# Key corrections vs. old code:
#   - collaborative_history_score recomputed from
#     employees.past_team_members pairwise overlap (NOT read
#     from team_formations, which used collaboration_score avg)
#   - predicted_success_rate dropped (circular feature)
#   - avg_team_compatibility dropped (35% is Normal(70,15) noise)
#   - Execution-state project columns excluded:
#     delay_risk_score, budget_overrun_risk, scope_creep_indicator,
#     quality_risk_score, resource_consumption_ratio,
#     milestone_completion_rate
#   - prep3.py extras removed: seniority ratios, budget_per_head,
#     budget_seniority_fit, avg_stress, avg_available_hours,
#     detailed review breakdowns not in spec
# =============================================================

import os
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", None)

from model4_config import (
    DATASET_DIR, OUTPUT_DIR,
    COMPLEXITY_MAP, PRIORITY_MAP, FORMATION_MAP,
    WORKLOAD_LOOKBACK_WEEKS,
    FEATURES_FILE, DROP_COLS, TARGET_COL,
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Step 1 — Load raw datasets ────────────────────────────────

print("Loading datasets...")
emp  = pd.read_csv(f"{DATASET_DIR}/employees.csv")
tf   = pd.read_csv(f"{DATASET_DIR}/team_formations.csv")
pr   = pd.read_csv(f"{DATASET_DIR}/performance_reviews.csv")
wh   = pd.read_csv(f"{DATASET_DIR}/workload_history.csv")
proj = pd.read_csv(f"{DATASET_DIR}/projects.csv")
asgn = pd.read_csv(f"{DATASET_DIR}/task_assignments.csv")
fb   = pd.read_csv(f"{DATASET_DIR}/feedback.csv")

print(f"  employees        : {emp.shape}")
print(f"  team_formations  : {tf.shape}")
print(f"  performance_rev  : {pr.shape}")
print(f"  workload_history : {wh.shape}")
print(f"  projects         : {proj.shape}")
print(f"  task_assignments : {asgn.shape}")
print(f"  feedback         : {fb.shape}")


# ── Step 2 — Clean employees ──────────────────────────────────

emp["is_available"] = emp["is_available"].astype(bool)

print(f"employees cleaned  | shape: {emp.shape}")


# ── Step 3 — Clean performance_reviews (latest review per employee) ──
# Spec features: avg_member_review_score, avg_member_productivity_score,
#                avg_member_collaboration_review, pct_members_promotion_ready

pr["review_date"] = pd.to_datetime(pr["review_date"], format="mixed")
pr_latest = (
    pr.sort_values("review_date", ascending=False)
      .groupby("employee_id", as_index=False)
      .first()
)

pr_keep = [
    "employee_id",
    "overall_performance_score",  # → review_performance_score
    "productivity_score",         # → review_productivity_score
    "collaboration_score",        # → review_collab_score
    "promotion_recommended",
]
pr_latest = pr_latest[pr_keep].rename(columns={
    "overall_performance_score": "review_performance_score",
    "productivity_score":        "review_productivity_score",
    "collaboration_score":       "review_collab_score",
})

print(f"performance_reviews cleaned | employees with review: {pr_latest['employee_id'].nunique()}")


# ── Step 4 — Clean workload_history (last N weeks) ───────────
# Spec features: avg_workload_intensity, avg_productivity_vs_avg,
#                avg_workload_vs_capacity, pct_members_overtime,
#                team_burnout_risk_today

wh["date"] = pd.to_datetime(wh["date"], format="mixed")
cutoff     = wh["date"].max() - pd.Timedelta(weeks=WORKLOAD_LOOKBACK_WEEKS)
wh_recent  = wh[wh["date"] >= cutoff].copy()

wh_agg = wh_recent.groupby("employee_id").agg(
    recent_workload_intensity  = ("workload_intensity_score", "mean"),
    recent_productivity_vs_avg = ("productivity_vs_avg",      "mean"),
    recent_workload_pct        = ("workload_vs_capacity",     "mean"),
    recent_avg_overtime        = ("overtime_hours",           "mean"),
    recent_avg_burnout_today   = ("burnout_risk_today",       "mean"),
).reset_index()

print(f"workload_history aggregated | employees: {wh_agg['employee_id'].nunique()}")


# ── Step 5 — Build master employee table ─────────────────────
# One row per employee. All member-level signals live here;
# team-level features are aggregated from this in Step 11.

master = emp.copy()
master = master.merge(pr_latest, on="employee_id", how="left")
master = master.merge(wh_agg,    on="employee_id", how="left")

conflicts = [c for c in master.columns if c.endswith("_x") or c.endswith("_y")]
assert not conflicts, f"Column conflicts after merge: {conflicts}"

print(f"Master employee table | shape: {master.shape}")


# ── Step 6 — Clean projects ───────────────────────────────────
# Only columns safe at team formation time are kept.
# Excluded (execution-state, near-zero at formation):
#   delay_risk_score, budget_overrun_risk, scope_creep_indicator,
#   quality_risk_score, resource_consumption_ratio,
#   milestone_completion_rate

proj["complexity_encoded"] = proj["complexity_level"].map(COMPLEXITY_MAP)
proj["priority_encoded"]   = proj["priority"].map(PRIORITY_MAP).fillna(2)

proj_keep = proj[[
    "project_id",
    "complexity_encoded",
    "priority_encoded",
    "success_probability",
    "team_size",            # for proj_required_team_size + team_size_match
]].set_index("project_id")

print(f"projects cleaned | {len(proj_keep)} projects indexed")


# ── Step 7 — Clean team_formations ───────────────────────────

tf["formation_date"]  = pd.to_datetime(tf["formation_date"], format="mixed")
tf["member_ids_list"] = tf["member_ids"].str.split(",").apply(
    lambda x: [s.strip() for s in x]
)

tf = tf[tf["project_completed"] == True].copy()
tf = tf.dropna(subset=["actual_performance_score"]).reset_index(drop=True)

print(f"team_formations | {len(tf)} completed teams with valid target")
print(f"Target stats:\n{tf['actual_performance_score'].describe().round(2)}")


# ── Step 8 — (skipped) ───────────────────────────────────────
# collaborative_history_score is read directly from team_formations
# (dataset-generated value) in extract_team_features below.


# ── Step 9 — Pre-aggregate task_assignments per employee ──────
# avg_team_compatibility excluded — 35% of team_compatibility_score
# is Normal(70,15) random noise by dataset generator design.

asgn_per_emp = asgn.groupby("employee_id").agg(
    emp_avg_skill_match = ("skill_match_score",         "mean"),
    emp_avg_suitability = ("overall_suitability_score", "mean"),
    emp_avg_efficiency  = ("efficiency_score",           "mean"),
    emp_pct_success     = ("assignment_success",         lambda x: x.astype(float).mean()),
).reset_index()

print(f"task_assignments aggregated | {asgn_per_emp['employee_id'].nunique()} employees")


# ── Step 10 — Pre-aggregate feedback per team ─────────────────

fb_per_team = (
    fb[fb["related_team_id"].notna()]
      .groupby("related_team_id")
      .agg(
          avg_feedback_overall       = ("overall_rating",       "mean"),
          avg_feedback_collaboration = ("collaboration_rating", "mean"),
          avg_feedback_communication = ("communication_rating", "mean"),
      )
      .reset_index()
      .rename(columns={"related_team_id": "team_id"})
)
print(f"feedback aggregated | {fb_per_team['team_id'].nunique()} teams")


# ── Step 11 — Feature extraction (one row per team) ──────────

def extract_team_features(tf_row, proj_row):
    """
    Build a flat feature dict for one completed team.
    All features are formation-time safe (available before the project runs).
    """
    member_ids = tf_row["member_ids_list"]
    members    = master[master["employee_id"].isin(member_ids)].copy()

    if members.empty:
        return None

    f = {}
    n = len(members)

    # ── Identifiers (kept for split / traceability, not used as features) ──
    f["team_id"]        = tf_row["team_id"]
    f["formation_date"] = tf_row["formation_date"]

    # ── Direct from team_formations ───────────────────────────
    f["team_size"]                   = n
    f["skill_diversity_score"]       = tf_row["skill_diversity_score"]
    f["experience_balance_score"]    = tf_row["experience_balance_score"]
    f["collaborative_history_score"] = tf_row["collaborative_history_score"]
    f["workload_balance_score"]      = tf_row["workload_balance_score"]
    f["skill_utilization_rate"]      = tf_row["skill_utilization_rate"]
    f["resource_utilization"]        = tf_row["resource_utilization"]
    f["formation_method_encoded"]    = FORMATION_MAP.get(tf_row["formation_method"], 1)

    # ── Employee aggregates — means ───────────────────────────────
    f["avg_technical_score"]        = members["technical_proficiency_score"].mean()
    f["avg_domain_score"]           = members["domain_expertise_score"].mean()
    f["avg_historical_performance"] = members["historical_performance_score"].mean()
    f["avg_collaboration"]          = members["collaboration_score"].mean()
    f["avg_leadership"]             = members["leadership_potential"].mean()
    f["avg_burnout_risk"]           = members["burnout_risk_score"].mean()
    f["avg_task_completion_rate"]   = members["average_task_completion_rate"].mean()
    f["avg_years_experience"]       = members["years_of_experience"].mean()
    f["pct_senior_or_above"]        = members["seniority_level"].isin(
                                          ["Senior", "Lead", "Principal"]
                                      ).mean()
    f["pct_available"]              = members["is_available"].mean()
    f["total_successful_projects"]  = members["successful_project_count"].sum()
    f["avg_failed_projects"]        = members["failed_project_count"].mean()
    f["n_unique_roles"]             = members["role"].nunique()
    f["n_unique_departments"]       = members["department"].nunique()

    # ── Dispersion features — std / min / max ─────────────────
    # Averages collapse individual variation by ~sqrt(n); dispersion
    # captures skill gaps, weakest links, and outlier risk.
    f["std_technical_score"]        = members["technical_proficiency_score"].std()
    f["std_historical_performance"] = members["historical_performance_score"].std()
    f["std_years_experience"]       = members["years_of_experience"].std()
    f["range_years_experience"]     = (members["years_of_experience"].max()
                                       - members["years_of_experience"].min())
    f["max_burnout_risk"]           = members["burnout_risk_score"].max()
    f["min_collaboration_score"]    = members["collaboration_score"].min()
    f["min_task_completion_rate"]   = members["average_task_completion_rate"].min()
    f["std_burnout_risk"]           = members["burnout_risk_score"].std()

    # ── Proportion / count features ───────────────────────────
    # Categorical cuts on continuous signals — nonlinear thresholds
    # the model can't easily discover from raw values alone.
    f["pct_high_performers"]        = (
        members["historical_performance_score"] > 75
    ).mean()
    f["pct_burnout_high"]           = (
        members["burnout_risk_score"] > 60
    ).mean()
    f["n_members_overloaded"]       = int(
        (members["current_project_count"] >= 2).sum()
    )

    # ── Project context (formation-time safe only) ─────────────
    if proj_row is not None:
        f["proj_complexity"]          = proj_row["complexity_encoded"]
        f["proj_priority"]            = proj_row["priority_encoded"]
        f["proj_success_probability"] = proj_row["success_probability"]
        f["proj_required_team_size"]  = proj_row["team_size"]
        f["team_size_match"]          = n / max(proj_row["team_size"], 1)
    else:
        for col in [
            "proj_complexity", "proj_priority", "proj_success_probability",
            "proj_required_team_size", "team_size_match",
        ]:
            f[col] = np.nan

    # ── Performance reviews (spec: 4 features) ────────────────
    f["avg_performance"]               = members["review_performance_score"].mean()
    f["avg_member_productivity_score"] = members["review_productivity_score"].mean()
    f["avg_review_collab"]             = members["review_collab_score"].mean()
    f["pct_promotion_ready"]           = members["promotion_recommended"].astype(float).mean()

    # ── Workload history — means, max, min ────────────────────
    f["avg_workload_intensity"]   = members["recent_workload_intensity"].mean()
    f["avg_productivity_vs_avg"]  = members["recent_productivity_vs_avg"].mean()
    f["avg_workload_vs_capacity"] = members["recent_workload_pct"].mean()
    f["max_workload_vs_capacity"] = members["recent_workload_pct"].max()
    f["max_overtime_recent"]      = members["recent_avg_overtime"].max()
    f["pct_members_overtime"]     = (members["recent_avg_overtime"].fillna(0) > 0).mean()
    f["avg_burnout_today"]        = members["recent_avg_burnout_today"].mean()
    f["max_burnout_today"]        = members["recent_avg_burnout_today"].max()

    # ── Task assignment quality ────────────────────────────────
    # avg_team_compatibility excluded — 35% noise by design
    team_asgn = asgn_per_emp[asgn_per_emp["employee_id"].isin(member_ids)]
    if not team_asgn.empty:
        f["avg_skill_match_score"]      = team_asgn["emp_avg_skill_match"].mean()
        f["avg_overall_suitability"]    = team_asgn["emp_avg_suitability"].mean()
        f["avg_assignment_efficiency"]  = team_asgn["emp_avg_efficiency"].mean()
        f["pct_assignments_successful"] = team_asgn["emp_pct_success"].mean()
        f["min_skill_match_score"]      = team_asgn["emp_avg_skill_match"].min()
    else:
        for col in [
            "avg_skill_match_score", "avg_overall_suitability",
            "avg_assignment_efficiency", "pct_assignments_successful",
            "min_skill_match_score",
        ]:
            f[col] = np.nan

    # ── Interaction features ───────────────────────────────────
    # Multiplicative signals the model can't easily construct itself
    # from individual features without very deep trees.
    f["experience_x_technical"]   = (
        f["experience_balance_score"] * f["avg_technical_score"] / 100
    )
    f["collab_history_x_teamsize"]= (
        f["collaborative_history_score"] * n / 10
    )
    f["burnout_x_workload"]       = (
        f["avg_burnout_risk"] * f["avg_workload_intensity"] / 100
    )
    f["performance_x_seniority"]  = (
        f["avg_historical_performance"] * f["pct_senior_or_above"]
    )

    # ── Target ────────────────────────────────────────────────
    f[TARGET_COL] = tf_row["actual_performance_score"]

    return f


# ── Step 12 — Run extraction on all completed teams ───────────

print("\nExtracting features...")
rows, skipped = [], 0

for _, tf_row in tf.iterrows():
    pid      = tf_row["project_id"]
    proj_row = proj_keep.loc[pid] if pid in proj_keep.index else None
    feat     = extract_team_features(tf_row, proj_row)
    if feat:
        rows.append(feat)
    else:
        skipped += 1

team_df = pd.DataFrame(rows)
print(f"  Extracted : {len(team_df)}")
print(f"  Skipped   : {skipped}")
print(f"  Shape     : {team_df.shape}")

top_nulls = team_df.isnull().sum().sort_values(ascending=False).head(10)
if top_nulls.iloc[0] > 0:
    print(f"\nTop null counts:\n{top_nulls}")


# ── Step 13 — Merge team-level feedback ───────────────────────

team_df = team_df.merge(fb_per_team, on="team_id", how="left")
print(f"\nAfter feedback merge: {team_df.shape}")


# ── Step 14 — Sanity checks ───────────────────────────────────

print("\n=== Target distribution ===")
print(team_df[TARGET_COL].describe().round(2))

print(f"\navg_burnout_risk range: "
      f"{team_df['avg_burnout_risk'].min():.1f} – {team_df['avg_burnout_risk'].max():.1f}  "
      f"(should NOT be all 0)")



# ── Step 15 — Fill remaining nulls and save ───────────────────

# Fill with column median (tree models tolerate imputed values;
# imputer in train.py will re-fit on X_train only)
feature_cols = [c for c in team_df.columns if c not in DROP_COLS + [TARGET_COL]]
team_df[feature_cols] = team_df[feature_cols].fillna(
    team_df[feature_cols].median(numeric_only=True)
)

# Save: team_id + formation_date kept for traceability / time-split
out = team_df[["team_id", "formation_date"] + feature_cols + [TARGET_COL]]

save_path = FEATURES_FILE
out.to_csv(save_path, index=False)

print(f"\nSaved -> {save_path}")
print(f"  Rows     : {out.shape[0]}")
print(f"  Columns  : {out.shape[1]}  ({len(feature_cols)} features + 2 ID cols + 1 target)")
print(f"\nFeature list:\n{feature_cols}")
