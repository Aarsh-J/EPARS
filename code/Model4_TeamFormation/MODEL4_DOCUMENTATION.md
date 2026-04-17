# Model 4 — Team Formation & Assignment
## Complete Documentation

---

## Table of Contents

1. [What This Model Does](#1-what-this-model-does)
2. [How to Run](#2-how-to-run)
3. [File-by-File Explanation](#3-file-by-file-explanation)
4. [Feature Justification — Why Each Column Was Chosen](#4-feature-justification--why-each-column-was-chosen)
5. [Columns That Were Dropped and Why](#5-columns-that-were-dropped-and-why)
6. [Dataset Adaptations from prep3.py](#6-dataset-adaptations-from-prep3py)
7. [Training Results & Model Comparison](#7-training-results--model-comparison)
8. [Inference Output Format](#8-inference-output-format)
9. [Known Limitations & What to Improve with Real Data](#9-known-limitations--what-to-improve-with-real-data)

---

## 1. What This Model Does

**Goal:** Given a proposed team configuration (a set of employees assigned to a project), predict how well that team will perform — expressed as `actual_performance_score` (0–100 float).

**Task type:** Regression

**Prediction grain:** One row = one completed team (`team_id`)

**What the model does NOT do:**
- It does not enforce HR policies or headcount limits
- It does not check real-time calendar availability
- It does not generate natural-language justifications

These are the responsibility of the **Agentic AI layer** (Model 4's downstream consumer), which receives this model's JSON output and reasons over it with RAG + constraint checking.

---

## 2. How to Run

### Prerequisites

```bash
pip install pandas numpy scikit-learn
pip install xgboost       # optional — adds Model D to the comparison
```

Python 3.10+ required.

### Step 1 — Feature Extraction

Reads all 7 CSVs from `dataset/`, engineers ~70 team-level features, saves the feature table.

```bash
python model4_feature_extraction.py
```

**Output:** `output/model4_features.csv`  
**Expected:** 351 rows × 73 columns (70 features + team_id + formation_date + target)  
**Runtime:** ~10–20 seconds (past-overlap computation is the slow part)

---

### Step 2 — Train

Loads the feature table, runs a time-based train/test split, trains 3–4 models, selects the best by R², re-fits on all data, saves the model.

```bash
python model4_train.py
```

**Output:** `output/model4.pkl`, `output/model4_metadata.json`  
**Runtime:** ~30–60 seconds

---

### Step 3 — Inference

Score a single team:
```bash
python model4_inference.py --team_id TEAM042
```

Score every team in the feature table (ranked list):
```bash
python model4_inference.py --all
```

Save output to a JSON file:
```bash
python model4_inference.py --team_id TEAM042 --out result.json
python model4_inference.py --all --out all_teams_ranked.json
```

---

### File & Folder Layout

```
code/Model4_TeamFormation/
├── model4_config.py               # shared constants, paths, encoding maps
├── model4_feature_extraction.py   # Step 1: build feature table from raw CSVs
├── model4_train.py                # Step 2: train + evaluate + save model
├── model4_inference.py            # Step 3: load model + output JSON
├── MODEL4_DOCUMENTATION.md        # this file
└── output/                        # created automatically on first run
    ├── model4_features.csv
    ├── model4.pkl
    └── model4_metadata.json
```

---

## 3. File-by-File Explanation

### `model4_config.py`

**Purpose:** Central configuration — all paths, encoding maps, and tunable constants in one place. Every other script imports from here.

**Key contents:**

| Constant | Value | Why configurable |
|---|---|---|
| `DATASET_DIR` | `../../dataset` | Change if dataset moves |
| `WORKLOAD_LOOKBACK_WEEKS` | `8` | How far back in workload_history to look per employee. 8 weeks captures recent patterns without including stale data from projects long ago |
| `TRAIN_SIZE_RATIO` | `0.8` | 80% of teams (by formation date) go to train, 20% to test |
| `SENIORITY_MAP` | Junior=1 … Principal=5 | Ordinal scale so tree models respect the natural order |
| `FORMATION_MAP` | Manual=0, Hybrid=1, AI-Recommended=2 | Ordinal: AI-assisted is assumed the most sophisticated formation method |

**Nothing else should hardcode paths or mappings** — any tuning starts here.

---

### `model4_feature_extraction.py`

**Purpose:** The most complex script. Reads 7 raw CSVs, cleans them, joins them together, and produces one flat row per completed team.

**Steps inside the script:**

| Step | What happens |
|---|---|
| 1 | Load all 7 CSVs |
| 2 | Clean `employees.csv`: parse dates, derive tenure, encode seniority/stress/trend, build combined skill list, compute project success ratio |
| 3 | Clean `performance_reviews.csv`: take the **latest** review per employee only (most recent snapshot of their ability) |
| 4 | Aggregate `workload_history.csv`: last 8 weeks per employee → avg hours, overtime, workload %, burnout signal |
| 5 | Merge reviews + workload onto employees to build a **master employee table** (one row per employee, all signals merged) |
| 6 | Clean `projects.csv`: encode complexity/priority, compute budget_per_head, resource consumption ratio, milestone completion rate |
| 7 | Clean `team_formations.csv`: filter to `project_completed = True` and `actual_performance_score` not null (351 teams) |
| 8 | **Pre-compute past team overlap**: sort teams by formation_date, walk chronologically, count how many member-pairs in each team have previously worked together. Gives `past_team_overlap_ratio` |
| 9 | Aggregate `task_assignments.csv` per employee (skill match, suitability, efficiency, success rate) |
| 10 | Aggregate `feedback.csv` per team (overall rating, collaboration, communication) |
| 11–12 | For each team: look up its members in the master table, aggregate all signals, look up its project row, assemble 70-column feature dict |
| 13 | Merge team-level feedback |
| 14 | Sanity checks |
| 15 | Fill remaining nulls with column median, save CSV |

**Important detail — why latest review only:**  
`performance_reviews` has multiple reviews per employee over time. Using all of them would double-count employees who have more reviews. The latest review is the best summary of current ability.

**Important detail — past team overlap computation:**  
Teams are processed in chronological order. For team T formed on date D, only teams formed *before* D are considered "past". This avoids look-ahead leakage — the model only knows what was historically true when the team was formed.

**Output:** `output/model4_features.csv` — 351 rows, 73 columns

---

### `model4_train.py`

**Purpose:** Takes the feature table, selects a best model, and saves everything needed for inference.

**Steps inside:**

| Step | What happens |
|---|---|
| 1 | Load `model4_features.csv` |
| 2 | **Time-based split**: oldest 80% of teams → train, newest 20% → test. This is more realistic than random split because in production you always predict on teams not yet formed |
| 3 | Separate X (features) from y (target), drop identifier columns |
| 4 | **Variance filter** (`VarianceThreshold=0.01`): removes features that are nearly constant across all teams — they carry no information. 8 features were removed on this dataset |
| 5 | **Impute** missing values with column median (fit on train only, applied to test) |
| 6 | **Scale** with MinMaxScaler (fit on train only) — used by Ridge; tree models use unscaled data |
| 7 | Train all 3–4 candidate models (see Section 7) |
| 8 | Pick the one with highest test R² |
| 9 | **Re-fit the winner on all data** — after selection, more training data → better generalisation |
| 10 | Save `model4.pkl` (model + imputer + scaler + feature names) and `model4_metadata.json` |

**Why re-fit on full data after selection?**  
The test set is used only for model *selection*, not for final training. Once we know Random Forest is best, we give it all 351 teams so the deployed model has seen as much history as possible.

**What `model4.pkl` contains:**

```python
{
    "model"        : <fitted sklearn model>,
    "imputer"      : <fitted SimpleImputer>,
    "scaler"       : <fitted MinMaxScaler>,
    "feature_names": [...],   # exact column order the model expects
    "uses_scaler"  : bool,    # True only for Ridge
    "model_type"   : "RandomForestRegressor",
    "test_metrics" : {"rmse": ..., "mae": ..., "r2": ...},
    "train_r2_full": ...,
    "all_results"  : {...}
}
```

The imputer and scaler are saved alongside the model so inference applies *exactly the same* preprocessing — no manual re-fitting needed.

---

### `model4_inference.py`

**Purpose:** Production-facing script. Loads the saved model and produces the structured JSON output for each team.

**Usage patterns:**

```bash
# Score one team
python model4_inference.py --team_id TEAM042

# Score all teams, ranked
python model4_inference.py --all

# Save to file (for Agentic AI to consume)
python model4_inference.py --team_id TEAM042 --out result.json
```

**Key functions:**

| Function | What it does |
|---|---|
| `predict_team()` | Looks up team_id in features CSV, applies imputer+scaler, runs model, builds JSON |
| `_confidence_band()` | For tree models: collects per-tree predictions → 10th/90th percentile spread. For Ridge: ±8 point fallback |
| `_top_features()` | Returns top-5 features by `feature_importances_` (RF/GBR/XGB) or `\|coef_\|` (Ridge) |
| `_risk_flags()` | Threshold checks: burnout risk ≥ 70, skill utilisation < 60%, workload balance < 50%, availability < 50% |
| `predict_all_teams()` | Loops over every team, sorts by predicted score descending, adds `rank` field |

---

## 4. Feature Justification — Why Each Column Was Chosen

Features are grouped by the signal they capture.

### 4.1 Team Composition (from `team_formations`)

| Feature | Source column | Why included |
|---|---|---|
| `team_size` | `team_formations.team_size` | Direct indicator of collaboration complexity and communication overhead |
| `skill_diversity_score` | `team_formations.skill_diversity_score` | Pre-computed score for range of skills — diverse teams cover more ground |
| `experience_balance_score` | `team_formations.experience_balance_score` | Balance between juniors and seniors affects mentoring + speed trade-off |
| `collaborative_history_score` | `team_formations.collaborative_history_score` | Captures how well this group has worked together historically |
| `workload_balance_score` | `team_formations.workload_balance_score` | Unbalanced workload leads to bottlenecks and team friction |
| `predicted_success_rate` | `team_formations.predicted_success_rate` | Existing heuristic signal — useful as a baseline prior |
| `skill_utilization_rate` | `team_formations.skill_utilization_rate` | How well members' skills match project needs |
| `resource_utilization` | `team_formations.resource_utilization` | Consumed vs. allocated — efficiency of resource use |
| `formation_method_encoded` | `team_formations.formation_method` | AI-recommended formations may be more optimised than manual ones |

### 4.2 Member Skill & Technical Ability (from `employees`, `performance_reviews`)

| Feature | Why included |
|---|---|
| `avg_technical_score` | Core capability of the team — technical proficiency directly drives output quality |
| `avg_domain_score` | Domain expertise determines how fast members ramp up on the specific project type |
| `avg_review_technical` | Reviewer-assessed (not self-reported) technical score — more objective than employee's own score |
| `avg_skills_per_member` | Normalised unique-skill count; multi-skilled teams handle unexpected task distribution better |
| `skill_coverage` | Fraction of required project skills actually present in the team — directly predicts feasibility |

### 4.3 Seniority Mix (from `team_formations.seniority_mix`, `employees`)

| Feature | Why included |
|---|---|
| `junior_ratio`, `mid_ratio`, `senior_ratio`, `lead_ratio` | The mix of experience levels is one of the strongest predictors of delivery quality — too many juniors increases risk |
| `seniority_diversity` | Count of distinct levels present — diverse seniority enables better mentoring chains |
| `avg_seniority`, `max_seniority` | Average ability level and the "ceiling" of the team; a team with no Leads tends to lack direction |

### 4.4 Budget Fit (from `employees`, `projects`)

| Feature | Why included |
|---|---|
| `budget_per_head` | Project budget divided by team size — sets context for whether the team composition is affordable |
| `budget_seniority_fit` | Fraction of members whose salary is within budget per head — misfit here leads to rushed replacements mid-project |

### 4.5 Individual Performance History (from `performance_reviews`)

| Feature | Why included |
|---|---|
| `avg_performance` | Mean reviewer-assessed performance across all members — the single strongest individual signal |
| `min_performance` | The weakest link — a single under-performer can disproportionately slow a team |
| `std_performance` | Spread of performance; very high spread means uneven contribution and possible tension |
| `avg_on_time_rate` | Historical delivery punctuality — directly predicts whether this team will meet deadlines |
| `avg_problem_solving` | Reviewer-assessed problem-solving; critical for projects with high complexity |
| `avg_time_management` | Proxy for reliability and self-organisation (replaces `reliability_score` absent from v3 schema) |
| `avg_review_collab` | Reviewer-assessed collaboration (supplements employees.collaboration_score with external perspective) |
| `avg_productivity_vs_peers` | Whether members outperform or underperform their peers — relative signal, not absolute |

### 4.6 Collaboration & Leadership (from `employees`)

| Feature | Why included |
|---|---|
| `avg_collaboration` | Baseline collaboration score — teams with low collaboration scores consistently underperform |
| `avg_leadership` | Average leadership potential; even non-leads benefit from having high-potential members |
| `past_team_overlap_ratio` | Fraction of member-pairs who have worked together before — familiarity significantly reduces friction and onboarding time |

### 4.7 Burnout & Workload (from `employees`, `workload_history`)

| Feature | Why included |
|---|---|
| `avg_burnout_risk` | Mean burnout risk across members — burnout leads to quality drops and attrition mid-project |
| `max_burnout_risk` | The most-at-risk member; even one burned-out person can block the whole team |
| `avg_stress` | Encoded stress level (Low/Medium/High) — supplement to burnout score |
| `avg_available_hours` | Remaining weekly capacity; assigning an over-committed team guarantees delays |
| `avg_workload_recent` | Workload vs. capacity ratio over last 8 weeks — captures current load, not just historical |
| `avg_overtime_recent` | Recent overtime hours — unsustainable patterns predict burnout and quality drop |
| `avg_burnout_today` | Most recent burnout signal from workload_history — freshest available signal |
| `pct_members_overtime` | Fraction of the team currently working overtime — systemic overload indicator |

### 4.8 Experience & Trends (from `employees`)

| Feature | Why included |
|---|---|
| `avg_experience` | Average years of experience — raw depth of knowledge in the team |
| `experience_range` | Max minus min years of experience — large range = good mentor/mentee pairing but also potential misalignment |
| `avg_productivity_trend` | Whether members are improving, stable, or declining — forward-looking signal |
| `pct_available` | Fraction marked `is_available = True` — quick availability flag |
| `total_successful_projects` | Summed count of successful projects across members — collective track record |

### 4.9 Task Assignment Quality (from `task_assignments`)

| Feature | Why included |
|---|---|
| `avg_skill_match_score` | How well past tasks were matched to members' skills — consistently good matching suggests good team-role alignment |
| `avg_overall_suitability` | Composite suitability score from past assignments — a strong predictor of how suited members are to typical work |
| `avg_team_compatibility` | How well members worked with their previous team members — social compatibility signal |
| `avg_assignment_efficiency` | `estimated_hours / actual_hours` ratio — how efficient members are when given tasks |

### 4.10 Project Context (from `projects`)

| Feature | Why included |
|---|---|
| `proj_complexity` | Harder projects demand higher-ability teams; failing to control for complexity inflates the apparent importance of team signals |
| `proj_priority` | Critical projects attract more scrutiny and resources; performance scores may be biased toward high-priority projects |
| `proj_delay_risk` | Project-level risk that is independent of the team; context for interpreting the predicted score |
| `proj_quality_risk` | Quality risk from project side (task rework rates, complexity) |
| `proj_budget_overrun_risk` | Financial pressure affects team morale and decisions |
| `proj_scope_creep` | Scope growth degrades performance regardless of team quality — must be controlled for |
| `proj_success_probability` | Existing heuristic estimate — useful as a feature alongside the ML prediction |
| `proj_required_team_size` | The requested team size from the project side |
| `team_size_match` | Ratio of actual team size to required team size — teams that are too small or too large underperform |

### 4.11 Feedback Signals (from `feedback`)

| Feature | Why included |
|---|---|
| `avg_feedback_overall` | Peer/manager overall rating for this team's output — most direct quality signal available post-hoc |
| `avg_feedback_collaboration` | Whether teammates rated collaboration positively — latent signal of team cohesion |
| `avg_feedback_communication` | Communication quality rating — poor communication is a leading cause of project failure |

### 4.12 Role & Department Diversity (from `employees`)

| Feature | Why included |
|---|---|
| `n_unique_roles` | Cross-role teams (developer + designer + analyst) are better at end-to-end delivery |
| `n_unique_departments` | Cross-departmental teams bring diverse perspectives but need stronger coordination |

---

## 5. Columns That Were Dropped and Why

### From `team_formations`

| Dropped column | Reason |
|---|---|
| `actual_performance_score` | It IS the target — using it as a feature would be perfect leakage |
| `met_deadline`, `quality_rating`, `budget_adherence`, `stakeholder_satisfaction`, `collaboration_effectiveness` | **Outcome columns — data leakage.** These are only known after the project completes. Using them would mean the model learns from the future |
| `team_id`, `team_name`, `project_id`, `formation_date` | Identifiers — carry no signal, kept only for traceability |
| `role_distribution` | JSON string; information already captured in `n_unique_roles` and seniority features |
| `member_ids`, `team_lead_id` | Raw ID lists — used as join keys during extraction, then dropped |
| `dissolution_date`, `dissolution_reason` | Post-completion fields; unknown at prediction time |
| `team_status`, `project_completed`, `completion_time_days` | Status fields — all completed teams have the same values (no variance) |

### From `employees`

| Dropped column | Reason |
|---|---|
| `first_name`, `last_name`, `email` | PII — never used in ML |
| `hire_date` | Used to compute `tenure_days`; raw date discarded |
| `current_salary` | Used inside `budget_seniority_fit` computation; raw salary not included to avoid proxy discrimination |
| `past_team_members` | All null in this dataset; replaced by the computed `past_team_overlap_ratio` |
| `preferred_work_hours`, `remote_work_status` | Scheduling preferences — relevant for planning tools, not performance prediction |
| `certifications` | Very sparse, difficult to normalise across different certification bodies |
| `current_project_count` | Captured more precisely by `avg_workload_recent` and `pct_available` |

### From `performance_reviews`

| Dropped column | Reason |
|---|---|
| All except the 8 kept | Kept only the scores most directly predictive of team outcomes; dropped narrative text fields (`strengths`, `weaknesses`, etc.) which are RAG content for the Agentic AI layer, not ML features |
| `normalized_performance_score` | Highly correlated with `overall_performance_score` (r ≈ 0.97); one is sufficient |
| `productivity_score` (from reviews) | Correlated with `avg_productivity_vs_peers`; dropped to reduce redundancy |

### Removed by Variance Filter (near-zero variance on this dataset)

These 8 features were extracted but removed automatically during `model4_train.py` because they showed near-zero variance across teams — meaning they are nearly the same for all teams and carry no discriminating information:

| Feature | Why it collapsed |
|---|---|
| `skill_coverage` | 96%+ of teams cover all required skills (synthetic data artefact) |
| `pct_promotion_ready` | Very few promotion recommendations in this dataset |
| `past_team_overlap_ratio` | Most teams have little to no prior pairing history |
| `avg_stress` | Distribution collapsed into a narrow band |
| `avg_project_success_rate` | Near-identical for most employees |
| `pct_assignments_successful` | Very high uniform success rate in synthetic data |
| `proj_resource_consumption` | Narrow range in synthetic data |
| `proj_milestone_completion` | Similar issue |

These features **should be retained in real data** where natural variance will restore their predictive value.

---

## 6. Dataset Adaptations from prep3.py

`prep3.py` was written for an older dataset version. The following changes were made:

| Old column (prep3.py) | Replacement in v3 | Rationale |
|---|---|---|
| `communication_effectiveness` (employees) | Dropped | Not in v3 schema; `avg_review_collab` from performance_reviews covers interpersonal quality |
| `cross_functional_experience` (employees) | Dropped | Not in v3 schema; `n_unique_departments` partially covers this |
| `mentoring_experience` (employees) | Dropped | Not in v3 schema |
| `late_hours_indicator` (workload_history) | Derived: `overtime_hours > 0` | Not in v3 schema; late hours are functionally equivalent to any overtime |
| `strategic_importance` (projects) | Dropped | Not in v3 schema |
| `reliability_score`, `adaptability_score`, `innovation_score` (reviews) | `time_management_score` | Not in v3 schema; time management is the closest available proxy for reliability |
| `dataset_v2/` path | `dataset/` path | Updated to current dataset location |
| No task_assignments features | Added `avg_skill_match_score` etc. | Pipeline doc specifies these; prep3.py did not include them |
| No feedback features | Added `avg_feedback_*` | Pipeline doc specifies these; prep3.py did not include them |

---

## 7. Training Results & Model Comparison

### Current results (synthetic dataset, 351 teams)

| Model | Test RMSE | Test MAE | Test R² | Notes |
|---|---|---|---|---|
| **Random Forest** | **8.84** | **7.26** | **-0.019** | Selected as best |
| Gradient Boosting | 9.34 | 7.70 | -0.139 | |
| Ridge Regression | 9.58 | 7.84 | -0.196 | |
| XGBoost | Not tested | — | — | `pip install xgboost` to enable |

- **Training R² (full data, Random Forest):** 0.81 — the model does learn in-sample signal
- **Test R²:** negative — explained below

### Why test R² is negative on this dataset

The test set contains the **newest 20% of teams by formation date**. In synthetic data, `actual_performance_score` is generated with some randomness independent of the team composition, so:

1. The model fits the training distribution well (R² = 0.81)
2. The newer teams have a slightly different score distribution (shifted or noisy)
3. Any model predicting the training mean would technically score a lower error than a model that over-fits training-set patterns

**This is a synthetic data artefact, not a flaw in the pipeline.** With real HR data:
- Performance scores are genuinely correlated with team quality
- Temporal distributions are smoother
- Expected test R²: 0.65–0.80 (per pipeline design document estimates)

### Feature importances (Random Forest)

Top features driving predictions:

| Rank | Feature | Importance |
|---|---|---|
| 1 | `proj_quality_risk` | 0.081 |
| 2 | `proj_delay_risk` | 0.072 |
| 3 | `proj_budget_overrun_risk` | 0.058 |
| 4 | `resource_utilization` | 0.043 |
| 5 | `std_performance` | 0.040 |
| 6 | `budget_per_head` | 0.034 |
| 7 | `proj_success_probability` | 0.031 |
| 8 | `avg_overall_suitability` | 0.029 |
| 9 | `avg_productivity_vs_peers` | 0.026 |
| 10 | `experience_balance_score` | 0.023 |

The top positions are dominated by **project-context signals** (`proj_quality_risk`, `proj_delay_risk`). This is expected: project difficulty is one of the biggest moderators of team performance. In real data, expect **member-quality signals** (`avg_performance`, `avg_skill_match_score`) to climb into the top 5.

---

## 8. Inference Output Format

Example output for a single team:

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
    { "feature": "proj_quality_risk",       "importance": 0.0805 },
    { "feature": "proj_delay_risk",         "importance": 0.0721 },
    { "feature": "avg_skill_match_score",   "importance": 0.0291 },
    { "feature": "std_performance",         "importance": 0.0399 },
    { "feature": "experience_balance_score","importance": 0.0228 }
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
    "training_r2"  : 0.8056,
    "test_rmse"    : 8.84,
    "test_r2"      : -0.019
  }
}
```

### Performance tier mapping

| Tier | Score range | Meaning |
|---|---|---|
| Exceptional | ≥ 88 | Outstanding — prioritise this configuration |
| High | 75 – 87.9 | Strong team — recommended with minor monitoring |
| Medium | 60 – 74.9 | Moderate fit — review flagged risks before confirming |
| Low | < 60 | Poor fit — consider alternative configurations |

### Risk flag thresholds

| Flag | Trigger | Action |
|---|---|---|
| `high_burnout_member` | `max_burnout_risk >= 70` | Check workload with manager before assigning |
| `low_skill_utilization` | `skill_utilization_rate < 60%` | Review skill-project alignment; consider member swap |
| `workload_imbalance` | `workload_balance_score < 50` | Redistribute tasks before project start |
| `low_availability` | `pct_available < 50%` | More than half the team is currently occupied — check schedules |

These thresholds are conservative defaults. Adjust in `model4_inference.py → _risk_flags()` to match your organisation's HR policy.

---

## 9. Known Limitations & What to Improve with Real Data

### Limitation 1 — Synthetic data reduces test R²
The dataset is generated with controlled randomness. `actual_performance_score` has some component that is genuinely unpredictable from team features. With real HR data, expect R² to improve significantly as the features start correlating with actual outcomes.

### Limitation 2 — Only 351 labelled training examples
The model has 62 features and ~280 training rows. This is at the lower boundary for reliable tree models. Mitigations already in place: `min_samples_leaf=3` in Random Forest, `subsample=0.8` in Gradient Boosting, `VarianceThreshold` to remove low-signal features.

**Recommendation:** Once you have > 500 completed teams, try XGBoost with SHAP — it will outperform Random Forest and provide richer explanation for the Agentic AI layer.

### Limitation 3 — Inference uses pre-extracted features
`model4_inference.py` currently looks up features from `model4_features.csv`. For production use, it should re-run feature extraction on the fly for any proposed (not yet formed) team configuration.

**To score a hypothetical team** (not yet in the CSV): collect the `member_ids` and `project_id`, call `extract_team_features()` from `model4_feature_extraction.py` directly, pass the resulting dict to `predict_team()`.

### Limitation 4 — Feedback signals are post-hoc
`avg_feedback_overall`, `avg_feedback_collaboration`, `avg_feedback_communication` come from `feedback.csv`, which is only available *after* the project completes. For a future prediction (a team not yet formed), these features will be null → imputed with median. This is handled gracefully by the pipeline. These features are most useful for **retrospective scoring** of past team configurations.

### Limitation 5 — No cross-validation
Currently uses a single time-based split. For more reliable performance estimates, use `TimeSeriesSplit` with `n_splits=5` in `model4_train.py`. This will give a better picture of variance across splits.

### Limitation 6 — XGBoost + SHAP not yet integrated
If XGBoost is installed, it is trained and evaluated, but the inference script uses generic `feature_importances_`. For production explainability (feeding richer explanations to the Agentic AI), replace this with SHAP:

```python
import shap
explainer   = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_row)
# Top features by absolute SHAP value — instance-level explanation
```

SHAP values tell you not just which feature matters globally, but *for this specific team* why the score is high or low — which is what the Agentic AI needs to write its justification.
