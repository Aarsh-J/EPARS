# ePARS Policy Documents & ChromaDB RAG Setup

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

ingest_policies.py   — Run once to load all docs into ChromaDB
rag_query.py         — Import in your agent to query policies
requirements.txt     — Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
python ingest_policies.py
```

## Usage in your Agent

```python
from rag_query import format_policy_context, policy_tool

# Direct call
context = format_policy_context("employee burnout score is 0.82, assign task?")
print(context)

# As a LangChain tool (add to your agent's tools list)
tools = [policy_tool, assign_task_tool, get_scores_tool, ...]
```
