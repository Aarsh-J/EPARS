# Model 4 — Team Formation & Assignment Model
## Complete Pipeline Documentation

---

## 1. Overview

**Goal:** Predict how well a given team configuration will perform on a project, and surface ranked, explainable team formation recommendations.

> **Scope note:** This model is a *performance scorer* — it evaluates an already-assembled team and predicts its success rate. Team member selection (recommending *who* to include given project requirements) is a planned upstream capability to be implemented in the Agentic AI layer. The ML model acts as the scoring component in that larger pipeline.

**Prediction target:** `actual_performance_score` (float 0–100, from `team_formations`)

**Task type:** Regression (score prediction) + Ranking (ordering candidate configurations)

**Grain of the feature table:** One row = one completed team (team_id)

---

## 2. End-to-End Pipeline Architecture

```
────────────────────────────────────────────────────────────
 PHASE A — TRAINING PIPELINE  (offline, run once / on refresh)
────────────────────────────────────────────────────────────

RAW CSV DATA
     │
     ▼
[STEP 1] Data Loading & Filtering
     │  - Load 8 tables
     │  - Filter team_formations to completed teams only
     │    (project_completed = True, actual_performance_score not null)
     │
     ▼
[STEP 2] Feature Engineering → model4_features.csv
     │  - Team-level aggregations from employees
     │  - Project context features
     │  - Historical performance signals
     │  - Workload & burnout signals
     │  - Assignment quality signals
     │  - Feedback signals
     │
     ▼
[STEP 3] Preprocessing
     │  - Encode categoricals (OrdinalEncoder via model4_config maps)
     │  - Impute nulls (median for numeric)
     │  - Drop near-zero variance features
     │  - Optional: MinMaxScaler for non-tree models
     │
     ▼
[STEP 4] ML Model Training
     │  - Time-based train/test split (80/20, oldest → newest)
     │  - Train 4 candidate models (see Section 7)
     │  - Evaluate: RMSE, MAE, R²
     │  - Select best model, save as model4.pkl
     │
     ▼
[STEP 5] model4.pkl  (model + imputer + scaler + feature_names + metadata)


────────────────────────────────────────────────────────────
 PHASE B — INFERENCE PIPELINE  (runtime, per request)
────────────────────────────────────────────────────────────

[STEP 6] ML Model Scoring
     │  - Input: team_id (looks up row in model4_features.csv)
     │           OR --all (scores every team)
     │  - Runs preprocessed features through model4.pkl
     │  - Output: predicted_performance_score, confidence_band,
     │            performance_tier, top_5_features, risk_flags
     │
     ▼
[STEP 7] AGENTIC AI LAYER  (planned — not yet implemented)
     │
     │  ┌─ [7a] Team Member Selection  ← PLANNED UPSTREAM STEP
     │  │    - Input: project requirements (project_id or direct fields)
     │  │    - Filter eligible employees (skills, availability, burnout)
     │  │    - Score candidates (skill match, performance, workload, collab)
     │  │    - Assemble candidate team(s) + select team lead
     │  │    - Feed assembled team into Step 6 to get predicted score
     │  │
     │  └─ [7b] Policy & Constraint Layer
     │       - RAG lookup: org policies, HR guidelines, headcount limits
     │       - Constraint checks: availability, budget, burnout thresholds
     │       - Reranking: penalize burnout flags, boost collab history
     │       - NL justification generation for HR manager
     │
     ▼
[STEP 8] Final Output to HR Manager / System
     - Suggested member IDs + team lead ID  (from 7a, when implemented)
     - predicted_performance_score + performance_tier
     - Per-recommendation NL justification
     - Risk flags (burnout, skill gaps, overload, availability)
     - Policy compliance status
     - Alternative team configurations (ranked)
```

---

## 3. ML Model Boundary vs Agentic AI Boundary

