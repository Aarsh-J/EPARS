# Model 3 — Task Assignment

Predicts, for a given (task, employee) pair, `assignment_success` (classification) and
`delay_risk_score` (regression), used to recommend the best-fit employee for a task.

Refreshed 2026-09-03 from `origin/dataset-branch:code/Model3_TaskAssignment/` — this branch's
own copy previously only had `preprocessing.py` + `label_encoders.joblib` (no trained model).
**Not yet wired into `dev-backend`'s live API** — no loader/predict module or route exists
there yet. See `dev-backend`'s `docs/ML_MODELS_OVERVIEW.md` for the integration plan.

## Files

| File | Purpose |
|---|---|
| `preprocessing.py` | Merges 7 raw tables, drops leakage-prone columns, label-encodes categoricals, engineers interaction features |
| `train.py` | Trains Layer 1 (classifier) + Layer 2 (regressor), compares 4 algorithms each |
| `train_novel_pair_models.py` | Trains Layer 3 (novel-pair regressor) |
| `save_models.py` | Picks the best model per target by test-set metric, saves as `best_*.pkl` |
| `inference.py` | Scores a (task, employee) pair that exists as a historical row |
| `scheduler.py` | Layer 3 heuristic scheduler for genuinely novel pairs |
| `profiles.py` | Builds employee/task/project profile tables |
| `app.py` | Flask API |
| `artifacts/best_classifier.pkl` | Winning classifier (Random Forest) |
| `artifacts/best_regressor.pkl` | Winning regressor (Random Forest) |
| `artifacts/novel_pair_regressor.pkl` | Layer 3 Random Forest, trained on non-leaky features only |
| `artifacts/label_encoders.joblib` | sklearn `LabelEncoder`s for categoricals |

## Architecture — 3 layers, all scikit-learn/xgboost (no deep learning)

### Layer 1 — Classifier (`assignment_success`)
Decision Tree, Random Forest, Gradient Boosting, and XGBoost all trained and compared,
70/10/20 train/val/test split (stratified), `random_state=42`.

| Model | Test accuracy | Test F1 |
|---|---|---|
| **Random Forest (winner)** | **0.595** | **0.614** |
| Gradient Boosting | 0.601 | 0.539 |
| Decision Tree | 0.597 | 0.527 |
| XGBoost | 0.574 | 0.497 |

`class_weight="balanced"` was added specifically to let Random Forest beat Gradient Boosting
after class imbalance was identified as the reason RF initially lagged — documented in the
training script's comments. Accuracy (~0.60) is only modestly above a majority-class
baseline, reflecting how noisy real-world assignment outcomes are to predict from static
features alone.

### Layer 2 — Regressor (`delay_risk_score`, full features)
Same 4 algorithms compared.

| Model | Test MAE | Test RMSE | Test R² |
|---|---|---|---|
| **Random Forest (winner)** | 8.00 | 10.36 | **0.840** |
| XGBoost | 8.22 | 10.58 | 0.833 |
| Gradient Boosting | 8.60 | 11.05 | 0.818 |
| Decision Tree | 8.82 | 11.40 | 0.806 |

`save_models.py` picks the winner programmatically by test-set metric (F1 for classification,
R² for regression) — Random Forest won both.

### Layer 3 — Novel-pair regressor
The Layer 1/2 models can only score (task, employee) pairs that already exist as historical
rows in the training data — they can't compute features for a pair with no assignment
history (features like `skill_match_score`, `reassignment_count` etc. require it). Layer 3
is a **separate** Random Forest regressor trained only on features computable without
assignment history.

| Metric | Value |
|---|---|
| MAE | 7.70 |
| RMSE | 9.99 |
| R² | **0.851** — better than the full-feature regressor |

**A novel-pair classifier was also attempted and explicitly rejected.** Its accuracy (0.551)
fell below the majority-class baseline (0.565) — worse than always guessing the majority
class — so it was deliberately left unshipped. The training script's own comment states:
*"The classifier has negative value here... NOT trained here — deliberately excluded from
Layer 3."*

## Feature engineering

Merges `tasks`, `task_assignments`, `employees`, `burnout_indicators`,
`performance_reviews`, `schedules`, `projects`. Drops leakage-prone and near-zero-importance
columns. Label-encodes categoricals (`task_type`, `priority`, `complexity`, `required_role`,
`required_seniority`, `required_certifications`, `risk_level`, `business_impact`,
`assignment_method`, `acceptance_status`). Engineers interaction features: `skill_gap`,
`emp_fitness`, `urgency_ratio`, `health_risk`.

## Known limitation

`inference.py` can only score pairs with assignment history. Scoring a genuinely novel
(task, employee) pair requires `scheduler.py` + the Layer 3 novel-pair regressor instead.

## To integrate into `dev-backend`

Write a new `modules/ml/task_assignment_*.py` loader/predict module mirroring
`modules/ml/burnout_features.py` / `modules/ml/performance_features.py`'s pattern, plus a new
route. Not attempted as part of the 2026-09-03 refresh — deliberately deferred to keep that
round scoped to the two models already live in production.

## Retraining

```
cd code/Model3_TaskAssignment
pip install pandas numpy scikit-learn xgboost joblib flask
python preprocessing.py             # writes artifacts/master_preprocessed.csv + profile CSVs
python train.py                     # Layer 1 + 2, writes results_classification.csv / results_regression.csv
python train_novel_pair_models.py   # Layer 3, writes novel_pair_regressor_results.csv
python save_models.py               # promotes the winners to artifacts/best_*.pkl
```
