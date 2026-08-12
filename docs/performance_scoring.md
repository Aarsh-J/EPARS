# Performance & burnout scoring — how the live numbers are computed

See `ml_models/README.md` for pickle provenance and the full missing-feature lists. This doc
covers the parts specific to the API/UI: what each returned field means and where its number
comes from.

## `live_predicted_score` (performance)

`performance_model.pkl` (Ridge regression + StandardScaler) takes 53 features. At request time
(`modules/ml/predict.py::predict_performance`):

1. Real values are pulled from `performance_reviews`, `employees`, `feedback`, and
   `workload_history` for the given employee (`modules/ml/performance_features.py`).
2. Whatever isn't available live (~9-15 of 53 features, employee-dependent — see
   `not_available_in_live_db` in `ml_models/performance_feature_list.json`) is filled with
   that feature's **training mean** (`scaler.mean_`). Because of how StandardScaler + Ridge
   combine, a feature imputed to its training mean contributes exactly 0 to the prediction —
   it's a neutral default, not a guess.
3. Composites (`output_quality_composite`, `overtime_ratio`, `peer_productivity_gap`,
   `fb_composite_rating`) are then computed from the (real-or-imputed) inputs, using the
   formulas recovered from the original training script.
4. `wh_health_score` is the one exception: it's always mean-imputed, never computed. The live
   `workload_history.efficiency_ratio` column runs 0-75, not the ~0-1.2 ratio the formula's
   `* 20` term assumes — a genuine scale drift between the training CSVs and the live seeded
   DB. Computing it anyway produced predictions >300 before clipping in testing.
5. `live_confidence` is `high` (≤5 imputed), `medium` (≤15), or `low` (>15) — a simple proxy
   for how much of the vector is real.

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

`burnout_gbm_model.pkl` is an sklearn `Pipeline([SimpleImputer(strategy="median"),
GradientBoostingClassifier])`. Unlike the performance model, it has its own imputer, so
`modules/ml/burnout_features.py` simply leaves unavailable features as `NaN` and lets the
pipeline fill them with its fitted training median — the "correct" way to handle missing data
for this particular model.

`confidence` is derived from `missing_top_features`: if the *combined importance* of missing
top-weighted features is ≥30% it's `low`, ≥10% `medium`, else `high`. In practice this is
`low` for nearly every employee today, because the model's top 3 features by importance
(`fatigue_enc_max` 19.5%, `stress_enc_max` 10.0%, `sleep_enc_std` 9.9%) need raw
`burnout_indicators` columns (`reported_fatigue_level`, `reported_stress_level`,
`sleep_quality`) that don't exist in the live schema — see `ml_models/README.md` for the full
list of 20 missing symptom columns.
