# =============================================================
# MODEL 4 — TEAM FORMATION
# model4_inference.py
#
# Given a team_id, loads raw dataset tables, computes all
# features on-the-fly (same logic as model4_feature_extraction.py),
# and scores the team using model4.pkl.
#
# Does NOT use model4_features.csv.
#
# Usage:
#   python model4_inference.py --team_id TEAM042
#   python model4_inference.py --all
#   python model4_inference.py --team_id TEAM042 --out result.json
# =============================================================

import argparse
import json
import os
import pickle
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from model4_config import (
    DATASET_DIR, OUTPUT_DIR, MODEL_FILE,
    COMPLEXITY_MAP, PRIORITY_MAP, FORMATION_MAP,
    WORKLOAD_LOOKBACK_WEEKS,
    TARGET_COL, DROP_COLS,
)


# ── Load raw datasets ─────────────────────────────────────────

def load_datasets():
    emp  = pd.read_csv(f"{DATASET_DIR}/employees.csv")
    tf   = pd.read_csv(f"{DATASET_DIR}/team_formations.csv")
    pr   = pd.read_csv(f"{DATASET_DIR}/performance_reviews.csv")
    wh   = pd.read_csv(f"{DATASET_DIR}/workload_history.csv")
    proj = pd.read_csv(f"{DATASET_DIR}/projects.csv")
    asgn = pd.read_csv(f"{DATASET_DIR}/task_assignments.csv")
    fb   = pd.read_csv(f"{DATASET_DIR}/feedback.csv")
    return emp, tf, pr, wh, proj, asgn, fb


def build_master_employee(emp, pr, wh):
    emp = emp.copy()
    emp["is_available"] = emp["is_available"].astype(bool)

    pr["review_date"] = pd.to_datetime(pr["review_date"], format="mixed")
    pr_latest = (
        pr.sort_values("review_date", ascending=False)
          .groupby("employee_id", as_index=False)
          .first()
    )
    pr_latest = pr_latest[[
        "employee_id",
        "overall_performance_score",
        "productivity_score",
        "collaboration_score",
        "promotion_recommended",
    ]].rename(columns={
        "overall_performance_score": "review_performance_score",
        "productivity_score":        "review_productivity_score",
        "collaboration_score":       "review_collab_score",
    })

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

    master = emp.merge(pr_latest, on="employee_id", how="left")
    master = master.merge(wh_agg,    on="employee_id", how="left")
    return master


def build_project_index(proj):
    proj = proj.copy()
    proj["complexity_encoded"] = proj["complexity_level"].map(COMPLEXITY_MAP)
    proj["priority_encoded"]   = proj["priority"].map(PRIORITY_MAP).fillna(2)
    return proj[[
        "project_id",
        "complexity_encoded",
        "priority_encoded",
        "success_probability",
        "team_size",
    ]].set_index("project_id")


def build_assignment_agg(asgn):
    return asgn.groupby("employee_id").agg(
        emp_avg_skill_match = ("skill_match_score",         "mean"),
        emp_avg_suitability = ("overall_suitability_score", "mean"),
        emp_avg_efficiency  = ("efficiency_score",           "mean"),
        emp_pct_success     = ("assignment_success",         lambda x: x.astype(float).mean()),
    ).reset_index()


