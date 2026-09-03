"""
ePARS — Agentic AI Layer (Step 3)
===================================
ReAct agent using LangGraph (compatible with langchain >= 0.2, langgraph >= 1.0)
Combines 7 PostgreSQL tools + 1 RAG policy tool + GPT-4o
"""

import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Imports ────────────────────────────────────────────────────────────────────
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from tools import (
    get_employee_profile,
    get_employee_ml_scores,
    get_employee_workload,
    get_task_details,
    find_available_employees,
    assign_task,
    flag_burnout_alert,
    _serialize,
)

# ── Policy RAG (pgvector, lives in epars_policies/) ────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "epars_policies"))
from rag_query import format_policy_context

# ── Helpers ────────────────────────────────────────────────────────────────────
def _j(result) -> str:
    return json.dumps(result, indent=2, default=_serialize)


# ── Tool definitions (LangGraph uses @tool decorator) ─────────────────────────

@tool
def tool_get_employee_profile(employee_id: str) -> str:
    """
    Fetches the full profile of an employee.
    Input: employee_id as a plain string e.g. EMP001.
    Returns: name, role, department, skills, availability, capacity, burnout risk, performance history.
    """
    return _j(get_employee_profile(employee_id.strip()))


@tool
def tool_get_employee_ml_scores(employee_id: str) -> str:
    """
    Fetches the latest ML model outputs for an employee.
    Input: employee_id as a plain string e.g. EMP001.
    Returns: pem_score (0-100), performance_rating, burnout_score (0.0-1.0),
    burnout_category, burnout_trend, intervention_urgency.
    ALWAYS call this before assigning tasks or flagging burnout.
    """
    return _j(get_employee_ml_scores(employee_id.strip()))


@tool
def tool_get_employee_workload(employee_id: str) -> str:
    """
    Fetches current workload of an employee.
    Input: employee_id as a plain string e.g. EMP001.
    Returns: active_task_count, total_estimated_hours_remaining,
    weekly_capacity_hours, capacity_used_percent.
    Call this before assigning tasks to check available capacity.
    """
    return _j(get_employee_workload(employee_id.strip()))


@tool
def tool_get_task_details(task_id: str) -> str:
    """
    Fetches full details of a task.
    Input: task_id as a plain string e.g. TSK0001.
    Returns: required_skills, priority, complexity, estimated_hours, due_date, status, assigned_to.
    Always call this first when asked to assign a task.
    """
    return _j(get_task_details(task_id.strip()))


@tool
def tool_find_available_employees(required_skills: str, required_role: str = "", required_seniority: str = "") -> str:
    """
    Finds available employees matching required skills.
    required_skills: comma-separated skills e.g. 'Python,Django'
    required_role: optional role filter e.g. 'Software Engineer'
    required_seniority: optional seniority filter e.g. 'Senior'
    Returns up to 5 candidates ranked by performance score.
    """
    return _j(find_available_employees(
        required_skills=required_skills,
        required_role=required_role,
        required_seniority=required_seniority,
    ))


@tool
def tool_assign_task(task_id: str, employee_id: str, skill_match_score: float = 0.0) -> str:
    """
    Assigns a task to an employee and writes it to the database.
    task_id: e.g. TSK0001
    employee_id: e.g. EMP001
    skill_match_score: 0-100 score of how well skills match
    ONLY call this AFTER checking ML scores, workload, and HR policy.
    Returns success status and assignment_id.
    """
    return _j(assign_task(
        task_id=task_id.strip(),
        employee_id=employee_id.strip(),
        assignment_method="agentic_ai",
        skill_match_score=float(skill_match_score),
    ))


@tool
def tool_flag_burnout_alert(employee_id: str, burnout_score: float, urgency: str, recommended_action: str) -> str:
    """
    Logs a burnout intervention alert for an employee.
    employee_id: e.g. EMP001
    burnout_score: current WBP score as a float e.g. 0.75
    urgency: one of Low, Medium, High, Critical
    recommended_action: free text recommendation e.g. 'Reduce workload and schedule 1-1'
    Call this when burnout_score >= 0.70.
    """
    return _j(flag_burnout_alert(
        employee_id=employee_id.strip(),
        burnout_score=float(burnout_score),
        urgency=urgency.strip(),
        recommended_action=recommended_action.strip(),
    ))


