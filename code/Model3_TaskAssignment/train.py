"""
train.py
────────────────────────────────────────────────────────────────────────────────
Task Assignment — Model Training & Comparison
────────────────────────────────────────────────────────────────────────────────
Loads master_preprocessed.csv, splits into train/val/test,
trains 4 models on 2 targets, and reports results.

Targets:
  - assignment_success   → Classification (Decision Tree, RF, GB, XGBoost)
  - delay_risk_score     → Regression     (Decision Tree, RF, GB, XGBoost)

Output:
  artifacts/results_classification.csv
  artifacts/results_regression.csv
  artifacts/<model>_<target>.joblib

Run:  python train.py
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
from xgboost import XGBClassifier, XGBRegressor

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    mean_absolute_error, mean_squared_error, r2_score,
)

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# 0. Paths
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(__file__)
ARTIFACTS_DIR  = os.path.join(BASE_DIR, "artifacts")
DATA_PATH      = os.path.join(ARTIFACTS_DIR, "master_preprocessed.csv")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Config
# ─────────────────────────────────────────────────────────────────────────────

# Columns to exclude from feature matrix (IDs + targets)
ID_COLS = ["assignment_id", "task_id", "employee_id", "project_id"]

CLF_TARGET = "assignment_success"
REG_TARGET = "delay_risk_score"

# Train / Val / Test split ratios
TRAIN_RATIO = 0.70
VAL_RATIO   = 0.10
TEST_RATIO  = 0.20

RANDOM_STATE = 42

# ─────────────────────────────────────────────────────────────────────────────
# 2. Model Definitions
# ─────────────────────────────────────────────────────────────────────────────

CLF_MODELS = {
    "Decision Tree":       DecisionTreeClassifier(random_state=RANDOM_STATE),
    "Random Forest":       RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1),
    "Gradient Boosting":   GradientBoostingClassifier(n_estimators=100, random_state=RANDOM_STATE),
    "XGBoost":             XGBClassifier(n_estimators=100, random_state=RANDOM_STATE,
                                         eval_metric="logloss", verbosity=0),
}

REG_MODELS = {
    "Decision Tree":       DecisionTreeRegressor(random_state=RANDOM_STATE),
    "Random Forest":       RandomForestRegressor(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1),
    "Gradient Boosting":   GradientBoostingRegressor(n_estimators=100, random_state=RANDOM_STATE),
    "XGBoost":             XGBRegressor(n_estimators=100, random_state=RANDOM_STATE, verbosity=0),
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_splits(df: pd.DataFrame, target: str):
    """Split into train / val / test. Returns feature matrices and label arrays."""
    drop = ID_COLS + [CLF_TARGET, REG_TARGET]
    X = df.drop(columns=[c for c in drop if c in df.columns])
    y = df[target]

    # First split off test set
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y,
        test_size=TEST_RATIO,
        random_state=RANDOM_STATE,
    )

    # Then split val from train
    val_ratio_adjusted = VAL_RATIO / (TRAIN_RATIO + VAL_RATIO)
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval,
        test_size=val_ratio_adjusted,
        random_state=RANDOM_STATE,
    )

    print(f"    Train: {X_train.shape[0]:,}  |  Val: {X_val.shape[0]:,}  |  Test: {X_test.shape[0]:,}")
    return X_train, X_val, X_test, y_train, y_val, y_test


def eval_classifier(model, X_val, y_val, X_test, y_test) -> dict:
    results = {}
    for split_name, X, y in [("val", X_val, y_val), ("test", X_test, y_test)]:
        pred = model.predict(X)
        results[f"{split_name}_accuracy"]  = round(accuracy_score(y, pred), 4)
        results[f"{split_name}_precision"] = round(precision_score(y, pred, zero_division=0), 4)
        results[f"{split_name}_recall"]    = round(recall_score(y, pred, zero_division=0), 4)
        results[f"{split_name}_f1"]        = round(f1_score(y, pred, zero_division=0), 4)
    return results


def eval_regressor(model, X_val, y_val, X_test, y_test) -> dict:
    results = {}
    for split_name, X, y in [("val", X_val, y_val), ("test", X_test, y_test)]:
        pred = model.predict(X)
        results[f"{split_name}_mae"]  = round(mean_absolute_error(y, pred), 4)
        results[f"{split_name}_rmse"] = round(np.sqrt(mean_squared_error(y, pred)), 4)
        results[f"{split_name}_r2"]   = round(r2_score(y, pred), 4)
    return results


def print_clf_table(rows: list[dict]):
    header = f"  {'Model':<22} {'Val Acc':>8} {'Val Pre':>8} {'Val Rec':>8} {'Val F1':>8} {'Test Acc':>9} {'Test Pre':>9} {'Test Rec':>9} {'Test F1':>9}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for r in rows:
        print(
            f"  {r['model']:<22}"
            f" {r['val_accuracy']:>8.4f}"
            f" {r['val_precision']:>8.4f}"
            f" {r['val_recall']:>8.4f}"
            f" {r['val_f1']:>8.4f}"
            f" {r['test_accuracy']:>9.4f}"
            f" {r['test_precision']:>9.4f}"
            f" {r['test_recall']:>9.4f}"
            f" {r['test_f1']:>9.4f}"
        )


def print_reg_table(rows: list[dict]):
    header = f"  {'Model':<22} {'Val MAE':>9} {'Val RMSE':>10} {'Val R²':>8} {'Test MAE':>10} {'Test RMSE':>11} {'Test R²':>9}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for r in rows:
        print(
            f"  {r['model']:<22}"
            f" {r['val_mae']:>9.4f}"
            f" {r['val_rmse']:>10.4f}"
            f" {r['val_r2']:>8.4f}"
            f" {r['test_mae']:>10.4f}"
            f" {r['test_rmse']:>11.4f}"
            f" {r['test_r2']:>9.4f}"
        )


def best_clf(rows: list[dict]) -> str:
    return max(rows, key=lambda r: r["test_f1"])["model"]


def best_reg(rows: list[dict]) -> str:
    return max(rows, key=lambda r: r["test_r2"])["model"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Main
# ─────────────────────────────────────────────────────────────────────────────

def run_training():
    print("\n" + "="*70)
    print("  TASK ASSIGNMENT — MODEL TRAINING & COMPARISON")
    print("="*70)

    # ── Load data ────────────────────────────────────────────────────────────
    print(f"\n[1] Loading data from {DATA_PATH} …")
    df = pd.read_csv(DATA_PATH)
    print(f"    Shape: {df.shape}")

    # Verify targets exist
    for t in [CLF_TARGET, REG_TARGET]:
        assert t in df.columns, f"Target column '{t}' not found in dataset!"
    print(f"    Targets confirmed: '{CLF_TARGET}', '{REG_TARGET}'")

    # ── Classification: assignment_success ───────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  TARGET 1: {CLF_TARGET.upper()} (Classification)")
    print(f"{'='*70}")
    print(f"\n  Class distribution:\n{df[CLF_TARGET].value_counts().to_string()}\n")

    print("  Splitting data …")
    X_train, X_val, X_test, y_train, y_val, y_test = make_splits(df, CLF_TARGET)

    clf_rows = []
    for name, model in CLF_MODELS.items():
        print(f"  Training {name} …")
        model.fit(X_train, y_train)
        metrics = eval_classifier(model, X_val, y_val, X_test, y_test)
        metrics["model"] = name
        clf_rows.append(metrics)

        # Save artifact
        safe_name = name.lower().replace(" ", "_")
        joblib.dump(model, os.path.join(ARTIFACTS_DIR, f"{safe_name}_clf.joblib"))

    print(f"\n  ── Classification Results ──────────────────────────────────────")
    print_clf_table(clf_rows)
    winner_clf = best_clf(clf_rows)
    print(f"\n  ★  Best model (Test F1): {winner_clf}")

    clf_df = pd.DataFrame(clf_rows)[
        ["model",
         "val_accuracy", "val_precision", "val_recall", "val_f1",
         "test_accuracy", "test_precision", "test_recall", "test_f1"]
    ]
    clf_csv = os.path.join(ARTIFACTS_DIR, "results_classification.csv")
    clf_df.to_csv(clf_csv, index=False)
    print(f"  Saved → {clf_csv}")

    # ── Regression: delay_risk_score ─────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  TARGET 2: {REG_TARGET.upper()} (Regression)")
    print(f"{'='*70}")
    print(f"\n  Target stats:\n{df[REG_TARGET].describe().to_string()}\n")

    print("  Splitting data …")
    X_train, X_val, X_test, y_train, y_val, y_test = make_splits(df, REG_TARGET)

    reg_rows = []
    for name, model in REG_MODELS.items():
        print(f"  Training {name} …")
        model.fit(X_train, y_train)
        metrics = eval_regressor(model, X_val, y_val, X_test, y_test)
        metrics["model"] = name
        reg_rows.append(metrics)

        # Save artifact
        safe_name = name.lower().replace(" ", "_")
        joblib.dump(model, os.path.join(ARTIFACTS_DIR, f"{safe_name}_reg.joblib"))

    print(f"\n  ── Regression Results ──────────────────────────────────────────")
    print_reg_table(reg_rows)
    winner_reg = best_reg(reg_rows)
    print(f"\n  ★  Best model (Test R²): {winner_reg}")

    reg_df = pd.DataFrame(reg_rows)[
        ["model",
         "val_mae", "val_rmse", "val_r2",
         "test_mae", "test_rmse", "test_r2"]
    ]
    reg_csv = os.path.join(ARTIFACTS_DIR, "results_regression.csv")
    reg_df.to_csv(reg_csv, index=False)
    print(f"  Saved → {reg_csv}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"  Classification  ({CLF_TARGET})")
    for r in clf_rows:
        marker = " ★" if r["model"] == winner_clf else ""
        print(f"    {r['model']:<22}  Acc={r['test_accuracy']:.4f}  F1={r['test_f1']:.4f}{marker}")
    print(f"\n  Regression  ({REG_TARGET})")
    for r in reg_rows:
        marker = " ★" if r["model"] == winner_reg else ""
        print(f"    {r['model']:<22}  MAE={r['test_mae']:.4f}  RMSE={r['test_rmse']:.4f}  R²={r['test_r2']:.4f}{marker}")
    print(f"\n{'='*70}")
    print(f"  TRAINING COMPLETE")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    run_training()
