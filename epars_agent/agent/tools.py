"""
=======================================
Each function queries your PostgreSQL tables and returns a clean Python dict that the LLM agent can reason over.
All tools are also wrapped as LangChain Tool objects at the bottom of this file, ready to plug into the agent.
Tables used: employees, tasks, task_assignments, workload_history, burnout_indicators, performance_reviews, team_formations
"""
import json
from datetime import date, datetime
from decimal import Decimal
from db import get_connection
from calendar_client import create_event, update_event, delete_event
# ── Utility ────────────────────────────────────────────────────────────────────

def _serialize(obj):
    """JSON-safe converter for dates, datetimes, and Decimals from psycopg2."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def _to_dict(row):
    """Convert a RealDictRow (or None) to a plain dict."""
    return dict(row) if row else {}

def _to_list(rows):
    """Convert a list of RealDictRows to plain dicts."""
    return [dict(r) for r in rows] if rows else []

# ══════════════════════════════════════════════════════════════════════════════
# TOOL 1 — get_employee_profile
# Purpose : Fetch everything the agent needs to know about one employee.
# Used by : Task assignment, team formation, burnout response agents.
# ══════════════════════════════════════════════════════════════════════════════

def get_employee_profile(employee_id: str) -> dict:
    sql = """
        SELECT
            employee_id,
            first_name || ' ' || last_name           AS full_name,
            department,
            role,
            seniority_level,
            primary_skills,
            secondary_skills,
            certifications,
            technical_proficiency_score,
            domain_expertise_score,
            weekly_capacity_hours,
            is_available,
            current_project_count,
            burnout_risk_score,
            stress_level,
            recent_overtime_hours,
            historical_performance_score,
            average_task_completion_rate,
            collaboration_score,
            leadership_potential,
            productivity_trend
        FROM employees
        WHERE employee_id = %s
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (employee_id,))
                row = cur.fetchone()
                if not row:
                    return {"error": f"Employee '{employee_id}' not found."}
                return _to_dict(row)
    except Exception as e:
        return {"error": str(e)}

# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2 — get_employee_ml_scores
# Purpose : Fetch the latest ML model outputs for an employee.
#           PEM score from performance_reviews,
#           Burnout score from burnout_indicators.
# Used by : Every agent decision — this is the core ML output the agent acts on.
# ══════════════════════════════════════════════════════════════════════════════