def build_feedback_agg(fb):
    return (
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


# ── Feature extraction for one team ──────────────────────────

def extract_features_for_team(tf_row, proj_index, master, asgn_per_emp, fb_per_team):
    member_ids = [s.strip() for s in str(tf_row["member_ids"]).split(",")]
    members    = master[master["employee_id"].isin(member_ids)].copy()

    if members.empty:
        return None

    f = {}
    n = len(members)

    f["team_size"]                   = n
    f["skill_diversity_score"]       = tf_row["skill_diversity_score"]
    f["experience_balance_score"]    = tf_row["experience_balance_score"]
    f["collaborative_history_score"] = tf_row["collaborative_history_score"]
    f["workload_balance_score"]      = tf_row["workload_balance_score"]
    f["skill_utilization_rate"]      = tf_row["skill_utilization_rate"]
    f["resource_utilization"]        = tf_row["resource_utilization"]
    f["formation_method_encoded"]    = FORMATION_MAP.get(tf_row["formation_method"], 1)

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

    f["std_technical_score"]        = members["technical_proficiency_score"].std()
    f["std_historical_performance"] = members["historical_performance_score"].std()
    f["std_years_experience"]       = members["years_of_experience"].std()
    f["range_years_experience"]     = (members["years_of_experience"].max()
                                       - members["years_of_experience"].min())
    f["max_burnout_risk"]           = members["burnout_risk_score"].max()
    f["min_collaboration_score"]    = members["collaboration_score"].min()
    f["min_task_completion_rate"]   = members["average_task_completion_rate"].min()
    f["std_burnout_risk"]           = members["burnout_risk_score"].std()

    f["pct_high_performers"]  = (members["historical_performance_score"] > 75).mean()
    f["pct_burnout_high"]     = (members["burnout_risk_score"] > 60).mean()
    f["n_members_overloaded"] = int((members["current_project_count"] >= 2).sum())

    pid      = tf_row.get("project_id")
    proj_row = proj_index.loc[pid] if (pid in proj_index.index) else None
    if proj_row is not None:
        f["proj_complexity"]          = proj_row["complexity_encoded"]
        f["proj_priority"]            = proj_row["priority_encoded"]
        f["proj_success_probability"] = proj_row["success_probability"]
        f["proj_required_team_size"]  = proj_row["team_size"]
        f["team_size_match"]          = n / max(proj_row["team_size"], 1)
    else:
        for col in ["proj_complexity", "proj_priority", "proj_success_probability",
                    "proj_required_team_size", "team_size_match"]:
            f[col] = np.nan

    f["avg_performance"]               = members["review_performance_score"].mean()
    f["avg_member_productivity_score"] = members["review_productivity_score"].mean()
    f["avg_review_collab"]             = members["review_collab_score"].mean()
    f["pct_promotion_ready"]           = members["promotion_recommended"].astype(float).mean()

    f["avg_workload_intensity"]   = members["recent_workload_intensity"].mean()
    f["avg_productivity_vs_avg"]  = members["recent_productivity_vs_avg"].mean()
    f["avg_workload_vs_capacity"] = members["recent_workload_pct"].mean()
    f["max_workload_vs_capacity"] = members["recent_workload_pct"].max()
    f["max_overtime_recent"]      = members["recent_avg_overtime"].max()
    f["pct_members_overtime"]     = (members["recent_avg_overtime"].fillna(0) > 0).mean()
    f["avg_burnout_today"]        = members["recent_avg_burnout_today"].mean()
    f["max_burnout_today"]        = members["recent_avg_burnout_today"].max()

    team_asgn = asgn_per_emp[asgn_per_emp["employee_id"].isin(member_ids)]
    if not team_asgn.empty:
        f["avg_skill_match_score"]      = team_asgn["emp_avg_skill_match"].mean()
        f["avg_overall_suitability"]    = team_asgn["emp_avg_suitability"].mean()
        f["avg_assignment_efficiency"]  = team_asgn["emp_avg_efficiency"].mean()
        f["pct_assignments_successful"] = team_asgn["emp_pct_success"].mean()
        f["min_skill_match_score"]      = team_asgn["emp_avg_skill_match"].min()
    else:
        for col in ["avg_skill_match_score", "avg_overall_suitability",
                    "avg_assignment_efficiency", "pct_assignments_successful",
                    "min_skill_match_score"]:
            f[col] = np.nan

    f["experience_x_technical"]    = f["experience_balance_score"] * f["avg_technical_score"] / 100
    f["collab_history_x_teamsize"] = f["collaborative_history_score"] * n / 10
    f["burnout_x_workload"]        = f["avg_burnout_risk"] * f["avg_workload_intensity"] / 100
    f["performance_x_seniority"]   = f["avg_historical_performance"] * f["pct_senior_or_above"]

    # Merge team-level feedback
    fb_row = fb_per_team[fb_per_team["team_id"] == tf_row["team_id"]]
    if not fb_row.empty:
        f["avg_feedback_overall"]       = fb_row.iloc[0]["avg_feedback_overall"]
        f["avg_feedback_collaboration"] = fb_row.iloc[0]["avg_feedback_collaboration"]
        f["avg_feedback_communication"] = fb_row.iloc[0]["avg_feedback_communication"]
    else:
        f["avg_feedback_overall"]       = np.nan
        f["avg_feedback_collaboration"] = np.nan
        f["avg_feedback_communication"] = np.nan

    return f


# ── Scoring helpers ───────────────────────────────────────────

def _performance_tier(score: float) -> str:
    if score < 60:   return "Low"
    if score < 75:   return "Medium"
    if score < 88:   return "High"
    return "Exceptional"


def _confidence_band(model, X_row: np.ndarray, pred: float) -> dict:
    if hasattr(model, "estimators_"):
        tree_preds = []
        for est in model.estimators_:
            if isinstance(est, (list, np.ndarray)):
                for sub_est in est:
                    if hasattr(sub_est, "predict"):
                        tree_preds.append(sub_est.predict(X_row)[0])
            else:
                if hasattr(est, "predict"):
                    tree_preds.append(est.predict(X_row)[0])
        if len(tree_preds) >= 2:
            return {
                "low" : round(max(0.0,   float(np.percentile(tree_preds, 10))), 1),
                "high": round(min(100.0, float(np.percentile(tree_preds, 90))), 1),
            }
    return {
        "low" : round(max(0.0,   pred - 8.0), 1),
        "high": round(min(100.0, pred + 8.0), 1),
    }



def _risk_flags(feat: dict) -> dict:
    return {
        "high_burnout_member"  : bool(feat.get("max_burnout_risk", 0) >= 70),
        "low_skill_utilization": bool(feat.get("skill_utilization_rate", 100) < 60),
        "workload_imbalance"   : bool(feat.get("workload_balance_score", 100) < 50),
        "low_availability"     : bool(feat.get("pct_available", 1.0) < 0.5),
    }


# ── Core predict function ─────────────────────────────────────

def predict_team(team_id: str, tf_df: pd.DataFrame, proj_index, master,
                 asgn_per_emp, fb_per_team, payload: dict) -> dict:
    row = tf_df[tf_df["team_id"] == team_id]
    if row.empty:
        raise ValueError(f"team_id '{team_id}' not found in team_formations.csv")
    tf_row = row.iloc[0]

    feat = extract_features_for_team(tf_row, proj_index, master, asgn_per_emp, fb_per_team)
    if feat is None:
        raise ValueError(f"No member data found for team '{team_id}'")

    model         = payload["model"]
    imputer       = payload["imputer"]
    scaler        = payload["scaler"]
    feature_names = payload["feature_names"]
    uses_scaler   = payload["uses_scaler"]

    feat_series = pd.Series(feat)
    X_raw = feat_series[feature_names].values.reshape(1, -1)

    X_imp = imputer.transform(X_raw)
    X_fin = scaler.transform(X_imp) if uses_scaler else X_imp

    pred = float(model.predict(X_fin)[0])
    pred = round(max(0.0, min(100.0, pred)), 2)

    return {
        "team_id"                    : team_id,
        "predicted_performance_score": pred,
        "confidence_band"            : _confidence_band(model, X_fin, pred),
        "performance_tier"           : _performance_tier(pred),
        "risk_flags"                 : _risk_flags(feat),
        # "model_metadata"             : {
        #     "model_type"   : model_type,
        #     "model_version": payload.get("model_version", "1.0"),
        #     "training_r2"  : payload.get("train_r2_full"),
        #     "test_rmse"    : payload["test_metrics"]["rmse"],
        #     "test_r2"      : payload["test_metrics"]["r2"],
        # },
    }


def predict_all_teams(tf_df, proj_index, master, asgn_per_emp, fb_per_team, payload) -> list:
    results = []
    for team_id in tf_df["team_id"]:
        try:
            results.append(predict_team(
                team_id, tf_df, proj_index, master, asgn_per_emp, fb_per_team, payload
            ))
        except Exception as e:
            print(f"  Warning: skipping {team_id} — {e}")

    results.sort(key=lambda r: r["predicted_performance_score"], reverse=True)
    for i, r in enumerate(results, start=1):
        r["rank"] = i
    return results


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Model 4 — Team Formation Inference")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--team_id", type=str,        help="Score a single team by ID")
    group.add_argument("--all",     action="store_true", help="Score all teams, ranked")
    parser.add_argument("--out",    type=str, default=None, help="Path to write JSON output")
    args = parser.parse_args()

    print("Loading model...")
    if not os.path.exists(MODEL_FILE):
        raise FileNotFoundError(f"Model not found: {MODEL_FILE}\nRun model4_train.py first.")
    with open(MODEL_FILE, "rb") as f:
        payload = pickle.load(f)
    print(f"  Model type : {payload['model_type']}")
    print(f"  Features   : {len(payload['feature_names'])}")

    print("Loading datasets...")
    emp, tf, pr, wh, proj, asgn, fb = load_datasets()

    tf["formation_date"] = pd.to_datetime(tf["formation_date"], format="mixed")

    master       = build_master_employee(emp, pr, wh)
    proj_index   = build_project_index(proj)
    asgn_per_emp = build_assignment_agg(asgn)
    fb_per_team  = build_feedback_agg(fb)
    print(f"  Teams in dataset : {len(tf)}")

    if args.team_id:
        result      = predict_team(args.team_id, tf, proj_index, master,
                                   asgn_per_emp, fb_per_team, payload)
        output_json = json.dumps(result, indent=2)
        print("\n" + output_json)
        if args.out:
            with open(args.out, "w") as f:
                f.write(output_json)
            print(f"\nSaved → {args.out}")

    else:
        results = predict_all_teams(tf, proj_index, master, asgn_per_emp, fb_per_team, payload)
        print(f"\nRanked {len(results)} teams:")
        print(f"{'Rank':<5} {'Team ID':<12} {'Score':>6}  {'Tier':<12}  Flags")
        print("-" * 55)
        for r in results[:20]:
            flags_str = ", ".join(k for k, v in r["risk_flags"].items() if v) or "—"
            print(f"  {r['rank']:<4} {r['team_id']:<12} "
                  f"{r['predicted_performance_score']:>6.1f}  "
                  f"{r['performance_tier']:<12}  {flags_str}")
        if len(results) > 20:
            print(f"  ... ({len(results) - 20} more)")
        if args.out:
            with open(args.out, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nFull ranked list saved → {args.out}")
