# Model 2 — Performance Score

Predicts an employee's `overall_performance_score` (0-100).

Refreshed 2026-09-03 from `UI_v2:code/Model2_Performance/`, replacing an older bundled-Ridge
version. Live in `dev-backend` as `ml_models/performance_ridge_model.pkl` +
`performance_scaler.pkl` — see that repo's `docs/ML_MODELS_OVERVIEW.md` for the production
integration writeup this doc feeds into.

## Files

| File | Purpose |
|---|---|
| `pre_processing.py` | Merges `performance_reviews.csv` + `employees.csv` + `workload_history.csv`, median-fills missing numerics, writes `processed_data.csv` |
| `train.py` | Trains the model, writes `ridge_model.pkl` + `scaler.pkl` + diagnostic plots |
| `pem_predict.py` | CLI inference script |
| `ridge_model.pkl` / `scaler.pkl` | Separate pickles — `dev-backend`'s loader wraps both into one dict at load time |
| `processed_data.csv` | Training data |

## Algorithm

`Ridge(alpha=1)` on `StandardScaler`-scaled features. The only algorithm ever tried for this
model in repo history — no RandomForest/XGBoost/other comparison was ever committed. An
earlier `train_ridge.py` iteration is explicitly labeled `"Complexity: Very Low"` in its own
docstring, implying higher-complexity alternatives were considered but never built.

## Target

`overall_performance_score`, from `performance_reviews`.

## Features (2)

`formula_score` and `historical_performance_score`.

```
formula_score = technical_cluster*0.30 + behavioral_cluster*0.25 + quality_norm*0.20 + productivity_norm*0.25
technical_cluster  = (technical_competence_score + domain_knowledge_score + problem_solving_score) / 3 * 10
behavioral_cluster = (communication_score + collaboration_score + leadership_score + initiative_score + time_management_score) / 5 * 10
quality_norm       = quality_of_work_score * 10
productivity_norm  = productivity_score * 10
```

### Known bug (present in the shipped model — not yet fixed)

`train.py` reads `collaboration_score` through a `col(name, default=0)` helper that silently
returns 0 when the exact column name isn't in the training dataframe. Because
`pre_processing.py`'s merge produces `collaboration_score_x`/`collaboration_score_y`
(suffix collision between `performance_reviews` and `employees`, both of which have a
`collaboration_score` column) and never an unsuffixed `collaboration_score`, this lookup
always returns 0 — **the model was trained with collaboration's contribution to
`behavioral_cluster` always 0**, not the real per-review value. `dev-backend`'s inference
code deliberately replicates this (rather than "fixing" it) so the model sees the same input
distribution it was trained on — feeding it real collaboration data would silently shift its
calibration. Fixing this properly requires retraining, not just a preprocessing patch: the
fix is to name the review-table and employee-table columns distinctly before merging (e.g.
`review_collaboration_score` / `employee_collaboration_score`), decide which one — or both —
should actually feed `behavioral_cluster`, and retrain.

## Metrics (re-measured 2026-09-03, scikit-learn 1.8.0 — not persisted by the original script)

| Metric | Value |
|---|---|
| R² | 0.817 |
| MAE | 3.242 |
| RMSE | 4.072 |
| CV R² (5-fold) | 0.814 |

## Retraining

```
cd code/Model2_Performance
pip install pandas numpy scikit-learn matplotlib
python pre_processing.py   # needs ../dataset/{performance_reviews,employees,workload_history}.csv
python train.py            # trains + saves ridge_model.pkl, scaler.pkl, diagnostic plots
```
