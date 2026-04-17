# =============================================================
# MODEL 4 — TEAM FORMATION
# model4_train.py
#
# Reads model4_features.csv, trains four candidate models,
# evaluates them, selects the best, and saves model4.pkl.
#
# Run after model4_feature_extraction.py.
#
# Split strategy: time-based (train on older teams, test on
# newer) — avoids temporal leakage.
# =============================================================

import json
import os
import pickle
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import MinMaxScaler

warnings.filterwarnings("ignore")

from model4_config import (
    FEATURES_FILE, MODEL_FILE, METADATA_FILE,
    TARGET_COL, DROP_COLS,
    TRAIN_SIZE_RATIO, RANDOM_STATE,
)

try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("XGBoost not installed — skipping Model D. (pip install xgboost)")


# ── Step 1 — Load feature table ───────────────────────────────

print("Loading feature table...")
df = pd.read_csv(FEATURES_FILE)
print(f"  Shape: {df.shape}")
print(f"  Target range: {df[TARGET_COL].min():.1f} – {df[TARGET_COL].max():.1f}")


# ── Step 2 — Time-based train / test split ────────────────────
# Train on the oldest TRAIN_SIZE_RATIO of teams; test on the rest.
# This mirrors real deployment: model is built on historical data
# and evaluated on teams it has never seen.

formation_dates = pd.to_datetime(df["formation_date"])
split_date      = formation_dates.quantile(TRAIN_SIZE_RATIO)

train_mask = formation_dates <= split_date
test_mask  = ~train_mask

print(f"\nTime-based split at {split_date.date()}")
print(f"  Train : {train_mask.sum()} teams  (up to {split_date.date()})")
print(f"  Test  : {test_mask.sum()} teams   (after {split_date.date()})")


# ── Step 3 — Build X / y ─────────────────────────────────────

ALL_DROP = DROP_COLS + [TARGET_COL]    # team_id, formation_date, target
X = df.drop(columns=ALL_DROP)
y = df[TARGET_COL]

X_train_raw = X[train_mask].reset_index(drop=True)
X_test_raw  = X[test_mask].reset_index(drop=True)
y_train     = y[train_mask].reset_index(drop=True)
y_test      = y[test_mask].reset_index(drop=True)


# ── Step 4 — Remove near-zero-variance features ───────────────

vt = VarianceThreshold(threshold=0.01)
vt.fit(X_train_raw)
kept_cols = X_train_raw.columns[vt.get_support()].tolist()
removed   = [c for c in X_train_raw.columns if c not in kept_cols]

X_train_filt = X_train_raw[kept_cols]
X_test_filt  = X_test_raw[kept_cols]

if removed:
    print(f"\nRemoved near-zero-variance features: {removed}")
print(f"Features after variance filter: {len(kept_cols)}")


# ── Step 5 — Impute (fit on train only) ──────────────────────

imputer = SimpleImputer(strategy="median")
X_train_imp = pd.DataFrame(
    imputer.fit_transform(X_train_filt), columns=kept_cols
)
X_test_imp = pd.DataFrame(
    imputer.transform(X_test_filt), columns=kept_cols
)


# ── Step 6 — Scale (used for Ridge; trees don't need it) ──────

scaler = MinMaxScaler()
X_train_scaled = pd.DataFrame(
    scaler.fit_transform(X_train_imp), columns=kept_cols
)
X_test_scaled = pd.DataFrame(
    scaler.transform(X_test_imp), columns=kept_cols
)


# ── Step 7 — Evaluation helper ────────────────────────────────

def evaluate(name, y_true, y_pred):
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae  = mean_absolute_error(y_true, y_pred)
    r2   = r2_score(y_true, y_pred)
    print(f"  {name:<30s} | RMSE: {rmse:6.2f} | MAE: {mae:6.2f} | R²: {r2:.4f}")
    return {"rmse": round(rmse, 4), "mae": round(mae, 4), "r2": round(r2, 4)}


# ── Step 8 — Train all candidate models ──────────────────────

print("\n" + "=" * 60)
print("MODEL EVALUATION  (test set)")
print("=" * 60)

results = {}   # model_name → {metrics, model, uses_scaler}

# ── Model A — Random Forest (recommended default) ─────────────
rf = RandomForestRegressor(
    n_estimators=200,
    max_depth=None,
    min_samples_leaf=3,
    random_state=RANDOM_STATE,
    n_jobs=-1,
)
rf.fit(X_train_imp, y_train)
metrics_rf = evaluate("Random Forest", y_test, rf.predict(X_test_imp))
results["Random Forest"] = {"model": rf, "metrics": metrics_rf, "uses_scaler": False}

