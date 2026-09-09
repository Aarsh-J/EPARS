"""
burnout_monitor.py
====================================
ePARS — Step 6: Burnout Monitoring Loop

Standalone script (not agent-invoked). Run manually or on a schedule
(Task Scheduler / cron). For every employee whose latest WBP burnout
score is >= 0.70, this:

    1. Pulls their active (incomplete) tasks
    2. For each task, asks the LLM (Groq) to decide: reschedule the
       task's calendar event, reassign it to a lower-burnout candidate,
       or take no action — with reasoning.
    3. Executes the decision via the existing tool functions in tools.py
    4. Logs a burnout alert via flag_burnout_alert

Run:
    python burnout_monitor.py
"""

import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

from db import get_connection
from calendar_client import list_events
from tools import (
    get_task_details,
    get_employee_workload,
    find_available_employees,
    create_calendar_event,
    reschedule_calendar_event,
    cancel_calendar_event,
    assign_task,
    flag_burnout_alert,
    _to_dict,
    _to_list,
)

load_dotenv()

BURNOUT_THRESHOLD = 0.70
RESCHEDULE_LOOKAHEAD_DAYS = 14
DEFAULT_EVENT_DURATION_HOURS = 2

try:
    from langchain_groq import ChatGroq
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY"),
    )
except ImportError:
    llm = None
    print("[WARN] langchain_groq not installed. Run: pip install langchain-groq")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Find high-burnout employees
# ══════════════════════════════════════════════════════════════════════════════

