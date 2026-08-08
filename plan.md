# EPARS Frontend (`ui-changes` branch) — Migration & Integration Plan

## Where we came from

This branch used to be a Flask app (`code/app.py` + Jinja templates in `code/templates/` +
`code/static/`) that directly imported Python modules (`modules.performance.model`,
`modules.performance.routes`) to query pandas dataframes and render server-side HTML.
Those modules never existed in this branch's working tree (only `app.py`/`diagnose.py`/
`test_flask_route.py` referencing them did) — the actual scoring logic (Model2_Performance,
Model3_TaskAssignment, Model4_TeamFormation) lives on other branches (`preprocessor`,
`ui-changes`'s sibling history, etc.), and the live agent/API backend now lives on
`dev-backend` (`epars_agent/`, LangGraph + FastAPI-to-be). So the old Flask frontend was
calling into backend code that no longer sits next to it — it was broken by construction,
not just outdated.

**Decision:** stop coupling frontend and backend in one Python process. Frontend becomes a
pure API client; backend (wherever it ends up running) exposes plain JSON endpoints.

## What's done

Converted the Flask/Jinja UI to a React app in [frontend/](frontend/) (Vite + React 18 +
react-router-dom, plain JS, no TypeScript — matches the original app's plain-JS style):

- [frontend/src/components/Sidebar.jsx](frontend/src/components/Sidebar.jsx),
  [Layout.jsx](frontend/src/components/Layout.jsx) — from `base.html`'s sidebar/topbar chrome.
- [frontend/src/pages/Dashboard.jsx](frontend/src/pages/Dashboard.jsx) — the module grid
  (`dashboard.html`), same 4 modules (Performance active, 3 "coming soon").
- [frontend/src/pages/Performance.jsx](frontend/src/pages/Performance.jsx) — employee
  table + search + analyse flow + results panel (score circle, cluster breakdown,
  sub-scores, review history), converted from `performance.html`'s server-rendered table +
  inline `<script>` DOM manipulation into React state/hooks. Same visual design, same CSS
  (ported verbatim to [frontend/src/styles/style.css](frontend/src/styles/style.css)).
- [frontend/src/api/client.js](frontend/src/api/client.js) — a small fetch wrapper reading
  the backend base URL from `VITE_API_URL` (see `.env.example`), with two calls:
  `getEmployees()` and `analyseEmployee(id, reviewId)`.
- Old Flask files (`code/app.py`, `code/templates/`, `code/static/`, `code/diagnose.py`,
  `code/test_flask_route.py`, `code/performance_page.html`) removed — they were broken
  (imported non-existent modules) and are fully superseded.
- Verified: `npm install`, `npm run build`, and `npm run dev` all work (dev server serves
  the app correctly on port 5173).

**Improvement made along the way:** the old vanilla-JS `analyseEmployee()`/`renderResult()`
functions mutated the DOM by ID lookups scattered across the file. That's now local
component state — the loading spinner, error state, and rendered result are all derived
from `analysing` / `analyseError` / `result` state in `Performance.jsx`, not manual
`classList.add("hidden")` toggling. Behavior is identical; the code is just less fragile.

## API contract — now real, on `dev-backend`

**Update:** the backend (`dev-backend` branch, checked out as a separate worktree at
`../backend`) now has a working FastAPI layer (`modules/main.py`) exposing
`GET /api/performance/employees` and `POST /api/performance/analyse`, plus
`POST /api/agent/query` (passthrough to the LangGraph agent). Full request/response shapes
and which backend function backs each route are documented in
[API-Contracts.md](API-Contracts.md) — copied verbatim from `backend/docs/API-Contracts.md`;
**re-copy it here whenever the backend contract changes**, until the two branches merge.

**⚠️ Breaking change for this frontend:** `/api/performance/analyse` does **not** return
`breakdown` (technical/behavioral/quality/productivity) or `sub_scores` (10 named 0–10
scores) — that data would come from `Model2_Performance`, which isn't part of `dev-backend`.
[frontend/src/pages/Performance.jsx](frontend/src/pages/Performance.jsx)'s `ResultContent`
component still renders those sections and will need updating to drop them (or render a
"not available yet" placeholder) — tracked as step 1 below. Everything else
(`predicted_score`, `rating_label`/`rating_color`, `all_reviews`) matches what the frontend
already expects.

## How frontend connects to backend

- **Local dev:** run the backend on `http://localhost:8000` (or wherever), set
  `frontend/.env` → `VITE_API_URL=http://localhost:8000`, `npm run dev` in `frontend/`.
  No proxy needed — the fetch client reads the URL directly; backend must allow CORS from
  `http://localhost:5173` in dev.
- **Production:** per the existing deployment plan (Supabase + Render for backend), deploy
  `frontend/` to Vercel (or Render static site) as a plain static build (`npm run build` →
  `dist/`), and set `VITE_API_URL` in Vercel's env vars to the deployed backend's Render URL.
  No Python runtime needed for the frontend anymore — this un-blocks Vercel, which couldn't
  host the old Flask app.

## Next steps, in order

1. **Update `Performance.jsx`** to stop rendering the `breakdown`/`sub_scores` sections
   (cluster bars, sub-score grid) in `ResultContent` since the real API doesn't return them
   — either remove those sections or show a "not available yet" placeholder until
   `Model2_Performance` is ported into `dev-backend`.
2. Point `frontend/.env`'s `VITE_API_URL` at the backend (`http://localhost:8000` when
   running `uvicorn modules.main:app` locally from the `backend` worktree) and verify the
   Performance page end-to-end — employee list loads, Analyse button returns real scores.
3. CORS is already enabled backend-side for `http://localhost:5173` (via `FRONTEND_ORIGIN`
   env var, see `API-Contracts.md`) — update that env var when deploying the frontend
   somewhere other than localhost.
4. Add the other three modules (Task Assignment, Workload & Risk, Team Formation) the same
   way: one React page + matching backend route each (`modules/<name>/routes.py` on the
   backend side), following the Performance module as the template on both sides.
5. Wire up CI (`.github/workflows/`) to run `npm run build` on this branch so a broken
   frontend build fails fast, same idea as backend tests on `dev-backend`.

## Verification

- `cd frontend && npm install && npm run build` — must succeed (already verified).
- `cd frontend && npm run dev` — open `http://localhost:5173`, confirm Dashboard renders,
  clicking "Performance Evaluation" navigates to `/performance`. The employee table will be
  empty and show a fetch error until the backend is running and `VITE_API_URL` points at it
  (step 2 above) — that's expected, not a bug in the frontend.
- Cross-check `frontend/API-Contracts.md` against `backend/docs/API-Contracts.md` — they
  should be identical; if not, re-copy from the backend worktree.
