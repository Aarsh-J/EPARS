"""
modules/ml/reassignment.py
===============================
Confidence-gated burnout assessment + manager-confirmed task reassignment.

Ports the LLM decision logic from src/epars_agent/agent/burnout_monitor.py
(decide_action_for_task, find_next_free_slot, execute_decision) — same
prompt/parse pattern, but split into two phases instead of one:

    assess_and_recommend()  — READ-ONLY. Predicts, generates a justification,
                               records an assessment, and (if warranted)
                               generates per-task recommendations. No task
                               reassignment, calendar event, or availability
                               change happens here.
    execute_recommendation() — Called only after explicit manager
                               confirmation. This is where the real
                               tools.py/calendar_client.py side effects
                               (that burnout_monitor.py used to fire
                               unattended) actually happen.

See ml_models/README.md for the burnout model's known live-data gap — most
predictions land in "low confidence" today, which is why this module treats
that tier as informational-only rather than pretending otherwise.
"""

import json
from datetime import datetime, timedelta

from calendar_client import list_events
from db import get_connection
from tools import (
    _to_list,
    assign_task,
    cancel_calendar_event,
    create_calendar_event,
    find_available_employees,
    flag_burnout_alert,
    get_employee_profile,
    get_task_details,
    reschedule_calendar_event,
)
from rag_query import format_policy_context

from .llm_client import invoke_json, llm
from .predict import predict_burnout

RESCHEDULE_LOOKAHEAD_DAYS = 14
DEFAULT_EVENT_DURATION_HOURS = 2
THRESHOLD_CLASSES = ("High", "Critical")


# ── Assessment justification ────────────────────────────────────────────────

def _generate_burnout_justification(employee_profile: dict, prediction: dict) -> dict:
    fallback = {
        "justification": (
            f"The model classifies this employee's burnout risk as "
            f"{prediction['predicted_class']} ({prediction['confidence']} confidence). "
            "Automated explanation is currently unavailable."
        ),
        "policy_citation": None,
    }
    if llm is None:
        return fallback

    policy_context = format_policy_context(
        "burnout classification thresholds Low Medium High score range mandatory "
        "intervention actions manager responsibilities",
        n_results=4,
    )

    prompt = f"""You are an HR wellbeing assistant. Explain, in plain language a manager can
read in a few seconds, why the model classified this employee's burnout risk the way it did.
Ground your explanation in the actual data below — do not invent numbers.

IMPORTANT: only {prediction['real_feature_count']} of {prediction['total_feature_count']}
model inputs are backed by live data for this employee (confidence: {prediction['confidence']}).
If confidence is low or medium, say so plainly and note the prediction leans on defaults for
its most important signals rather than this employee's real data.

EMPLOYEE:
{json.dumps(employee_profile, indent=2, default=str)}

MODEL OUTPUT:
{json.dumps({
    "predicted_class": prediction["predicted_class"],
    "confidence": prediction["confidence"],
    "predicted_probabilities": prediction["predicted_probabilities"],
}, indent=2)}

RELEVANT HR POLICY:
{policy_context}

Respond with ONLY a JSON object, no other text, no markdown fences:
{{
  "justification": "2-4 sentences explaining the classification and what it implies",
  "policy_citation": "short reference like 'POL-WELL-002 — Red alert' or null if no clear policy match"
}}"""

    parsed = invoke_json(prompt)
    if not parsed or "justification" not in parsed:
        return fallback
    return {
        "justification": parsed["justification"],
        "policy_citation": parsed.get("policy_citation"),
    }


# ── Per-task reassignment/reschedule decision (ported from burnout_monitor.py) ──

def decide_action_for_task(employee: dict, task: dict, candidates: list) -> dict:
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

    parsed = invoke_json(prompt)
    if not parsed:
        return {"action": "none", "reasoning": "LLM decision failed or returned unparsable output."}
    return parsed


def find_next_free_slot(employee_id: str, duration_hours: int = DEFAULT_EVENT_DURATION_HOURS,
                         days_ahead: int = 7, work_start_hour: int = 9, work_end_hour: int = 18):
    """Ported verbatim from burnout_monitor.py."""
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

    fallback_start = window_start.replace(hour=work_start_hour)
    return fallback_start, fallback_start + timedelta(hours=duration_hours)


