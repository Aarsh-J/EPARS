"""
ePARS — Agent Tool Functions (Step 2)
=======================================
These are the "hands" of the Agentic AI.
Each function queries your PostgreSQL tables and returns
a clean Python dict that the LLM agent can reason over.

All tools are also wrapped as LangChain Tool objects at
the bottom of this file, ready to plug into your agent.

Tables used (from your schema):
  - employees
  - tasks
  - task_assignments
  - workload_history
  - burnout_indicators
  - performance_reviews
  - team_formations
"""

import json
from datetime import date, datetime
from decimal import Decimal
from db import get_connection

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
    """
    Returns the full profile of a single employee including their skills,
    availability, performance history, and well-being indicators.

    Args:
        employee_id: e.g. "EMP001"

    Returns:
        Dict with all key employee fields, or {"error": "..."} on failure.

    Example return:
        {
          "employee_id": "EMP042",
          "full_name": "Priya Sharma",
          "department": "Engineering",
          "role": "Software Engineer",
          "seniority_level": "Mid",
          "primary_skills": "Python, Django, REST APIs",
          "secondary_skills": "Docker, PostgreSQL",
          "weekly_capacity_hours": 40,
          "is_available": true,
          "current_project_count": 2,
          "burnout_risk_score": 38.5,
          "stress_level": "Low",
          "historical_performance_score": 74.2,
          "average_task_completion_rate": 0.88,
          "collaboration_score": 7.2,
          "leadership_potential": 6.5
        }
    """
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
    """
    Returns the latest PEM (performance) score and WBP (burnout) score
    for a given employee, along with their risk category and trend.

    Args:
        employee_id: e.g. "EMP001"

    Returns:
        {
          "employee_id": "EMP042",
          "pem_score": 74.5,
          "performance_rating": "Good",
          "pem_review_date": "2025-10-01",
          "burnout_score": 0.42,
          "burnout_category": "Moderate",
          "burnout_trend": "Worsening",
          "intervention_urgency": "Medium",
          "predicted_burnout_30days": 0.55
        }
    """
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
    """
    Returns the current active task count, estimated active hours,
    and the last 7 days of workload history for an employee.

    Args:
        employee_id: e.g. "EMP001"

    Returns:
        {
          "employee_id": "EMP042",
          "active_task_count": 3,
          "total_estimated_hours_remaining": 28.5,
          "weekly_capacity_hours": 40,
          "capacity_used_percent": 71.25,
          "recent_avg_hours_per_day": 8.4,
          "recent_avg_overtime_hours": 1.2,
          "recent_avg_stress_level": "Medium"
        }
    """
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
    """
    Returns full details of a task — its required skills, priority,
    deadline, estimated effort, and current assignment status.

    Args:
        task_id: e.g. "TASK0042"

    Returns:
        {
          "task_id": "TASK0042",
          "project_id": "PROJ010",
          "task_type": "Development",
          "priority": "High",
          "complexity": "Medium",
          "required_skills": "Python, REST APIs",
          "required_role": "Software Engineer",
          "required_seniority": "Mid",
          "estimated_hours": 16.0,
          "due_date": "2025-11-15",
          "status": "Not Started",
          "assigned_to": null,
          "is_overdue": false
        }
    """
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

def find_available_employees(required_skills: str, required_role: str = "",
                              required_seniority: str = "", limit: int = 5) -> list:
    """
    Finds employees who are available and have matching skills,
    ranked by performance score descending.

    Args:
        required_skills  : Comma-separated skill string e.g. "Python, Django"
        required_role    : Optional role filter e.g. "Software Engineer"
        required_seniority: Optional seniority filter e.g. "Senior"
        limit            : Max number of candidates to return (default 5)

    Returns:
        List of candidate dicts with key scores for the agent to evaluate.
    """
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

def assign_task(task_id: str, employee_id: str,
                assignment_method: str = "agentic_ai",
                skill_match_score: float = 0.0) -> dict:
    """
    Creates a task assignment record and updates the task's assigned_to field.

    Args:
        task_id           : e.g. "TASK0042"
        employee_id       : e.g. "EMP042"
        assignment_method : How the assignment was made (default: "agentic_ai")
        skill_match_score : 0–100 score of how well skills match (default 0)

    Returns:
        {"success": True, "assignment_id": "...", "message": "..."}
        or {"success": False, "error": "..."}
    """
    insert_sql = """
        INSERT INTO task_assignments (
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
                # Insert assignment record
                cur.execute(insert_sql, (
                    task_id, employee_id, assignment_method, skill_match_score, task_id
                ))
                row = cur.fetchone()
                assignment_id = row["assignment_id"] if row else None

                # Update task status
                cur.execute(update_task_sql, (employee_id, task_id))

                # Update employee project count
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
    """
    Logs a burnout intervention alert in the burnout_indicators table
    and reduces the employee's is_available flag if urgency is High.

    Args:
        employee_id        : e.g. "EMP042"
        burnout_score      : current WBP score (0.0–1.0)
        urgency            : "Low", "Medium", "High", "Critical"
        recommended_action : Free-text recommendation from the agent

    Returns:
        {"success": True, "message": "..."} or {"success": False, "error": "..."}
    """
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
# LANGCHAIN TOOL WRAPPERS
# Add these to your agent's `tools` list in Step 3.
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

    # Collect all tools for easy import in Step 3
    ALL_TOOLS = [
        employee_profile_tool,
        ml_scores_tool,
        workload_tool,
        task_details_tool,
        find_employees_tool,
        assign_task_tool,
        flag_burnout_tool,
    ]

    print("[INFO] All 7 LangChain tools registered successfully.")

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

    print("\nAll tool tests complete.")