| Concern | ML Model | Agentic AI |
|---|---|---|
| Predict team performance score | ✅ | ❌ |
| Filter eligible employees for a project | ❌ | ✅ (planned) |
| Select team members + team lead | ❌ | ✅ (planned) |
| Rank candidates by suitability | ✅ (via score) | ✅ (final reranking with context) |
| Enforce HR policies / headcount limits | ❌ | ✅ |
| Explain *why* a team is recommended | ❌ (feature importance only) | ✅ (natural language justification) |
| Check real-time availability | ❌ | ✅ |
| Flag burnout / ethical risks | ❌ | ✅ |
| Trigger notifications / actions | ❌ | ✅ |
| Handle cold-start (new employee) | Partial (clustering fallback) | ✅ (RAG fills context gaps) |

**The ML model stops at the score. The agent decides what to do with it.**

---

## 4. Tables Used & Features to Extract

### 4.1 `team_formations` — Primary Table (one row per team)

These columns are used directly (no aggregation needed):

| Feature | Column | Notes |
|---|---|---|
| `team_size` | `team_size` | Direct |
| `skill_diversity_score` | `skill_diversity_score` | Direct |
| `experience_balance_score` | `experience_balance_score` | Direct |
| `collaborative_history_score` | `collaborative_history_score` | ⚠️ Recompute — see Section 4.1a |
| `workload_balance_score` | `workload_balance_score` | Direct |
| `skill_utilization_rate` | `skill_utilization_rate` | Direct |
| `resource_utilization` | `resource_utilization` | Direct |
| `formation_method_encoded` | `formation_method` | Encode: Manual=0, Hybrid=1, AI=2 |
| **TARGET** | `actual_performance_score` | Drop from features, use as label |

**Dropped from original pipeline (with reasons):**
- `predicted_success_rate` — circular: weighted combo of other features already in the model (multicollinearity)
- Outcome columns: `met_deadline`, `quality_rating`, `budget_adherence`, `stakeholder_satisfaction`, `collaboration_effectiveness`, `completion_time_days`, `team_feedback_score` — post-completion data leakage
- Identifiers: `team_id`, `team_name`, `project_id`, `member_ids`, `team_lead_id`, `role_distribution`, `seniority_mix`, `dissolution_date`, `dissolution_reason`, `created_at`, `last_updated`

#### 4.1a — Recomputing `collaborative_history_score`

The dataset generator used individual `collaboration_score` averages as a proxy. This is incorrect — it measures personal collaboration style, not actual shared team history.

**Correct formula:**
```
For every pair (A, B) in the team:
    check if B appears in A's past_team_members

collaborative_history_score = (pairs with prior history / total possible pairs) × 100
```

Source: `past_team_members` column in `employees.csv`. Must be computed during feature extraction, not read from `team_formations`.

---

### 4.2 `employees` — Aggregated per team via `member_ids`

Explode `member_ids` → join to employees → aggregate per `team_id`:

| Feature | Derivation |
|---|---|
| `avg_technical_proficiency` | mean(`technical_proficiency_score`) |
| `avg_domain_expertise` | mean(`domain_expertise_score`) |
| `avg_historical_performance` | mean(`historical_performance_score`) |
| `avg_collaboration_score` | mean(`collaboration_score`) |
| `avg_leadership_potential` | mean(`leadership_potential`) |
| `avg_burnout_risk` | mean(`burnout_risk_score`) |
| `max_burnout_risk` | max(`burnout_risk_score`) — flag extreme risk |
| `avg_task_completion_rate` | mean(`average_task_completion_rate`) |
| `avg_years_experience` | mean(`years_of_experience`) |
| `std_years_experience` | std(`years_of_experience`) — seniority spread |
| `pct_senior_or_above` | count(seniority ∈ {Senior, Lead, Principal}) / team_size |
| `pct_available` | count(`is_available` == True) / team_size |
| `total_successful_projects` | sum(`successful_project_count`) |
| `avg_failed_projects` | mean(`failed_project_count`) |
| `n_unique_roles` | count distinct roles in team |
| `n_unique_departments` | count distinct departments — cross-functional flag |

Drop: PII columns (name, email), `hire_date`, `salary`, `certifications`, `preferred_work_hours`, `remote_work_status`

