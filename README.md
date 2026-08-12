# EPARS Frontend

React app (Vite + React 18 + react-router-dom, plain JS) for the Employee Performance
Analyser & Recommendation System. Talks to the backend purely over REST — see
[plan.md](plan.md) for the API contract and how this connects to the backend branch.

To copy repo use this command: `git clone https://github.com/Aarsh-J/EPARS.git`

## This branch (`dev-frontend`)

This branch holds the **frontend** — it no longer contains any Python/Flask code or ML
model code (those live on other branches, see below).

- **Migration history, API contract the backend must implement, deployment plan:**
  see [plan.md](plan.md)

### Other branches

- **`dev-backend`** : the Python backend — LangGraph agent (`epars_agent/`) and the
  RAG/HR-policy subsystem (`epars_policies/`), backed by Supabase Postgres.
- **`preprocessor`** : dataset generation code and ML model training/artifacts.
- **`main`** / **`production`** : integration branches — features get merged in once
  built and tested on their own branch.

## Setup

```bash
npm install
cp .env.example .env   # then set VITE_API_URL to your backend's URL
npm run dev             # http://localhost:5173
```

### Run / Stop

```powershell
npm run dev             # starts the dev server at http://localhost:5173
```
Stop: `Ctrl+C` in the terminal running it. If it was started in the background and you lost
the terminal, find and kill it by port:
```powershell
netstat -ano | findstr :5173       # note the PID in the last column
taskkill /F /PID <pid>
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
  `src/api/client.js`. Must live in this repo's root `.env` (Vite loads env files
  relative to the project root).

## Adding a new module

Follow the `Performance` page as the template: one page component under `src/pages/`,
one or more functions in `src/api/client.js` calling the matching backend endpoint, and
a nav entry in `src/components/Sidebar.jsx`.

### Git Commands
- `git branch` : List out existing branches
- `git branch <branch_name>` : Create new branch from your current branch (but you dont move to the created branch)
- `git branch -d <name>` : delete branch
- `git branch -m <old-name> <new-name>` : rename branch

- `git checkout <branch_name>` : move to existing branch
- `git checkout -b <branch_name>` : create new branch (from your current branch) and open that
- `git checkout --orphan <branch_name>` : create new branch with no parent

- `git pull <branch-name>` : pull branch to your current (existing in your device/local)
- `git pull origin <branch-name>` : pull branch from git to your current

- `git commit -m "[message]"` : commit
- `git push origin <branch-name>` : pushes/merges your branch to specified one in git