def get_high_burnout_employees() -> list:
    """
    Returns employees whose latest burnout_indicators row shows
    overall_burnout_risk / 100.0 >= BURNOUT_THRESHOLD.
    """
    sql = """
        SELECT DISTINCT ON (bi.employee_id)
            bi.employee_id,
            e.first_name || ' ' || e.last_name AS full_name,
            bi.overall_burnout_risk / 100.0     AS burnout_score,
            bi.burnout_category,
            bi.burnout_trend,
            bi.assessment_date
        FROM burnout_indicators bi
        JOIN employees e ON e.employee_id = bi.employee_id
        WHERE bi.overall_burnout_risk / 100.0 >= %s
        ORDER BY bi.employee_id, bi.assessment_date DESC
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (BURNOUT_THRESHOLD,))
                rows = cur.fetchall()
                return _to_list(rows)
    except Exception as e:
        print(f"[ERROR] get_high_burnout_employees: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Get an employee's active tasks (with assignment + calendar info)
# ══════════════════════════════════════════════════════════════════════════════

def get_active_tasks_for_employee(employee_id: str) -> list:
    """
    Returns active (not Completed/Cancelled) tasks currently assigned to
    this employee, including their google_event_id if one exists.
    """
    sql = """
        SELECT
            t.task_id,
            t.task_type,
            t.priority,
            t.complexity,
            t.estimated_hours,
            t.due_date,
            t.status,
            t.completion_percentage,
            ta.google_event_id,
            ta.assignment_id
        FROM task_assignments ta
        JOIN tasks t ON t.task_id = ta.task_id
        WHERE ta.employee_id = %s
          AND t.status NOT IN ('Completed', 'Cancelled')
          AND ta.completion_status NOT IN ('Completed', 'Cancelled', 'Reassigned')
        ORDER BY t.due_date ASC NULLS LAST
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (employee_id,))
                rows = cur.fetchall()
                return _to_list(rows)
    except Exception as e:
        print(f"[ERROR] get_active_tasks_for_employee: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — LLM decision: reschedule / reassign / none
# ══════════════════════════════════════════════════════════════════════════════

def decide_action_for_task(employee: dict, task: dict, candidates: list) -> dict:
    """
    Asks the LLM to decide what to do about one task for one high-burnout
    employee. Returns a dict like:

        {"action": "reschedule", "new_start_time": "...", "new_end_time": "...", "reasoning": "..."}
        {"action": "reassign", "new_employee_id": "EMP123", "reasoning": "..."}
        {"action": "none", "reasoning": "..."}
    """
    if llm is None:
        return {"action": "none", "reasoning": "LLM not available."}

    today = datetime.now().strftime("%Y-%m-%d")
    lookahead = (datetime.now() + timedelta(days=RESCHEDULE_LOOKAHEAD_DAYS)).strftime("%Y-%m-%d")

    candidates_summary = [
        {
            "employee_id": c.get("employee_id"),
            "full_name": c.get("full_name"),
            "burnout_risk_score": c.get("burnout_risk_score"),
            "current_project_count": c.get("current_project_count"),
            "historical_performance_score": c.get("historical_performance_score"),
        }
        for c in candidates if "employee_id" in c
    ]

    prompt = f"""You are an HR workload-balancing assistant. An employee is showing high burnout risk.
Decide the single best action for ONE of their tasks: "reschedule" (push the deadline/work later,
same owner), "reassign" (hand the task to a different, less burnt-out employee), or "none" (leave as-is,
e.g. task is nearly done or too urgent to move).

EMPLOYEE (high burnout risk):
{json.dumps(employee, indent=2, default=str)}

TASK IN QUESTION:
{json.dumps(task, indent=2, default=str)}

CANDIDATE EMPLOYEES AVAILABLE FOR REASSIGNMENT (may be empty):
{json.dumps(candidates_summary, indent=2, default=str)}

Today's date: {today}. If rescheduling, propose a new start/end datetime within the next
{RESCHEDULE_LOOKAHEAD_DAYS} days (by {lookahead}), each {DEFAULT_EVENT_DURATION_HOURS} hours long,
in ISO 8601 format (e.g. "2026-08-15T10:00:00"), that does not exceed the task's due_date if one exists.

Respond with ONLY a JSON object, no other text, no markdown fences:
{{
  "action": "reschedule" | "reassign" | "none",
  "new_start_time": "ISO 8601 or null",
  "new_end_time": "ISO 8601 or null",
  "new_employee_id": "EMP0000 or null",
  "reasoning": "one or two sentences explaining the decision"
}}"""

    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        # strip accidental markdown fences if the model adds them anyway
        text = text.replace("```json", "").replace("```", "").strip()
        decision = json.loads(text)
        return decision
    except Exception as e:
        return {"action": "none", "reasoning": f"LLM decision failed: {e}"}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3.5 — Find a genuinely free calendar slot before creating an event
# ══════════════════════════════════════════════════════════════════════════════

def find_next_free_slot(employee_id: str, duration_hours: int = DEFAULT_EVENT_DURATION_HOURS,
                         days_ahead: int = 7, work_start_hour: int = 9, work_end_hour: int = 18):
    """
    Scans this employee's existing calendar events over the next `days_ahead`
    days and returns the first non-overlapping slot within working hours.
    Checks the employee's own calendar (if they have a real, shared one),
    falling back to the shared team calendar otherwise — matching the same
    routing logic used by create_calendar_event in tools.py.
    """
    from tools import get_employee_profile

    window_start = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = window_start + timedelta(days=days_ahead)

    employee = get_employee_profile(employee_id)
    employee_email = employee.get("email") if "error" not in employee else None

    result = None
    if employee_email:
        result = list_events(
            time_min=window_start.isoformat() + "Z",
            time_max=window_end.isoformat() + "Z",
            max_results=100,
            calendar_id=employee_email,
        )
    if not result or not result.get("success"):
        result = list_events(
            time_min=window_start.isoformat() + "Z",
            time_max=window_end.isoformat() + "Z",
            max_results=100,
            calendar_id=None,
        )

    busy = []
    if result.get("success"):
        for ev in result.get("events", []):
            # Filter by employee_id in the summary as a safety net for the
            # shared-calendar fallback case (which may hold other people's events too)
            if employee_id in ev.get("summary", ""):
                try:
                    start_dt = datetime.fromisoformat(ev["start"].replace("Z", "+00:00")).replace(tzinfo=None)
                    end_dt = datetime.fromisoformat(ev["end"].replace("Z", "+00:00")).replace(tzinfo=None)
                    busy.append((start_dt, end_dt))
                except Exception:
                    continue

    day = window_start
    for _ in range(days_ahead):
        slot_start = day.replace(hour=work_start_hour, minute=0)
        while slot_start.hour + duration_hours <= work_end_hour:
            slot_end = slot_start + timedelta(hours=duration_hours)
            overlaps = any(s < slot_end and slot_start < e for s, e in busy)
            if not overlaps:
                return slot_start, slot_end
            slot_start += timedelta(hours=duration_hours)
        day += timedelta(days=1)

    # Fallback — shouldn't normally hit this
    fallback_start = window_start.replace(hour=work_start_hour)
    return fallback_start, fallback_start + timedelta(hours=duration_hours)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Execute the decision
# ══════════════════════════════════════════════════════════════════════════════

def execute_decision(employee_id: str, task: dict, decision: dict) -> dict:
    task_id = task["task_id"]
    action = decision.get("action", "none")

    if action == "reschedule":
        new_start = decision.get("new_start_time")
        new_end = decision.get("new_end_time")
        if not new_start or not new_end:
            return {"success": False, "error": "LLM chose reschedule but gave no valid times."}

        if task.get("google_event_id"):
            return reschedule_calendar_event(task_id, employee_id, new_start, new_end)
        else:
            # No event exists yet — create one at the proposed time instead
            return create_calendar_event(task_id, employee_id, new_start, new_end)

    elif action == "reassign":
        new_employee_id = decision.get("new_employee_id")
        if not new_employee_id:
            return {"success": False, "error": "LLM chose reassign but gave no new_employee_id."}

        results = {}
        # Cancel old owner's calendar event, if any
        if task.get("google_event_id"):
            results["cancel"] = cancel_calendar_event(task_id, employee_id)
        # Reassign in DB
        results["assign"] = assign_task(task_id, new_employee_id)
        # Create a fresh calendar event at the new owner's next genuinely free slot
        start, end = find_next_free_slot(new_employee_id)
        results["create"] = create_calendar_event(
            task_id, new_employee_id, start.isoformat(), end.isoformat()
        )
        overall_success = all(r.get("success", False) for r in results.values())
        return {"success": overall_success, "details": results}

    else:  # "none"
        return {"success": True, "message": "No action taken."}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Find high-burnout employees, log alerts, decide actions (no execution)
# ══════════════════════════════════════════════════════════════════════════════

def run_step1_decide():
    """
    Finds high-burnout employees, logs an alert for each, fetches their
    active tasks, and asks the LLM to decide an action per task.

    Returns a flat list of "pending decisions", one per task:
        {"employee": {...}, "task": {...}, "decision": {...}}

    No reassignment/reschedule is executed here — that happens in step 2.
    """
    print("=" * 60)
    print("ePARS Burnout Monitor — STEP 1: gathering decisions")
    print("=" * 60)

    pending_decisions = []

    flagged_employees = get_high_burnout_employees()
    if not flagged_employees:
        print("No employees currently at or above the burnout threshold. Nothing to do.")
        return pending_decisions

    print(f"\nFound {len(flagged_employees)} high-burnout employee(s).\n")

    for emp in flagged_employees:
        employee_id = emp["employee_id"]
        print(f"--- {employee_id} ({emp.get('full_name')}) — burnout {emp['burnout_score']:.2f} ---")

        # Alert logging is informational only — stays automatic in step 1
        # commented to remove writes in step 1. only reads 
        # alert_result = flag_burnout_alert(
        #    employee_id=employee_id,
        #    burnout_score=float(emp["burnout_score"]),
        #    urgency="Immediate" if emp["burnout_score"] >= 0.85 else "Recommend",
        #    recommended_action="Reviewed by automated burnout monitor for task rebalancing.",
        #)
        #print(f"  Alert logged: {alert_result.get('success')}")

        tasks = get_active_tasks_for_employee(employee_id)
        if not tasks:
            print("  No active tasks to rebalance.")
            continue

        task_summary = ", ".join(
            f"{t['task_id']} ({t.get('task_type')}, due {t.get('due_date')})" for t in tasks
        )
        print(f"  Current Tasks: {task_summary}")

        for task in tasks:
            task_id = task["task_id"]

            # Pull candidates in case reassignment is the right call
            task_full = get_task_details(task_id)
            required_skills = task_full.get("required_skills", "") or ""
            candidates = find_available_employees(required_skills) if required_skills else []
            candidates = [c for c in candidates if c.get("employee_id") != employee_id]

            decision = decide_action_for_task(emp, task, candidates)

            pending_decisions.append({
                "employee": emp,
                "task": task,
                "decision": decision,
            })

    print("\n" + "=" * 60)
    print(f"STEP 1 complete. {len(pending_decisions)} task decision(s) gathered.")
    print("=" * 60)

    return pending_decisions


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Per-task confirmation, then execute
# ══════════════════════════════════════════════════════════════════════════════

def run_step2_confirm_and_execute(pending_decisions: list):
    """
    Walks through each pending decision. For "reassign"/"reschedule" actions,
    asks the user to confirm (y/n) before executing. "none" actions are just
    noted — there's nothing to confirm.
    """
    print("\n" + "=" * 60)
    print("ePARS Burnout Monitor — STEP 2: confirm & execute")
    print("=" * 60)

    if not pending_decisions:
        print("Nothing to confirm.")
        return
    alerted_employees = set()

    for item in pending_decisions:
        emp = item["employee"]
        employee_id = emp["employee_id"]
        task = item["task"]
        decision = item["decision"]
        action = decision.get("action", "none")
        task_id = task["task_id"]

        print(f"\n--- {employee_id} ({emp.get('full_name')}) — Task {task_id} "
              f"({task.get('task_type')}, due {task.get('due_date')}) ---")
        print(f"  Decision: {action} — {decision.get('reasoning')}")

        if employee_id not in alerted_employees:
            ans = input(f"  Log burnout alert for {employee_id}? "
                        f"(sets is_available=False, stress_level=High, +1 intervention) [y/N]: ").strip().lower()
            if ans == "y":
                alert_result = flag_burnout_alert(
                    employee_id=employee_id,
                    burnout_score=float(emp["burnout_score"]),
                    urgency="Immediate" if emp["burnout_score"] >= 0.85 else "Recommend",
                    recommended_action="Reviewed by automated burnout monitor for task rebalancing.",
                )
                print(f"  Alert logged: {alert_result.get('success')}")
            alerted_employees.add(employee_id)

        if action == "none":
            print("  No action needed — skipping.")
            continue

        answer = input(f"  Proceed with '{action}' for {task_id}? [y/N]: ").strip().lower()
        if answer != "y":
            print("  Skipped.")
            continue

        result = execute_decision(emp["employee_id"], task, decision)
        print(f"  Execution result: {result}")

    print("\n" + "=" * 60)
    print("Burnout monitor run complete.")
    print("=" * 60)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def run_burnout_monitor():
    pending_decisions = run_step1_decide()
    run_step2_confirm_and_execute(pending_decisions)

if __name__ == "__main__":
    run_burnout_monitor()