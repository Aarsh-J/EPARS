> These are the quick day-to-day commands. For full setup, the shared Supabase DB, and
> troubleshooting, see [`SUPABASE.md`](SUPABASE.md). For the deployment plan, see [`plan.md`](plan.md).

### 1. Install dependencies
```bash
# from the worktree root — installs src/epars_agent + src/epars_policies + the API layer (modules/) in one go
pip install -r requirements.txt
```

### 2. Configure `.env`
Create a single `.env` in the **project root** (not inside `src/epars_agent/` or
`src/epars_policies/` — every script finds it automatically by walking up directories):
```
DATABASE_URL=postgresql://postgres:<password>@<supabase-host>:5432/postgres
GROQ_API_KEY=gsk_...
ANTHROPIC_API_KEY=sk-ant-...
```
Get the real `DATABASE_URL` from whoever set up the shared Supabase project (see
`SUPABASE.md`) — don't create your own local Postgres instance, everyone shares one DB.

### 3. Load the dataset (one-time, already done for the shared DB)
```bash
cd path/to/src/epars_agent
python setup_database.py
# Creates all 10 tables and loads all 10 CSVs from <worktree_root>/dataset/
```

### 4. Embed the policy docs into pgvector (one-time, already done for the shared DB)
```bash
cd path/to/src/epars_policies
python ingest_policies.py
# Safe to re-run any time a doc under epars_policies/docs/ changes
```

### 5. Verify everything connects
```bash
python src/epars_agent/agent/db.py            # should print: [OK] Connected to PostgreSQL
python src/epars_policies/rag_query.py        # runs sample policy queries
cd src/epars_agent && python agent/tools.py EMP001 TSK0001   # use real IDs from your DB
```

### 6. Set up Google Calendar integration (needed for tools 8-10 + burnout_monitor.py)
Full steps (service account, sharing the calendar, `CALENDAR_ID`) are in
[`../src/epars_agent/README.md`](../src/epars_agent/README.md#3-set-up-google-calendar-integration).
One-time DB migration this requires, run once against the shared Supabase DB:
```sql
ALTER TABLE task_assignments ADD COLUMN IF NOT EXISTS google_event_id TEXT;
ALTER TABLE schedules ADD COLUMN IF NOT EXISTS google_event_id TEXT;
```

### 7. Run the agent
```bash
cd path/to/src/epars_agent
python test_agent.py       # 4 standard test queries (needs GROQ_API_KEY)

# once that works, run any custom query:
python agent/epars_agent.py
```

### 8. Run the burnout monitor
```bash
cd path/to/src/epars_agent
python burnout_monitor.py
# For every employee with burnout score >= 0.70: LLM decides reschedule/reassign/no
# action, and executes it via the calendar + assignment tools. See
# src/epars_agent/README.md for details.
```

### 9. Run the API layer (serves the frontend)
```bash
# from the worktree root
uvicorn modules.main:app --reload --port 8000
```
Everything above (steps 1-8) is pure functions/CLI scripts — nothing there talks HTTP.
`modules/` is the only place that does; every route in it calls straight into the functions
you just tested in steps 5/7/8. See [`API-Contracts.md`](API-Contracts.md) for the full
route reference.

### Folder Structure
```
src/
├── epars_agent/
│   ├── .env.example        ← template only; the real .env lives in the project root
│   ├── test_agent.py
│   ├── setup_database.py
│   ├── burnout_monitor.py
│   ├── requirements.txt
│   └── agent/
│       ├── epars_agent.py
│       ├── db.py
│       ├── tools.py               ← 10 tools (7 + 3 Google Calendar)
│       ├── calendar_client.py
│       └── sa_key.json            ← gitignored, not committed
└── epars_policies/
    ├── docs/                ← the 8 policy markdown files
    ├── ingest_policies.py
    ├── rag_query.py
    └── requirements.txt

modules/                       ← FastAPI layer, calls into src/ — see API-Contracts.md
├── main.py
├── performance/routes.py
└── agent/routes.py

dataset/                       ← the 10 seed CSVs (project root, not inside src/)
```
