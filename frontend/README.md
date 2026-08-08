# EPARS Frontend

React app (Vite + React 18 + react-router-dom, plain JS) for the Employee Performance
Analyser & Recommendation System. Talks to the backend purely over REST — see
[../plan.md](../plan.md) for the API contract and how this connects to the backend branch.

## Setup

```bash
npm install
cp .env.example .env   # then set VITE_API_URL to your backend's URL
npm run dev             # http://localhost:5173
```

## Scripts

- `npm run dev` — Vite dev server with hot reload
- `npm run build` — production build to `dist/`
- `npm run preview` — serve the production build locally

## Structure

```
src/
├── api/client.js          # fetch wrapper, reads VITE_API_URL
├── components/
│   ├── Layout.jsx          # topbar + content wrapper
│   └── Sidebar.jsx         # left nav
├── pages/
│   ├── Dashboard.jsx        # module grid (landing page)
│   └── Performance.jsx      # employee table, analyse flow, results panel
└── styles/style.css
```

## Environment variables

- `VITE_API_URL` — base URL of the backend API (e.g. `http://localhost:8000` in dev,
  the deployed Render URL in production). Read via `import.meta.env.VITE_API_URL` in
  `src/api/client.js`. Must live in `frontend/.env` (Vite loads env files relative to
  this folder, not the repo root).

## Adding a new module

Follow the `Performance` page as the template: one page component under `src/pages/`,
one or more functions in `src/api/client.js` calling the matching backend endpoint, and
a nav entry in `src/components/Sidebar.jsx`.