Note: `past_team_members` is **actively used** to recompute `collaborative_history_score` (Section 4.1a), not dropped.

---

### 4.3 `projects` — Context features via `project_id`

Join `team_formations.project_id` → `projects`:

| Feature | Column | Notes |
|---|---|---|
| `project_complexity_encoded` | `complexity_level` | Low=1, Medium=2, High=3, Very High=4 |
| `project_priority_encoded` | `priority` | Low=1, Medium=2, High=3, Critical=4 |
| `project_success_probability` | `success_probability` | Direct |

**Dropped from original pipeline (with reasons):**
- `delay_risk_score` — derived from `overdue_milestones` + `days_ahead_behind`: near-zero at formation time, not a valid pre-project signal
- `budget_overrun_risk` — derived from `consumed_resources`: near-zero at formation time
- `scope_creep_indicator` — derived from `overdue_milestones`: near-zero at formation time
- `resource_consumption_ratio` (`consumed/allocated`) — consumed ≈ 0 at formation time
- `milestone_completion_rate` (`completed/total milestones`) — completed ≈ 0 at formation time

Drop: free-text fields, timestamps, `team_member_ids`, `project_manager_id`

---

### 4.4 `performance_reviews` — Historical per-member signal

Group by `employee_id` → aggregate → join via `member_ids`:

| Feature | Derivation |
|---|---|
| `avg_member_review_score` | mean(`overall_performance_score`) per team |
| `avg_member_productivity_score` | mean(`productivity_score`) per team |
| `avg_member_collaboration_review` | mean(`collaboration_score`) per team |
| `pct_members_promotion_ready` | count(`promotion_recommended` == True) / team_size |

Only use employees who have at least one review; others get median imputation.

---

### 4.5 `workload_history` — Recent stress & capacity signals

Aggregate last 30 days per employee → team-level aggregation:

| Feature | Derivation |
|---|---|
| `avg_workload_intensity` | mean(`workload_intensity_score`) per team |
| `avg_productivity_vs_avg` | mean(`productivity_vs_avg`) per team |
| `avg_workload_vs_capacity` | mean(`workload_vs_capacity`) per team |
| `pct_members_overtime` | count(overtime_hours > 0) / team_size |
| `team_burnout_risk_today` | mean(`burnout_risk_today`) per team |

---

### 4.6 `task_assignments` — Assignment quality signals

Group by `employee_id` → aggregate → join via `member_ids`:

| Feature | Derivation |
|---|---|
| `avg_skill_match_score` | mean(`skill_match_score`) per team |
| `avg_overall_suitability` | mean(`overall_suitability_score`) per team |
| `avg_assignment_efficiency` | mean(`efficiency_score`) per team |
| `pct_assignments_successful` | count(`assignment_success` == True) / total per team |

**Dropped:** `avg_team_compatibility` — 35% of `team_compatibility_score` is `Normal(70,15)` pure random noise by dataset generator design. Averaging noise across members adds no signal.

---

### 4.7 `feedback` — Interpersonal quality signal

Filter to `related_team_id` ∈ team's `team_id`:

| Feature | Derivation |
|---|---|
| `avg_feedback_overall_rating` | mean(`overall_rating`) |
| `avg_feedback_collaboration` | mean(`collaboration_rating`) |
| `avg_feedback_communication` | mean(`communication_rating`) |

---

## 5. Feature Table Construction

**Script:** `model4_feature_extraction.py`
**Output:** `model4_features.csv`
**Grain:** 1 row per completed team (team_id)
**Expected rows:** ~75–100 (completed teams only)
**Expected columns:** ~38 features + 1 target (reduced from 45 after audit)

### Construction Steps