def get_employee_ml_scores(employee_id: str) -> dict:
    pem_sql = """
        SELECT
            overall_performance_score       AS pem_score,
            normalized_performance_score    AS pem_normalized,
            performance_rating,
            review_date                     AS pem_review_date,
            promotion_recommended,
            productivity_vs_peers
        FROM performance_reviews
        WHERE employee_id = %s
        ORDER BY review_date DESC
        LIMIT 1
    """
    burnout_sql = """
        SELECT
            overall_burnout_risk / 100.0    AS burnout_score,
            burnout_category,
            burnout_trend,
            intervention_urgency,
            predicted_burnout_30days / 100.0 AS predicted_burnout_30days,
            predicted_burnout_90days / 100.0 AS predicted_burnout_90days,
            emotional_exhaustion_score,
            job_satisfaction,
            late_hours_frequency,
            assessment_date
        FROM burnout_indicators
        WHERE employee_id = %s
        ORDER BY assessment_date DESC
        LIMIT 1
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(pem_sql, (employee_id,))
                pem = _to_dict(cur.fetchone())
                cur.execute(burnout_sql, (employee_id,))
                burnout = _to_dict(cur.fetchone())
        if not pem and not burnout:
            return {"error": f"No ML scores found for employee '{employee_id}'."}
        return {
            "employee_id": employee_id,
            **pem,
            **burnout,
        }
    except Exception as e:
        return {"error": str(e)}

# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3 — get_employee_workload
# Purpose : How busy is this employee right now?
#           Active tasks + recent workload history.
# Used by : Task assignment agent (check before assigning more work).
# ══════════════════════════════════════════════════════════════════════════════

def get_employee_workload(employee_id: str) -> dict:
    active_tasks_sql = """
        SELECT
            COUNT(*)                                AS active_task_count,
            COALESCE(SUM(t.estimated_hours * (1 - t.completion_percentage / 100.0)), 0)
                                                    AS total_estimated_hours_remaining
        FROM task_assignments ta
        JOIN tasks t ON ta.task_id = t.task_id
        WHERE ta.employee_id = %s
          AND t.status NOT IN ('Completed', 'Cancelled')
          AND ta.completion_status NOT IN ('Completed', 'Cancelled')
    """
    workload_history_sql = """
        SELECT
            AVG(total_hours_worked)         AS avg_hours_per_day,
            AVG(overtime_hours)             AS avg_overtime_hours,
            AVG(workload_intensity_score)   AS avg_workload_intensity,
            AVG(deadline_pressure_score)    AS avg_deadline_pressure,
            AVG(productivity_score)         AS avg_productivity_score
        FROM workload_history
        WHERE employee_id = %s
          AND date >= CURRENT_DATE - INTERVAL '7 days'
    """
    capacity_sql = """
        SELECT weekly_capacity_hours
        FROM employees
        WHERE employee_id = %s
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(active_tasks_sql, (employee_id,))
                tasks = _to_dict(cur.fetchone())
                cur.execute(workload_history_sql, (employee_id,))
                history = _to_dict(cur.fetchone())
                cur.execute(capacity_sql, (employee_id,))
                capacity_row = cur.fetchone()
                weekly_capacity = float(capacity_row["weekly_capacity_hours"]) if capacity_row else 40.0
        active_task_count = int(tasks.get("active_task_count") or 0)
        hours_remaining   = float(tasks.get("total_estimated_hours_remaining") or 0)
        capacity_used_pct = round((hours_remaining / weekly_capacity) * 100, 1) if weekly_capacity else 0
        return {
            "employee_id": employee_id,
            "active_task_count": active_task_count,
            "total_estimated_hours_remaining": round(hours_remaining, 1),
            "weekly_capacity_hours": weekly_capacity,
            "capacity_used_percent": capacity_used_pct,
            "recent_avg_hours_per_day":  round(float(history.get("avg_hours_per_day") or 0), 1),
            "recent_avg_overtime_hours": round(float(history.get("avg_overtime_hours") or 0), 1),
            "recent_avg_workload_intensity": round(float(history.get("avg_workload_intensity") or 0), 1),
            "recent_avg_productivity_score": round(float(history.get("avg_productivity_score") or 0), 1),
        }
    except Exception as e:
        return {"error": str(e)}

# ══════════════════════════════════════════════════════════════════════════════
# TOOL 4 — get_task_details
# Purpose : What does this task need? Skills, priority, deadline, hours.
# Used by : Task assignment and team formation agents.
# ══════════════════════════════════════════════════════════════════════════════

