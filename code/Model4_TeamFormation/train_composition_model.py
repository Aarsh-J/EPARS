"""
Train the Model 4 composition anomaly detector (Isolation Forest).
Run:  python train_composition_model.py
Evaluation is honest about having no outcome label: we hold out 20% of REAL
teams and check that they score as typical, while synthetic random-roster teams
(same sizes, employees drawn uniformly) score as anomalous.
"""
import os
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

import composition_model as cm

SEED = 42


def build_matrix(teams: pd.DataFrame) -> pd.DataFrame:
    rows = [cm.team_features(cm.historical_team_members(r)) for _, r in teams.iterrows()]
    return pd.DataFrame(rows)[cm.FEATURE_COLUMNS]


def fit(X: pd.DataFrame):
    scaler = StandardScaler().fit(X)
    forest = IsolationForest(n_estimators=100, contamination="auto", random_state=SEED).fit(scaler.transform(X))
    return scaler, forest


def main():
    teams = pd.read_csv(os.path.join(cm.DATASET_DIR, "team_formations.csv"))
    X = build_matrix(teams)
    X_tr, X_te = train_test_split(X, test_size=0.2, random_state=SEED)

    # synthetic "nobody would staff it this way" teams, matching historical sizes
    rng = np.random.default_rng(SEED)
    all_ids = np.array(sorted(cm.employee_ids_known()))
    sizes = [len(cm.historical_team_members(r)) for _, r in teams.iterrows()]
    X_rand = pd.DataFrame([cm.team_features(list(rng.choice(all_ids, size=n, replace=False)))
                           for n in sizes])[cm.FEATURE_COLUMNS]

    # ---- validation fit on train split only
    scaler, forest = fit(X_tr)
    s_te = forest.score_samples(scaler.transform(X_te))
    s_rand = forest.score_samples(scaler.transform(X_rand))
    auc = roc_auc_score([1] * len(s_te) + [0] * len(s_rand), np.r_[s_te, s_rand])
    thr_raw = np.percentile(forest.score_samples(scaler.transform(X_tr)), 5)
    print(f"Held-out real teams flagged anomalous (<train p5): {(s_te < thr_raw).mean():.1%}  (expect ~5%)")
    print(f"Random-roster teams flagged anomalous:             {(s_rand < thr_raw).mean():.1%}")
    print(f"AUC (held-out real vs random rosters):             {auc:.3f}")

    # ---- final fit on all real teams
    scaler, forest = fit(X)
    s_all = forest.score_samples(scaler.transform(X))
    lo, hi = np.percentile(s_all, 1), np.percentile(s_all, 99)
    thr = float(np.clip((np.percentile(s_all, 5) - lo) / (hi - lo) * 100.0, 0, 100))
    model = cm.CompositionModel(scaler, forest, lo, hi, thr)
    os.makedirs(os.path.dirname(cm.ARTIFACT_PATH), exist_ok=True)
    joblib.dump(model, cm.ARTIFACT_PATH)
    print(f"Saved {cm.ARTIFACT_PATH}  (anomaly threshold = typicality < {thr:.1f})")


if __name__ == "__main__":
    main()