```python
# Step 1: Load all tables
teams = pd.read_csv("team_formations.csv")
employees = pd.read_csv("employees.csv")
projects = pd.read_csv("projects.csv")
reviews = pd.read_csv("performance_reviews.csv")
workload = pd.read_csv("workload_history.csv")
assignments = pd.read_csv("task_assignments.csv")
feedback = pd.read_csv("feedback.csv")

# Step 2: Filter to completed teams with known target
teams = teams[
    (teams["project_completed"] == True) &
    (teams["actual_performance_score"].notna())
].copy()

# Step 3: Explode member_ids → per-member rows
teams["member_list"] = teams["member_ids"].str.split(",")
teams_exploded = teams.explode("member_list").rename(
    columns={"member_list": "employee_id"}
)
teams_exploded["employee_id"] = teams_exploded["employee_id"].str.strip()

# Step 4: Join employees and aggregate
emp_feats = teams_exploded.merge(employees, on="employee_id", how="left")
emp_agg = emp_feats.groupby("team_id").agg(
    avg_technical_proficiency=("technical_proficiency_score", "mean"),
    avg_domain_expertise=("domain_expertise_score", "mean"),
    avg_historical_performance=("historical_performance_score", "mean"),
    avg_collaboration_score=("collaboration_score", "mean"),
    avg_leadership_potential=("leadership_potential", "mean"),
    avg_burnout_risk=("burnout_risk_score", "mean"),
    max_burnout_risk=("burnout_risk_score", "max"),
    avg_task_completion_rate=("average_task_completion_rate", "mean"),
    avg_years_experience=("years_of_experience", "mean"),
    std_years_experience=("years_of_experience", "std"),
    total_successful_projects=("successful_project_count", "sum"),
    avg_failed_projects=("failed_project_count", "mean"),
    n_unique_roles=("role", "nunique"),
    n_unique_departments=("department", "nunique"),
    pct_available=("is_available", lambda x: x.sum() / len(x)),
    pct_senior_or_above=("seniority_level",
        lambda x: x.isin(["Senior", "Lead", "Principal"]).sum() / len(x)),
).reset_index()

# Step 4b: Recompute collaborative_history_score from past_team_members
# (replaces the flawed dataset-generated value)
emp_ptm = employees[["employee_id", "past_team_members"]].copy()
emp_ptm["past_set"] = emp_ptm["past_team_members"].fillna("").apply(
    lambda x: set(str(x).split(",")) if x else set()
)
collab_scores = {}
for team_id, grp in teams_exploded.groupby("team_id"):
    members = list(grp["employee_id"].unique())
    ptm_map = emp_ptm.set_index("employee_id")["past_set"].to_dict()
    total_pairs = len(list(combinations(members, 2)))
    if total_pairs == 0:
        collab_scores[team_id] = 0.0
        continue
    history_pairs = sum(
        1 for a, b in combinations(members, 2)
        if b in ptm_map.get(a, set()) or a in ptm_map.get(b, set())
    )
    collab_scores[team_id] = round(history_pairs / total_pairs * 100, 2)
emp_agg["collaborative_history_score"] = emp_agg["team_id"].map(collab_scores)

# Step 5: Join project features (formation-time safe columns only)
proj_feats = projects[[
    "project_id", "complexity_level", "priority", "success_probability"
]].copy()
proj_feats["project_complexity_encoded"] = proj_feats["complexity_level"].map(
    {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}
)
proj_feats["project_priority_encoded"] = proj_feats["priority"].map(
    {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
)

# Step 6: Join performance reviews (per-employee → team aggregate)
review_agg = reviews.groupby("employee_id").agg(
    emp_avg_review=("overall_performance_score", "mean"),
    emp_avg_productivity=("productivity_score", "mean"),
    emp_avg_collab_review=("collaboration_score", "mean"),
    emp_pct_promoted=("promotion_recommended", "mean"),
).reset_index()
teams_with_reviews = teams_exploded.merge(review_agg, on="employee_id", how="left")
review_team_agg = teams_with_reviews.groupby("team_id").agg(
    avg_member_review_score=("emp_avg_review", "mean"),
    avg_member_productivity_score=("emp_avg_productivity", "mean"),
    avg_member_collaboration_review=("emp_avg_collab_review", "mean"),
    pct_members_promotion_ready=("emp_pct_promoted", "mean"),
).reset_index()

# Step 7: Join workload history (last 30 days per employee → team aggregate)
workload["date"] = pd.to_datetime(workload["date"])
cutoff = workload["date"].max() - pd.Timedelta(days=30)
recent_wl = workload[workload["date"] >= cutoff]
wl_agg_emp = recent_wl.groupby("employee_id").agg(
    avg_wl_intensity=("workload_intensity_score", "mean"),
    avg_productivity_vs_avg=("productivity_vs_avg", "mean"),
    avg_workload_vs_capacity=("workload_vs_capacity", "mean"),
    avg_overtime=("overtime_hours", "mean"),
    avg_burnout_risk_today=("burnout_risk_today", "mean"),
).reset_index()
teams_with_wl = teams_exploded.merge(wl_agg_emp, on="employee_id", how="left")
wl_team_agg = teams_with_wl.groupby("team_id").agg(
    avg_workload_intensity=("avg_wl_intensity", "mean"),
    avg_productivity_vs_avg=("avg_productivity_vs_avg", "mean"),
    avg_workload_vs_capacity=("avg_workload_vs_capacity", "mean"),
    pct_members_overtime=("avg_overtime", lambda x: (x > 0).sum() / len(x)),
    team_burnout_risk_today=("avg_burnout_risk_today", "mean"),
).reset_index()

# Step 8: Join task assignments (avg_team_compatibility excluded — noisy by design)
asgn_agg_emp = assignments.groupby("employee_id").agg(
    emp_avg_skill_match=("skill_match_score", "mean"),
    emp_avg_suitability=("overall_suitability_score", "mean"),
    emp_avg_efficiency=("efficiency_score", "mean"),
    emp_pct_success=("assignment_success", "mean"),
).reset_index()
teams_with_asgn = teams_exploded.merge(asgn_agg_emp, on="employee_id", how="left")
asgn_team_agg = teams_with_asgn.groupby("team_id").agg(
    avg_skill_match_score=("emp_avg_skill_match", "mean"),
    avg_overall_suitability=("emp_avg_suitability", "mean"),
    avg_assignment_efficiency=("emp_avg_efficiency", "mean"),
    pct_assignments_successful=("emp_pct_success", "mean"),
).reset_index()

# Step 9: Join feedback (team-level)
fb_agg = feedback[feedback["related_team_id"].notna()].groupby(
    "related_team_id"
).agg(
    avg_feedback_overall=("overall_rating", "mean"),
    avg_feedback_collaboration=("collaboration_rating", "mean"),
    avg_feedback_communication=("communication_rating", "mean"),
).reset_index().rename(columns={"related_team_id": "team_id"})

# Step 10: Merge all into feature table
# NOTE: collaborative_history_score taken from recomputed emp_agg (Step 4b),
#       NOT from team_formations
base = teams[[
    "team_id", "project_id",
    "team_size", "skill_diversity_score", "experience_balance_score",
    "workload_balance_score", "skill_utilization_rate",
    "resource_utilization", "formation_method",
    "actual_performance_score"  # TARGET
]].copy()
base["formation_method_encoded"] = base["formation_method"].map(
    {"Manual": 0, "Hybrid": 1, "AI-Recommended": 2}
)
base.drop(columns=["formation_method"], inplace=True)

feature_table = (
    base
    .merge(emp_agg, on="team_id", how="left")
    .merge(proj_feats[[
        "project_id", "project_complexity_encoded", "project_priority_encoded",
        "success_probability"
    ]], on="project_id", how="left")
    .merge(review_team_agg, on="team_id", how="left")
    .merge(wl_team_agg, on="team_id", how="left")
    .merge(asgn_team_agg, on="team_id", how="left")
    .merge(fb_agg, on="team_id", how="left")
)
feature_table.drop(columns=["project_id"], inplace=True)

feature_table.to_csv("model4_features.csv", index=False)
print(f"Feature table: {feature_table.shape[0]} rows × {feature_table.shape[1]} columns")
```