def get_task_details(task_id: str) -> dict:
    sql = """
        SELECT
            task_id,
            project_id,
            task_type,
            priority,
            complexity,
            required_skills,
            required_role,
            required_seniority,
            estimated_hours,
            actual_hours,
            due_date,
            start_date,
            status,
            completion_percentage,
            assigned_to,
            is_overdue,
            days_overdue,
            delay_risk_score,
            task_description AS description
        FROM tasks
        WHERE task_id = %s
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (task_id,))
                row = cur.fetchone()
                if not row:
                    return {"error": f"Task '{task_id}' not found."}
                return _to_dict(row)
    except Exception as e:
        return {"error": str(e)}

# ══════════════════════════════════════════════════════════════════════════════
# TOOL 5 — find_available_employees
# Purpose : Find candidate employees for a task based on skill and availability.
# Used by : Task assignment agent and team formation agent.
# ══════════════════════════════════════════════════════════════════════════════

def find_available_employees(required_skills: str, required_role: str = "", required_seniority: str = "", limit: int = 5) -> list:
    # Build dynamic WHERE clauses for each skill keyword
    skill_list = [s.strip() for s in required_skills.split(",") if s.strip()]

    # Build ILIKE conditions for each skill against primary + secondary skills
    skill_conditions = " OR ".join(
        f"(primary_skills ILIKE %s OR secondary_skills ILIKE %s)"
        for _ in skill_list
    )
    skill_params = []
    for skill in skill_list:
        skill_params.extend([f"%{skill}%", f"%{skill}%"])
    role_clause     = "AND role ILIKE %s"         if required_role      else ""
    seniority_clause= "AND seniority_level = %s"  if required_seniority else ""
    sql = f"""
        SELECT
            e.employee_id,
            e.first_name || ' ' || e.last_name          AS full_name,
            e.role,
            e.seniority_level,
            e.department,
            e.primary_skills,
            e.secondary_skills,
            e.weekly_capacity_hours,
            e.is_available,
            e.burnout_risk_score,
            e.stress_level,
            e.historical_performance_score,
            e.average_task_completion_rate,
            e.current_project_count
        FROM employees e
        WHERE e.is_available = TRUE
          AND e.burnout_risk_score < 70
          AND ({skill_conditions})
          {role_clause}
          {seniority_clause}
        ORDER BY e.historical_performance_score DESC
        LIMIT %s
    """
    params = skill_params
    if required_role:
        params.append(f"%{required_role}%")
    if required_seniority:
        params.append(required_seniority)
    params.append(limit)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                if not rows:
                    return [{"message": f"No available employees found matching skills: {required_skills}"}]
                return _to_list(rows)
    except Exception as e:
        return [{"error": str(e)}]

# ══════════════════════════════════════════════════════════════════════════════
# TOOL 6 — assign_task
# Purpose : Write a new task assignment record to the database.
# Used by : Task assignment agent (the actual write action).
# ══════════════════════════════════════════════════════════════════════════════
def assign_task(task_id: str, employee_id: str, assignment_method: str = "agentic_ai", skill_match_score: float = 0.0) -> dict:
    next_id_sql = """
        SELECT COALESCE(MAX(CAST(SUBSTRING(assignment_id FROM 4) AS INTEGER)), 0) AS max_num
        FROM task_assignments
        WHERE assignment_id ~ '^ASG[0-9]+$'
    """
    insert_sql = """
        INSERT INTO task_assignments (
            assignment_id,
            task_id,
            employee_id,
            project_id,
            assignment_date,
            assignment_method,
            skill_match_score,
            completion_status
        )
        SELECT
            %s,
            %s,
            %s,
            t.project_id,
            CURRENT_DATE,
            %s,
            %s,
            'Assigned'
        FROM tasks t
        WHERE t.task_id = %s
        RETURNING assignment_id
    """
    update_task_sql = """
        UPDATE tasks
        SET assigned_to = %s,
            status = CASE WHEN status = 'Not Started' THEN 'In Progress' ELSE status END
        WHERE task_id = %s
    """
    update_employee_sql = """
        UPDATE employees
        SET current_project_count = current_project_count + 1
        WHERE employee_id = %s
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(next_id_sql)
                max_row = cur.fetchone()
                next_num = (max_row["max_num"] if max_row else 0) + 1
                new_id = f"ASG{next_num:04d}"

                cur.execute(insert_sql, (new_id, task_id, employee_id, assignment_method, skill_match_score, task_id))
                row = cur.fetchone()
                assignment_id = row["assignment_id"] if row else None

                cur.execute(update_task_sql, (employee_id, task_id))
                cur.execute(update_employee_sql, (employee_id,))
            conn.commit()
        return {
            "success": True,
            "assignment_id": str(assignment_id),
            "task_id": task_id,
            "employee_id": employee_id,
            "message": f"Task {task_id} successfully assigned to {employee_id} via {assignment_method}."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
# ══════════════════════════════════════════════════════════════════════════════
# TOOL 7 — flag_burnout_alert
# Purpose : Log a burnout intervention flag for a high-risk employee.
# Used by : Burnout intervention agent.
# ══════════════════════════════════════════════════════════════════════════════
def flag_burnout_alert(employee_id: str, burnout_score: float,
                        urgency: str, recommended_action: str) -> dict:
    update_sql = """
        UPDATE burnout_indicators
        SET intervention_urgency    = %s,
            interventions_received  = COALESCE(interventions_received, 0) + 1
        WHERE employee_id = %s
          AND assessment_date = (
              SELECT MAX(assessment_date) FROM burnout_indicators WHERE employee_id = %s
          )
    """
    # If high urgency, temporarily mark as unavailable for new tasks
    availability_sql = """
        UPDATE employees
        SET is_available = FALSE,
            stress_level = 'High'
        WHERE employee_id = %s
          AND %s >= 0.70
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(update_sql, (urgency, employee_id, employee_id))
                cur.execute(availability_sql, (employee_id, burnout_score))
            conn.commit()
        msg = (
            f"Burnout alert logged for {employee_id}. "
            f"Score: {burnout_score:.2f}, Urgency: {urgency}. "
            f"Recommended action: {recommended_action}"
        )
        return {"success": True, "message": msg}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ══════════════════════════════════════════════════════════════════════════════
# TOOL 8 — create_calendar_event
# Purpose : Creates a Google Calendar event for a task assignment and
#           stores the returned google_event_id on the task_assignments row.
# Used by : Task assignment agent / burnout monitoring loop (Step 6).
# ══════════════════════════════════════════════════════════════════════════════
def create_calendar_event(task_id: str, employee_id: str, start_time: str, end_time: str) -> dict:
    # Pull task description for the event summary
    task = get_task_details(task_id)
    if "error" in task:
        return {"success": False, "error": task["error"]}

    summary = f"[{task_id}] {task.get('task_type', 'Task')} — {employee_id}"
    description = task.get("description", "") or ""
    cal_result = create_event(
        summary=summary,
        start_time=start_time,
        end_time=end_time,
        description=description,
    )
    if not cal_result.get("success"):
        return {"success": False, "error": cal_result.get("error", "Calendar API call failed.")}
    event_id = cal_result["event_id"]
    update_sql = """
        UPDATE task_assignments
        SET google_event_id = %s
        WHERE task_id = %s AND employee_id = %s
          AND assignment_id = (
              SELECT assignment_id FROM task_assignments
              WHERE task_id = %s AND employee_id = %s
              ORDER BY assignment_date DESC
              LIMIT 1
          )
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(update_sql, (event_id, task_id, employee_id, task_id, employee_id))
                rows_updated = cur.rowcount
            conn.commit()

        if rows_updated == 0:
            delete_event(event_id)
            return {
                "success": False,
                "error": f"No task_assignments row found for {task_id}/{employee_id}. "
                         f"Assign the task first via assign_task. Orphaned calendar event was auto-deleted."
            }

        return {
            "success": True,
            "event_id": event_id,
            "message": f"Calendar event created for {task_id} ({employee_id}) and linked in DB."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Event created in Calendar (id={event_id}) but DB update failed: {e}"
        }   

# ══════════════════════════════════════════════════════════════════════════════
# TOOL 9 — reschedule_calendar_event
# Purpose : Moves an existing task's calendar event to a new time.
#           This is the core action for burnout-triggered rescheduling.
# Used by : Burnout monitoring loop (Step 6).
# ══════════════════════════════════════════════════════════════════════════════

def reschedule_calendar_event(task_id: str, employee_id: str, new_start_time: str, new_end_time: str) -> dict:
    lookup_sql = """
        SELECT google_event_id FROM task_assignments
        WHERE task_id = %s AND employee_id = %s
        ORDER BY assignment_date DESC
        LIMIT 1
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(lookup_sql, (task_id, employee_id))
                row = cur.fetchone()
        if not row or not row.get("google_event_id"):
            return {"success": False, "error": f"No calendar event found for {task_id}/{employee_id}. Create one first."}
        event_id = row["google_event_id"]
        cal_result = update_event(event_id=event_id, start_time=new_start_time, end_time=new_end_time,)
        if not cal_result.get("success"):
            return {"success": False, "error": cal_result.get("error", "Calendar API update failed.")}
        return {
            "success": True,
            "event_id": event_id,
            "message": f"Rescheduled {task_id} ({employee_id}) to {new_start_time} - {new_end_time}."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ══════════════════════════════════════════════════════════════════════════════
# TOOL 10 — cancel_calendar_event
# Purpose : Deletes the calendar event for a task, e.g. when reassigning the task to a different employee.
# Used by : Burnout monitoring loop (Step 6) — pairs with create_calendar_event
#           when reassigning: cancel old owner's event, create new owner's event.
# ══════════════════════════════════════════════════════════════════════════════

def cancel_calendar_event(task_id: str, employee_id: str) -> dict:
    lookup_sql = """
        SELECT google_event_id FROM task_assignments
        WHERE task_id = %s AND employee_id = %s
        ORDER BY assignment_date DESC
        LIMIT 1
    """
    clear_sql = """
        UPDATE task_assignments
        SET google_event_id = NULL
        WHERE task_id = %s AND employee_id = %s
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(lookup_sql, (task_id, employee_id))
                row = cur.fetchone()
        if not row or not row.get("google_event_id"):
            return {"success": False, "error": f"No calendar event found for {task_id}/{employee_id}."}
        event_id = row["google_event_id"]
        cal_result = delete_event(event_id)
        if not cal_result.get("success"):
            return {"success": False, "error": cal_result.get("error", "Calendar API delete failed.")}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(clear_sql, (task_id, employee_id))
            conn.commit()
        return {"success": True, "message": f"Cancelled calendar event for {task_id} ({employee_id})."}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ══════════════════════════════════════════════════════════════════════════════
# LANGCHAIN TOOL WRAPPERS
# ══════════════════════════════════════════════════════════════════════════════
try:
    try:
        from langchain.tools import Tool
    except ImportError:
        from langchain_core.tools import Tool
    # Tool 1
    employee_profile_tool = Tool(
        name="get_employee_profile",
        func=lambda eid: json.dumps(get_employee_profile(eid.strip()), default=_serialize),
        description=(
            "Fetches the full profile of an employee given their employee_id (e.g. 'EMP042'). "
            "Returns skills, role, seniority, availability, performance history, "
            "stress level, and capacity. Use this to understand who an employee is before "
            "making any recommendation about them."
        ),
    )
    # Tool 2
    ml_scores_tool = Tool(
        name="get_employee_ml_scores",
        func=lambda eid: json.dumps(get_employee_ml_scores(eid.strip()), default=_serialize),
        description=(
            "Fetches the latest PEM (performance) score and WBP (burnout) score for an "
            "employee. Input is employee_id (e.g. 'EMP042'). Returns pem_score (0-100), "
            "performance_rating, burnout_score (0-1.0), burnout_category, burnout_trend, "
            "and intervention_urgency. Always call this before deciding to assign a task "
            "or flag burnout."
        ),
    )
    # Tool 3
    workload_tool = Tool(
        name="get_employee_workload",
        func=lambda eid: json.dumps(get_employee_workload(eid.strip()), default=_serialize),
        description=(
            "Returns the current workload of an employee: how many active tasks they have, "
            "estimated hours remaining, weekly capacity, and recent daily hours worked. "
            "Input is employee_id. Use this before assigning new tasks to check if the "
            "employee has capacity."
        ),
    )
    # Tool 4
    task_details_tool = Tool(
        name="get_task_details",
        func=lambda tid: json.dumps(get_task_details(tid.strip()), default=_serialize),
        description=(
            "Fetches full details of a task given its task_id (e.g. 'TASK0042'). "
            "Returns required skills, priority, complexity, estimated hours, due date, "
            "current status, and whether it is overdue. Call this first whenever you "
            "need to assign a task."
        ),
    )
    # Tool 5
    find_employees_tool = Tool(
        name="find_available_employees",
        func=lambda q: json.dumps(
            find_available_employees(
                **{k: v for k, v in
                   [item.split("=", 1) for item in q.split("|") if "=" in item]}
            ), default=_serialize
        ),
        description=(
            "Finds available employees who match the required skills. "
            "Input format: 'required_skills=Python, Django|required_role=Software Engineer|required_seniority=Mid' "
            "Only required_skills is mandatory. Returns up to 5 candidates ranked by "
            "performance score, with their burnout risk and availability status."
        ),
    )
    # Tool 6
    assign_task_tool = Tool(
        name="assign_task",
        func=lambda q: json.dumps(
            assign_task(
                **{k: v for k, v in
                   [item.split("=", 1) for item in q.split("|") if "=" in item]}
            ), default=_serialize
        ),
        description=(
            "Assigns a task to an employee in the database. "
            "Input format: 'task_id=TASK0042|employee_id=EMP042|skill_match_score=85' "
            "Only call this AFTER you have verified the employee's PEM score, "
            "burnout score, workload, and retrieved the relevant HR policy. "
            "Returns success status and the new assignment_id."
        ),
    )
    # Tool 7
    flag_burnout_tool = Tool(
        name="flag_burnout_alert",
        func=lambda q: json.dumps(
            flag_burnout_alert(
                **{k: v for k, v in
                   [item.split("=", 1) for item in q.split("|") if "=" in item]}
            ), default=_serialize
        ),
        description=(
            "Logs a burnout intervention alert for an employee and updates their "
            "availability status. Input format: "
            "'employee_id=EMP042|burnout_score=0.75|urgency=High|recommended_action=Reduce workload and schedule 1-1' "
            "Call this when the WBP burnout score is above 0.70 or when the agent "
            "determines immediate intervention is required."
        ),
    )
    # Tool 8
    create_calendar_event_tool = Tool(
        name="create_calendar_event",
        func=lambda q: json.dumps(
            create_calendar_event(
                **{k: v for k, v in
                   [item.split("=", 1) for item in q.split("|") if "=" in item]}
            ), default=_serialize
        ),
        description=(
            "Creates a Google Calendar event for a task assignment. "
            "Input format: 'task_id=TASK0042|employee_id=EMP042|"
            "start_time=2026-08-10T10:00:00|end_time=2026-08-10T12:00:00' "
            "Call this after assign_task to put the work on the employee's calendar."
        ),
    )
    # Tool 9
    reschedule_calendar_event_tool = Tool(
        name="reschedule_calendar_event",
        func=lambda q: json.dumps(
            reschedule_calendar_event(
                **{k: v for k, v in
                   [item.split("=", 1) for item in q.split("|") if "=" in item]}
            ), default=_serialize
        ),
        description=(
            "Reschedules an existing task's calendar event to a new time. "
            "Input format: 'task_id=TASK0042|employee_id=EMP042|"
            "new_start_time=2026-08-12T10:00:00|new_end_time=2026-08-12T12:00:00' "
            "Use this when an employee's burnout score is high and their workload "
            "needs to be spread out, rather than reassigned to someone else."
        ),
    )
    # Tool 10
    cancel_calendar_event_tool = Tool(
        name="cancel_calendar_event",
        func=lambda q: json.dumps(
            cancel_calendar_event(
                **{k: v for k, v in
                   [item.split("=", 1) for item in q.split("|") if "=" in item]}
            ), default=_serialize
        ),
        description=(
            "Cancels the calendar event for a task assignment. "
            "Input format: 'task_id=TASK0042|employee_id=EMP042' "
            "Call this when reassigning a task to a different employee — "
            "cancel the old owner's event, then create_calendar_event for the new owner."
        ),
    )
    # Collect all tools for easy import in Step 3
    ALL_TOOLS = [
        employee_profile_tool,
        ml_scores_tool,
        workload_tool,
        task_details_tool,
        find_employees_tool,
        assign_task_tool,
        flag_burnout_tool,
        create_calendar_event_tool,
        reschedule_calendar_event_tool,
        cancel_calendar_event_tool,
    ]
    print("[INFO] All 10 LangChain tools registered successfully.")

except ImportError:
    ALL_TOOLS = []
    print("[WARN] LangChain not installed. ALL_TOOLS is empty. "
          "Install langchain to use the tool wrappers.")


# ── Quick smoke test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    test_employee = sys.argv[1] if len(sys.argv) > 1 else "EMP001"
    test_task     = sys.argv[2] if len(sys.argv) > 2 else "TASK0001"

    print(f"\n{'='*50}")
    print(f"Testing tools with employee={test_employee}, task={test_task}")
    print('='*50)
    
    print("\n[1] get_employee_profile")
    result = get_employee_profile(test_employee)
    print(json.dumps(result, indent=2, default=_serialize))

    print("\n[2] get_employee_ml_scores")
    result = get_employee_ml_scores(test_employee)
    print(json.dumps(result, indent=2, default=_serialize))

    print("\n[3] get_employee_workload")
    result = get_employee_workload(test_employee)
    print(json.dumps(result, indent=2, default=_serialize))

    print("\n[4] get_task_details")
    result = get_task_details(test_task)
    print(json.dumps(result, indent=2, default=_serialize))

    print("\n[5] find_available_employees")
    result = find_available_employees("Python", limit=3)
    print(json.dumps(result, indent=2, default=_serialize))
    
    print("\n[6] create_calendar_event")
    result = create_calendar_event(test_task, test_employee, "2026-08-10T10:00:00", "2026-08-10T12:00:00")
    print(json.dumps(result, indent=2, default=_serialize))
    
    print("\n[7] reschedule_calendar_event")
    result = reschedule_calendar_event(test_task, test_employee, "2026-08-12T10:00:00", "2026-08-12T12:00:00")
    print(json.dumps(result, indent=2, default=_serialize))
    
    print("\n[8] cancel_calendar_event")
    result = cancel_calendar_event(test_task, test_employee)
    print(json.dumps(result, indent=2, default=_serialize))
    
    print("\nAll tool tests complete.")