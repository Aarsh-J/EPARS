# ePARS Agentic AI — Tool Functions & Burnout Monitoring

## Folder Structure
```
epars_agent/
├── .env.example              ← template only; the real .env lives in the project root
├── requirements.txt
├── setup_database.py         ← creates all 10 tables + loads CSVs
├── test_agent.py             ← 4 standard agent tests
├── burnout_monitor.py        ← burnout detection + LLM-reasoned rebalancing
├── agent/
│   ├── db.py                 ← PostgreSQL connection (single source of truth)
│   ├── tools.py               ← 10 tool functions + LangChain wrappers
│   ├── calendar_client.py     ← Google Calendar API wrapper (create/update/delete/list events)
│   ├── epars_agent.py         ← LangGraph ReAct agent
│   └── sa_key.json            ← Google service account key (gitignored — not committed)
└── (dataset/ lives at the project root, not here)
```

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure your database
```bash
cp .env.example ../.env
# Edit the root .env with your DATABASE_URL (Supabase connection string) and API keys
# (GROQ_API_KEY at minimum). See ../docs/SUPABASE.md for the shared team DB connection details.
```
Note: `.env` lives in the **project root**, not inside `epars_agent/` — every script here
finds it automatically by walking up directories (`python-dotenv`'s default behavior).

### 3. Set up Google Calendar integration
1. Go to Google Cloud Console (console.cloud.google.com) → create/select a project.
2. Enable the Google Calendar API (APIs & Services → Library → search "Google Calendar API").
3. Create a Service Account: APIs & Services → Credentials → Create Credentials → Service Account.
4. Generate a key for it: open the service account → Keys tab → Add Key → Create new key → JSON → download it, rename to `sa_key.json`, place in `epars_agent/agent/` (gitignored — **do not commit it**). Use the shared team key if using the shared team calendar.
5. Share the team Google Calendar with the service account: open the calendar → Settings → "Share with specific people" → paste the service account's email (`xxx@xxx.iam.gserviceaccount.com`) → permission: "Make changes to events".
6. Get the Calendar ID: Calendar Settings → "Integrate calendar" → copy the Calendar ID.
7. Open `agent/calendar_client.py` and set `CALENDAR_ID` to your calendar (or the shared team one).

Test it:
```bash
cd agent
python calendar_client.py
```

### 4. Add the Google Calendar columns to the shared DB (one-time, run once against Supabase)
```sql
ALTER TABLE task_assignments ADD COLUMN IF NOT EXISTS google_event_id TEXT;
ALTER TABLE schedules ADD COLUMN IF NOT EXISTS google_event_id TEXT;
```

### 5. Test your DB connection
```bash
cd agent
python db.py
# Should print: [OK] Connected to PostgreSQL: ...
```

### 6. Test all tool functions
```bash
cd agent
python tools.py EMP001 TSK0001
# Replace EMP001 and TSK0001 with real IDs from your database — tests all 10 tools
```

### 7. Load the dataset + run the full agent
```bash
python setup_database.py    # creates all 10 tables + loads all CSVs (from ../dataset/)
python test_agent.py        # 4 canned agent tests — requires GROQ_API_KEY in .env

# once that works, run any custom query:
python agent/epars_agent.py
```
See `../docs/SUPABASE.md` for common setup issues and their fixes.

---

## The 10 Tools

| # | Function | What it does | DB Tables |
|---|---|---|---|
| 1 | `get_employee_profile` | Full profile: skills, role, availability | employees |
| 2 | `get_employee_ml_scores` | Latest PEM + burnout scores | performance_reviews, burnout_indicators |
| 3 | `get_employee_workload` | Active tasks + hours + capacity | task_assignments, tasks, workload_history |
| 4 | `get_task_details` | Task requirements, deadline, priority | tasks |
| 5 | `find_available_employees` | Candidate employees by skill | employees |
| 6 | `assign_task` | **WRITES** assignment to DB (auto-generates `assignment_id`, supersedes prior active assignment for the task) | task_assignments, tasks, employees |
| 7 | `flag_burnout_alert` | **WRITES** burnout flag to DB | burnout_indicators, employees |
| 8 | `create_calendar_event` | **WRITES** a Google Calendar event for a task assignment, links `google_event_id` back to DB | task_assignments, Google Calendar |
| 9 | `reschedule_calendar_event` | **WRITES** — moves an existing calendar event to a new time | task_assignments, Google Calendar |
| 10 | `cancel_calendar_event` | **WRITES** — deletes a calendar event and clears `google_event_id` | task_assignments, Google Calendar |

Tools 1–5 are **read-only**. Tools 6–10 **write to the database and/or Google Calendar**.

---

## Burnout Monitoring Loop (`burnout_monitor.py`)

Standalone script — run manually or on a schedule (not agent-invoked):

```bash
python burnout_monitor.py
```

For every employee whose latest WBP burnout score is **≥ 0.70**, it:
1. Pulls their active (incomplete) tasks
2. Asks the LLM (Groq, `llama-3.3-70b-versatile`) to decide: **reschedule**, **reassign**, or **no action** — with reasoning, given the employee's burnout context, the task, and candidate employees for reassignment
3. Executes the decision via Tools 6, 8, 9, 10 above
4. Avoids double-booking by checking the target employee's real calendar availability before picking a new slot (`find_next_free_slot`)
5. Logs the intervention via `flag_burnout_alert`

---

## Next Step
Import `ALL_TOOLS` from `tools.py` into your LangChain ReAct agent:

```python
from agent.tools import ALL_TOOLS
from rag_query import policy_tool   # lives in ../epars_policies, see its README

all_agent_tools = ALL_TOOLS + [policy_tool]
```
