# ML Models Overview

Model development summary for ePARS's three ML models: what each predicts, what algorithms
were tried, why the shipped one was picked, and its real accuracy. Written 2026-09-03 when
the Burnout and Performance models in `dev-backend` were refreshed to newer versions from the
`UI_v2` branch, and the Task Assignment model from `dataset-branch` was documented (not yet
wired into the live API — see "Task Assignment" below).

For pickle-level detail (exact file shapes, loader code, feature lists) see `ml_models/README.md`.
Per-model training/retraining docs live on the `preprocessor` branch (`docs/MODEL1_BURNOUT.md`,
`docs/MODEL2_PERFORMANCE.md`, `docs/MODEL3_TASK_ASSIGNMENT.md`).

---

## 1. Burnout Model

**Predicts:** an employee's burnout risk, bucketed Low / Moderate / High.

**Currently shipped:** `GradientBoostingRegressor` (800 estimators, lr=0.03, max_depth=4,
subsample=0.85, max_features="sqrt"), trained to regress a continuous 0-100
`burnout_risk_computed` target, then bucketed into 3 classes via percentile thresholds
(50th/80th percentile of the training target).

**Target definition (synthetic, not a real label):** `0.75 * maslach_core + 0.25 * behavioral_score`,
where `maslach_core` is a weighted blend of min-max-scaled emotional exhaustion (40%),
depersonalization (30%), and reduced accomplishment (30%) scores, and `behavioral_score`
blends late-hours frequency, unused vacation days, (inverted) job satisfaction, and role
ambiguity. Small Gaussian noise is added for realism. Because the target itself is a
hand-built formula rather than a clinically validated label, the model's accuracy should be
read as "how well it reproduces this formula from a reduced feature set," not as validated
clinical accuracy.

**Features (17):** technical_proficiency_score, domain_expertise_score, leadership_potential,
workload_compatibility_score, availability_score, collaboration_score, years_of_experience,
historical_performance_score, average_task_completion_rate, successful_project_count,
late_hours_frequency, vacation_days_unused, job_satisfaction, role_ambiguity, job_control,
plus 2 engineered interaction terms: `stress_load = (late_hours_frequency *
vacation_days_unused) / 10` and `pressure_index = late_hours_frequency + role_ambiguity`.

**Top feature importances:** stress_load (25.1%), job_satisfaction (16.4%), pressure_index
(16.3%), late_hours_frequency (11.2%), vacation_days_unused (7.2%), job_control (6.9%).

**Real accuracy (re-measured 2026-09-03 by re-running `WBP-train.py` under scikit-learn
1.8.0 — the source repo never persisted these numbers):**
| Metric | Value |
|---|---|
| R² | 0.824 |
| RMSE | 7.65 |
| CV R² (5-fold) | 0.781 ± 0.023 |
| Bucketed accuracy (Low/Moderate/High) | 0.76 |
| Bucketed F1-macro | 0.74 |
| Per-class F1 | Low 0.84, Moderate 0.57, High 0.82 |

The Moderate bucket is the weakest (F1 0.57) — it's the narrowest percentile band (50th-80th)
and gets confused with both neighbors more often.

**What else was tried:** an earlier, now-superseded burnout model (deleted from history, once
lived as `code/Model1/workload_train.py`) used a `GradientBoostingClassifier` directly on a
4-class target (Low/Moderate/High/Critical) with 135 engineered features (symptom
mean/max/std aggregates, task-assignment aggregates, ordinal encodings). It scored
**89.5% accuracy / 0.847 F1-macro** with a committed confusion matrix — meaningfully higher
than the current regressor's 76%. However, 20 of its 135 features (including its top 3 most
important) had no live-DB source and required a schema migration + backfill to become usable
in production, and it depended on `task_assignments` aggregates unavailable for new
employees. The current model trades some accuracy for a feature set that's 100% live from
day one with no missing-data workarounds — a deliberate simplicity/robustness tradeoff, not
an oversight. No other algorithm (RandomForest, XGBoost, etc.) was tried for the burnout
target in the repo history found.

**Known limitation:** the model has no native `predict_proba` (it's a regressor with
hard percentile bucketing), so the API's `predicted_probabilities` field is now a one-hot
vector on the bucketed class rather than a calibrated distribution. The real continuous
score is exposed separately as `predicted_score`.

---

## 2. Performance Model

**Predicts:** an employee's `overall_performance_score` (0-100).

**Currently shipped:** `Ridge(alpha=1)` + `StandardScaler`, using just 2 features:
`formula_score` (a weighted blend of 9 raw review-dimension scores) and
`historical_performance_score`.