---

## 6. ML Model Training

**Script:** `model4_train.py`

### 6.1 Preprocessing

```python
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

df = pd.read_csv("model4_features.csv")

TARGET = "actual_performance_score"
DROP_COLS = ["team_id"]

X = df.drop(columns=[TARGET] + DROP_COLS)
y = df[TARGET]

# Drop near-zero variance columns
from sklearn.feature_selection import VarianceThreshold
vt = VarianceThreshold(threshold=0.01)
X = pd.DataFrame(vt.fit_transform(X), columns=X.columns[vt.get_support()])

# Impute
imputer = SimpleImputer(strategy="median")
X_imp = pd.DataFrame(imputer.fit_transform(X), columns=X.columns)

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X_imp, y, test_size=0.2, random_state=42
)
```

### 6.2 Evaluation Metrics

```python
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import numpy as np

def evaluate(name, y_true, y_pred):
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    print(f"{name:30s} | RMSE: {rmse:.2f} | MAE: {mae:.2f} | R²: {r2:.3f}")
```

---

## 7. Four Candidate Models

### Model A — Random Forest Regressor ⭐ (Recommended)

```python
from sklearn.ensemble import RandomForestRegressor

rf = RandomForestRegressor(
    n_estimators=200,
    max_depth=None,
    min_samples_leaf=3,
    random_state=42,
    n_jobs=-1
)
rf.fit(X_train, y_train)
evaluate("Random Forest", y_test, rf.predict(X_test))
```

