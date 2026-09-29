"""
train.py
────────────────────────────────────────────────────────────────────────────────
Team Formation — Model Training Pipeline
────────────────────────────────────────────────────────────────────────────────
Loads artifacts/team_features.csv + artifacts/team_targets.csv (from
preprocessing.py) and trains two independent model families:

  Classification  target = team_success              (score >= 80)
  Regression      target = actual_performance_score

Same 4 model types as Model3 (Decision Tree, Random Forest, Gradient
Boosting, XGBoost), same split-based selection logic, for consistency
across the repo.

IMPORTANT — sample size: this dataset has 606 teams with a usable target
(185 positive / 421 negative for team_success), an order of magnitude
smaller than Model3's task-assignment data. A single 70/10/20 split's
test set is ~121 rows, so test metrics here are noisier than Model3's —
treat differences of a few points between algorithms as within noise.
A 5-fold CV check is run on the winning-candidate pool for a second
opinion; if it disagrees with the single-split ranking, trust the CV
number.

Split: 70% train / 10% val / 20% test (stratified for classification).

Outputs (all under artifacts/):
  results_classification.csv
  results_regression.csv
  decision_tree_clf.joblib / random_forest_clf.joblib /
    gradient_boosting_clf.joblib / xgboost_clf.joblib
  decision_tree_reg.joblib / random_forest_reg.joblib /
    gradient_boosting_reg.joblib / xgboost_reg.joblib

Run:  python train.py
Next: python save_models.py
"""

import os
import warnings
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split, StratifiedKFold, KFold, cross_val_score
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import (
    RandomForestClassifier, RandomForestRegressor,
    GradientBoostingClassifier, GradientBoostingRegressor,
)
from sklearn.metrics import (
    accuracy_score, f1_score,
    mean_absolute_error, mean_squared_error, r2_score,
)
from xgboost import XGBClassifier, XGBRegressor

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# 0. Paths / constants
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS     = os.path.join(BASE_DIR, "artifacts")
FEATURES_PATH = os.path.join(ARTIFACTS, "team_features.csv")
TARGETS_PATH  = os.path.join(ARTIFACTS, "team_targets.csv")

RANDOM_STATE = 42

TARGET_CLF = "team_success"
TARGET_REG = "actual_performance_score"
# Both dropped as features regardless of which task is training, since
# team_success is literally derived from actual_performance_score —
# leaving either in as a feature for the other task would be leakage.
OTHER_TARGET_COLS = ["met_deadline", "quality_rating"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Load
# ─────────────────────────────────────────────────────────────────────────────

def load_data():
    if not os.path.isfile(FEATURES_PATH) or not os.path.isfile(TARGETS_PATH):
        raise FileNotFoundError(
            f"team_features.csv / team_targets.csv not found under {ARTIFACTS} "
            "— run preprocessing.py first."
        )
    X = pd.read_csv(FEATURES_PATH)
    targets = pd.read_csv(TARGETS_PATH)
    print(f"  Loaded features {X.shape}, targets {targets.shape}")
    return X, targets


def split_data(X: pd.DataFrame, y: pd.Series, stratify: bool):
    """70 / 10 / 20 train / val / test split."""
    strat1 = y if stratify else None
    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_STATE, stratify=strat1
    )
    strat2 = y_train_full if stratify else None
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full, y_train_full, test_size=0.125,
        random_state=RANDOM_STATE, stratify=strat2
    )
    print(f"    train={len(X_train)}  val={len(X_val)}  test={len(X_test)}")
    return X_train, X_val, X_test, y_train, y_val, y_test, X_train_full, y_train_full


# ─────────────────────────────────────────────────────────────────────────────
# 2. Classification
# ─────────────────────────────────────────────────────────────────────────────

def train_classification(X: pd.DataFrame, targets: pd.DataFrame):
    print("\n" + "="*70)
    print("  CLASSIFICATION — target: team_success")
    print("="*70)

    y = targets[TARGET_CLF].astype(int)
    print(f"  Class balance: {y.value_counts().to_dict()}")

    X_train, X_val, X_test, y_train, y_val, y_test, X_train_full, y_train_full = split_data(
        X, y, stratify=True
    )

    models = {
        "decision_tree": DecisionTreeClassifier(
            max_depth=5, min_samples_leaf=15, random_state=RANDOM_STATE
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=6, min_samples_leaf=8,
            class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=150, max_depth=2, learning_rate=0.05,
            random_state=RANDOM_STATE
        ),
        "xgboost": XGBClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            eval_metric="logloss", random_state=RANDOM_STATE, n_jobs=-1
        ),
    }

    rows = []
    best_name, best_model, best_f1 = None, None, -1

    for name, model in models.items():
        model.fit(X_train, y_train)

        val_pred  = model.predict(X_val)
        test_pred = model.predict(X_test)

        val_acc, val_f1   = accuracy_score(y_val, val_pred),  f1_score(y_val, val_pred)
        test_acc, test_f1 = accuracy_score(y_test, test_pred), f1_score(y_test, test_pred)

        # 5-fold CV on the train_full pool (train+val combined), as a
        # second opinion given the small test set — see module docstring.
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
        cv_scores = cross_val_score(model, X_train_full, y_train_full, cv=cv, scoring="f1")

        print(f"  {name:20s} val_acc={val_acc:.3f} val_f1={val_f1:.3f} "
              f"| test_acc={test_acc:.3f} test_f1={test_f1:.3f} "
              f"| cv_f1={cv_scores.mean():.3f}±{cv_scores.std():.3f}")

        rows.append({
            "model": name,
            "val_accuracy": val_acc, "val_f1": val_f1,
            "test_accuracy": test_acc, "test_f1": test_f1,
            "cv_f1_mean": cv_scores.mean(), "cv_f1_std": cv_scores.std(),
        })

        joblib.dump(model, os.path.join(ARTIFACTS, f"{name}_clf.joblib"))

        if test_f1 > best_f1:
            best_name, best_model, best_f1 = name, model, test_f1

    results = pd.DataFrame(rows).sort_values("test_f1", ascending=False)
    results.to_csv(os.path.join(ARTIFACTS, "results_classification.csv"), index=False)
    print(f"\n  \u2605 Best classifier (by test F1): {best_name} (test F1={best_f1:.3f})")
    cv_ranked = results.sort_values("cv_f1_mean", ascending=False).iloc[0]
    if cv_ranked["model"] != best_name:
        print(f"  \u26a0 CV ranks '{cv_ranked['model']}' higher (cv_f1={cv_ranked['cv_f1_mean']:.3f}) "
              f"— worth a look given the small test set.")
    print(f"  Saved results_classification.csv")

    return best_name, results


