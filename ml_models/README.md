# ml_models/

Three trained models, wired into the API by `modules/ml/`. The first two were refreshed on
2026-09-03 from newer versions developed on other branches — see
`../docs/ML_MODELS_OVERVIEW.md` for the full model-development writeup (algorithms
tried, features, real accuracy numbers) and the per-model docs on the
`preprocessor` branch. This replaced the previous `burnout_gbm_model.pkl` /
`performance_model.pkl` pair (still recoverable from git history / the
`preprocessor` branch if a rollback is ever needed).

**Note:** the performance model pkls were re-copied same-day from a slightly newer `UI_v2`
commit (`811254b3`) than the first pass used, which fixed a real preprocessing bug
(`collaboration_score` was silently zeroed for every row) — see `performance_feature_list.json`
and `modules/ml/performance_features.py` for the corrected behavior.

## performance_ridge_model.pkl + performance_scaler.pkl
- Source: `UI_v2:code/Model2_Performance/{ridge_model.pkl,scaler.pkl}` (`train.py`), retrained
  under scikit-learn 1.8.0 (this repo's pinned version) to guarantee a clean unpickle.
- `modules/ml/loader.py:get_performance_model()` loads both files and wraps them into the
  same `{"model": Ridge, "scaler": StandardScaler, "type": "ridge"}` shape the rest of
  `modules/ml/` already expects — no other code needed to change shape.
- Only **2 input features**: `formula_score` (a weighted blend of 9 performance_reviews scores
  plus `employees.collaboration_score`) and `historical_performance_score`. Down from 53
  features in the previous model. Full formula documented in `performance_feature_list.json`.
  Note: `collaboration_score` comes from `employees`, not `performance_reviews` — both tables
  have a same-named column, and the model trains on the `employees` one specifically (see
  `modules/ml/performance_features.py`'s docstring for why).
- Both features are 100% live — no live-data gap, unlike the previous model's 9 missing columns.
- Metrics (re-measured, not persisted in the source repo): R²=0.813, MAE=3.292, RMSE=4.107,
  5-fold CV R²=0.811.

## burnout_model_bundle.pkl
- Source: `UI_v2:code/Model1/model_bundle.pkl` (`WBP-train.py`), retrained under scikit-learn
  1.8.0 for the same reason as above.
- `joblib.load()` → `{"model": GradientBoostingRegressor, "features": [...17...], "low_max":
  float, "medium_max": float}` — a **regressor**, not the previous model's classifier. Its
  continuous 0-100 score is bucketed into 3 classes (Low/Moderate/High) via the two
  percentile thresholds in the bundle. There is no more "Critical" 4th tier — see
  `modules/ml/predict.py` and `modules/ml/reassignment.py::THRESHOLD_CLASSES`.
- No native `predict_proba` (it's a regressor) — `predicted_probabilities` in the API response
  is now a one-hot vector on the bucketed class, kept only for backward compatibility with
  callers that read the dict by class key (e.g. `reassignment.py`'s alert `risk_fraction`).
  The real continuous score is exposed as `predicted_score`.
- 17 input features (down from 135), **all sourceable live** from `employees` + the employee's
  single latest `burnout_indicators` row — no ADD COLUMN/backfill gap like the previous model
  needed. This model has no built-in imputer, so missing values are filled with training-set
  medians (`burnout_model_metadata.json:live_medians`) in `modules/ml/burnout_features.py`.
- Metrics (re-measured, not persisted in the source repo): R²=0.824, RMSE=7.65,
  5-fold CV R²=0.781, bucketed accuracy=0.76, bucketed F1-macro=0.74.

## task_assignment_regressor.pkl + task_assignment_label_encoders.joblib
- Source: `preprocessor:code/Model3_TaskAssignment/artifacts/{novel_pair_regressor.pkl,
  label_encoders.joblib}` — "Layer 3" of that branch's 3-model pipeline (`scheduler.py`).
- **Layers 1/2 on that branch (`best_classifier.pkl` + `best_regressor.pkl`) are deliberately
  NOT used here.** They only score task/employee pairs that already exist as historical rows
  in the training data — useless for the real product need (recommending a genuinely new
  pairing). Layer 1's classifier specifically was measured at AUC=0.58 on novel pairs
  (barely above the 0.50 random baseline) and was excluded from `scheduler.py` by its own
  author for that reason.
- `task_assignment_regressor.pkl` is a `RandomForestRegressor` (33 features, `feature_names_in_`
  pinned) predicting `delay_risk_score` for ANY (task, employee) pair — trained and validated
  specifically on pairs with zero assignment history. R²=0.851 on that novel-pair test set,
  the only one of the three models actually measured on the scenario this API needs.
- `task_assignment_label_encoders.joblib` — `{column: fitted LabelEncoder}` for the task's
  categorical inputs (`task_type`, `priority`, `complexity`, `required_role`,
  `required_seniority`, `risk_level`, `business_impact`); unseen values at inference time fall
  back to each encoder's first known class (same policy as the source branch's
  `encode_categoricals(fit=False)`). Unpickles with a scikit-learn version warning (fitted
  under 1.5.2, this repo pins 1.8.0) — functionally fine for a `LabelEncoder` (just an array of
  classes + a mapping), but retrain-and-recopy under 1.8.0 if that ever becomes a concern.
- All 33 features are sourced live via `modules/ml/task_assignment_features.py` — the live
  Postgres schema (`tasks`, `projects`, `employees`, `burnout_indicators`, `schedules`) mirrors
  the CSVs Layer 3 was trained on column-for-column, so there's no live-data gap here either.
  The composite 0-100 ranking score blends this model's delay-risk prediction (35%) with
  4 explainable heuristics — skill fit (25%, from raw `required_skills`/`primary_skills` text
  overlap, sourceable for every pair), availability (15%), historical reliability (15%), and
  health/burnout risk (10%) — see `modules/ml/task_assignment_predict.py` for the exact
  formula (ported verbatim from `scheduler.py`).