**Why it fits best:**
- Handles mixed-scale numerical features without needing StandardScaler
- Naturally handles non-linear interactions (burnout × experience balance)
- Feature importances directly usable by Agentic AI for justification
- Robust to small dataset size (~100 rows)
- No hyperparameter sensitivity to outliers

**Expected performance:** R² ~0.72–0.82, RMSE ~6–9

---

### Model B — Gradient Boosting Regressor

```python
from sklearn.ensemble import GradientBoostingRegressor

gb = GradientBoostingRegressor(
    n_estimators=150,
    learning_rate=0.05,
    max_depth=4,
    subsample=0.8,
    random_state=42
)
gb.fit(X_train, y_train)
evaluate("Gradient Boosting", y_test, gb.predict(X_test))
```

**Why to consider:**
- Higher accuracy than RF when tuned
- More sensitive to hyperparameters; can overfit on ~100 rows
- Better for when dataset grows with real data

**Expected performance:** R² ~0.74–0.85, RMSE ~5–8

---

### Model C — Ridge Regression (Baseline)

```python
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

ridge = Ridge(alpha=1.0)
ridge.fit(X_train_s, y_train)
evaluate("Ridge Regression", y_test, ridge.predict(X_test_s))
```

**Why to include:**
- Fast, interpretable baseline — if RF doesn't beat Ridge by >5% R², features likely need more work
- Good sanity check before deploying complex models
- Coefficients usable for simple explanations

**Expected performance:** R² ~0.55–0.70, RMSE ~9–12

---

### Model D — XGBoost Regressor

```python
from xgboost import XGBRegressor

xgb = XGBRegressor(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=5,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    random_state=42,
    verbosity=0
)
xgb.fit(X_train, y_train)
evaluate("XGBoost", y_test, xgb.predict(X_test))
```

**Why to consider:**
- Best raw accuracy potential
- Built-in regularization prevents overfitting on small datasets
- Requires `pip install xgboost`; adds a dependency
- SHAP values natively supported → great for Agentic AI explainability

**Expected performance:** R² ~0.76–0.87, RMSE ~5–7

---

## 8. ML Model Output Format

The trained model outputs a JSON object per team evaluation request:

```json
{
  "team_id": "TEAM042",
  "project_id": "PRJ017",
  "predicted_performance_score": 81.4,
  "confidence_band": {
    "low": 74.2,
    "high": 88.6
  },
  "performance_tier": "High",
  "top_contributing_features": [
    { "feature": "avg_skill_match_score",       "importance": 0.142 },
    { "feature": "collaborative_history_score", "importance": 0.118 },
    { "feature": "avg_burnout_risk",            "importance": 0.097 },
    { "feature": "skill_diversity_score",       "importance": 0.091 },
    { "feature": "avg_historical_performance",  "importance": 0.083 }
  ],
  "risk_flags": {
    "high_burnout_member": true,
    "low_skill_utilization": false,
    "workload_imbalance": false,
    "low_availability": false
  },
  "model_metadata": {
    "model_type": "RandomForestRegressor",
    "model_version": "1.0",
    "training_r2": 0.79,
    "test_rmse": 7.3
  }
}
```