def _get_active_tasks_for_employee(employee_id: str) -> list:
    """
    Active tasks CURRENTLY owned by this employee. Unlike burnout_monitor.py's
    original version, this only looks at each task's LATEST assignment row
    (DISTINCT ON task_id, most recent assignment_date) and excludes
    'Reassigned' — a task can have older rows still tagged with this
    employee_id from before it was handed off, which must not be treated as
    "their active work" (confirmed via testing: without this, tasks already
    reassigned away from an employee were still being recommended for
    reassignment off of them again).
    """
    sql = """
        SELECT t.task_id, t.task_type, t.priority, t.complexity, t.estimated_hours,
               t.due_date, t.status, t.completion_percentage,
               ta.google_event_id, ta.assignment_id
        FROM (
            SELECT DISTINCT ON (task_id) *
            FROM task_assignments
            ORDER BY task_id, assignment_date DESC
        ) ta
        JOIN tasks t ON t.task_id = ta.task_id
        WHERE ta.employee_id = %s
          AND t.status NOT IN ('Completed', 'Cancelled')
          AND ta.completion_status NOT IN ('Completed', 'Cancelled', 'Reassigned')
        ORDER BY t.due_date ASC NULLS LAST
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (employee_id,))
            return _to_list(cur.fetchall())


def _next_id(table: str, id_col: str, prefix: str) -> str:
    sql = f"""
        SELECT COALESCE(MAX(CAST(SUBSTRING({id_col} FROM {len(prefix) + 1}) AS INTEGER)), 0) AS max_num
        FROM {table}
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            next_num = cur.fetchone()["max_num"] + 1
    return f"{prefix}{next_num:04d}"


# ── Phase 1: assess + recommend (read-only, no side effects) ────────────────

