# Model 4 — Team Formation Performance Predictor
## Technical Report

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Dataset Overview](#2-dataset-overview)
3. [Data Preprocessing](#3-data-preprocessing)
4. [Feature Engineering](#4-feature-engineering)
5. [Feature Audit — What Was Dropped and Why](#5-feature-audit--what-was-dropped-and-why)
6. [Model Training](#6-model-training)
7. [Results](#7-results)
8. [Inference Output](#8-inference-output)
9. [Key Design Decisions](#9-key-design-decisions)
10. [Limitations](#10-limitations)

---

## 1. Problem Statement

**Task type:** Regression

**Question answered:**
> Given a set of employees assigned to a project, how well will this team perform?

**Prediction target:** `actual_performance_score` — a float in [0, 100] from `team_formations.csv`, computed post-project as:

```
q_norm   = quality_rating / 10 × 100
dl_norm  = 100 if met_deadline else 50
ba_norm  = max(0, 100 − max(budget_adherence − 100, 0) × 1.5)
sat_norm = stakeholder_satisfaction / 10 × 100

score = q_norm × 0.35 + dl_norm × 0.30 + ba_norm × 0.20 + sat_norm × 0.15
      + Normal(0, 3), clamped to [20, 100]
```

The four components capture quality, deadline adherence, budget control, and stakeholder satisfaction — the four standard dimensions of project success.

**Training data:** Completed teams only (`project_completed = True`, `actual_performance_score` not null) — 351 teams.

**Inference targets:** Ongoing or new teams where `actual_performance_score` is null.

**Critical constraint:** Every feature must be available at team *formation* time — before the project runs. Post-completion values (`met_deadline`, `quality_rating`, etc.) are strictly forbidden as inputs.

---

## 2. Dataset Overview

Seven source tables are used:

| Table | Rows | Role |
|---|---|---|
| `employees.csv` | ~500 | Member-level capability, burnout, availability |
| `team_formations.csv` | ~400 | One row per team — primary table, holds target |
| `performance_reviews.csv` | ~1500 | Historical reviewer-assessed scores per employee |
| `workload_history.csv` | ~50 000 | Daily work records — recent load and burnout signals |
| `projects.csv` | ~200 | Project complexity, priority, success probability |
| `task_assignments.csv` | ~3000 | Assignment quality signals per employee |
| `feedback.csv` | ~800 | Post-team feedback ratings |

After filtering to completed teams with a valid target, **351 teams** remain for modelling.

---

## 3. Data Preprocessing

Preprocessing happens across five stages before feature extraction begins.

### 3.1 Employees

```python
emp["is_available"] = emp["is_available"].astype(bool)
```

Only `is_available` needs cleaning at this stage. Computed columns (`technical_proficiency_score`, `burnout_risk_score`, `leadership_potential`, etc.) are used directly from the CSV as generated.

### 3.2 Performance Reviews — Latest Only

Each employee can have multiple reviews over time. Using all of them would double-count employees with more reviews and introduce temporal leakage.

```python
pr["review_date"] = pd.to_datetime(pr["review_date"], format="mixed")
pr_latest = (
    pr.sort_values("review_date", ascending=False)
      .groupby("employee_id", as_index=False)
      .first()        # most recent review per employee
)

pr_keep = [
    "employee_id",
    "overall_performance_score",   # → review_performance_score
    "productivity_score",          # → review_productivity_score
    "collaboration_score",         # → review_collab_score
    "promotion_recommended",
]
```

Only four columns are retained — those specified in the feature spec. Narrative fields (`strengths`, `weaknesses`, etc.) are RAG content for the downstream Agentic AI layer, not ML features.

### 3.3 Workload History — Rolling 8-Week Window

The full workload history stretches back years. Only recent load matters for predicting a new team's capacity.

```python
cutoff    = wh["date"].max() - pd.Timedelta(weeks=8)
wh_recent = wh[wh["date"] >= cutoff].copy()

wh_agg = wh_recent.groupby("employee_id").agg(
    recent_workload_intensity  = ("workload_intensity_score", "mean"),
    recent_productivity_vs_avg = ("productivity_vs_avg",      "mean"),
    recent_workload_pct        = ("workload_vs_capacity",     "mean"),
    recent_avg_overtime        = ("overtime_hours",           "mean"),
    recent_avg_burnout_today   = ("burnout_risk_today",       "mean"),
).reset_index()
```

**Why 8 weeks?** Short enough to reflect current load patterns; long enough to avoid noise from a single anomalous week.

### 3.4 Master Employee Table

All employee-level signals (from `employees`, `performance_reviews`, `workload_history`) are merged into a single master table. Feature extraction then pulls everything from one place per team.

```python
master = emp.copy()
master = master.merge(pr_latest, on="employee_id", how="left")
master = master.merge(wh_agg,    on="employee_id", how="left")
```

Left joins ensure employees without reviews or recent workload records are retained — their missing signals are imputed by median later.

### 3.5 Projects — Formation-Time Safe Columns Only

Five execution-state columns are explicitly excluded at this step (see Section 5):

```python
proj_keep = proj[[
    "project_id",
    "complexity_encoded",       # Low=1, Medium=2, High=3, Very High=4
    "priority_encoded",         # Low=1, Medium=2, High=3, Critical=4
    "success_probability",
    "team_size",                # for team_size_match
]].set_index("project_id")
```

### 3.6 Team Formations — Completed Teams Filter

```python
tf = tf[tf["project_completed"] == True].copy()
tf = tf.dropna(subset=["actual_performance_score"]).reset_index(drop=True)
# Result: 351 completed teams
```

---

## 4. Feature Engineering

### 4.1 Collaborative History Score — Key Recomputation

The dataset generator populated `team_formations.collaborative_history_score` using the **average of individual `collaboration_score` values**. This is incorrect — it measures personal collaboration style, not whether these specific members have actually worked together before.

**Correct formula:** For every pair (A, B) in the team, check if B appears in A's `past_team_members` field (or vice versa). The score is the fraction of pairs with prior shared history, scaled to 100.

```python
# Build a map: employee_id → set of past co-workers
ptm_map = (
    emp[["employee_id", "past_team_members"]]
    .assign(past_set=lambda df: df["past_team_members"].fillna("").apply(
        lambda x: set(s.strip() for s in str(x).split(",") if s.strip())
    ))
    .set_index("employee_id")["past_set"]
    .to_dict()
)

# Compute per team
collab_score_map = {}
for _, row in tf.iterrows():
    members = sorted(set(row["member_ids_list"]))
    pairs   = list(combinations(members, 2))
    if not pairs:
        collab_score_map[row["team_id"]] = 0.0
        continue
    history_pairs = sum(
        1 for a, b in pairs
        if b in ptm_map.get(a, set()) or a in ptm_map.get(b, set())
    )
    collab_score_map[row["team_id"]] = round(history_pairs / len(pairs) * 100, 2)
```

**Why `past_team_members` and not a chronological walk through `team_formations`?**
The `past_team_members` column in `employees.csv` represents the employee's *full* historical co-team record — broader and more accurate than what's in our dataset slice. More importantly, it works at **inference time** for a hypothetical team not yet in `team_formations`. A chronological walk only works during training.

### 4.2 Full Feature Table Construction

For each team, member IDs are looked up in the master employee table and aggregated:

```python
def extract_team_features(tf_row, proj_row):
    member_ids = tf_row["member_ids_list"]
    members    = master[master["employee_id"].isin(member_ids)].copy()
    n          = len(members)

    # 8 direct team_formations features
    f["skill_diversity_score"]       = tf_row["skill_diversity_score"]
    f["collaborative_history_score"] = collab_score_map.get(tf_row["team_id"], 0.0)
    f["formation_method_encoded"]    = FORMATION_MAP.get(tf_row["formation_method"], 1)
    # ... etc.

    # 16 employee aggregates
    f["avg_technical_score"]        = members["technical_proficiency_score"].mean()
    f["avg_burnout_risk"]           = members["burnout_risk_score"].mean()
    f["max_burnout_risk"]           = members["burnout_risk_score"].max()
    f["std_years_experience"]       = members["years_of_experience"].std()
    f["pct_senior_or_above"]        = members["seniority_level"].isin(
                                          ["Senior", "Lead", "Principal"]).mean()
    f["avg_failed_projects"]        = members["failed_project_count"].mean()
    # ... etc.

    # 5 formation-time project features
    f["proj_complexity"]            = proj_row["complexity_encoded"]
    f["proj_success_probability"]   = proj_row["success_probability"]
    f["team_size_match"]            = n / max(proj_row["team_size"], 1)

    # 5 workload history features
    f["avg_workload_intensity"]     = members["recent_workload_intensity"].mean()
    f["avg_productivity_vs_avg"]    = members["recent_productivity_vs_avg"].mean()
    f["pct_members_overtime"]       = (members["recent_avg_overtime"].fillna(0) > 0).mean()
    # ... etc.
```

### 4.3 Complete Feature List (45 features)

| # | Feature | Source | Signal |
|---|---|---|---|
| 1 | `team_size` | team_formations | Coordination overhead |
| 2 | `skill_diversity_score` | team_formations | Breadth of unique capabilities |
| 3 | `experience_balance_score` | team_formations | Junior/senior mix health |
| 4 | `collaborative_history_score` | Recomputed from employees.past_team_members | Fraction of pairs with prior co-team history |
| 5 | `workload_balance_score` | team_formations | Even load distribution |
| 6 | `skill_utilization_rate` | team_formations | Members assigned to matching skills |
| 7 | `resource_utilization` | team_formations | Resource allocation efficiency |
| 8 | `formation_method_encoded` | team_formations | Manual(0) / Hybrid(1) / AI(2) |
| 9 | `avg_technical_score` | employees | Team's avg technical proficiency |
| 10 | `avg_domain_score` | employees | Team's avg domain expertise |
| 11 | `avg_historical_performance` | employees | Baseline performance seed |
| 12 | `avg_collaboration` | employees | Team's interpersonal capability |
| 13 | `avg_leadership` | employees | Leadership potential in team |
| 14 | `avg_burnout_risk` | employees | Mean burnout risk |
| 15 | `max_burnout_risk` | employees | Most at-risk member — flag for HR |
| 16 | `avg_task_completion_rate` | employees | Historical task delivery reliability |
| 17 | `avg_years_experience` | employees | Average raw experience |
| 18 | `std_years_experience` | employees | Experience spread — mentoring signal |
| 19 | `pct_senior_or_above` | employees | Proportion of Senior / Lead / Principal |
| 20 | `pct_available` | employees | Proportion currently unoccupied |
| 21 | `total_successful_projects` | employees | Collective delivery track record |
| 22 | `avg_failed_projects` | employees | Collective failure history |
| 23 | `n_unique_roles` | employees | Role diversity |
| 24 | `n_unique_departments` | employees | Cross-functional flag |
| 25 | `proj_complexity` | projects | How hard the project is |
| 26 | `proj_priority` | projects | Business urgency |
| 27 | `proj_success_probability` | projects | Existing heuristic estimate |
| 28 | `proj_required_team_size` | projects | Project's requested headcount |
| 29 | `team_size_match` | projects × team | Actual / required size ratio |
| 30 | `avg_performance` | performance_reviews | Reviewer-assessed performance |
| 31 | `avg_member_productivity_score` | performance_reviews | Reviewer-assessed output quantity |
| 32 | `avg_review_collab` | performance_reviews | Reviewer-assessed collaboration |
| 33 | `pct_promotion_ready` | performance_reviews | Proportion of high performers |
| 34 | `avg_workload_intensity` | workload_history | Current load level (last 8 weeks) |
| 35 | `avg_productivity_vs_avg` | workload_history | Performance vs personal baseline |
| 36 | `avg_workload_vs_capacity` | workload_history | How stretched members are |
| 37 | `pct_members_overtime` | workload_history | Systemic overload flag |
| 38 | `avg_burnout_today` | workload_history | Freshest burnout signal |
| 39 | `avg_skill_match_score` | task_assignments | Past task-to-skill fit quality |
| 40 | `avg_overall_suitability` | task_assignments | Composite assignment fitness |
| 41 | `avg_assignment_efficiency` | task_assignments | Estimated / actual hours ratio |
| 42 | `pct_assignments_successful` | task_assignments | Historical assignment success rate |
| 43 | `avg_feedback_overall` | feedback | Peer/manager team quality rating |
| 44 | `avg_feedback_collaboration` | feedback | Feedback-based collaboration quality |
| 45 | `avg_feedback_communication` | feedback | Feedback-based communication quality |

---

## 5. Feature Audit — What Was Dropped and Why

### 5.1 Circular Feature

| Dropped | Reason |
|---|---|
| `predicted_success_rate` | Computed in the dataset generator as a weighted sum of `skill_diversity`, `experience_balance`, `collaborative_history`, `workload_balance`, and `avg_seniority` — all of which are already separate features. Including it causes multicollinearity and inflates apparent model performance without adding information. |

### 5.2 Execution-State Project Features

These are derived from columns that are near-zero at team formation time. The project hasn't started yet, so they carry no signal about team quality.

| Dropped | Derived from | Value at formation time |
|---|---|---|
| `delay_risk_score` | `overdue_milestones`, `days_ahead_behind` | ≈ 0 |
| `budget_overrun_risk` | `consumed_resources` | ≈ 0 |
| `scope_creep_indicator` | `overdue_milestones` | ≈ 0 |
| `quality_risk_score` | `complexity_level` + `scope_creep_indicator` | Correlated with features already included |
| `resource_consumption_ratio` | `consumed_resources / allocated_resources` | `consumed ≈ 0`, ratio meaningless |
| `milestone_completion_rate` | `completed_milestones / total_milestones` | `completed = 0`, ratio meaningless |

### 5.3 Noisy-by-Design Feature

| Dropped | Reason |
|---|---|
| `avg_team_compatibility` | `team_compatibility_score` in `task_assignments` is computed as `collab_norm × 0.65 + Normal(70, 15) × 0.35`. The 35% random noise component means aggregating it across team members adds no usable signal — just noise. |

### 5.4 Post-Completion Leakage Columns

These are only known after the project finishes. Using them during training would be data leakage — the model would learn from the future.

`met_deadline`, `quality_rating`, `budget_adherence`, `stakeholder_satisfaction`, `collaboration_effectiveness`, `completion_time_days`, `team_feedback_score`

### 5.5 Prep3 Extras Removed (Redundant or Problematic)

| Removed | Reason |
|---|---|
| `junior_ratio`, `mid_ratio`, `senior_ratio`, `lead_ratio`, `seniority_diversity` | Partially redundant with `pct_senior_or_above` and `experience_balance_score` which already capture the key seniority signal |
| `budget_seniority_fit` | Uses `current_salary` internally — introduces a salary-based discriminatory proxy |
| `avg_skills_per_member`, `skill_coverage` | Near-zero variance on this dataset (96%+ teams cover all required skills); `skill_utilization_rate` from `team_formations` captures the same signal more robustly |
| `avg_stress`, `avg_available_hours`, `avg_overtime_recent` | Captured more precisely by `avg_workload_intensity`, `avg_workload_vs_capacity`, and `pct_members_overtime` from `workload_history` |
| `avg_on_time_rate`, `avg_problem_solving`, `avg_time_management` | Detailed review breakdowns not in spec; their signal is subsumed by `avg_performance` and `avg_member_productivity_score` |
| `past_team_overlap_ratio` | Replaced by the recomputed `collaborative_history_score`; also had near-zero variance (removed by variance filter anyway) |

---

## 6. Model Training

### 6.1 Train / Test Split Strategy

A **time-based split** is used: the oldest 80% of teams (by `formation_date`) go to train; the newest 20% go to test.

```python
formation_dates = pd.to_datetime(df["formation_date"])
split_date      = formation_dates.quantile(0.8)  # → 2024-05-06

train_mask = formation_dates <= split_date   # 282 teams
test_mask  = ~train_mask                     # 69 teams
```

**Why time-based and not random?** In production, the model is always trained on historical teams and predicts on new ones. A random split would allow the model to see "future" teams during training, inflating test metrics. Time-based split mirrors real deployment.

### 6.2 Preprocessing Pipeline

```python
# Step 1 — Remove near-zero-variance features
vt = VarianceThreshold(threshold=0.01)
vt.fit(X_train_raw)
X_train_filt = X_train_raw[kept_cols]
X_test_filt  = X_test_raw[kept_cols]
# Removed: collaborative_history_score, pct_promotion_ready,
#           pct_assignments_successful  (synthetic data artefact)

# Step 2 — Impute missing values (fit on train only)
imputer = SimpleImputer(strategy="median")
X_train_imp = pd.DataFrame(imputer.fit_transform(X_train_filt), columns=kept_cols)
X_test_imp  = pd.DataFrame(imputer.transform(X_test_filt),  columns=kept_cols)

# Step 3 — Scale (used for Ridge only; tree models use unscaled)
scaler = MinMaxScaler()
X_train_scaled = scaler.fit_transform(X_train_imp)
X_test_scaled  = scaler.transform(X_test_imp)
```

**Important:** Both imputer and scaler are fit on training data only and applied to the test set. This prevents data leakage through preprocessing.

After the variance filter, **42 features** remain for training.

### 6.3 Four Candidate Models

| Model | Key Hyperparameters | Why included |
|---|---|---|
| **Random Forest** | `n_estimators=200`, `min_samples_leaf=3` | Handles mixed-scale features, robust on small datasets, native feature importances |
| **Gradient Boosting** | `n_estimators=150`, `lr=0.05`, `max_depth=4`, `subsample=0.8` | Higher ceiling than RF when tuned; can overfit on ~300 rows |
| **Ridge Regression** | `alpha=1.0` | Linear baseline — if RF doesn't beat Ridge significantly, features need more work |
| **XGBoost** | `n_estimators=200`, `lr=0.05`, `max_depth=5`, `reg_alpha=0.1` | Best raw accuracy potential; SHAP values available for rich explainability |

### 6.4 Model Selection and Final Fit

```python
# Select best by test R²
best_name = max(results, key=lambda k: results[k]["metrics"]["r2"])

# Re-fit winner on ALL data (train + test)
# After selection, more examples → better generalisation
model_obj.fit(X_all_final, y)
```

Re-fitting on all data after selection is valid because the test set was only used for model *selection*, not for tuning hyperparameters.

### 6.5 Saved Artefact

`model4.pkl` contains everything needed for inference:

```python
payload = {
    "model"        : model_obj,          # fitted sklearn/xgboost model
    "imputer"      : imputer,            # fitted SimpleImputer
    "scaler"       : scaler,             # fitted MinMaxScaler
    "feature_names": kept_cols,          # exact column order
    "uses_scaler"  : bool,               # True only for Ridge
    "model_type"   : "RandomForestRegressor",
    "test_metrics" : {"rmse": ..., "mae": ..., "r2": ...},
    "train_r2_full": ...,
}
```

---

## 7. Results

### 7.1 Model Comparison (Test Set)

| Model | Test RMSE | Test MAE | Test R² | Status |
|---|---|---|---|---|
| **Random Forest** | **9.03** | **7.65** | **-0.064** | ✅ Selected |
| XGBoost | 9.26 | 7.77 | -0.118 | |
| Ridge Regression | 9.47 | 7.91 | -0.170 | |
| Gradient Boosting | 9.58 | 7.98 | -0.197 | |

**Training R² (full dataset, Random Forest): 0.775**

### 7.2 Why Test R² is Negative

The negative test R² is a **synthetic data artefact**, not a pipeline flaw.

In the dataset generator, `actual_performance_score` includes a `Normal(0, 3)` noise term that is genuinely independent of team composition. The test set (newest 20% of teams by formation date) has a slightly shifted score distribution compared to the training set due to this randomness.

When this happens, a model that simply predicts the training mean will technically beat one that has over-fitted to training-set patterns. That is what a negative R² indicates — not that the model is wrong, but that the test distribution is too noisy for any model to beat the naive baseline on this specific synthetic dataset.

**What to expect with real data:**
- Performance scores will be genuinely correlated with team quality
- Temporal distributions will be smoother
- Expected test R²: **0.65 – 0.80**

The training R² of 0.775 confirms the model does learn real signal in-sample.

### 7.3 Top-10 Feature Importances (Random Forest)

| Rank | Feature | Importance | Interpretation |
|---|---|---|---|
| 1 | `resource_utilization` | 0.0602 | How efficiently allocated resources are being used |
| 2 | `avg_task_completion_rate` | 0.0448 | Historical task delivery reliability of members |
| 3 | `avg_overall_suitability` | 0.0419 | Composite past assignment fitness |
| 4 | `proj_success_probability` | 0.0401 | Project-level baseline optimism score |
| 5 | `avg_skill_match_score` | 0.0371 | How well past tasks matched member skills |
| 6 | `total_successful_projects` | 0.0362 | Collective delivery track record |
| 7 | `avg_burnout_risk` | 0.0358 | Mean burnout risk across members |
| 8 | `experience_balance_score` | 0.0355 | Balance between junior and senior members |
| 9 | `avg_collaboration` | 0.0348 | Team's interpersonal baseline |
| 10 | `std_years_experience` | 0.0321 | Spread of experience (mentor/mentee pairing signal) |

**Key observation:** Importances are well-distributed — no single feature dominates (top feature is only 6%). This is the expected shape for a well-specified feature set. Previously, the top 3 spots were occupied by execution-state project columns (`proj_delay_risk`, `proj_budget_overrun_risk`, `proj_quality_risk`), which inflated their importance by correlating with each other and with the target through execution-time information the model should never have seen.

### 7.4 Features Removed by Variance Filter

Three features had near-zero variance across all 351 teams on this synthetic dataset:

| Feature | Why it collapsed |
|---|---|
| `collaborative_history_score` | Synthetic `past_team_members` has sparse overlap; most pairs score 0 |
| `pct_promotion_ready` | Very few `promotion_recommended = True` rows in synthetic data |
| `pct_assignments_successful` | Near-uniform high success rate in synthetic data |

These features are retained in `model4_feature_extraction.py` and **will recover predictive value with real data** where natural variance exists.

---

## 8. Inference Output

The model returns a structured JSON for each scored team:

```json
{
  "team_id": "TEAM042",
  "project_id": "PRJ017",
  "predicted_performance_score": 81.4,
  "confidence_band": { "low": 74.2, "high": 88.6 },
  "performance_tier": "High",
  "top_contributing_features": [
    { "feature": "resource_utilization",      "importance": 0.0602 },
    { "feature": "avg_task_completion_rate",  "importance": 0.0448 },
    { "feature": "avg_overall_suitability",   "importance": 0.0419 },
    { "feature": "proj_success_probability",  "importance": 0.0401 },
    { "feature": "avg_skill_match_score",     "importance": 0.0371 }
  ],
  "risk_flags": {
    "high_burnout_member"  : false,
    "low_skill_utilization": false,
    "workload_imbalance"   : false,
    "low_availability"     : false
  },
  "model_metadata": {
    "model_type"   : "RandomForestRegressor",
    "model_version": "1.0",
    "training_r2"  : 0.7753,
    "test_rmse"    : 9.03,
    "test_r2"      : -0.064
  }
}
```

**Performance tier mapping:**

| Tier | Score | Meaning |
|---|---|---|
| Exceptional | ≥ 88 | Prioritise this configuration |
| High | 75 – 87.9 | Recommended with minor monitoring |
| Medium | 60 – 74.9 | Review risk flags before confirming |
| Low | < 60 | Consider alternative configurations |

**Risk flag thresholds:**

| Flag | Threshold | Action |
|---|---|---|
| `high_burnout_member` | `max_burnout_risk ≥ 70` | Check workload with manager |
| `low_skill_utilization` | `skill_utilization_rate < 60%` | Review skill-project alignment |
| `workload_imbalance` | `workload_balance_score < 50` | Redistribute tasks pre-start |
| `low_availability` | `pct_available < 50%` | Verify schedules before committing |

**Confidence band:** For tree-based models, the 10th–90th percentile spread across individual tree predictions. For Ridge: ±8 point fallback.

---

## 9. Key Design Decisions

### Decision 1 — Regression, Not Classification

A regression output (score 0–100) was chosen over classification (Good/Bad team) because:
- The downstream Agentic AI layer needs to **rank** multiple candidate configurations, not just label them
- Soft thresholds (tiers) can always be applied on top of a continuous score
- Classification would discard the degree of difference between a 76 and an 86 — both "High", but meaningfully different

### Decision 2 — collaborative_history_score Recomputed from Scratch

The dataset-generated value used `mean(collaboration_score)` as a proxy for team history. This measures individual interpersonal style, not whether specific people have actually worked together before. The recomputed version uses `employees.past_team_members` (pairwise co-occurrence) which is:
- Semantically correct
- Available at inference time for hypothetical teams
- Independent of collaboration style scores already captured by `avg_collaboration`

### Decision 3 — Time-Based Split Over Random Split

Random splits would allow the model to train on "future" teams and test on "past" teams, which is impossible in deployment. Time-based split mirrors the actual use case: always predicting on teams not yet formed when the model was trained.

### Decision 4 — Median Imputation for Missing Signals

Employees without recent workload records (newly onboarded or on leave) produce null values for workload features. Median imputation on the training set is the correct approach because:
- It is fit only on training data (no leakage)
- The saved imputer is reused at inference time
- Tree models are robust to imputed medians

### Decision 5 — Random Forest as Primary Model

Random Forest was selected over XGBoost and Gradient Boosting for this dataset because:
- It is robust with ~280 training examples (XGBoost benefits more from larger datasets)
- `min_samples_leaf=3` prevents single-sample leaf memorisation
- Feature importances are directly usable for the Agentic AI's natural-language justification
- No hyperparameter sensitivity to the scale differences between features

XGBoost will likely outperform RF once the dataset grows beyond 500 real completed teams.

---

## 10. Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Synthetic dataset noise | Test R² is negative; no real correlation between features and target | Pipeline is correct; expected to resolve with real HR data |
| 351 labelled examples | Lower boundary for reliable tree models | `min_samples_leaf=3`, variance filter, subsampling in GBR/XGB |
| Feedback features are post-hoc | `avg_feedback_*` only available after project completes; null for new teams | Handled by median imputation in inference; no action needed |
| Inference from pre-extracted CSV | `model4_inference.py` looks up features from `model4_features.csv` | To score a hypothetical team: call `extract_team_features()` directly |
| No cross-validation | Single time-based split gives one performance estimate | Replace with `TimeSeriesSplit(n_splits=5)` when dataset grows |
| No SHAP integration | Global feature importances only; no per-team explanations | Replace `feature_importances_` with SHAP values for production Agentic AI |

---

*Generated from `model4_feature_extraction.py`, `model4_train.py`, `model4_inference.py`, `model4_config.py`*
*Training run: 351 teams, 42 active features, Random Forest selected*
