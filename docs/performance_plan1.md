# Wire `ml_models/*.pkl` into EPARS (live performance + burnout predictions)

## Context

`EPARS-backend/ml_models/` contains two trained models dropped in but never wired up: `performance_model.pkl` (Ridge regressor + StandardScaler) and `burnout_gbm_model.pkl` (GradientBoostingClassifier pipeline). Today the app's "ML output" is entirely pre-computed — `get_employee_ml_scores()` in `tools.py` just reads `overall_performance_score`/`overall_burnout_risk` columns straight out of Postgres. Neither pickle is imported anywhere in the codebase.

Two real problems motivate this work:
1. There's no live inference at all — the two capstone-defining models sit unused.
2. The frontend's `Performance.jsx` `ResultContent` component already **crashes today** on every "Analyse" click: it dereferences `data.breakdown[c.key]` and `data.sub_scores[key]` unconditionally, but `/api/performance/analyse` never returns those fields (a gap documented in `docs/API-Contracts.md` — that data was supposed to come from a "Model2_Performance" never merged into this branch).

Both training scripts/feature lists no longer exist in the working tree but are fully recoverable from this repo's own git history (old paths `code/Model1/`, `code/Model2_Performance/`), which is how the feature order/encodings below were determined — not guessed.

**Confirmed blocker:** `burnout_gbm_model.pkl` was trained on scikit-learn 1.8.0 and fails to unpickle under the currently-installed 1.9.0 (`ModuleNotFoundError: No module named '_loss'`, an internal sklearn layout change). `performance_model.pkl` (trained on 1.7.1) loads under 1.9.0 with just a warning. Fix: pin `scikit-learn==1.8.0` for both.

