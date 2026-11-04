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

## `GET /api/team_formation/projects`

Lists projects with open tasks for the Team Formation selector. Each project row
includes `project_id`, `project_name`, `project_description`, `current_status`,
`team_size`, `priority`, `start_date`, `planned_end_date`,
`project_manager_id`, `required_skills`, and `open_task_count`. A missing team
size is returned as `null`; this endpoint does not update project data.

Team Formation data preparation is provided by
`modules/ml/team_formation_features.py`. Its open-task records include existing
`tasks.assigned_to` values rather than silently filtering assigned tasks.
Existing workload is read from open tasks' current `tasks.assigned_to` values
and estimated hours; assignment-history rows are not joined. The prepared
workload is the sum of original non-null estimates without an added time
horizon; tasks with a missing estimate are counted separately rather than
assigned an inferred duration.

## `PATCH /api/team_formation/projects/{project_id}`

Updates only the supplied project fields using existing `projects` columns.
Supported fields are `project_name`, `project_description`, `current_status`,
`team_size`, `priority`, `start_date`, `planned_end_date`,
`project_manager_id`, and `required_skills`. `team_size` must be a positive
integer; `project_name`, `current_status`, and `priority` cannot be blank.
`project_description`, dates, `project_manager_id`, and `required_skills` may be
`null`. A supplied manager ID must identify an employee, and the start date
cannot be after the planned end date. Unknown fields and empty update bodies are
rejected.

**Request**:
```json
{
  "project_name": "Updated project name",
  "project_description": "Updated description",
  "current_status": "Active",
  "team_size": 5,
  "priority": "High",
  "start_date": "2026-01-15",
  "planned_end_date": "2026-12-31",
  "project_manager_id": "EMP012",
  "required_skills": "Python, PostgreSQL"
}
```

Returns the updated project fields with HTTP `200`, returns `404` for an unknown
project, and `422` for invalid fields. This endpoint updates existing project
columns only and does not change the database schema.

## `GET /api/team_formation/recommend/{project_id}`

Returns up to `num_teams` recommendations, each with a unique
`team_member_ids` roster of exactly `projects.team_size` employees and one
eligible employee assignment for every selected open task. Multiple tasks may
be assigned to one roster member. `top_m` is passed to Model 3's existing
`recommend_top_n()` interface; all returned pairs are eligible, with no added
score threshold. The default candidate limit is 5; the API accepts 1 through 10.

Roster search visits at most 200,000 recursive nodes and stops earlier after
finding the requested number of rosters. It explores candidate employees in a
deterministic heuristic order and does not guarantee a globally optimal result.
If the search finishes within the node budget without a feasible roster, the
candidate graph is proven infeasible and the endpoint returns HTTP `422`. If
the node budget is exhausted before any feasible roster is found, the endpoint
returns HTTP `503` to indicate that feasibility is undetermined. If one or more
feasible rosters were found before exhaustion, those recommendations may be
returned with `search_mode` set to
`search_exhausted_with_feasible_rosters+greedy_allocation`.
If the optional `task_ids` query parameter is provided, it must identify the
complete set of open project tasks; a subset is rejected with HTTP `422`.

Workload comparison is lexicographic: when every roster member has a finite
positive weekly capacity, compare projected-hours/capacity spread first and
projected-hours spread second. If any capacity is missing or invalid, compare
projected-hours spread across the entire roster first, and compare utilization
spread only among members with valid capacities as a tie-breaker. No capacity
is imputed. Recommendations are read-only and do not persist task assignments
or team formations.

Each recommendation includes the six 0–100 scoring components in
`score_breakdown` and their fixed fractional weights in `score_weights`:
`task_fit` 0.45, `skill_coverage` 0.20, `experience_balance` 0.10,
`workload_balance` 0.10, `historical_cooccurrence` 0.05, and
`composition_typicality` 0.10. `team_score` is their weighted sum, computed
from the displayed one-decimal component values. If any component cannot be
calculated from available data, that component is `null`, its name appears in
`score_unavailable_components`, and `team_score` is `null`; weights are never
renormalized. The former `past_overlap` breakdown key is replaced by
`historical_cooccurrence`; the latter measures recorded team-member
co-occurrence only, not successful collaboration. Workload balance measures
projected workload fairness, not burnout. Projected hours are current open-task
hours across projects, less known hours for selected-project tasks being
reallocated, plus the recommended assignments. With valid capacity for every
member, projected load is hours divided by weekly capacity; otherwise raw
projected hours are used for every member. The score is `100 * min(load) /
max(load)`, or 100 when every load is zero. It is unavailable if an estimate
or existing workload is missing. Skill coverage is unavailable when the
selected tasks provide no required skills or a roster member's skill profile
is missing; task fit is unavailable if any assigned candidate score is missing;
experience balance is unavailable if seniority data is missing; historical
co-occurrence is unavailable when there are fewer than two roster members or
its source is unavailable; composition typicality is unavailable if a roster
member is missing profile inputs used by the existing composition features.

Composition typicality is an Isolation Forest advisory about resemblance to
historical team compositions, not team quality, compatibility, or predicted
friction.

## `POST /api/team_formation/confirm/{project_id}`

Recommendations are temporary. This endpoint persists only after an explicit
manager confirmation and requires the selected `team_lead_id` to be in the
recommended roster. Submit the full recommendation object returned by the
recommendation endpoint; scoring fields are accepted for round-tripping but
are ignored for persistence.

