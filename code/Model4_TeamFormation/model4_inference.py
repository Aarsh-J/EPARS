# =============================================================
# MODEL 4 — TEAM FORMATION
# model4_inference.py
#
# Loads model4.pkl and produces the structured JSON output
# defined in the pipeline (Section 8).
#
# Usage:
#   python model4_inference.py --team_id TEAM042
#   python model4_inference.py --all          # score every team in features CSV
#
# Run after model4_train.py.
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
    FEATURES_FILE, MODEL_FILE,
    TARGET_COL, DROP_COLS,
)


# ── Helpers ────────────────────────────────────────────────────

def _performance_tier(score: float) -> str:
    if score < 60:
        return "Low"
    elif score < 75:
        return "Medium"
    elif score < 88:
        return "High"
    return "Exceptional"


def _confidence_band(model, X_row: np.ndarray, pred: float) -> dict:
    """
    Tree-based models: use per-tree predictions to estimate
    10th–90th percentile spread.
    Ridge: use ±1.5 × residual std stored at train time (approximated as 8.0).
    """
    if hasattr(model, "estimators_"):
        # RandomForest / GradientBoosting
        tree_preds = []
        for est in model.estimators_:
            if isinstance(est, (list, np.ndarray)):
                # GradientBoosting stores estimators differently
                for sub_est in est:
                    if hasattr(sub_est, "predict"):
                        tree_preds.append(sub_est.predict(X_row)[0])
            else:
                if hasattr(est, "predict"):
                    tree_preds.append(est.predict(X_row)[0])

        if len(tree_preds) >= 2:
            low  = float(np.percentile(tree_preds, 10))
            high = float(np.percentile(tree_preds, 90))
            # Clamp to valid score range
            return {
                "low" : round(max(0.0, low), 1),
                "high": round(min(100.0, high), 1),
            }

    # Fallback: ±8 points (approximate 80% interval for Ridge)
    return {
        "low" : round(max(0.0, pred - 8.0), 1),
        "high": round(min(100.0, pred + 8.0), 1),
    }


def _top_features(model, feature_names: list, n: int = 5) -> list:
    """Return top-N features by importance (or |coefficient|)."""
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        importances = np.abs(model.coef_)
    else:
        return []

    idx = np.argsort(importances)[::-1][:n]
    return [
        {"feature": feature_names[i], "importance": round(float(importances[i]), 4)}
        for i in idx
    ]


def _risk_flags(row: pd.Series) -> dict:
    """
    Compute simple threshold-based risk flags from feature values.
    Thresholds are conservative; adapt to your organisation's policies.
    """
    return {
        "high_burnout_member"  : bool(row.get("max_burnout_risk", 0) >= 70),
        "low_skill_utilization": bool(row.get("skill_utilization_rate", 100) < 60),
        "workload_imbalance"   : bool(row.get("workload_balance_score", 100) < 50),
        "low_availability"     : bool(row.get("pct_available", 1.0) < 0.5),
    }


# ── Core prediction function ──────────────────────────────────