@tool
def tool_retrieve_hr_policy(query: str) -> str:
    """
    Retrieves relevant HR policies from the organizational policy database.
    Input: a natural language description of the decision you are making.
    Examples: 'rules for assigning P1 tasks',
              'what to do when burnout score is above 0.7',
              'team lead selection criteria'
    ALWAYS call this before making any final recommendation or taking any action.
    """
    try:
        return format_policy_context(query, n_results=3)
    except Exception as e:
        return f"Policy retrieval unavailable: {e}. Use general HR best practices."


# ── All tools collected ────────────────────────────────────────────────────────
TOOLS = [
    tool_get_employee_profile,
    tool_get_employee_ml_scores,
    tool_get_employee_workload,
    tool_get_task_details,
    tool_find_available_employees,
    tool_assign_task,
    tool_flag_burnout_alert,
    tool_retrieve_hr_policy,
]

# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are the ePARS Agentic AI — an intelligent HR and resource management assistant. You help managers make data-driven decisions about task assignment, team formation, burnout intervention, and workload management.

DECISION RULES — follow these strictly:

FOR TASK ASSIGNMENT:
1. Call tool_get_task_details to understand what the task needs
2. Call tool_find_available_employees with the required skills
3. For each top candidate, call tool_get_employee_ml_scores and tool_get_employee_workload
4. Call tool_retrieve_hr_policy describing the task priority and situation
5. Apply policy rules to select the best candidate
6. Call tool_assign_task only if all checks pass
7. State who you assigned, why, and which policy rules applied

FOR BURNOUT RESPONSE:
1. Call tool_get_employee_ml_scores to get current burnout score
2. Call tool_get_employee_workload to understand current load
3. Call tool_retrieve_hr_policy with the burnout score context
4. If burnout_score >= 0.70, call tool_flag_burnout_alert
5. State the score, the policy threshold breached, and recommended actions

FOR WORKLOAD CHECK:
1. Call tool_get_employee_profile for context
2. Call tool_get_employee_workload for current load
3. Call tool_get_employee_ml_scores for burnout risk
4. Summarise capacity, risk level, and any recommendations

FOR TEAM FORMATION:
1. Call tool_find_available_employees for each required skill area
2. Call tool_get_employee_ml_scores and tool_get_employee_workload for top candidates
3. Call tool_retrieve_hr_policy with 'team formation rules'
4. Propose the team with roles, justify each member

ALWAYS:
- Retrieve HR policy before making any final recommendation
- State which policy document (doc_id) informed your decision
- If an employee is ineligible, clearly state why
- Be concise and structured in your final response"""


# ── Build agent (singleton) ────────────────────────────────────────────────────
_agent = None

def build_agent():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not found. Add it to your .env file:\n"
            "GROQ_API_KEY=gsk_your-key-here"
        )

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=api_key,
        temperature=0,
        max_tokens=4096,
    )

    agent = create_react_agent(
        model=llm,
        tools=TOOLS,
        prompt=SYSTEM_PROMPT,
    )
    return agent


def run_agent(query: str) -> dict:
    """
    Run the ePARS agent on a natural language query.

    Args:
        query: e.g. "Assign task TSK0042 to the best available employee"

    Returns:
        {"input": query, "output": final answer, "steps": list of tool calls}
    """
    global _agent
    if _agent is None:
        print("[INFO] Building ePARS agent...")
        _agent = build_agent()
        print("[INFO] Agent ready.\n")

    result = _agent.invoke({"messages": [HumanMessage(content=query)]})

    # Extract final answer — last AI message
    messages = result.get("messages", [])
    output = ""
    steps = []

    for msg in messages:
        msg_type = type(msg).__name__
        if msg_type == "AIMessage":
            if msg.content:
                output = msg.content
        elif msg_type == "ToolMessage":
            steps.append({
                "tool": msg.name,
                "output": msg.content[:300] + "..." if len(msg.content) > 300 else msg.content,
            })

    return {
        "input":  query,
        "output": output,
        "steps":  steps,
    }


# ── CLI interactive mode ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("ePARS Agent — Interactive Mode")
    print("=" * 60)
    print("Example queries:")
    print("  Assign task TSK0010 to the best available employee")
    print("  Check burnout status of employee EMP042")
    print("  What is the workload of EMP001?")
    print("  Find the best Python developer for a high priority task")
    print("\nType 'quit' to exit.\n")

    while True:
        try:
            query = input("Query> ").strip()
            if query.lower() in ("quit", "exit", "q"):
                break
            if not query:
                continue
            result = run_agent(query)
            print("\n" + "=" * 60)
            print("FINAL ANSWER:")
            print("=" * 60)
            print(result["output"])
            print(f"\n[Used {len(result['steps'])} tool calls]")
            print()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[ERROR] {e}\n")
