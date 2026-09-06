# ePARS API Contracts

Canonical copy: `backend/docs/API-Contracts.md` on the **`dev-backend`** branch. A copy of
this file is kept at `EPARS/frontend/API-Contracts.md` on the **`ui-changes`** branch so the
frontend team can read it without backend code access — **re-copy this file there after any
change** until the branches are merged.

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
  "live_real_feature_count": 38,
  "live_total_feature_count": 53,
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
comes from `performance_model.pkl` run against real DB data, mean-imputing whatever isn't
available live (~15 of 53 features today — see `ml_models/README.md`); `live_confidence` is
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
`modules/ml/predict.py::predict_burnout` (`burnout_gbm_model.pkl`).

**Response** `200`:
```json
{
  "employee": { "employee_id": "EMP001", "role": "Team Lead", "department": "Engineering", "seniority": "Mid" },
  "predicted_class": "Moderate",
  "predicted_class_color": "#92400e",
  "predicted_probabilities": { "Low": 0.0571, "Moderate": 0.9357, "High": 0.0071, "Critical": 0.0001 },
  "class_thresholds": { "Low": "score < 30", "Moderate": "30 <= score < 60", "High": "60 <= score < 80", "Critical": "score >= 80" },
  "confidence": "low",
  "imputed_features": ["fatigue_enc_max", "..."],
  "missing_top_features": ["fatigue_enc_max", "stress_enc_max", "sleep_enc_std", "..."],
  "real_feature_count": 71,
  "total_feature_count": 135,
  "top_contributing_features": { "fatigue_enc_max": 0.1953, "...": "..." },
  "stored_score": 18.4,
  "stored_category": "Low Risk"
}
```

**Update:** the 20 raw `burnout_indicators` symptom columns this model trained on — including
its top 3 most-weighted features (`fatigue_enc_max`, `stress_enc_max`, `sleep_enc_std`, ~40%
combined importance) — that were previously missing from the live schema (see
`ml_models/README.md`) have been added and backfilled from `dataset_v2/*.csv` (the same
generated dataset the model trained on, verified by real `employee_id` overlap before
backfilling). `confidence` should now reflect genuine data availability per employee rather
than being structurally `"low"` for everyone. `stored_score`/`stored_category` remain useful
as an independent point of comparison, not because the live prediction is untrustworthy.

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

## `GET /health`

No prefix. Plain liveness check, returns `{"status": "ok"}`.

---

## Not yet built

- Task assignment, workload/risk, and team-formation modules — no routes yet. Follow the
  `performance` module as the template: one `modules/<name>/routes.py` + one router
  included in `modules/main.py`, calling into existing `tools.py` functions where they
  exist.
- Burnout monitor (`src/epars_agent/agent/burnout_monitor.py`) is still a standalone
  cron/manual script (`python burnout_monitor.py`), not exposed over HTTP. If the frontend
  needs to trigger it or read its results, that's a new route to add here.
