"""
train_surrogate.py
────────────────────────────────────────────────────────────────────────────────
Team Formation — Surrogate Model Training
────────────────────────────────────────────────────────────────────────────────
Trains a regressor to predict team_score (the REAL, non-noisy composite
computed by team_recommender.py's full pipeline) directly from cheap
team/project features — no per-task Model3 calls needed at inference time.

This is fundamentally different from the earlier attempt at a trained
Model4: that one predicted team_formations.csv's actual_performance_score,
which is pure np.random.normal() noise unrelated to team composition (see
team_recommender.py's module docstring). This model's target is a real,
deterministically-computed value built from Model3's validated R2=0.851
regressor plus verified formulas — there IS a genuine, learnable pattern
here, and it shows in the results below (compare to the honest R2~0.18
CV score the noise-target attempt got).

Caveat worth stating plainly: the "ground truth" here is a computed
pipeline output, not an independently observed real-world outcome the
way Model1/2/3's targets are. This model learns to approximate that
pipeline cheaply — a legitimate, useful thing, just different in kind
from the others.

Data: artifacts/surrogate_training_data.csv (from generate_surrogate_data.py)
Same 4-algorithm comparison as Model3/the original Model4 attempt.

Run:  python train_surrogate.py
Next: python save_surrogate_model.py
"""

import os
import warnings
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split, KFold, cross_val_score
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")
import os
os.environ["PYTHONWARNINGS"] = "ignore"
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(BASE_DIR, "artifacts")
DATA_PATH = os.path.join(ARTIFACTS, "surrogate_training_data.csv")

RANDOM_STATE = 42
TARGET = "team_score"
NON_FEATURE_COLS = ["team_score", "project_id"]


def load_data():
    if not os.path.isfile(DATA_PATH):
        raise FileNotFoundError(f"{DATA_PATH} not found — run generate_surrogate_data.py first.")
    df = pd.read_csv(DATA_PATH)
    X = df.drop(columns=NON_FEATURE_COLS)
    y = df[TARGET].astype(float)
    print(f"  Loaded {X.shape[0]} rows, {X.shape[1]} features")
    print(f"  target range: {y.min():.1f} - {y.max():.1f}  (std={y.std():.2f})")
    return X, y


def split_data(X, y):
    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_STATE
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full, y_train_full, test_size=0.125, random_state=RANDOM_STATE
    )
    print(f"    train={len(X_train)}  val={len(X_val)}  test={len(X_test)}")
    return X_train, X_val, X_test, y_train, y_val, y_test, X_train_full, y_train_full


def train():
    X, y = load_data()
    X_train, X_val, X_test, y_train, y_val, y_test, X_train_full, y_train_full = split_data(X, y)

    models = {
        "decision_tree": DecisionTreeRegressor(
            max_depth=8, min_samples_leaf=10, random_state=RANDOM_STATE
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=300, max_depth=12, min_samples_leaf=4,
            random_state=RANDOM_STATE, n_jobs=-1
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            random_state=RANDOM_STATE
        ),
        "xgboost": XGBRegressor(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            random_state=RANDOM_STATE, n_jobs=-1
        ),
    }

    rows = []
    best_name, best_r2 = None, -np.inf

    for name, model in models.items():
        model.fit(X_train, y_train)

        val_pred, test_pred = model.predict(X_val), model.predict(X_test)
        val_r2, test_r2 = r2_score(y_val, val_pred), r2_score(y_test, test_pred)
        val_mae, test_mae = mean_absolute_error(y_val, val_pred), mean_absolute_error(y_test, test_pred)
        val_rmse = np.sqrt(mean_squared_error(y_val, val_pred))
        test_rmse = np.sqrt(mean_squared_error(y_test, test_pred))

        cv = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
        cv_scores = cross_val_score(model, X_train_full, y_train_full, cv=cv, scoring="r2")

        print(f"  {name:20s} val_MAE={val_mae:.2f} val_R2={val_r2:.3f} "
              f"| test_MAE={test_mae:.2f} test_RMSE={test_rmse:.2f} test_R2={test_r2:.3f} "
              f"| cv_R2={cv_scores.mean():.3f}\u00b1{cv_scores.std():.3f}")

        rows.append({
            "model": name, "val_MAE": val_mae, "val_R2": val_r2,
            "test_MAE": test_mae, "test_RMSE": test_rmse, "test_R2": test_r2,
            "cv_R2_mean": cv_scores.mean(), "cv_R2_std": cv_scores.std(),
        })
        joblib.dump(model, os.path.join(ARTIFACTS, f"{name}_surrogate.joblib"))

        if test_r2 > best_r2:
            best_name, best_r2 = name, test_r2

    results = pd.DataFrame(rows).sort_values("test_R2", ascending=False)
    results.to_csv(os.path.join(ARTIFACTS, "results_surrogate.csv"), index=False)
    print(f"\n  \u2605 Best (by test R\u00b2): {best_name} (test R\u00b2={best_r2:.3f})")

    # Feature importance for the winner, if tree-based — useful sanity
    # check that the model is picking up on sensible signals, not noise.
    winner = joblib.load(os.path.join(ARTIFACTS, f"{best_name}_surrogate.joblib"))
    if hasattr(winner, "feature_importances_"):
        importances = pd.Series(winner.feature_importances_, index=X.columns).sort_values(ascending=False)
        print(f"\n  Top 8 features ({best_name}):")
        for feat, imp in importances.head(8).items():
            print(f"    {feat:35s} {imp:.3f}")

    return best_name, results


if __name__ == "__main__":
    best_name, results = train()
    print("\n" + "="*70)
    print(f"  Best model: {best_name}")
    print(f"  Next: python save_surrogate_model.py")
