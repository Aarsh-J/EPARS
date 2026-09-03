# ml_models/

Two trained models, wired into the API by `modules/ml/`. Both were refreshed on
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
