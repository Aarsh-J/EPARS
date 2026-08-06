# ePARS Policy Documents & pgvector RAG Setup

Policy chunks are embedded and stored in Postgres (`policy_chunks` table, via the
`vector` extension) in the same Supabase database as the rest of the app — not a
separate local vector store. See `../docs/SUPABASE.md` for the DB details.

## Contents
```
docs/
  01_task_assignment_policy.md        POL-TASK-001
  02_burnout_wellbeing_policy.md      POL-WELL-002
  03_team_formation_policy.md         POL-TEAM-003
  04_performance_evaluation_policy.md POL-PERF-004
  05_workflow_monitoring_policy.md    POL-WFLOW-005
  06_leave_availability_policy.md     POL-LEAVE-006
  07_promotion_career_sop.md          SOP-CAREER-007
  08_skill_development_policy.md      POL-SKILL-008

ingest_policies.py   — Run to (re-)embed all docs into the policy_chunks table
rag_query.py         — Import in your agent to query policies
requirements.txt     — Python dependencies
```

## Setup

Requires `DATABASE_URL` set in the root `.env` (see `../docs/SUPABASE.md`) and the
`vector` extension enabled on that Postgres instance — `ingest_policies.py` enables it
automatically if it isn't already.

```bash
pip install -r requirements.txt
python ingest_policies.py
```

Re-run `ingest_policies.py` any time a doc under `docs/` changes — it's idempotent
(upserts by chunk ID, removes stale/deleted chunks), so it's always safe to re-run.

## Usage in your Agent

```python
from rag_query import format_policy_context, policy_tool

# Direct call
context = format_policy_context("employee burnout score is 0.82, assign task?")
print(context)

# As a LangChain tool (add to your agent's tools list)
tools = [policy_tool, assign_task_tool, get_scores_tool, ...]
```