**Performance tier mapping:**
- `Low`: predicted_score < 60
- `Medium`: 60 ≤ score < 75
- `High`: 75 ≤ score < 88
- `Exceptional`: score ≥ 88

**Confidence band:** 10th–90th percentile across decision trees (RF) or ±1.5 × residual std.

---

## 9. Agentic AI Layer

> **Status:** Planned — not yet implemented. The ML scoring pipeline (Sections 4–8) is complete. The agentic layer will be built as a separate module and call into the ML model as a scoring service.

The Agentic AI layer has two sub-components:

### 9a — Team Member Selection  *(Planned)*

Triggered by a project requirement input:

```
Input fields (from project_id lookup or direct):
  department, priority, budget, complexity_level,
  start_date, planned_end_date, team_size,
  required_skills, allocated_resources
```

**Logic (rule-based, no separate ML model needed):**

1. **Hard filter** — eliminate employees who fail: `is_available`, skill overlap with `required_skills`, burnout below critical threshold, sufficient remaining capacity
2. **Candidate scoring** — weighted formula per employee:
   - Skill match vs required_skills (35%)
   - Historical performance score (25%)
   - Workload vs capacity (20%)
   - Experience vs complexity (10%)
   - Collaboration score (10%)
3. **Team assembly** — pick top `team_size` by suitability score
4. **Team lead selection** — highest `leadership_potential` among selected with seniority ≥ Senior
5. **Feed assembled team → Section 9b** for scoring + policy check

---

### 9b — Policy, Scoring & Recommendation  *(Planned)*

The Agentic AI receives the ML output JSON and operates as follows:

#### Step 1 — Receive & Parse ML Output
```
Input: predicted_performance_score, top_contributing_features, risk_flags
```

#### Step 2 — RAG Retrieval
Query the organizational knowledge base for:
- Team size limits per project type
- Department pairing restrictions
- HR policies on overtime / burnout thresholds
- Past team formation SOPs

#### Step 3 — Constraint Checking
- Is any flagged employee on leave?
- Does team size comply with project budget headcount?
- Does burnout flag breach HR intervention threshold?

#### Step 4 — Reranking
If evaluating multiple candidate teams:
- Sort by `predicted_performance_score` descending
- Penalize configurations with `high_burnout_member = true`
- Boost configurations with prior successful collaboration history

#### Step 5 — Generate Recommendation

```json
{
  "recommendation_id": "REC-2024-089",
  "project_id": "PRJ017",
  "suggested_members": ["EMP005", "EMP023", "EMP041"],
  "team_lead": "EMP041",
  "rank": 1,
  "predicted_performance_score": 81.4,
  "performance_tier": "High",
  "justification": "This team configuration scores in the High tier (81.4/100). Key strengths are strong skill alignment (skill_match: 0.142 importance), high prior collaboration history between members, and balanced workload. One member shows elevated burnout risk — recommend monitoring workload in first sprint.",
  "risk_summary": {
    "burnout_flag": "EMP023 — burnout_risk_score: 74.2. Recommend workload check before assignment.",
    "policy_compliance": "Compliant",
    "headcount_check": "Pass"
  },
  "alternative_teams": [
    { "suggested_members": ["EMP012", "EMP031", "EMP044"], "predicted_score": 76.1, "rank": 2 },
    { "suggested_members": ["EMP007", "EMP019", "EMP038"], "predicted_score": 71.8, "rank": 3 }
  ],
  "action_items": [
    "Check availability of EMP023 with their current manager",
    "Confirm project budget covers team of 6"
  ],
  "generated_at": "2024-03-15T10:32:00Z"
}
```

---

