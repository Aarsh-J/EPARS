# =============================================================
# MODEL 4 — TEAM FORMATION
# model4_feature_extraction.py
#
# Builds model4_features.csv  (one row per completed team).
# Uses prep3.py as structural reference, adapted for the
# current dataset schema (v3).
#
# Column differences vs. prep3.py / older dataset:
#   - employees: no cross_functional_experience, mentoring_experience,
#                communication_effectiveness
#   - workload_history: no late_hours_indicator  →  derived from
#                       overtime_hours > 0
#   - projects: no strategic_importance
#   - performance_reviews: no reliability_score, adaptability_score,
#                          innovation_score  →  time_management_score used
# =============================================================

import json
import os
import warnings
from itertools import combinations

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", None)

from model4_config import (
    DATASET_DIR, OUTPUT_DIR,
    SENIORITY_MAP, STRESS_MAP, TREND_MAP,
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

emp["hire_date"]   = pd.to_datetime(emp["hire_date"], format="mixed")
emp["tenure_days"] = (pd.Timestamp.today() - emp["hire_date"]).dt.days
emp["is_available"] = emp["is_available"].astype(bool)
emp["certifications"] = emp["certifications"].fillna("")

# Ordinal encodings
emp["seniority_encoded"]      = emp["seniority_level"].map(SENIORITY_MAP)
emp["stress_encoded"]         = emp["stress_level"].map(STRESS_MAP)
emp["productivity_trend_enc"] = emp["productivity_trend"].map(TREND_MAP)

# Combined skill list for coverage calculation
emp["all_skills_list"] = (
    emp["primary_skills"].fillna("") + "," + emp["secondary_skills"].fillna("")
).str.split(",").apply(lambda x: [s.strip().lower() for s in x if s.strip()])

# Derived: project success ratio
emp["project_success_rate"] = (
    emp["successful_project_count"]
    / (emp["successful_project_count"] + emp["failed_project_count"])
).fillna(0)

print(f"employees cleaned  | shape: {emp.shape}")


# ── Step 3 — Clean performance_reviews (latest review per employee) ──

pr["review_date"] = pd.to_datetime(pr["review_date"], format="mixed")
pr_latest = (
    pr.sort_values("review_date", ascending=False)
      .groupby("employee_id", as_index=False)
      .first()
)

pr_keep = [
    "employee_id",
    "overall_performance_score",   # → review_performance_score
    "technical_competence_score",  # → review_technical_score
    "collaboration_score",         # → review_collab_score
    "on_time_delivery_rate",
    "productivity_vs_peers",
    "problem_solving_score",
    "time_management_score",       # replaces reliability/adaptability (not in schema v3)
    "promotion_recommended",
]
pr_latest = pr_latest[pr_keep].rename(columns={
    "overall_performance_score" : "review_performance_score",
    "technical_competence_score": "review_technical_score",
    "collaboration_score"       : "review_collab_score",
})

print(f"performance_reviews cleaned | employees with review: {pr_latest['employee_id'].nunique()}")


# ── Step 4 — Clean workload_history (last N weeks) ───────────

wh["date"]   = pd.to_datetime(wh["date"], format="mixed")
cutoff       = wh["date"].max() - pd.Timedelta(weeks=WORKLOAD_LOOKBACK_WEEKS)
wh_recent    = wh[wh["date"] >= cutoff].copy()

# late_hours_indicator is absent in v3 → derive from overtime_hours > 0
wh_recent["late_hours_indicator"] = (wh_recent["overtime_hours"] > 0).astype(int)

wh_agg = wh_recent.groupby("employee_id").agg(
    recent_avg_hours         = ("total_hours_worked",     "mean"),
    recent_avg_overtime      = ("overtime_hours",         "mean"),
    recent_workload_pct      = ("workload_vs_capacity",   "mean"),
    recent_avg_productivity  = ("productivity_score",     "mean"),
    recent_focus_hours       = ("focused_work_hours",     "mean"),
    late_hours_count         = ("late_hours_indicator",   "sum"),
    weekend_work_count       = ("weekend_work_indicator", "sum"),
    recent_avg_burnout_today = ("burnout_risk_today",     "mean"),
).reset_index()

print(f"workload_history aggregated | employees: {wh_agg['employee_id'].nunique()}")


# ── Step 5 — Build master employee table ─────────────────────
# One row per employee. All member-level signals live here;
# team-level features are aggregated from this in Step 9.

master = emp.copy()
master = master.merge(pr_latest, on="employee_id", how="left")
master = master.merge(wh_agg,    on="employee_id", how="left")

# Remaining capacity this week (fallback: assume 70% utilised if no workload data)
master["available_hours"] = (
    master["weekly_capacity_hours"]
    - master["recent_avg_hours"].fillna(master["weekly_capacity_hours"] * 0.7)
).clip(lower=0)

conflicts = [c for c in master.columns if c.endswith("_x") or c.endswith("_y")]
assert not conflicts, f"Column conflicts after merge: {conflicts}"

print(f"Master employee table | shape: {master.shape}")


# ── Step 6 — Clean projects ───────────────────────────────────

proj["complexity_encoded"] = proj["complexity_level"].map(COMPLEXITY_MAP)
proj["priority_encoded"]   = proj["priority"].map(PRIORITY_MAP).fillna(2)

proj["required_skills_list"] = (
    proj["required_skills"].fillna("").str.split(",")
    .apply(lambda x: [s.strip().lower() for s in x if s.strip()])
)

# budget_per_head: proxy for seniority affordability
proj["budget_per_head"] = proj["budget"] / proj["team_size"].replace(0, np.nan)

proj["resource_consumption_ratio"] = (
    proj["consumed_resources"] / proj["allocated_resources"].replace(0, np.nan)
).fillna(1.0)

proj["milestone_completion_rate"] = (
    proj["completed_milestones"] / proj["total_milestones"].replace(0, np.nan)
).fillna(0.0)

proj_keep = proj[[
    "project_id",
    "complexity_encoded",
    "priority_encoded",
    "budget_per_head",
    "team_size",              # required team size (for team_size_match)
    "delay_risk_score",
    "quality_risk_score",
    "budget_overrun_risk",
    "scope_creep_indicator",
    "success_probability",
    "resource_consumption_ratio",
    "milestone_completion_rate",
    "required_skills_list",
]].set_index("project_id")

print(f"projects cleaned | {len(proj_keep)} projects indexed")


# ── Step 7 — Clean team_formations ───────────────────────────

tf["formation_date"]    = pd.to_datetime(tf["formation_date"], format="mixed")
tf["member_ids_list"]   = tf["member_ids"].str.split(",").apply(
    lambda x: [s.strip() for s in x]
)

def _parse_json(val):
    try:
        return json.loads(str(val).replace("'", '"'))
    except Exception:
        return {}

tf["seniority_mix_parsed"] = tf["seniority_mix"].apply(_parse_json)
tf["met_deadline"] = tf["met_deadline"].map(
    {True: 1, False: 0, "True": 1, "False": 0}
)

# Keep only completed teams that have a valid target
tf = tf[tf["project_completed"] == True].copy()
tf = tf.dropna(subset=["actual_performance_score"]).reset_index(drop=True)

print(f"team_formations | {len(tf)} completed teams with valid target")
print(f"Target stats:\n{tf['actual_performance_score'].describe().round(2)}")


# ── Step 8 — Pre-compute past team overlap ────────────────────
# For each team (ordered by formation_date), count how many
# member-pairs appeared together in any earlier team.
# Only the ratio is kept (scale-invariant).

print("\nComputing past team overlap...")
tf_sorted       = tf.sort_values("formation_date").reset_index(drop=True)
historical_pairs = set()

def _compute_overlap(row):
    members = set(row["member_ids_list"])
    pairs   = list(combinations(sorted(members), 2))
    overlap = sum(1 for p in pairs if p in historical_pairs)
    ratio   = overlap / len(pairs) if pairs else 0.0
    historical_pairs.update(pairs)
    return ratio

tf_sorted["past_team_overlap_ratio"] = [
    _compute_overlap(r) for _, r in tf_sorted.iterrows()
]
tf = tf.merge(
    tf_sorted[["team_id", "past_team_overlap_ratio"]],
    on="team_id", how="left",
)
print(f"  overlap ratio — mean: {tf['past_team_overlap_ratio'].mean():.3f}")


# ── Step 9 — Pre-aggregate task_assignments per employee ──────

asgn_per_emp = asgn.groupby("employee_id").agg(
    emp_avg_skill_match    = ("skill_match_score",        "mean"),
    emp_avg_suitability    = ("overall_suitability_score","mean"),
    emp_avg_compatibility  = ("team_compatibility_score", "mean"),
    emp_avg_efficiency     = ("efficiency_score",         "mean"),
    emp_pct_success        = ("assignment_success",       lambda x: x.astype(float).mean()),
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


# ── Step 11 — Helper functions ────────────────────────────────

def _budget_seniority_fit(member_ids, budget_per_head):
    """Fraction of members whose salary fits within project budget per head."""
    if pd.isna(budget_per_head):
        return np.nan
    members = master[master["employee_id"].isin(member_ids)]
    if members.empty:
        return np.nan
    return (members["current_salary"] <= budget_per_head).mean()


def _skill_coverage(team_skill_set, required_skills_list):
    """Fraction of required project skills present in the team."""
    if not required_skills_list:
        return np.nan
    covered = sum(1 for s in required_skills_list if s in team_skill_set)
    return covered / len(required_skills_list)


# ── Step 12 — Feature extraction (one row per team) ──────────

def extract_team_features(tf_row, proj_row):
    """
    Build a flat feature dict for one completed team.

    Parameters
    ----------
    tf_row   : row from the cleaned team_formations DataFrame
    proj_row : Series from proj_keep (or None if project not found)

    Returns
    -------
    dict  — one entry per feature + target, or None if member table is empty
    """
    member_ids = tf_row["member_ids_list"]
    members    = master[master["employee_id"].isin(member_ids)].copy()

    if members.empty:
        return None

    f = {}
    n = len(members)   # actual member count (may differ from team_size column)

    # ── Identifiers (kept for split / traceability, not used as features) ──
    f["team_id"]        = tf_row["team_id"]
    f["formation_date"] = tf_row["formation_date"]

    # ── Team size ─────────────────────────────────────────────
    f["team_size"] = n

    # ── Skill features ────────────────────────────────────────
    all_skills = set(s for sl in members["all_skills_list"] for s in sl)
    f["avg_skills_per_member"] = len(all_skills) / max(n, 1)
    f["avg_technical_score"]   = members["technical_proficiency_score"].mean()
    f["avg_domain_score"]      = members["domain_expertise_score"].mean()
    f["avg_review_technical"]  = members["review_technical_score"].mean()

    if proj_row is not None:
        f["skill_coverage"] = _skill_coverage(all_skills, proj_row["required_skills_list"])
    else:
        f["skill_coverage"] = np.nan

    # ── Seniority mix ─────────────────────────────────────────
    sen = tf_row["seniority_mix_parsed"]
    f["junior_ratio"]        = sen.get("Junior", 0)    / max(n, 1)
    f["mid_ratio"]           = sen.get("Mid", 0)       / max(n, 1)
    f["senior_ratio"]        = sen.get("Senior", 0)    / max(n, 1)
    f["lead_ratio"]          = (sen.get("Lead", 0) + sen.get("Principal", 0)) / max(n, 1)
    f["seniority_diversity"] = sum(1 for v in sen.values() if v > 0)
    f["avg_seniority"]       = members["seniority_encoded"].mean()
    f["max_seniority"]       = members["seniority_encoded"].max()

    # ── Budget fit ────────────────────────────────────────────
    budget_per_head = proj_row["budget_per_head"] if proj_row is not None else np.nan
    f["budget_per_head"]      = budget_per_head
    f["budget_seniority_fit"] = _budget_seniority_fit(member_ids, budget_per_head)

    # ── Role & department diversity ────────────────────────────
    f["n_unique_roles"]       = members["role"].nunique()
    f["n_unique_departments"] = members["department"].nunique()

    # ── Performance history (from reviews) ────────────────────
    f["avg_performance"]           = members["review_performance_score"].mean()
    f["min_performance"]           = members["review_performance_score"].min()
    f["std_performance"]           = members["review_performance_score"].std()
    f["avg_on_time_rate"]          = members["on_time_delivery_rate"].mean()
    f["avg_problem_solving"]       = members["problem_solving_score"].mean()
    f["avg_time_management"]       = members["time_management_score"].mean()
    f["avg_review_collab"]         = members["review_collab_score"].mean()
    f["avg_productivity_vs_peers"] = members["productivity_vs_peers"].mean()
    f["pct_promotion_ready"]       = members["promotion_recommended"].astype(float).mean()

    # ── Collaboration & leadership ─────────────────────────────
    f["avg_collaboration"]      = members["collaboration_score"].mean()
    f["avg_leadership"]         = members["leadership_potential"].mean()
    f["past_team_overlap_ratio"]= tf_row["past_team_overlap_ratio"]

    # ── Burnout & workload ────────────────────────────────────
    f["avg_burnout_risk"]     = members["burnout_risk_score"].mean()
    f["max_burnout_risk"]     = members["burnout_risk_score"].max()
    f["avg_stress"]           = members["stress_encoded"].mean()
    f["avg_available_hours"]  = members["available_hours"].mean()
    f["avg_workload_recent"]  = members["recent_workload_pct"].mean()
    f["avg_overtime_recent"]  = members["recent_avg_overtime"].mean()
    f["avg_burnout_today"]    = members["recent_avg_burnout_today"].mean()
    f["pct_members_overtime"] = (members["recent_avg_overtime"].fillna(0) > 0).mean()

    # ── Experience ────────────────────────────────────────────
    f["avg_experience"]         = members["years_of_experience"].mean()
    f["experience_range"]       = (
        members["years_of_experience"].max() - members["years_of_experience"].min()
    )
    f["avg_productivity_trend"] = members["productivity_trend_enc"].mean()
    f["pct_available"]          = members["is_available"].mean()

    # ── Project success history ────────────────────────────────
    f["avg_project_success_rate"]   = members["project_success_rate"].mean()
    f["total_successful_projects"]  = members["successful_project_count"].sum()

    # ── Task assignment quality ────────────────────────────────
    team_asgn = asgn_per_emp[asgn_per_emp["employee_id"].isin(member_ids)]
    if not team_asgn.empty:
        f["avg_skill_match_score"]     = team_asgn["emp_avg_skill_match"].mean()
        f["avg_overall_suitability"]   = team_asgn["emp_avg_suitability"].mean()
        f["avg_team_compatibility"]    = team_asgn["emp_avg_compatibility"].mean()
        f["avg_assignment_efficiency"] = team_asgn["emp_avg_efficiency"].mean()
        f["pct_assignments_successful"]= team_asgn["emp_pct_success"].mean()
    else:
        for col in [
            "avg_skill_match_score", "avg_overall_suitability",
            "avg_team_compatibility", "avg_assignment_efficiency",
            "pct_assignments_successful",
        ]:
            f[col] = np.nan

    # ── Project context ───────────────────────────────────────
    if proj_row is not None:
        f["proj_complexity"]           = proj_row["complexity_encoded"]
        f["proj_priority"]             = proj_row["priority_encoded"]
        f["proj_delay_risk"]           = proj_row["delay_risk_score"]
        f["proj_quality_risk"]         = proj_row["quality_risk_score"]
        f["proj_budget_overrun_risk"]  = proj_row["budget_overrun_risk"]
        f["proj_scope_creep"]          = proj_row["scope_creep_indicator"]
        f["proj_success_probability"]  = proj_row["success_probability"]
        f["proj_resource_consumption"] = proj_row["resource_consumption_ratio"]
        f["proj_milestone_completion"] = proj_row["milestone_completion_rate"]
        f["proj_required_team_size"]   = proj_row["team_size"]
        f["team_size_match"]           = n / max(proj_row["team_size"], 1)
    else:
        for col in [
            "proj_complexity", "proj_priority", "proj_delay_risk",
            "proj_quality_risk", "proj_budget_overrun_risk", "proj_scope_creep",
            "proj_success_probability", "proj_resource_consumption",
            "proj_milestone_completion", "proj_required_team_size", "team_size_match",
        ]:
            f[col] = np.nan

    # ── Direct columns from team_formations ───────────────────
    f["skill_diversity_score"]       = tf_row["skill_diversity_score"]
    f["experience_balance_score"]    = tf_row["experience_balance_score"]
    f["collaborative_history_score"] = tf_row["collaborative_history_score"]
    f["workload_balance_score"]      = tf_row["workload_balance_score"]
    f["predicted_success_rate"]      = tf_row["predicted_success_rate"]
    f["skill_utilization_rate"]      = tf_row["skill_utilization_rate"]
    f["resource_utilization"]        = tf_row["resource_utilization"]
    f["formation_method_encoded"]    = FORMATION_MAP.get(tf_row["formation_method"], 1)

    # ── Target ────────────────────────────────────────────────
    f[TARGET_COL] = tf_row["actual_performance_score"]

    return f


# ── Step 13 — Run extraction on all completed teams ───────────

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


# ── Step 14 — Merge team-level feedback ───────────────────────

team_df = team_df.merge(fb_per_team, on="team_id", how="left")
print(f"\nAfter feedback merge: {team_df.shape}")


# ── Step 15 — Sanity checks ───────────────────────────────────

print("\n=== Target distribution ===")
print(team_df[TARGET_COL].describe().round(2))

ratio_sum = team_df[["junior_ratio", "mid_ratio", "senior_ratio", "lead_ratio"]].sum(axis=1)
print(f"\nSeniority ratio sum — min: {ratio_sum.min():.2f}  max: {ratio_sum.max():.2f}")
print("  (>1.0 is normal when seniority_mix counts exceed resolved member count)")

print(f"\navg_burnout_risk range: "
      f"{team_df['avg_burnout_risk'].min():.1f} – {team_df['avg_burnout_risk'].max():.1f}  "
      f"(should NOT be all 0)")


# ── Step 16 — Fill remaining nulls and save ───────────────────

# Fill with column median (tree models tolerate imputed values;
# imputer in train.py will re-fit on X_train only)
feature_cols = [c for c in team_df.columns if c not in DROP_COLS + [TARGET_COL]]
team_df[feature_cols] = team_df[feature_cols].fillna(
    team_df[feature_cols].median(numeric_only=True)
)

# Save: team_id + formation_date kept for traceability / time-split
out = team_df[["team_id", "formation_date"] + feature_cols + [TARGET_COL]]

save_path = FEATURES_FILE
if os.path.exists(save_path):
    os.remove(save_path)
out.to_csv(save_path, index=False)

print(f"\nSaved -> {save_path}")
print(f"  Rows     : {out.shape[0]}")
print(f"  Columns  : {out.shape[1]}  ({len(feature_cols)} features + 2 ID cols + 1 target)")
print(f"\nFeature list:\n{feature_cols}")
