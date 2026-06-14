# ePARS Agentic AI — Step 2: Tool Functions

## Folder Structure
```
epars_agent/
├── .env.example          ← copy to .env and fill credentials
├── requirements.txt
└── agent/
    ├── db.py             ← PostgreSQL connection (single source of truth)
    └── tools.py          ← All 7 tool functions + LangChain wrappers
```

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure your database
```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials
```

### 3. Test your DB connection
```bash
cd agent
python db.py
# Should print: [OK] Connected to PostgreSQL: ...
```

### 4. Test all tool functions
```bash
cd agent
python tools.py EMP001 TASK0001
# Replace EMP001 and TASK0001 with real IDs from your database
```

---

## The 7 Tools

| # | Function | What it does | DB Tables |
|---|---|---|---|
| 1 | `get_employee_profile` | Full profile: skills, role, availability | employees |
| 2 | `get_employee_ml_scores` | Latest PEM + burnout scores | performance_reviews, burnout_indicators |
| 3 | `get_employee_workload` | Active tasks + hours + capacity | task_assignments, tasks, workload_history |
| 4 | `get_task_details` | Task requirements, deadline, priority | tasks |
| 5 | `find_available_employees` | Candidate employees by skill | employees |
| 6 | `assign_task` | **WRITES** assignment to DB | task_assignments, tasks, employees |
| 7 | `flag_burnout_alert` | **WRITES** burnout flag to DB | burnout_indicators, employees |

Tools 1–5 are **read-only**. Tools 6–7 **write to the database**.

---

## Next Step (Step 3)
Import `ALL_TOOLS` from `tools.py` into your LangChain ReAct agent:

```python
from agent.tools import ALL_TOOLS
from agent.rag_query import policy_tool   # from Step 1

all_agent_tools = ALL_TOOLS + [policy_tool]
```
