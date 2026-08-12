# Employee Performance Analyzer and Recommendation System (EPARS)

To copy repo use this command: `git clone https://github.com/Aarsh-J/EPARS.git`

### Layout

```
backend/
├── src/                    # pure functions + CLI-testable code — no API/HTTP logic here
│   ├── epars_agent/         # LangGraph agent, DB tools, burnout monitor, calendar client
│   └── epars_policies/      # RAG policy embedding + query (pgvector)
├── modules/                # FastAPI layer — HTTP routes that call into src/
│   ├── main.py               # entrypoint: uvicorn modules.main:app
│   ├── performance/routes.py
│   └── agent/routes.py
├── dataset/                 # seed CSVs loaded into Supabase
└── docs/
```

`src/epars_agent` and `src/epars_policies` stay independently testable from the terminal
exactly as before (`python agent/db.py`, `python agent/tools.py EMP001 TASK0001`, etc.) — see
each package's own README. `modules/` is the only place HTTP/API logic lives; run it with:

```bash
pip install -r requirements.txt
uvicorn modules.main:app --reload --port 8000
```

### Run (local dev, Windows)

```powershell
# from the repo root, one-time: python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn modules.main:app --reload --port 8000    # http://localhost:8000, docs at /docs
```

Stop: `Ctrl+C` in the terminal running uvicorn. If it was started in the background and
you lost the terminal, find and kill it by port:
```powershell
netstat -ano | findstr :8000       # note the PID in the last column
taskkill /F /PID <pid>
```

Or via Docker (see [`Dockerfile`](Dockerfile) — secrets are passed at runtime, not baked in):
```bash
docker build -t epars-backend .
docker run -p 8000:8000 --env-file .env epars-backend
```
Stop: `docker stop <container_id>` (or `docker compose down` if using `docker-compose.yml`).

### Documentation
- [`docs/API-Contracts.md`](docs/API-Contracts.md) — every API route: request/response shape, which `src/` function backs it, known gaps
- [`docs/instructions.md`](docs/instructions.md) — day-to-day setup/run commands
- [`docs/SUPABASE.md`](docs/SUPABASE.md) — shared DB details, keeping it running, common bugs & fixes
- [`docs/plan.md`](docs/plan.md) — deployment plan (DB, backend, frontend hosting)
- [`docs/dataset_schema.md`](docs/dataset_schema.md) — full dataset/table schema spec
- [`src/epars_agent/README.md`](src/epars_agent/README.md) — backend tools, Google Calendar & burnout monitor setup
- [`src/epars_policies/README.md`](src/epars_policies/README.md) — RAG policy embedding setup

### Branch rules
- **develop** : Current working branch with our changes being pushed to it
- **prod** : Final Branch, develop will be merged when a feature is complete and tested
- **preprocessor** : Branch containing our Dataset generation code and our ML Model code (we will copy the complete ML model to main branches, tweeking will be done here)

#### Try using proper branch naming conventions and commit messages for clearity 
