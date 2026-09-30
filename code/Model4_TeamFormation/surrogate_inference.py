"""
surrogate_inference.py
────────────────────────────────────────────────────────────────────────────────
Fast team-quality estimation using the trained surrogate model —
no per-task Model3 calls needed. ~50-100x faster than
team_recommender.recommend_teams() (~0.007s vs ~0.3-1.1s per team in
testing), at a mean absolute error of ~1.16 points on held-out projects
(team_score typically ranges ~49-80).

Use this when you need to quickly compare or rank MANY candidate teams
(e.g. as a pre-filter before running the full search on the most
promising few) — not as a replacement for team_recommender.py, which
remains the authoritative scorer (it's what this model was trained to
approximate, and what generated its training labels).

Run:  python surrogate_inference.py --project-id PRJ001
"""

import os
import argparse
import joblib
import pandas as pd

import team_recommender as tr
from generate_surrogate_data import _cheap_team_features  # same feature logic used for training — must stay in sync

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(BASE_DIR, "artifacts")
MODEL_PATH = os.path.join(ARTIFACTS, "best_surrogate.pkl")
TRAINING_DATA_PATH = os.path.join(ARTIFACTS, "surrogate_training_data.csv")

_model = None
_feature_cols = None


def _load():
    global _model, _feature_cols
    if _model is None:
        if not os.path.isfile(MODEL_PATH):
            raise FileNotFoundError(f"{MODEL_PATH} not found — run train_surrogate.py then save_surrogate_model.py first.")
        _model = joblib.load(MODEL_PATH)
        _feature_cols = [c for c in pd.read_csv(TRAINING_DATA_PATH, nrows=1).columns
                          if c not in ("team_score", "project_id")]
    return _model, _feature_cols


def predict_team_score(assignment: dict, project_id: str) -> float:
    """assignment: {task_id: {"employee_id": ..., "composite_score": ...}}
    — same format team_recommender.py uses internally, and what each
    result's "assignments" list can be rebuilt into."""
    model, feature_cols = _load()
    feats = _cheap_team_features(assignment, project_id)
    X = pd.DataFrame([feats])[feature_cols]
    return float(model.predict(X)[0])


def predict_from_result(result: dict) -> float:
    """Convenience: takes one of recommend_teams()'s own result dicts
    and re-scores it via the surrogate instead of the real pipeline —
    mainly useful for sanity-checking the two against each other."""
    assignment = {
        a["task_id"]: {"employee_id": a["employee_id"], "composite_score": a["task_composite_score"]}
        for a in result["assignments"]
    }
    return predict_team_score(assignment, result["project_id"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Surrogate team-score prediction demo")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--top-m", type=int, default=5)
    args = parser.parse_args()

    real_result = tr.recommend_teams(args.project_id, top_m=args.top_m, num_teams=1)[0]
    predicted = predict_from_result(real_result)

    print(f"Real team_score (full pipeline):  {real_result['team_score']}")
    print(f"Surrogate prediction:              {round(predicted, 1)}")
    print(f"Absolute error:                     {abs(real_result['team_score'] - predicted):.2f}")