**Decision — breakdown/sub-scores shape:** The Ridge model outputs a single scalar; it has no 4-cluster/10-subscore structure. Rather than fabricate numbers to match the old frontend shape, replace that UI with real signals: the engineered composites (`output_quality_composite`, `overtime_ratio`, `peer_productivity_gap`, feedback rating) plus the actual per-dimension scores already stored in `performance_reviews` (technical_competence, domain_knowledge, etc. — same label set as today's `SUBSCORE_LABELS`, real data instead of invented).

**Scope cut:** `burnout_monitor.py` keeps reading the stored DB column for now; switching it to live inference is a follow-up, not part of this pass.

## Implementation steps

### 1. Unblock sklearn
- `EPARS-backend/requirements.txt`: pin `scikit-learn==1.8.0`, add `joblib>=1.3.0`, `numpy>=1.26.0`, `pandas>=2.2.0` (comment noting the pin matches `burnout_gbm_model.pkl`'s training env).
- Rebuild the venv, then smoke-test both pickles load via a throwaway `joblib.load()` call before writing any app code.

### 2. Recover and store feature specs (ground truth, not guessed)
- Extract from git history into `EPARS-backend/ml_models/`:
  - `performance_feature_list.py` (or `.json`) — ordered feature list recovered from `git show ff35243c:code/Model2_Performance/feature_list.pkl`, cross-checked against `performance_preprocessing.py` (commit `8d893c0a`). Order: 21 `performance_reviews` numeric cols + `review_type_enc` + 7 `employees` numeric cols + feedback agg cols (`fb_*`) + workload_history agg cols (`wh_*`) + 3 engineered composites.
  - `burnout_model_metadata.json` — recovered from `git show cf763293^:code/Model1/model_metadata.json` (135 `feature_columns`, `label_map` `{0:Low,1:Moderate,2:High,3:Critical}`, `class_thresholds`, `top_features`), cross-checked against `workload_preprocessing.py` (commit `9126e7e1`). Order: 36 symptom cols × {mean,max,std} (108) + 22 static `employees` cols (with ordinal encodings for stress/fatigue/sleep/trend/seniority) + 5 `ta_*` task-assignment aggregates.
- Add `EPARS-backend/ml_models/README.md` documenting provenance (commit hashes) so this isn't an opaque recovered blob.

### 3. Feature-assembly layer
New package `EPARS-backend/modules/ml/`:
- `loader.py` — `get_performance_model()`, `get_burnout_model()`, lazy module-level singletons via `joblib.load()`.
- `feature_specs.py` — loads the ordered feature lists/encoding maps from `ml_models/`.
- `performance_features.py` — `assemble_performance_features(employee_id, review_id=None) -> pd.DataFrame` (1 row). New SQL for feedback/workload_history aggregation (not currently in `tools.py`); reuse `get_employee_profile` pattern for the rest. Applies the same encodings/composites as the recovered preprocessing script, reindexes to exact training column order.
- `burnout_features.py` — `assemble_burnout_features(employee_id) -> pd.DataFrame` (1 row). New SQL for `burnout_indicators` mean/max/std aggregation and `task_assignments` aggregation.
- `predict.py` — `predict_performance(employee_id, review_id=None) -> dict`, `predict_burnout(employee_id) -> dict`.
- Missing values: fall back to a documented default (0), not a per-request median (training used dataset-wide medians) — log a warning when this happens. Call this out as a known limitation in a code comment.

### 4. Startup wiring
- `modules/main.py`: call `get_performance_model()`/`get_burnout_model()` once at import/startup (e.g. via `lifespan`) so a broken pickle fails fast at boot with a clear log line, without crashing the rest of the app (performance-list/agent routes should keep working even if ML load fails).

### 5. API changes
- `modules/performance/routes.py` — extend `POST /api/performance/analyse` response with:
  - `live_predicted_score` (from `predict_performance`)
  - `score_signals`: `{output_quality_composite, overtime_ratio, peer_productivity_gap, fb_composite_rating, review_dimensions: {technical_competence, domain_knowledge, ...}}` (real values, reusing today's `SUBSCORE_LABELS` keys where they map to `performance_reviews` columns).
  - Keep existing `predicted_score` (DB-stored) as-is for comparison.
- New `modules/burnout/routes.py` (mirrors `modules/performance/routes.py`):
  - `GET /api/burnout/employees` — latest stored `burnout_category` per employee, for a selector table.
  - `POST /api/burnout/analyse` (body `{employee_id}`) — returns `predicted_class` (Low/Moderate/High/Critical), `predicted_probabilities` (per-class), `stored_score` (existing DB value for comparison), `top_contributing_indicators` (from `model_metadata.json`'s `top_features`).
  - Register in `modules/main.py`: `app.include_router(burnout_router, prefix="/api")`.

### 6. Frontend
- `EPARS-frontend/src/pages/Performance.jsx` — in `ResultContent`, replace the `CLUSTER_META`/`data.breakdown[c.key]` block and the `SUBSCORE_LABELS`/`data.sub_scores[key]` block with rendering over `data.score_signals` (4 real metric cards + `review_dimensions` list), with null-guards (`data.score_signals?.review_dimensions?.[key] ?? "—"`) since a first-time employee may have no review row. This both fixes the pre-existing crash and delivers real data.
- `EPARS-frontend/src/api/client.js` — add `getBurnoutEmployees()` and `analyseBurnout(employeeId)`.
- New `EPARS-frontend/src/pages/Burnout.jsx` — mirrors `Performance.jsx`'s selector-table → Analyse → result pattern, reusing existing CSS classes (`card`, `employee-table`, `score-pill`). Shows: employee header, class badge (colored per `class_thresholds`), a 4-class probability bar list (plain inline-width divs, same technique the app already uses — no new chart library needed for this), top contributing indicators.
- Add route in `App.jsx` (`/burnout` → `Burnout.jsx`, page title "Workload & Risk") and flip Dashboard's "Workload & Risk" card from disabled to active.

## Verification

1. After Step 1: raw `joblib.load()` on both `.pkl` files succeeds with pinned sklearn — no exceptions.
2. After Step 3: standalone script `EPARS-backend/scripts/test_ml_models.py` (throwaway harness, connects via existing `db.py::get_connection`) runs both `predict_*` functions against 2–3 real `employee_id`s, prints raw output; sanity-check predictions land in a believable range vs. each employee's existing DB-stored score.
3. After Step 5: `uvicorn modules.main:app --reload --port 8000` boots cleanly, `/health` still returns ok; manually call `/api/performance/analyse` and `/api/burnout/analyse` for a real employee_id and confirm the new fields match Step 2's script output for that same employee.
4. After Step 6: run both `uvicorn` and `npm run dev`, click through the Performance page (confirm no console error, real score_signals render) and the new Burnout page end-to-end; confirm displayed numbers match what the backend script printed.
