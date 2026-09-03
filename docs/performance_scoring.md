# Performance & burnout scoring — how the live numbers are computed

See `ml_models/README.md` for pickle provenance and the full missing-feature lists. This doc
covers the parts specific to the API/UI: what each returned field means and where its number
comes from.

## `live_predicted_score` (performance)

**Updated 2026-09-03** — `performance_ridge_model.pkl` + `performance_scaler.pkl` (Ridge
regression + StandardScaler) takes just 2 features: `formula_score` and
`historical_performance_score`. At request time
(`modules/ml/predict.py::predict_performance`):

1. `formula_score` is a weighted blend of 9 `performance_reviews` scores plus
   `employees.collaboration_score` — technical cluster (30%), behavioral cluster (25%,
   includes collaboration), quality (20%), productivity (25%). All 10 raw inputs are 100%
   live (no missing-column gap, unlike the previous model). `collaboration_score` comes from
   `employees`, not `performance_reviews` — both tables have a same-named column, and the
   model was specifically trained on the `employees` one (see
   `ml_models/performance_feature_list.json` and `modules/ml/performance_features.py`'s
   docstring for why).
2. `historical_performance_score` also comes from `employees` (also live).
3. Whatever's missing on an employee's latest review or profile (any of the 11 raw inputs —
   9 from `performance_reviews`, `collaboration_score` and `historical_performance_score`
   from `employees`) is filled with that field's **training-set median**
   (`ml_models/performance_feature_list.json:raw_medians`), computed and applied *before*
   `formula_score`, not on the final 2 model features.
4. `live_confidence` is `high` (≤1 of the 11 raw inputs imputed), `medium` (≤3), or `low`
   (>3) — a simple proxy for how much of the vector is real.

The old model's `wh_health_score`/composite-feature scale-drift issue and its mean-imputed
`not_available_in_live_db` columns no longer apply — this model doesn't use
`workload_history` or `feedback` data at all.

## `score_signals` (performance UI)

A real-data-only view, separate from the model-feeding vector above (`get_score_signals` in
`modules/ml/performance_features.py`). This is what replaced the old fabricated
`breakdown`/`sub_scores` shape:

- `review_dimensions`: the 10 named competency scores (`technical_competence`,
  `domain_knowledge`, ...) read directly from `performance_reviews`, 0-10 scale, real data.
- `overtime_ratio`, `peer_productivity_gap`, `fb_composite_rating`: computed only from real
  inputs (the latter averages whichever of the 5 live `feedback` rating columns exist).
- `output_quality_composite`: always `null`. One of its 3 training inputs
  (`utilization_rate`) has no live source at all, so it can never be honestly computed —
  reporting a 2-of-3-real number would silently bake in a training-mean placeholder without
  saying so.

There was never an official rubric for a 4-cluster (technical/behavioral/quality/productivity)
weighted breakdown — the original frontend UI invented one. Rather than fabricate a mapping to
match it, the UI was changed to show these real signals instead.

## `predicted_class` / `predicted_probabilities` (burnout)

**Updated 2026-09-03** — `burnout_model_bundle.pkl` is a bare `GradientBoostingRegressor`
(not a `Pipeline`, no built-in imputer), so `modules/ml/burnout_features.py` fills any
missing raw input with that feature's **training-set median**
(`ml_models/burnout_model_metadata.json:live_medians`) before scoring. All 17 features are
sourceable live from `employees` + the employee's latest `burnout_indicators` row, so
imputation should be rare in practice.

The model regresses a continuous 0-100 score (`predicted_score`), then buckets it into 3
classes (Low/Moderate/High — no more "Critical") via the two percentile thresholds
(`low_max`/`medium_max`) it was trained with. `predicted_probabilities` is therefore a
one-hot vector on the bucketed class, not a calibrated distribution like the previous
classifier produced — kept only so existing callers that read it by class key
(`reassignment.py`'s alert `risk_fraction`) keep working.

`confidence` is derived the same way as before, from `missing_top_features`: if the
*combined importance* of missing top-weighted features is ≥30% it's `low`, ≥10% `medium`,
else `high` — see `ml_models/burnout_model_metadata.json:top_features` for the new model's
weights (`stress_load` 25.1%, `job_satisfaction` 16.4%, `pressure_index` 16.3%, ...).
