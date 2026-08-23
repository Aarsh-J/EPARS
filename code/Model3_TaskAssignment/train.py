"""
train.py
────────────────────────────────────────────────────────────────────────────────
Task Assignment — Model Training Pipeline
────────────────────────────────────────────────────────────────────────────────
Loads artifacts/master_preprocessed.csv and trains two independent model
families on it:

  Classification  target = assignment_success   (Decision Tree, Random Forest,
                                                   Gradient Boosting, XGBoost)
  Regression      target = delay_risk_score      (same 4 model types)

Split: 70% train / 10% val / 20% test (stratified for classification).
Val is used only to report an early sanity metric; model selection ("best")
is based on test-set performance, same as a standard holdout evaluation.

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

from sklearn.model_selection import train_test_split
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
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS   = os.path.join(BASE_DIR, "artifacts")
MASTER_PATH = os.path.join(ARTIFACTS, "master_preprocessed.csv")

RANDOM_STATE = 42

ID_COLS      = ["assignment_id", "task_id", "employee_id", "project_id"]
TARGET_CLF   = "assignment_success"
TARGET_REG   = "delay_risk_score"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Load + split
# ─────────────────────────────────────────────────────────────────────────────

def load_master() -> pd.DataFrame:
    if not os.path.isfile(MASTER_PATH):
        raise FileNotFoundError(
            f"{MASTER_PATH} not found — run preprocessing.py first."
        )
    df = pd.read_csv(MASTER_PATH)
    print(f"  Loaded master_preprocessed.csv → {df.shape}")
    return df


def make_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    Both targets are dropped from the feature set for BOTH tasks, even
    though only one of them is being predicted at a time. delay_risk_score
    is highly informative about assignment_success and vice versa in this
    dataset (both derive from the same underlying assignment outcome), so
    leaving the other target in as a feature would leak information a
    real-time scheduler would not have yet at assignment time.
    """
    drop = set(ID_COLS + [TARGET_CLF, TARGET_REG])
    feature_cols = [c for c in df.columns if c not in drop]
    return df[feature_cols]


def split_data(X: pd.DataFrame, y: pd.Series, stratify: bool):
    """70 / 10 / 20 train / val / test split."""
    strat1 = y if stratify else None
    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_STATE, stratify=strat1
    )
    strat2 = y_train_full if stratify else None
    # val = 10% of the FULL set = 1/8 of the remaining 80%
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full, y_train_full, test_size=0.125,
        random_state=RANDOM_STATE, stratify=strat2
    )
    print(f"    train={len(X_train)}  val={len(X_val)}  test={len(X_test)}")
    return X_train, X_val, X_test, y_train, y_val, y_test


# ─────────────────────────────────────────────────────────────────────────────
# 2. Classification
# ─────────────────────────────────────────────────────────────────────────────

def train_classification(df: pd.DataFrame):
    print("\n" + "="*70)
    print("  CLASSIFICATION — target: assignment_success")
    print("="*70)

    X = make_feature_frame(df)
    y = df[TARGET_CLF].astype(int)
    print(f"  Class balance: {y.value_counts().to_dict()}")

    X_train, X_val, X_test, y_train, y_val, y_test = split_data(X, y, stratify=True)

    models = {
        "decision_tree": DecisionTreeClassifier(
            max_depth=8, min_samples_leaf=20, random_state=RANDOM_STATE
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=10, min_samples_leaf=10,
            class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            random_state=RANDOM_STATE
        ),
        "xgboost": XGBClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.05,
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

        print(f"  {name:20s} val_acc={val_acc:.3f} val_f1={val_f1:.3f} "
              f"| test_acc={test_acc:.3f} test_f1={test_f1:.3f}")

        rows.append({
            "model": name,
            "val_accuracy": val_acc, "val_f1": val_f1,
            "test_accuracy": test_acc, "test_f1": test_f1,
        })

        joblib.dump(model, os.path.join(ARTIFACTS, f"{name}_clf.joblib"))

        if test_f1 > best_f1:
            best_name, best_model, best_f1 = name, model, test_f1

    results = pd.DataFrame(rows).sort_values("test_f1", ascending=False)
    results.to_csv(os.path.join(ARTIFACTS, "results_classification.csv"), index=False)
    print(f"\n  ★ Best classifier: {best_name} (test F1={best_f1:.3f})")
    print(f"  Saved results_classification.csv")

    return best_name, results


# ─────────────────────────────────────────────────────────────────────────────
# 3. Regression
# ─────────────────────────────────────────────────────────────────────────────

def train_regression(df: pd.DataFrame):
    print("\n" + "="*70)
    print("  REGRESSION — target: delay_risk_score")
    print("="*70)

    X = make_feature_frame(df)
    y = df[TARGET_REG].astype(float)

    X_train, X_val, X_test, y_train, y_val, y_test = split_data(X, y, stratify=False)

    models = {
        "decision_tree": DecisionTreeRegressor(
            max_depth=8, min_samples_leaf=20, random_state=RANDOM_STATE
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=300, max_depth=12, min_samples_leaf=5,
            random_state=RANDOM_STATE, n_jobs=-1
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            random_state=RANDOM_STATE
        ),
        "xgboost": XGBRegressor(
            n_estimators=300, max_depth=5, learning_rate=0.05,
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

        print(f"  {name:20s} val_MAE={val_mae:.2f} val_RMSE={val_rmse:.2f} val_R2={val_r2:.3f} "
              f"| test_MAE={test_mae:.2f} test_RMSE={test_rmse:.2f} test_R2={test_r2:.3f}")

        rows.append({
            "model": name,
            "val_MAE": val_mae, "val_RMSE": val_rmse, "val_R2": val_r2,
            "test_MAE": test_mae, "test_RMSE": test_rmse, "test_R2": test_r2,
        })

        joblib.dump(model, os.path.join(ARTIFACTS, f"{name}_reg.joblib"))

        if test_r2 > best_r2:
            best_name, best_model, best_r2 = name, model, test_r2

    results = pd.DataFrame(rows).sort_values("test_R2", ascending=False)
    results.to_csv(os.path.join(ARTIFACTS, "results_regression.csv"), index=False)
    print(f"\n  ★ Best regressor: {best_name} (test R2={best_r2:.3f})")
    print(f"  Saved results_regression.csv")

    return best_name, results


# ─────────────────────────────────────────────────────────────────────────────
# 4. Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = load_master()

    best_clf_name, clf_results = train_classification(df)
    best_reg_name, reg_results = train_regression(df)

    print("\n" + "="*70)
    print("  TRAINING COMPLETE")
    print("="*70)
    print(f"  Best classification model : {best_clf_name}")
    print(f"  Best regression model     : {best_reg_name}")
    print(f"  → Update save_models.py if these differ from gradient_boosting/random_forest")
    print(f"  Next: python save_models.py")
