# =============================================================================
# Performance Evaluation Model
# train_1_ridge.py  |  Ridge Regression  |  Complexity: Very Low
# =============================================================================

import os, pickle, warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

ARTIFACTS_DIR = "PEM"
TARGET        = "normalized_performance_score"
MODEL_NAME    = "Ridge Regression"

# =============================================================================
# LOAD DATA
# =============================================================================

print("=" * 65)
print(f"MODEL : {MODEL_NAME}")
print("=" * 65)

df = pd.read_csv(os.path.join(ARTIFACTS_DIR, "processed_data.csv"))
with open(os.path.join(ARTIFACTS_DIR, "feature_list.pkl"), "rb") as f:
    ALL_FEATURES = pickle.load(f)

print(f"Rows: {len(df)}  |  Features: {len(ALL_FEATURES)}")

X = df[ALL_FEATURES]
y = df[TARGET]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"Train: {len(X_train)}  |  Test: {len(X_test)}")


# =============================================================================
# SCALE 
# =============================================================================

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s  = scaler.transform(X_test)
X_s       = scaler.transform(X)

# =============================================================================
# TRAIN
# =============================================================================

print("\nTraining ...")
model = Ridge(alpha=1.0)
model.fit(X_train_s, y_train)
print("Done.")


# =============================================================================
# EVALUATE
# =============================================================================

print("\n" + "=" * 65)
print("EVALUATION")
print("=" * 65)

y_pred = np.clip(model.predict(X_test_s), 0, 100)

mae   = mean_absolute_error(y_test, y_pred)
rmse  = np.sqrt(mean_squared_error(y_test, y_pred))
r2    = r2_score(y_test, y_pred)
mape  = float(np.mean(np.abs((y_test - y_pred) / (y_test + 1e-6))) * 100)
w5    = float(np.mean(np.abs(y_test - y_pred) <= 5)  * 100)
w10   = float(np.mean(np.abs(y_test - y_pred) <= 10) * 100)

kf     = KFold(n_splits=5, shuffle=True, random_state=42)
cv_r2  = cross_val_score(model, X_s, y, cv=kf, scoring="r2")
cv_mae = -cross_val_score(model, X_s, y, cv=kf,
                          scoring="neg_mean_absolute_error")

print(f"\n  {'Metric':<40} {'Value':>10}")
print(f"  {'-'*52}")
print(f"  {'MAE  — avg error in score points':<40} {mae:>10.3f}")
print(f"  {'RMSE — penalises large errors more':<40} {rmse:>10.3f}")
print(f"  {'R²   — variance explained (max 1.0)':<40} {r2:>10.3f}")
print(f"  {'MAPE — avg % error (lower = better)':<40} {mape:>10.2f}%")
print(f"  {'Within 5pts — % predictions close':<40} {w5:>10.1f}%")
print(f"  {'Within 10pts — % predictions close':<40} {w10:>10.1f}%")
print(f"  {'CV R²  mean (5-fold)':<40} {cv_r2.mean():>10.3f}")
print(f"  {'CV R²  std  (5-fold)':<40} {cv_r2.std():>10.3f}")
print(f"  {'CV MAE mean (5-fold)':<40} {cv_mae.mean():>10.3f}")

# Error breakdown by performance band
res = pd.DataFrame({"actual": y_test.values, "predicted": y_pred,
                    "error": np.abs(y_test.values - y_pred)})
res["band"] = pd.cut(res["actual"], bins=[0,45,60,75,90,100],
    labels=["Needs Improvement","Below Average","Meets Average","Above Average","Exceptional"])
print(f"\n  Mean error by performance band:")
print(res.groupby("band", observed=True)["error"].mean().round(2).to_string())


# =============================================================================
# PLOT
# =============================================================================

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
axes[0].scatter(y_test, y_pred, alpha=0.5, color="#4C72B0", edgecolors="white", s=40)
lims = [min(y_test.min(), y_pred.min())-2, max(y_test.max(), y_pred.max())+2]
axes[0].plot(lims, lims, "r--", lw=1.5, label="Perfect prediction")
axes[0].set_xlabel("Actual Score"); axes[0].set_ylabel("Predicted Score")
axes[0].set_title(f"{MODEL_NAME} — Actual vs Predicted (R²={r2:.3f})")
axes[0].legend()

axes[1].hist(y_test - y_pred, bins=25, color="#C44E52", edgecolor="white")
axes[1].axvline(0, color="black", linestyle="--")
axes[1].set_xlabel("Residual (Actual – Predicted)")
axes[1].set_title("Residual Distribution")
plt.tight_layout()
plt.savefig(os.path.join(ARTIFACTS_DIR, "eval_ridge.png"), dpi=120)
plt.close()
print(f"\n[Saved] eval_ridge.png")


# =============================================================================
# SAVE MODEL
# =============================================================================

# Save both the model AND the scaler — predict.py needs both for Ridge
with open(os.path.join(ARTIFACTS_DIR, "performance_model.pkl"), "wb") as f:
    pickle.dump({"model": model, "scaler": scaler, "type": "ridge"}, f)
with open(os.path.join(ARTIFACTS_DIR, "test_indices.pkl"), "wb") as f:
    pickle.dump(X_test.index.tolist(), f)

print(f"[Saved] performance_model.pkl  (Ridge + Scaler)")

print("\n" + "=" * 65)
print(f"SUMMARY — {MODEL_NAME}")
print(f"  MAE : {mae:.3f}")
print(f"  R² : {r2:.3f}")
print(f"  RMSE : {rmse:.3f}")
print("=" * 65)