# ── Model B — Gradient Boosting ───────────────────────────────
gb = GradientBoostingRegressor(
    n_estimators=150,
    learning_rate=0.05,
    max_depth=4,
    subsample=0.8,
    random_state=RANDOM_STATE,
)
gb.fit(X_train_imp, y_train)
metrics_gb = evaluate("Gradient Boosting", y_test, gb.predict(X_test_imp))
results["Gradient Boosting"] = {"model": gb, "metrics": metrics_gb, "uses_scaler": False}

# ── Model C — Ridge Regression (baseline) ────────────────────
ridge = Ridge(alpha=1.0)
ridge.fit(X_train_scaled, y_train)
metrics_ridge = evaluate("Ridge Regression", y_test, ridge.predict(X_test_scaled))
results["Ridge Regression"] = {"model": ridge, "metrics": metrics_ridge, "uses_scaler": True}

# ── Model D — XGBoost (optional) ─────────────────────────────
if XGBOOST_AVAILABLE:
    xgb = XGBRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        random_state=RANDOM_STATE,
        verbosity=0,
    )
    xgb.fit(X_train_imp, y_train)
    metrics_xgb = evaluate("XGBoost", y_test, xgb.predict(X_test_imp))
    results["XGBoost"] = {"model": xgb, "metrics": metrics_xgb, "uses_scaler": False}

print("=" * 60)


# ── Step 9 — Select best model (highest R²) ───────────────────

best_name = max(results, key=lambda k: results[k]["metrics"]["r2"])
best      = results[best_name]
print(f"\nBest model: {best_name}  (R² = {best['metrics']['r2']:.4f})")


# ── Step 10 — Report feature importances ─────────────────────

model_obj = best["model"]
if hasattr(model_obj, "feature_importances_"):
    fi = pd.Series(model_obj.feature_importances_, index=kept_cols)
    top10 = fi.sort_values(ascending=False).head(10)
    print("\nTop-10 feature importances:")
    for feat, imp in top10.items():
        print(f"  {feat:<40s} {imp:.4f}")
elif hasattr(model_obj, "coef_"):
    coef = pd.Series(np.abs(model_obj.coef_), index=kept_cols)
    top10 = coef.sort_values(ascending=False).head(10)
    print("\nTop-10 |coefficients| (Ridge):")
    for feat, val in top10.items():
        print(f"  {feat:<40s} {val:.4f}")


# ── Step 11 — Re-fit best model on full dataset ───────────────
# After selecting the winner on the test split, retrain on ALL
# data so the saved model benefits from every example.

print(f"\nRe-fitting {best_name} on full dataset...")

X_all_filt = X[kept_cols]
X_all_imp  = pd.DataFrame(imputer.fit_transform(X_all_filt), columns=kept_cols)

if best["uses_scaler"]:
    X_all_final = pd.DataFrame(scaler.fit_transform(X_all_imp), columns=kept_cols)
else:
    X_all_final = X_all_imp
    # Re-fit scaler on all data anyway (used for Ridge fallback in inference)
    scaler.fit(X_all_imp)

model_obj.fit(X_all_final, y)

# Training R² on full set (in-sample, informational only)
train_r2 = r2_score(y, model_obj.predict(X_all_final))
print(f"  Training R² (full data): {train_r2:.4f}")


# ── Step 12 — Save artefacts ──────────────────────────────────

os.makedirs(os.path.dirname(MODEL_FILE), exist_ok=True)

payload = {
    "model"        : model_obj,
    "imputer"      : imputer,
    "scaler"       : scaler,
    "feature_names": kept_cols,
    "uses_scaler"  : best["uses_scaler"],
    "model_type"   : type(model_obj).__name__,
    "model_version": "1.0",
    "test_metrics" : best["metrics"],
    "train_r2_full": round(train_r2, 4),
    "all_results"  : {k: v["metrics"] for k, v in results.items()},
}

with open(MODEL_FILE, "wb") as f:
    pickle.dump(payload, f)

metadata = {
    "model_type"   : payload["model_type"],
    "model_version": payload["model_version"],
    "feature_names": kept_cols,
    "n_features"   : len(kept_cols),
    "n_train_teams": int(train_mask.sum()),
    "n_test_teams" : int(test_mask.sum()),
    "test_metrics" : best["metrics"],
    "train_r2_full": round(train_r2, 4),
    "all_model_results": {k: v["metrics"] for k, v in results.items()},
}
with open(METADATA_FILE, "w") as f:
    json.dump(metadata, f, indent=2)

print(f"\nSaved -> {MODEL_FILE}")
print(f"Saved -> {METADATA_FILE}")
print("\nTraining complete.")
