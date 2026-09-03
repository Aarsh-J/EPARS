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

Or via Docker (see [`Dockerfile`](Dockerfile) — secrets are passed at runtime, not baked in):
```bash
docker build -t epars-backend .
docker run -p 8000:8000 --env-file .env epars-backend
```

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

### Git Commands
- `git branch` : List out existing branches
- `git branch <branch_name>` : Create ew branch from your current branch (but you dont move to the created branch)
- `git branch -d <name>` : delete branch
- `git branch -m <old-name> <new-name>` : rename branch
  
- `git checkout <branch_name>` : move to existing branch
- `git checkout -b <branch_name>` : create new branch (from your current branch) and open that 
- `git checkout --orphan <branch_name>` : create new branch with no parent

- `git pull <branch-name>` : pull branch to yor current (existing in your device/local)
- `git pull origin <branch-name>` : pull branch from git to yor current

- `git commit -m "[message]"` : commit
- `git push origin <branch-nae>` : pushes/merges your branch to specified one in git
# Employee Performance Analyzer and Recommendation System (EPARS)

To copy repo use this command: `git clone https://github.com/Aarsh-J/EPARS.git`

### Branch rules
- **develop** : Current working branch with our changes being pushed to it
- **prod** : Final Branch, develop will be merged when a feature is complete and tested
- **preprocessor** : Branch containing our Dataset generation code and our ML Model code (we will copy the complete ML model to main branches, tweeking will be done here)

#### Try using proper branch naming conventions and commit messages for clearity 

### Git Commands
- `git branch` : List out existing branches
- `git branch <branch_name>` : Create ew branch from your current branch (but you dont move to the created branch)
- `git branch -d <name>` : delete branch
- `git branch -m <old-name> <new-name>` : rename branch
  
- `git checkout <branch_name>` : move to existing branch
- `git checkout -b <branch_name>` : create new branch (from your current branch) and open that 
- `git checkout --orphan <branch_name>` : create new branch with no parent

- `git pull <branch-name>` : pull branch to yor current (existing in your device/local)
- `git pull origin <branch-name>` : pull branch from git to yor current

- `git commit -m "[message]"` : commit
- `git push origin <branch-nae>` : pushes/merges your branch to specified one in git