**formula_score definition:**
`technical_cluster*0.30 + behavioral_cluster*0.25 + quality_norm*0.20 + productivity_norm*0.25`,
where `technical_cluster` averages technical_competence/domain_knowledge/problem_solving
(scaled ×10), `behavioral_cluster` averages communication/collaboration/leadership/initiative/
time_management (scaled ×10), `quality_norm = quality_of_work_score * 10`, and
`productivity_norm = productivity_score * 10`.

**Preprocessing note — `collaboration_score` source:** both `performance_reviews` and
`employees` have a same-named `collaboration_score` column. UI_v2's `pre_processing.py`
explicitly keeps the `employees` one (via the merge's `collaboration_score_y`, renamed) as
what the model trains on — `modules/ml/performance_features.py` sources it from `employees`
to match. (An earlier iteration of this same model, superseded before this integration and
never shipped to `dev-backend`, had a preprocessing bug where this column resolved to neither
suffix and silently defaulted to 0 for every row — worth knowing about only because it's an
easy mistake to reintroduce if this preprocessing is ever rewritten.)

**Real accuracy (re-measured 2026-09-03 by re-running `train.py` under scikit-learn 1.8.0 —
also never persisted in the source repo):**
| Metric | Value |
|---|---|
| R² | 0.813 |
| MAE | 3.292 |
| RMSE | 4.107 |
| CV R² (5-fold) | 0.811 |

**What else was tried:** Ridge regression is the only algorithm found anywhere in this
model's repo history — no RandomForest/XGBoost/other comparison was ever committed. An
earlier `train_ridge.py` iteration is explicitly labeled "Complexity: Very Low" in its own
docstring, implying higher-complexity alternatives were considered but never built.

**All inputs are live:** unlike the previous model (53 features, 9 with no live-DB source),
every input this model needs is already present in `performance_reviews`/`employees`.

---

## 3. Task Assignment Model

**Status: documented here, NOT yet integrated into `dev-backend`'s live API.** It has no
existing loader, predict function, or route — this write-up exists so the capability is
understood and ready to wire up when prioritized. Source: `dataset-branch`,
`code/Model3_TaskAssignment/`.

**Predicts:** for a given (task, employee) pair — `assignment_success` (classification) and
`delay_risk_score` (regression), used to recommend the best-fit employee for a task. A
separate 3rd "Layer 3" model handles pairs with no assignment history.

**Architecture — 3 layers, all scikit-learn/xgboost (no deep learning):**
1. **Classifier** (`assignment_success`) — Decision Tree, Random Forest, Gradient Boosting,
   and XGBoost were all trained and compared; **Random Forest won** (test F1 0.614, accuracy
   0.595 — only modestly above a majority-class baseline, reflecting how noisy real-world
   assignment outcomes are to predict from static features alone).
2. **Regressor** (`delay_risk_score`) — same 4 algorithms compared; **Random Forest won**
   again (R²=0.84, MAE=8.00, RMSE=10.36).
3. **Novel-pair regressor** (Layer 3, for task/employee pairs with no assignment history) —
   Random Forest, trained only on features computable without historical assignment data.
   Scored **R²=0.851** (MAE=7.70, RMSE=9.99) — actually better than the full-feature
   regressor. A **novel-pair classifier was also attempted and explicitly rejected**: its
   accuracy (0.551) fell below the majority-class baseline (0.565), so it was deliberately
   left out of the shipped system — documented directly in the training script's own
   comments as "the classifier has negative value here."

**Feature engineering:** merges 7 raw tables (tasks, task_assignments, employees,
burnout_indicators, performance_reviews, schedules, projects), drops leakage-prone/
near-zero-importance columns, label-encodes categoricals, and engineers interaction features
(`skill_gap`, `emp_fitness`, `urgency_ratio`, `health_risk`). `class_weight="balanced"` was
added to the classifier specifically to let Random Forest beat Gradient Boosting after class
imbalance was identified as the reason RF initially lagged.

**Known limitation:** the standard classifier/regressor can only score (task, employee) pairs
that already exist as historical rows — it cannot score a genuinely novel pairing, which is
exactly why Layer 3 (the novel-pair regressor + a heuristic scheduler) exists.

**To integrate into `dev-backend`:** would need a new `modules/ml/task_assignment_*.py`
loader/predict module (mirroring `burnout_features.py`/`performance_features.py`) and a new
route, following the pattern in `modules/ml/loader.py` and `modules/ml/predict.py`. Not
attempted in this pass — deferred to keep this round scoped to refreshing the two models
already live in production.
