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
- **Live-data gap — fixed.** 20 of the 36 raw `burnout_indicators` symptom columns the model was trained
  on (`workload_pressure`, `work_life_conflict`, `job_demands`, `role_conflict`, `reported_stress_level`,
  `reported_fatigue_level`, `sleep_quality`, `physical_health_concerns`, `energy_level`, `engagement_score`,
  `motivation_level`, `sense_of_accomplishment`, `organizational_commitment`, `team_cohesion`,
  `workplace_relationships`, `isolation_feeling`, `coping_effectiveness`, `resource_adequacy`,
  `work_recovery_ability`, `resilience_score`) — including the model's **top 3 most important features**
  (`fatigue_enc_max` 19.5%, `stress_enc_max` 10.0%, `sleep_enc_std` 9.9%) — originally didn't exist in the
  production schema, only in the CSVs the model trained on. Root cause: `dataset_v2/burnout_indicators.csv`
  (the actual generated dataset, tracked on the `preprocessor` branch) has always had these columns; the
  `CREATE TABLE burnout_indicators` in `src/epars_agent/setup_database.py` simply never included them, so
  they never made it into the live Postgres DB.

  **Fixed via schema migration + backfill** (all 20 columns, plus `employees.communication_effectiveness`,
  `employees.work_life_balance_score`, `employees.cross_functional_experience`,
  `employees.mentoring_experience`): `ALTER TABLE ... ADD COLUMN` for each, then backfilled real values
  from `dataset_v2/*.csv` matched by primary key. Verified ID overlap before backfilling: 100% for
  `burnout_indicators`, ~47% for `employees` (the rest keep imputing — no matching source data exists for
  the other ~53% of live employee rows, which is honest given they were never in this generated dataset).
  `modules/ml/feature_specs.py` and `modules/ml/burnout_features.py` now source all 36 symptom columns and
  all `employees.*` fields live instead of imputing them. `confidence` should now reflect genuine per-
  employee data availability rather than being structurally `"low"` for everyone.