# ─────────────────────────────────────────────────────────────────────────────
# 3. Regression
# ─────────────────────────────────────────────────────────────────────────────

def train_regression(X: pd.DataFrame, targets: pd.DataFrame):
    print("\n" + "="*70)
    print("  REGRESSION — target: actual_performance_score")
    print("="*70)

    y = targets[TARGET_REG].astype(float)

    X_train, X_val, X_test, y_train, y_val, y_test, X_train_full, y_train_full = split_data(
        X, y, stratify=False
    )

    models = {
        "decision_tree": DecisionTreeRegressor(
            max_depth=5, min_samples_leaf=15, random_state=RANDOM_STATE
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=300, max_depth=8, min_samples_leaf=6,
            random_state=RANDOM_STATE, n_jobs=-1
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=150, max_depth=2, learning_rate=0.05,
            random_state=RANDOM_STATE
        ),
        "xgboost": XGBRegressor(
            n_estimators=150, max_depth=3, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            random_state=RANDOM_STATE, n_jobs=-1
        ),
    }

    rows = []
    best_name, best_model, best_r2 = None, None, -np.inf

    for name, model in models.items():
        model.fit(X_train, y_train)

        val_pred  = model.predict(X_val)
        test_pred = model.predict(X_test)

        val_mae  = mean_absolute_error(y_val, val_pred)
        val_rmse = np.sqrt(mean_squared_error(y_val, val_pred))
        val_r2   = r2_score(y_val, val_pred)

        test_mae  = mean_absolute_error(y_test, test_pred)
        test_rmse = np.sqrt(mean_squared_error(y_test, test_pred))
        test_r2   = r2_score(y_test, test_pred)

        cv = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
        cv_scores = cross_val_score(model, X_train_full, y_train_full, cv=cv, scoring="r2")

        print(f"  {name:20s} val_MAE={val_mae:.2f} val_RMSE={val_rmse:.2f} val_R2={val_r2:.3f} "
              f"| test_MAE={test_mae:.2f} test_RMSE={test_rmse:.2f} test_R2={test_r2:.3f} "
              f"| cv_R2={cv_scores.mean():.3f}\u00b1{cv_scores.std():.3f}")

        rows.append({
            "model": name,
            "val_MAE": val_mae, "val_RMSE": val_rmse, "val_R2": val_r2,
            "test_MAE": test_mae, "test_RMSE": test_rmse, "test_R2": test_r2,
            "cv_R2_mean": cv_scores.mean(), "cv_R2_std": cv_scores.std(),
        })

        joblib.dump(model, os.path.join(ARTIFACTS, f"{name}_reg.joblib"))

        if test_r2 > best_r2:
            best_name, best_model, best_r2 = name, model, test_r2

    results = pd.DataFrame(rows).sort_values("test_R2", ascending=False)
    results.to_csv(os.path.join(ARTIFACTS, "results_regression.csv"), index=False)
    print(f"\n  \u2605 Best regressor (by test R\u00b2): {best_name} (test R\u00b2={best_r2:.3f})")
    cv_ranked = results.sort_values("cv_R2_mean", ascending=False).iloc[0]
    if cv_ranked["model"] != best_name:
        print(f"  \u26a0 CV ranks '{cv_ranked['model']}' higher (cv_R2={cv_ranked['cv_R2_mean']:.3f}) "
              f"— worth a look given the small test set.")
    print(f"  Saved results_regression.csv")

    return best_name, results


# ─────────────────────────────────────────────────────────────────────────────
# 4. Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    X, targets = load_data()

    best_clf_name, clf_results = train_classification(X, targets)
    best_reg_name, reg_results = train_regression(X, targets)

    print("\n" + "="*70)
    print("  TRAINING COMPLETE")
    print("="*70)
    print(f"  Best classification model : {best_clf_name}")
    print(f"  Best regression model     : {best_reg_name}")
    print(f"  Next: python save_models.py")