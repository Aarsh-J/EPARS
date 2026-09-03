import pandas as pd
import numpy as np
import joblib
import json
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error, classification_report

# ==============================
# LOAD DATA
# ==============================
df = pd.read_csv("processed.csv")
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

with open("selected_features.json") as f:
    FEATURES = json.load(f)

with open("thresholds.json") as f:
    thresholds = json.load(f)

LOW_MAX = thresholds["low_max"]
MEDIUM_MAX = thresholds["medium_max"]

TARGET = "burnout_risk_computed"


df["stress_load"] = (df["late_hours_frequency"] * df["vacation_days_unused"]) / 10
df["pressure_index"] = df["late_hours_frequency"] + df["role_ambiguity"]

FEATURES = FEATURES + ["stress_load", "pressure_index"]


X = df[FEATURES]
y = df[TARGET]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ==============================
# MODEL
model = GradientBoostingRegressor(
    n_estimators=800,
    learning_rate=0.03,
    max_depth=4,
    min_samples_split=10,
    min_samples_leaf=5,
    subsample=0.85,
    max_features="sqrt",
    random_state=42
)# ==============================


model.fit(X_train, y_train)

# ==============================
# EVALUATION
# ==============================
y_pred = model.predict(X_test)

r2 = r2_score(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))

# cross-validation ONLY on training set
cv = cross_val_score(
    GradientBoostingRegressor(**model.get_params()),
    X_train,
    y_train,
    cv=5,
    scoring="r2"
)

print("=" * 55)
print("📊 REGRESSION METRICS")
print("=" * 55)
print(f"R² Score : {r2:.4f}")
print(f"RMSE     : {rmse:.4f}")
print(f"CV R²    : {cv.mean():.4f} ± {cv.std():.4f}")

# ==============================
# CLASSIFICATION
# ==============================
def categorize(x):
    if x < LOW_MAX:
        return "Low"
    elif x < MEDIUM_MAX:
        return "Medium"
    else:
        return "High"

y_test_cat = y_test.apply(categorize)
y_pred_cat = pd.Series(y_pred, index=y_test.index).apply(categorize)

print("\n📊 CLASSIFICATION REPORT")
print(classification_report(y_test_cat, y_pred_cat, zero_division=0))

accuracy = np.mean(y_test_cat.values == y_pred_cat.values)
print(f"Accuracy : {accuracy:.4f}")

# ==============================
# FEATURE IMPORTANCE
# ==============================
feat_df = pd.DataFrame({
    "Feature": FEATURES,
    "Importance": model.feature_importances_
}).sort_values("Importance", ascending=False)

print("\n🔥 FEATURE IMPORTANCE")
print(feat_df.to_string(index=False))

# ==============================
# SAVE (SAFE BUNDLE)
# ==============================
joblib.dump({
    "model": model,
    "features": FEATURES,
    "low_max": LOW_MAX,
    "medium_max": MEDIUM_MAX
}, "model_bundle.pkl")

feat_df.to_csv("feature_importance.csv", index=False)

print("\n✅ model_bundle.pkl saved")
print("✅ feature_importance.csv saved")