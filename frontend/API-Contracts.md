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
`modules/performance/routes.py::_review_history`.

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
  "all_reviews": [
    { "review_id": "REV0001", "review_type": "Annual", "review_date": "2026-03-01",
      "overall_score": 78.4 }
  ]
}
```

**⚠️ Known gap:** the frontend's `Performance.jsx` was originally built against a richer
shape that included `breakdown` (technical/behavioral/quality/productivity percentages) and
`sub_scores` (10 named 0–10 scores). **Those fields are NOT returned** — that data would
come from `Model2_Performance`, which lives on other branches (`preprocessor`, etc.), not
`dev-backend`. Frontend TODO: `Performance.jsx`'s `ResultContent` component needs to stop
rendering the cluster-breakdown and sub-score sections until `Model2_Performance` is ported
into this branch and a real endpoint can supply them.

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
