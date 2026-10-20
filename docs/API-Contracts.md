# ePARS API Contracts

Canonical copy: `backend/docs/API-Contracts.md` on the **`dev-backend`** branch. A copy of
this file is kept at `docs/API-Contracts.md` (repo root) on the **`dev-frontend`** branch so
the frontend team can read it without backend code access — **re-copy this file there after
any change** until the branches are merged.

Base URL: `http://localhost:8000` in dev (`VITE_API_URL` in the frontend's `.env`), the
deployed Render URL in production. All routes are prefixed `/api`.

Server: `modules/main.py` (FastAPI). Every route is a thin wrapper — it calls straight into
functions in `src/epars_agent` / `src/epars_policies` and does not reimplement business
logic. The function(s) backing each route are named below so you know where to look/change
behavior.

---

## `GET /api/performance/employees`

Employee list with latest performance score, for the employee-selector table.

Backed by: `modules/performance/routes.py::list_employees` (direct SQL query — no
equivalent "list all" function exists in `tools.py` yet).

**Response** `200`:
```json
[
  { "employee_id": "EMP001", "department": "Engineering", "role": "Software Engineer",
    "seniority": "Mid", "score": 78.4 }
]
```

## `POST /api/performance/analyse`

**Request body:**
```json
{ "employee_id": "EMP001", "review_id": null }
```
(`review_id` is accepted for forward-compatibility but not yet used to select a specific
historical review — currently always returns the latest.)

Backed by: `get_employee_profile()` + `get_employee_ml_scores()` in
`src/epars_agent/agent/tools.py`, plus a review-history query in
`modules/performance/routes.py::_review_history`, plus live model inference via
`modules/ml/predict.py::predict_performance` (see `docs/performance_scoring.md` and
`ml_models/README.md` for how that's computed).

**Response** `200`:
```json
{
  "employee": {
    "employee_id": "EMP001", "role": "Software Engineer", "department": "Engineering",
    "seniority": "Mid", "review_type": "Annual", "review_date": "2026-03-01"
  },
  "predicted_score": 78.4,
  "rating_label": "High Performer",
  "rating_color": "#1e40af",
  "live_predicted_score": 74.6,
  "live_confidence": "medium",
  "live_real_feature_count": 10,
  "live_total_feature_count": 11,
  "score_signals": {
    "review_dimensions": { "technical_competence": 6.0, "domain_knowledge": 7.0, "...": "..." },
    "output_quality_composite": null,
    "overtime_ratio": 0.0309,
    "peer_productivity_gap": -8.9,
    "fb_composite_rating": 7.66
  },
  "all_reviews": [
    { "review_id": "REV0001", "review_type": "Annual", "review_date": "2026-03-01",
      "overall_score": 78.4 }
  ]
}
```

`predicted_score` is the DB-stored value (unchanged, for comparison). `live_predicted_score`
comes from `performance_ridge_model.pkl` run against real DB data (2 model features derived
from 11 real raw inputs, all live — see `ml_models/README.md`), median-imputing any
individual raw input missing on the employee's latest review/profile; `live_confidence` is
`high`/`medium`/`low` based on how many were imputed. `score_signals.review_dimensions`
replaces the old fabricated `breakdown`/`sub_scores` shape with real per-competency scores
from `performance_reviews`; the 4 composite signals are `null` when their inputs aren't fully
real rather than silently reporting a training-mean-derived number — see
`docs/performance_scoring.md`.

## `GET /api/burnout/employees`

Employee list with latest stored burnout assessment, for the selector table.

Backed by: `modules/burnout/routes.py::list_employees`.

**Response** `200`:
```json
[
  { "employee_id": "EMP001", "department": "Engineering", "role": "Team Lead",
    "seniority": "Mid", "stored_score": 18.4, "stored_category": "Low Risk" }
]
```

## `POST /api/burnout/analyse`

**Request body:**
```json
{ "employee_id": "EMP001" }
```

Backed by: `get_employee_profile()` in `tools.py` plus live model inference via
`modules/ml/predict.py::predict_burnout` (`burnout_model_bundle.pkl`).

**Response** `200`:
```json
{
  "employee": { "employee_id": "EMP001", "role": "Team Lead", "department": "Engineering", "seniority": "Mid" },
  "predicted_class": "Moderate",
  "predicted_class_color": "#92400e",
  "predicted_probabilities": { "Low": 0.0, "Moderate": 1.0, "High": 0.0 },
  "predicted_score": 24.1,
  "class_thresholds": { "low_max": 19.48, "medium_max": 37.78 },
  "confidence": "high",
  "imputed_features": ["..."],
  "missing_top_features": [],
  "real_feature_count": 15,
  "total_feature_count": 17,
  "top_contributing_features": { "stress_load": 0.2505, "...": "..." },
  "stored_score": 18.4,
  "stored_category": "Low Risk"
}
```

**Update (2026-09-03):** the burnout model was swapped for a newer version (see
`ml_models/README.md`, `docs/ML_MODELS_OVERVIEW.md`). It's now a `GradientBoostingRegressor`
whose continuous score is bucketed into 3 classes (Low/Moderate/High — no more "Critical"),
not the previous 4-class classifier. `predicted_probabilities` is a one-hot vector on the
bucketed class (kept only for callers that read it by class key), not a calibrated
distribution — use the new `predicted_score` field for the real continuous value. All 17
input features are sourceable live (no ADD COLUMN/backfill gap like the previous model
needed), so `confidence` should genuinely vary by employee rather than being structurally
`"low"` for everyone. `stored_score`/`stored_category` remain useful as an independent point
of comparison, not because the live prediction is untrustworthy.

## `POST /api/agent/query`

Passes a natural-language request straight to the existing LangGraph agent.

**Request body:**
```json
{ "query": "Assign task TSK0042 to the best available employee" }
```

Backed by: `run_agent()` in `src/epars_agent/agent/epars_agent.py` — the exact function
`src/epars_agent/test_agent.py` already calls for its canned tests.

**Response** `200`:
```json
{
  "input": "Assign task TSK0042 to the best available employee",
  "output": "Assigned TSK0042 to EMP042 because ...",
  "steps": [
    { "tool": "get_task_details", "output": "{...}" }
  ]
}
```
`steps` is the ordered list of tool calls the agent made — useful for the frontend to show
its work, not just the final answer.

## `GET /api/task_assignment/tasks`

Open (not completed/cancelled) tasks for the selector UI.

Backed by: `modules/task_assignment/routes.py::list_tasks`, `modules/ml/task_assignment_features.py::get_open_tasks`.

**Response** `200`:
```json
[
  { "task_id": "TSK1195", "task_name": "Code review #1195", "task_type": "Review",
    "priority": "Critical", "required_role": "Senior Engineer", "due_date": "2023-01-06",
    "status": "In Review" }
]
```

## `GET /api/task_assignment/score?task_id=&employee_id=`

Score a single (task, employee) pair — works for pairs with no assignment history.

Backed by: `modules/ml/task_assignment_predict.py::score_pair` (Model3, Layer 3 —
`task_assignment_regressor.pkl`; see `ml_models/README.md` for why Layers 1/2 aren't used).

**Response** `200`:
```json
{
  "task_id": "TSK1195",
  "employee_id": "EMP001",
  "predicted_delay_risk": 78.7,
  "real_skill_match": 0.0,
  "composite_score": 39.5,
  "delay_component": 21.3,
  "skill_component": 0.0,
  "availability_component": 58.8,
  "reliability_component": 100.0,
  "health_component": 81.7
}
```
`composite_score` (0-100, higher is better) blends `predicted_delay_risk` (35%, inverted),
skill fit (25%), availability (15%), historical reliability (15%), and health/burnout risk
(10%, inverted) — the `*_component` fields are each already on a 0-100 "higher is better" scale
so the frontend can render them directly (e.g. as a breakdown bar chart) without re-deriving
signs/weights client-side.

## `GET /api/task_assignment/recommend/{task_id}?top_n=3`

Ranks every employee against a task, returns the top N by `composite_score` descending.

Backed by: `modules/ml/task_assignment_predict.py::recommend_top_n` — batches the regressor
call across the whole candidate pool instead of one predict() per employee.

**Response** `200`: array of the same shape as `/score`'s response, sorted by `composite_score` descending.

---

## Not yet built

- Team-formation module (Model 4) — no trained pickle exists yet with an acceptable accuracy
  (the one attempt, on `dataset-branch`, has negative test R² per its own docs). Deferred until
  a properly trained model exists; follow `task_assignment` as the template once it does.
- Burnout monitor (`src/epars_agent/agent/burnout_monitor.py`) is still a standalone
  cron/manual script (`python burnout_monitor.py`), not exposed over HTTP. If the frontend
  needs to trigger it or read its results, that's a new route to add here.
