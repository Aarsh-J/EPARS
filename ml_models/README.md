# ml_models/

Two trained models, wired into the API by `modules/ml/`.

## performance_model.pkl
- `joblib.load()` → `{"model": Ridge(alpha=3.0), "scaler": StandardScaler(), "type": "ridge"}`
- 53 input features, single scalar output (0-100 `normalized_performance_score`).
- Feature order recovered from `git show ff35243c:code/Model2_Performance/feature_list.pkl` (commit "Add
  files via upload"), stored at `performance_feature_list.json`. Verified to match
  `scaler.feature_names_in_` exactly.
- Preprocessing/feature-engineering logic (aggregations, composites) recovered from
  `git show 8d893c0a:code/Model2_Performance/performance_preprocessing.py`.
- 9 of the 53 features have no live source column in the current Postgres schema (see
  `not_available_in_live_db` in `performance_feature_list.json`) — these are mean-imputed at inference time
  (see `modules/ml/performance_features.py`).

## burnout_gbm_model.pkl
- `joblib.load()` → `sklearn.Pipeline([("imputer", SimpleImputer(strategy="median")), ("model",
  GradientBoostingClassifier(...))])`. The imputer step natively handles missing features via median
  imputation, so a fully-populated feature vector isn't required.
- 135 input features, 4-class output (`Low`/`Moderate`/`High`/`Critical`, see `label_map`).
- Metadata (exact feature order, `class_thresholds`, `label_map`, `top_features` importances) recovered
  verbatim from `git show cf763293^:code/Model1/model_metadata.json`, stored at
  `burnout_model_metadata.json`.
- Feature engineering (symptom aggregation mean/max/std, ordinal encodings, task_assignments aggregation)
  recovered from `git show 9126e7e1:code/workload_preprocessing.py`.
- **Known live-data gap:** 20 of the 36 raw `burnout_indicators` symptom columns the model was trained on
  (`workload_pressure`, `work_life_conflict`, `job_demands`, `role_conflict`, `reported_stress_level`,
  `reported_fatigue_level`, `sleep_quality`, `physical_health_concerns`, `energy_level`, `engagement_score`,
  `motivation_level`, `sense_of_accomplishment`, `organizational_commitment`, `team_cohesion`,
  `workplace_relationships`, `isolation_feeling`, `coping_effectiveness`, `resource_adequacy`,
  `work_recovery_ability`, `resilience_score`) do not exist in the current production schema — only in the
  CSVs the model trained on. This includes the model's **top 3 most important features**
  (`fatigue_enc_max` 19.5%, `stress_enc_max` 10.0%, `sleep_enc_std` 9.9% — ~40% of total importance
  combined), which are therefore always imputed rather than real. `employees.communication_effectiveness`,
  `employees.cross_functional_experience`, and `employees.mentoring_experience` are similarly missing.
  The API surfaces a `confidence` flag and a `missing_features` list so the frontend can visibly warn users
  that predictions are running on mostly-imputed top-weighted inputs.
