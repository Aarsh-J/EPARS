# Model 2 — Performance Score

Predicts an employee's `overall_performance_score` (0-100).

Refreshed 2026-09-03 from `UI_v2:code/Model2_Performance/` @ commit `811254b3` ("updated
model"), replacing an older bundled-Ridge version. Live in `dev-backend` as
`ml_models/performance_ridge_model.pkl` + `performance_scaler.pkl` — see that repo's
`docs/ML_MODELS_OVERVIEW.md` for the production integration writeup this doc feeds into.

## Files

| File | Purpose |
|---|---|
| `pre_processing.py` | Merges `performance_reviews.csv` + `employees.csv`, median-fills missing numerics, writes `processed_data.csv` |
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

### `collaboration_score` source — read carefully if touching this preprocessing

Both `performance_reviews` and `employees` have a same-named `collaboration_score` column.
`pre_processing.py`'s merge produces `collaboration_score_x` (from `performance_reviews`) and
`collaboration_score_y` (from `employees`) — `pre_processing.py` explicitly selects
`collaboration_score_y` and renames it back to `collaboration_score`, so **the model trains
on the `employees` value, not the review-specific one**. This is intentional (per the
script's own comment), not an oversight.

An earlier iteration of this preprocessing (commit `d4082c18` and before, superseded by
`811254b3` and never shipped to `dev-backend`) had a real bug here: it looked up the
unsuffixed `collaboration_score` name directly, which never existed post-merge, so a
`col(name, default=0)` helper silently substituted 0 for every row — collaboration's
contribution to `behavioral_cluster` was always 0 regardless of the actual data. Worth
knowing about only because it's an easy mistake to reintroduce if this preprocessing is ever
rewritten — always confirm which suffix survives a merge before referencing a column that
exists in both source tables.

## Metrics (re-measured 2026-09-03, scikit-learn 1.8.0 — not persisted by the original script)

| Metric | Value |
|---|---|
| R² | 0.813 |
| MAE | 3.292 |
| RMSE | 4.107 |
| CV R² (5-fold) | 0.811 |

## Retraining

```
cd code/Model2_Performance
pip install pandas numpy scikit-learn matplotlib
python pre_processing.py   # needs ../../dataset/{performance_reviews,employees}.csv
python train.py            # trains + saves ridge_model.pkl, scaler.pkl, diagnostic plots
```