def predict_team(team_id: str, features_df: pd.DataFrame, payload: dict) -> dict:
    """
    Score one team and return the full output JSON (Section 8 of pipeline).

    Parameters
    ----------
    team_id     : team identifier to look up in features_df
    features_df : the full model4_features.csv loaded as a DataFrame
    payload     : dict loaded from model4.pkl

    Returns
    -------
    dict — structured prediction result
    """
    model         = payload["model"]
    imputer       = payload["imputer"]
    scaler        = payload["scaler"]
    feature_names = payload["feature_names"]
    uses_scaler   = payload["uses_scaler"]
    model_type    = payload["model_type"]

    # Locate the team row
    row = features_df[features_df["team_id"] == team_id]
    if row.empty:
        raise ValueError(f"team_id '{team_id}' not found in features file.")

    row = row.iloc[0]

    # Keep only the features the model was trained on
    X_raw = row[feature_names].values.reshape(1, -1)

    # Impute → scale (if Ridge)
    X_imp = imputer.transform(X_raw)
    X_fin = scaler.transform(X_imp) if uses_scaler else X_imp

    pred  = float(model.predict(X_fin)[0])
    pred  = round(max(0.0, min(100.0, pred)), 2)

    # Confidence band
    band = _confidence_band(model, X_fin, pred)

    # Feature importances
    top_feats = _top_features(model, feature_names)

    # Risk flags (from raw feature values)
    flags = _risk_flags(row)

    # Retrieve known project_id if available
    project_id = str(row.get("project_id", "")) if "project_id" in features_df.columns else ""

    output = {
        "team_id"                    : team_id,
        "project_id"                 : project_id,
        "predicted_performance_score": pred,
        "confidence_band"            : band,
        "performance_tier"           : _performance_tier(pred),
        "top_contributing_features"  : top_feats,
        "risk_flags"                 : flags,
        "model_metadata"             : {
            "model_type"   : model_type,
            "model_version": payload.get("model_version", "1.0"),
            "training_r2"  : payload.get("train_r2_full"),
            "test_rmse"    : payload["test_metrics"]["rmse"],
            "test_r2"      : payload["test_metrics"]["r2"],
        },
    }
    return output


def predict_all_teams(features_df: pd.DataFrame, payload: dict) -> list[dict]:
    """Score every team in the features file and return a ranked list."""
    all_results = []
    for team_id in features_df["team_id"]:
        try:
            result = predict_team(team_id, features_df, payload)
            all_results.append(result)
        except Exception as e:
            print(f"  Warning: skipping {team_id} — {e}")

    # Rank by predicted score descending
    all_results.sort(key=lambda r: r["predicted_performance_score"], reverse=True)
    for i, r in enumerate(all_results, start=1):
        r["rank"] = i

    return all_results


# ── Load artefacts ────────────────────────────────────────────

def load_model(model_path: str = MODEL_FILE) -> dict:
    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Model file not found: {model_path}\n"
            "Run model4_train.py first."
        )
    with open(model_path, "rb") as f:
        return pickle.load(f)


def load_features(features_path: str = FEATURES_FILE) -> pd.DataFrame:
    if not os.path.exists(features_path):
        raise FileNotFoundError(
            f"Features file not found: {features_path}\n"
            "Run model4_feature_extraction.py first."
        )
    return pd.read_csv(features_path)


# ── CLI entry point ───────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Model 4 — Team Formation Inference"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--team_id", type=str, help="Score a single team by ID")
    group.add_argument("--all",     action="store_true",
                       help="Score all teams and print ranked list")

    parser.add_argument("--out", type=str, default=None,
                        help="Optional path to write JSON output")
    args = parser.parse_args()

    print("Loading model artefacts...")
    payload     = load_model()
    features_df = load_features()
    print(f"  Model type : {payload['model_type']}")
    print(f"  Features   : {len(payload['feature_names'])}")
    print(f"  Teams      : {len(features_df)}")

    if args.team_id:
        result = predict_team(args.team_id, features_df, payload)
        output_json = json.dumps(result, indent=2)
        print("\n" + output_json)

        if args.out:
            with open(args.out, "w") as f:
                f.write(output_json)
            print(f"\nSaved → {args.out}")

    else:  # --all
        results = predict_all_teams(features_df, payload)
        print(f"\nRanked {len(results)} teams:")
        print(f"{'Rank':<5} {'Team ID':<12} {'Score':>6}  {'Tier':<12}  Flags")
        print("-" * 55)
        for r in results[:20]:   # show top 20 by default
            flags_str = ", ".join(
                k for k, v in r["risk_flags"].items() if v
            ) or "—"
            print(
                f"  {r['rank']:<4} {r['team_id']:<12} "
                f"{r['predicted_performance_score']:>6.1f}  "
                f"{r['performance_tier']:<12}  {flags_str}"
            )
        if len(results) > 20:
            print(f"  ... ({len(results) - 20} more)")

        if args.out:
            with open(args.out, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nFull ranked list saved → {args.out}")