def assess_and_recommend(employee_id: str) -> dict:
    profile = get_employee_profile(employee_id)
    prediction = predict_burnout(employee_id)
    justification = _generate_burnout_justification(profile, prediction)

    confidence = prediction["confidence"]
    predicted_class = prediction["predicted_class"]

    if confidence == "high":
        status = "applied"
    elif confidence == "medium":
        status = "pending_review"
    else:
        status = "informational"

    assessment_id = _next_id("burnout_ai_assessments", "assessment_id", "BOAI")
    now = datetime.now()
    insert_sql = """
        INSERT INTO burnout_ai_assessments (
            assessment_id, employee_id, ai_predicted_class, ai_probabilities,
            confidence, justification, status, reviewed_at, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(insert_sql, (
                assessment_id, employee_id, predicted_class,
                json.dumps(prediction["predicted_probabilities"]),
                confidence, justification["justification"], status, None, now,
            ))
        conn.commit()

    # High-confidence + over threshold is trusted enough to act on immediately
    # (mirrors flag_burnout_alert's own behavior in burnout_monitor.py, which
    # marks the employee unavailable for new tasks — a real side effect, so
    # only fired for the tier we actually trust without a human checking first).
    if status == "applied" and predicted_class in THRESHOLD_CLASSES:
        risk_fraction = max(prediction["predicted_probabilities"].get(c, 0) for c in THRESHOLD_CLASSES)
        flag_burnout_alert(
            employee_id=employee_id,
            burnout_score=risk_fraction,
            urgency="High" if predicted_class == "Critical" else "Medium",
            recommended_action="Flagged by confidence-gated burnout assessment for task rebalancing review.",
        )

    recommendations = []
    if confidence != "low" and predicted_class in THRESHOLD_CLASSES:
        recommendations = _generate_recommendations(assessment_id, employee_id, profile)

    return {
        "assessment_id": assessment_id,
        "predicted_class": predicted_class,
        "predicted_probabilities": prediction["predicted_probabilities"],
        "confidence": confidence,
        "real_feature_count": prediction["real_feature_count"],
        "total_feature_count": prediction["total_feature_count"],
        "justification": justification["justification"],
        "policy_citation": justification["policy_citation"],
        "status": status,
        "recommendations": recommendations,
    }


def _generate_recommendations(assessment_id: str, employee_id: str, profile: dict) -> list:
    tasks = _get_active_tasks_for_employee(employee_id)
    recommendations = []

    insert_sql = """
        INSERT INTO task_reassignment_recommendations (
            recommendation_id, assessment_id, employee_id, task_id, action,
            target_employee_id, new_start_time, new_end_time, reasoning,
            manager_decision, executed_at, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    now = datetime.now()

    for task in tasks:
        task_full = get_task_details(task["task_id"])
        required_skills = task_full.get("required_skills", "") or ""
        candidates = find_available_employees(required_skills) if required_skills else []
        candidates = [c for c in candidates if c.get("employee_id") != employee_id]

        decision = decide_action_for_task(profile, task, candidates)
        action = decision.get("action", "none")

        recommendation_id = _next_id("task_reassignment_recommendations", "recommendation_id", "TRR")
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(insert_sql, (
                    recommendation_id, assessment_id, employee_id, task["task_id"], action,
                    decision.get("new_employee_id"), decision.get("new_start_time"),
                    decision.get("new_end_time"), decision.get("reasoning"),
                    None, None, now,
                ))
            conn.commit()

        recommendations.append({
            "recommendation_id": recommendation_id,
            "task_id": task["task_id"],
            "task_type": task.get("task_type"),
            "due_date": task.get("due_date").isoformat() if task.get("due_date") else None,
            "action": action,
            "target_employee_id": decision.get("new_employee_id"),
            "new_start_time": decision.get("new_start_time"),
            "new_end_time": decision.get("new_end_time"),
            "reasoning": decision.get("reasoning"),
        })

    return recommendations


# ── Phase 2: execute a confirmed recommendation (real side effects) ─────────

def _safe_calendar_call(fn, *args) -> dict:
    """
    calendar_client.py raises RuntimeError (not a {"success": False, ...}
    dict) when Google Calendar isn't configured (no sa_key.json). Calendar
    sync is best-effort here, so convert that into the same dict shape the
    rest of this module expects rather than letting it propagate.
    """
    try:
        return fn(*args)
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_recommendation(recommendation_id: str) -> dict:
    sql = "SELECT * FROM task_reassignment_recommendations WHERE recommendation_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (recommendation_id,))
            rec = cur.fetchone()
    if not rec:
        return {"success": False, "error": "Recommendation not found."}

    task = get_task_details(rec["task_id"])
    employee_id = rec["employee_id"]
    action = rec["action"]

    if action == "reschedule":
        new_start, new_end = rec.get("new_start_time"), rec.get("new_end_time")
        if not new_start or not new_end:
            return {"success": False, "error": "No valid reschedule time on this recommendation."}
        if task.get("google_event_id"):
            result = reschedule_calendar_event(rec["task_id"], employee_id, new_start.isoformat(), new_end.isoformat())
        else:
            result = create_calendar_event(rec["task_id"], employee_id, new_start.isoformat(), new_end.isoformat())

    elif action == "reassign":
        new_employee_id = rec.get("target_employee_id")
        if not new_employee_id:
            return {"success": False, "error": "No target employee on this recommendation."}
        results = {}
        if task.get("google_event_id"):
            results["cancel"] = _safe_calendar_call(cancel_calendar_event, rec["task_id"], employee_id)
        # The DB reassignment is the primary effect the manager confirmed; it
        # commits unconditionally inside assign_task (no surrounding
        # transaction to roll back even if we wanted to). Calendar sync is a
        # secondary, best-effort follow-up — its failure must not make this
        # look like nothing happened when the reassignment itself succeeded
        # (confirmed via testing: a bare calendar exception here previously
        # bubbled up as a 500 with the DB change already committed, leaving
        # the recommendation stuck looking "undecided" while already applied).
        results["assign"] = assign_task(rec["task_id"], new_employee_id)
        try:
            start, end = find_next_free_slot(new_employee_id)
            results["create"] = _safe_calendar_call(
                create_calendar_event, rec["task_id"], new_employee_id, start.isoformat(), end.isoformat()
            )
        except Exception as e:
            results["create"] = {"success": False, "error": str(e)}
        result = {
            "success": results["assign"].get("success", False),
            "details": results,
        }

    else:  # "none"
        result = {"success": True, "message": "No action taken."}

    return result
