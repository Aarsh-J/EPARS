import pickle
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

TARGET = "overall_performance_score"

# ---------------------------------------------------
# LOAD
# ---------------------------------------------------
df = pd.read_csv("processed_data.csv")

# helper
def col(name, default=0):
    if name in df.columns:
        return df[name]
    return pd.Series(default, index=df.index)

# ---------------------------------------------------
# BUILD FORMULA FEATURES
# ---------------------------------------------------
technical_cluster = (
    col("technical_competence_score") + col("domain_knowledge_score") + col("problem_solving_score")) / 3 * 10

behavioral_cluster = (
    col("communication_score") + col("collaboration_score") + col("leadership_score") + col("initiative_score") +
    col("time_management_score")) / 5 * 10

quality_norm = col("quality_of_work_score") * 10

productivity_norm = col("productivity_score") * 10

formula_score = (
    technical_cluster * 0.30 +
    behavioral_cluster * 0.25 +
    quality_norm * 0.20 +
    productivity_norm * 0.25
)

X = pd.DataFrame({
    "formula_score": formula_score,
    "historical_performance_score": col("historical_performance_score")
})

y = df[TARGET]

# ---------------------------------------------------
# TRAIN TEST SPLIT
# ---------------------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ---------------------------------------------------
# SCALE
# ---------------------------------------------------
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)
X_all_s = scaler.transform(X)

# ---------------------------------------------------
# MODEL
# ---------------------------------------------------
model = Ridge(alpha=1)
model.fit(X_train_s, y_train)
pred = np.clip(model.predict(X_test_s), 0, 100)

# ---------------------------------------------------
# METRICS
# ---------------------------------------------------
mae = mean_absolute_error(y_test, pred)
rmse = np.sqrt(mean_squared_error(y_test, pred))
r2 = r2_score(y_test, pred)

cv = KFold(n_splits=5, shuffle=True, random_state=42)
cv_r2 = cross_val_score(model, X_all_s, y, cv=cv, scoring="r2").mean()

print("="*60)
print("RIDGE MODEL")
print("="*60)
print("MAE :", round(mae,3))
print("RMSE:", round(rmse,3))
print("R2  :", round(r2,3))
print("CV  :", round(cv_r2,3))

# ---------------------------------------------------
# SAVE MODEL
# ---------------------------------------------------
pickle.dump(model, open("ridge_model.pkl","wb"))
pickle.dump(scaler, open("scaler.pkl","wb"))

# ---------------------------------------------------
# PLOT 1 ACTUAL VS PRED WITH LINE
# ---------------------------------------------------
plt.figure(figsize=(8,6))
plt.scatter(y_test, pred, alpha=0.6)
min_val = min(y_test.min(), pred.min())
max_val = max(y_test.max(), pred.max())
plt.plot(
    [min_val, max_val],
    [min_val, max_val],
    linestyle="--",
    linewidth=2
)
plt.xlabel("Actual")
plt.ylabel("Predicted")
plt.title("Actual vs Predicted")
plt.tight_layout()

plt.savefig("actual_vs_predicted.png", dpi=300)
plt.close()

# ---------------------------------------------------
# PLOT 2 RESIDUALS
# ---------------------------------------------------
residuals = y_test - pred

plt.figure(figsize=(8,6))
plt.hist(residuals, bins=30)
plt.title("Residual Distribution")
plt.xlabel("Error")
plt.savefig("residuals.png", dpi=300)
plt.close()
