# Model 1 — Burnout Risk

Predicts an employee's burnout risk, bucketed **Low / Moderate / High**.

Refreshed 2026-09-03 from `UI_v2:code/Model1/`, replacing an older `GradientBoostingClassifier`
version. Live in `dev-backend` as `ml_models/burnout_model_bundle.pkl` — see that repo's
`docs/ML_MODELS_OVERVIEW.md` for the production integration writeup this doc feeds into.

## Files

| File | Purpose |
|---|---|
| `WBP-pp.py` | Preprocessing: merges `employees.csv` + `burnout_indicators.csv`, engineers the target and 2 workload features, writes `processed.csv` |
| `WBP-train.py` | Trains the model, writes `model_bundle.pkl` + `feature_importance.csv` |
| `WBP-pred.py` | CLI inference script (loads `model_bundle.pkl`, scores a given input) |
| `model_bundle.pkl` | `joblib` dict: `{"model": GradientBoostingRegressor, "features": [...17...], "low_max": float, "medium_max": float}` |
| `thresholds.json` / `selected_features.json` | Same threshold/feature-order info, in plain JSON |
| `processed.csv` | Training data (from `WBP-pp.py`) |
| `feature_importance.csv` | `model.feature_importances_`, sorted |

## Algorithm

`GradientBoostingRegressor(n_estimators=800, learning_rate=0.03, max_depth=4,
min_samples_split=10, min_samples_leaf=5, subsample=0.85, max_features="sqrt", random_state=42)`.
A **regressor**, not a classifier — the continuous output is bucketed into 3 classes only
after prediction, via the 50th/80th percentile thresholds of the training target.

## Target

`burnout_risk_computed`, engineered (not a real label) in `WBP-pp.py`:
```
maslach_core = exhaustion*0.40 + depersonalization*0.30 + reduced_accomplishment*0.30   (each min-max scaled 0-100)
behavioral   = late_hours*5 + vacation_unused*1.5 + (10-job_satisfaction)*4 + role_ambiguity*3  (then min-max scaled 0-100)
target = clip(maslach_core*0.75 + behavioral*0.25 + noise(0, 2), 0, 100)
```
Because this is a hand-built formula rather than a clinically validated label, treat model
accuracy as "how well it reproduces this formula from a reduced feature set," not validated
clinical accuracy.

## Features (17)

15 base: `technical_proficiency_score`, `domain_expertise_score`, `leadership_potential`,
`workload_compatibility_score`, `availability_score`, `collaboration_score`,
`years_of_experience`, `historical_performance_score`, `average_task_completion_rate`,
`successful_project_count`, `late_hours_frequency`, `vacation_days_unused`,
`job_satisfaction`, `role_ambiguity`, `job_control`.

2 engineered: `stress_load = (late_hours_frequency * vacation_days_unused) / 10`,
`pressure_index = late_hours_frequency + role_ambiguity`.

`workload_compatibility_score` and `availability_score` are themselves engineered in
`WBP-pp.py` from `weekly_capacity_hours`/`current_project_count`/`is_available`, with
Gaussian noise added for synthetic-data realism (the production inference code in
`dev-backend` omits that noise term, since live scoring must be deterministic).

## Metrics (re-measured 2026-09-03, scikit-learn 1.8.0 — not persisted by the original script)

| Metric | Value |
|---|---|
| R² | 0.824 |
| RMSE | 7.65 |
| CV R² (5-fold) | 0.781 ± 0.023 |
| Bucketed accuracy | 0.76 |
| Bucketed F1-macro | 0.74 |
| Per-class F1 | Low 0.84, Moderate 0.57, High 0.82 |

Top feature importances: `stress_load` 25.1%, `job_satisfaction` 16.4%, `pressure_index`
16.3%, `late_hours_frequency` 11.2%, `vacation_days_unused` 7.2%, `job_control` 6.9%.

## What else was tried

An earlier (now-deleted from this branch's history) `GradientBoostingClassifier` version
directly classified a 4-class target (Low/Moderate/High/Critical) from 135 features (symptom
mean/max/std aggregates + task-assignment aggregates). It scored **89.5% accuracy / 0.847
F1-macro** — meaningfully higher — but 20 of its 135 features (including its top 3) had no
live-DB source without a schema migration + backfill, and it needed `task_assignments`
history unavailable for new employees. The current, simpler model trades some accuracy for a
feature set that's 100% production-live from day one. No other algorithm family
(RandomForest, XGBoost, etc.) was found tried for this target anywhere in repo history.

## Retraining

```
cd code/Model1
pip install pandas numpy scikit-learn joblib
python WBP-pp.py      # regenerate processed.csv (needs employees.csv, burnout_indicators.csv)
python WBP-train.py   # trains + saves model_bundle.pkl, feature_importance.csv
```