**Request**:
```json
{
  "team_lead_id": "EMP001",
  "recommendation": {
    "project_id": "PRJ001",
    "project_status": "Active",
    "candidate_limit": 5,
    "team_size": 2,
    "team_member_ids": ["EMP001", "EMP002"],
    "assignments": [
      {
        "task_id": "TSK001",
        "task_status": "Not Started",
        "task_assigned_to": null,
        "task_estimated_hours": 3,
        "task_required_skills": "python",
        "employee_id": "EMP001"
      },
      {
        "task_id": "TSK002",
        "task_status": "In Progress",
        "task_assigned_to": "EMP001",
        "task_estimated_hours": 4,
        "task_required_skills": "sql",
        "employee_id": "EMP002"
      }
    ]
  }
}
```

The example omits nonessential recommendation fields such as score details; a
valid request must include the complete recommendation object and every
currently open project task exactly once, with at least one task per roster
member. The backend checks the project and task
snapshot, authoritative `projects.team_size`, employee existence, lead
membership, and each assignment against fresh Model 3 candidates at the
recommendation's `candidate_limit`. Stale task/project state or changed
eligibility returns HTTP `409`; malformed or infeasible roster structure
returns HTTP `422`; unknown projects return HTTP `404`; repeated active AI
formation for the same project/roster/lead returns HTTP `409`.

On success, HTTP `201` returns `confirmed`, `team_id`, `project_id`,
authoritative `team_size`, `team_lead_id`, `member_ids`, and task-to-
`assignment_ids`. Since the existing schema stores the lead separately,
`member_ids` excludes the lead while `team_size` includes it. `tasks.assigned_to`,
assignment history, and the `team_formations` row are written in one
serializable transaction. Any failure rolls back the full confirmation.
`projects.team_size` is never updated. Distinct formations for a project are
supported by the existing historical data, but confirmation is rejected with
HTTP `409` while that project already has any active AI-Recommended formation,
regardless of whether the new roster or lead differs. No schema change is
required.
The existing schema has no normalized team-member table or team-to-task
association: roster members (excluding the lead) are stored as comma-separated
`team_formations.member_ids`, while task assignments reference only task,
employee, and project IDs. The confirmation response returns assignment IDs,
but the persisted schema cannot directly link those assignment rows to the
specific formation row.

**Response** `201`:
```json
{
  "confirmed": true,
  "team_id": "TEAM1001",
  "project_id": "PRJ001",
  "team_size": 2,
  "team_lead_id": "EMP001",
  "member_ids": ["EMP002"],
  "assignment_ids": {
    "TSK001": "ASG1001",
    "TSK002": "ASG1002"
  }
}
```

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

## Kanban task persistence

The board continues to use `GET /api/task_assignment/board`,
`GET /api/task_assignment/board_projects`, and
`GET /api/task_assignment/board_employees` for its existing filters and data.

### `POST /api/task_assignment/tasks`

Creates a task in PostgreSQL. `task_name` is required. Supported optional fields are
`task_description`, `project_id`, `priority`, `status`, `assigned_to`, `story_points`,
`due_date`, and `required_skills`. Project and employee IDs are checked against their
tables. IDs use the existing `TSK<number>` format and retry on primary-key collisions.

**Response** `201`: `{ "task": { ...board task fields... } }`.

### `PUT /api/task_assignment/tasks/{task_id}`

Partially updates only the supported fields listed above, except that status changes use
the dedicated endpoint below. Omitted fields are left unchanged. Unsupported fields are
rejected. Assignment changes are performed in the same transaction as the task update.

**Response** `200`: `{ "task": { ...board task fields... } }`.

### `POST /api/task_assignment/tasks/{task_id}/status`

Accepts `{ "status": "Not Started" | "In Progress" | "In Review" | "Blocked" | "Completed" }`.
These are the five task statuses present in the live database. `Cancelled` is not a
supported task status and is not mapped to another value. Completing sets
`completion_percentage` to 100 and records `actual_completion_date`; reopening clears the
date and resets a completion-generated 100% to 0 while preserving other progress values.

**Response** `200`: `{ "status": "success", "task": { ...board task fields... } }`.

### `POST /api/task_assignment/tasks/{task_id}/assign`

Accepts `{ "employee_id": "<employee id>" }`. The task update and new
`task_assignments` history record are committed together. Repeating the current assignment
does not create a duplicate active record. To unassign, send `{ "employee_id": null }`;
this clears `tasks.assigned_to` and leaves assignment history unchanged.

**Response** `200`: `{ "task": { ...board task fields... }, "assignment": { ... } | null }`.

### `DELETE /api/task_assignment/tasks/{task_id}`

Deletes only tasks with no known related rows. It returns `409` if assignment history,
scheduled events, feedback, reassignment recommendations, child tasks, or task dependency
references exist; those records are not silently deleted.

**Response** `200`: `{ "deleted": true, "task_id": "TSK..." }`.

Task persistence uses the existing PostgreSQL schema; no migration is required.

---

## Not yet built

- Team-formation module (Model 4) — no trained pickle exists yet with an acceptable accuracy
  (the one attempt, on `dataset-branch`, has negative test R² per its own docs). Deferred until
  a properly trained model exists; follow `task_assignment` as the template once it does.
- Burnout monitor (`src/epars_agent/agent/burnout_monitor.py`) is still a standalone
  cron/manual script (`python burnout_monitor.py`), not exposed over HTTP. If the frontend
  needs to trigger it or read its results, that's a new route to add here.
