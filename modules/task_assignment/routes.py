"""
Task assignment and Kanban board API routes.

Expected module location:
    modules/task_assignment/routes.py

The board endpoints use the existing public tables:
    tasks, projects, employees
"""

import sys
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg2 import IntegrityError

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = REPO_ROOT / "src" / "epars_agent" / "agent"
SRC_DIR = REPO_ROOT / "src"

for candidate in (str(AGENT_DIR), str(SRC_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

try:
    from db import get_connection
except ModuleNotFoundError:  # pragma: no cover - safety fallback for non-legacy imports
    from epars_agent.agent.db import get_connection

from ..ml.task_assignment_features import get_open_tasks
from ..ml.task_assignment_predict import recommend_top_n, score_pair

router = APIRouter(prefix="/task_assignment", tags=["task_assignment"])

TaskStatus = Literal["Not Started", "In Progress", "In Review", "Blocked", "Completed"]
TaskPriority = Literal["Critical", "High", "Medium", "Low"]


class TaskCreate(BaseModel):
    task_name: str = Field(..., min_length=1, max_length=200)
    task_description: Optional[str] = None
    project_id: Optional[str] = Field(default=None, min_length=1, max_length=20)
    priority: Optional[TaskPriority] = "Medium"
    status: TaskStatus = "Not Started"
    assigned_to: Optional[str] = Field(default=None, min_length=1, max_length=20)
    story_points: Optional[int] = Field(default=None, ge=0, le=100)
    due_date: Optional[date] = None
    required_skills: Optional[str] = None

    class Config:
        extra = "forbid"


class TaskUpdate(BaseModel):
    task_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    task_description: Optional[str] = None
    project_id: Optional[str] = Field(default=None, min_length=1, max_length=20)
    priority: Optional[TaskPriority] = None
    assigned_to: Optional[str] = Field(default=None, min_length=1, max_length=20)
    story_points: Optional[int] = Field(default=None, ge=0, le=100)
    due_date: Optional[date] = None
    required_skills: Optional[str] = None

    class Config:
        extra = "forbid"


class TaskAssignmentRequest(BaseModel):
    employee_id: Optional[str] = Field(..., min_length=1, max_length=20)

    class Config:
        extra = "forbid"


class TaskStatusUpdate(BaseModel):
    status: str

    class Config:
        extra = "forbid"


TASK_SELECT = """
    SELECT
        t.task_id,
        t.task_name,
        t.task_description,
        t.project_id,
        p.project_name,
        t.priority,
        t.task_type,
        t.required_role,
        t.required_skills,
        t.assigned_to,
        NULLIF(TRIM(CONCAT_WS(' ', e.first_name, e.last_name)), '') AS assignee_name,
        t.status,
        t.completion_percentage,
        t.story_points,
        t.estimated_hours,
        t.start_date,
        t.due_date,
        t.actual_completion_date,
        t.created_at,
        t.last_updated
    FROM tasks t
    LEFT JOIN projects p ON p.project_id = t.project_id
    LEFT JOIN employees e ON e.employee_id = t.assigned_to
"""


def _validate_project(cur, project_id):
    if project_id is None:
        return
    cur.execute("SELECT 1 FROM projects WHERE project_id = %s", (project_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail=f"Project {project_id} was not found.")


def _validate_employee(cur, employee_id):
    if employee_id is None:
        return
    cur.execute("SELECT 1 FROM employees WHERE employee_id = %s", (employee_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} was not found.")


def _fetch_task(cur, task_id):
    cur.execute(f"{TASK_SELECT} WHERE t.task_id = %s", (task_id,))
    row = cur.fetchone()
    if not row:
        return None

    task = dict(row)
    for field in (
        "start_date",
        "due_date",
        "actual_completion_date",
        "created_at",
        "last_updated",
    ):
        task[field] = _iso(task.get(field))
    return task


def _next_task_id(cur):
    cur.execute(
        """
        SELECT COALESCE(MAX(SUBSTRING(task_id FROM 4)::BIGINT), 0) AS max_num
        FROM tasks
        WHERE task_id ~ '^TSK[0-9]+$'
        """
    )
    return f"TSK{int(cur.fetchone()['max_num']) + 1:04d}"


def _next_assignment_id(cur):
    cur.execute(
        """
        SELECT COALESCE(MAX(SUBSTRING(assignment_id FROM 4)::BIGINT), 0) AS max_num
        FROM task_assignments
        WHERE assignment_id ~ '^ASG[0-9]+$'
        """
    )
    return f"ASG{int(cur.fetchone()['max_num']) + 1:04d}"


def _apply_assignment(cur, task_id, employee_id):
    cur.execute(
        "SELECT project_id, assigned_to, status FROM tasks WHERE task_id = %s FOR UPDATE",
        (task_id,),
    )
    task = cur.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} was not found.")

    if employee_id is None:
        cur.execute(
            "UPDATE tasks SET assigned_to = NULL, last_updated = NOW() WHERE task_id = %s",
            (task_id,),
        )
        return None

    _validate_employee(cur, employee_id)

    if task["assigned_to"] == employee_id:
        cur.execute(
            """
            SELECT assignment_id
            FROM task_assignments
            WHERE task_id = %s
              AND employee_id = %s
              AND COALESCE(completion_status, 'Assigned')
                    NOT IN ('Completed', 'Cancelled', 'Reassigned')
            ORDER BY assignment_date DESC NULLS LAST, created_at DESC NULLS LAST
            LIMIT 1
            """,
            (task_id, employee_id),
        )
        existing = cur.fetchone()
        if existing:
            return existing["assignment_id"]

    cur.execute(
        """
        UPDATE task_assignments
        SET completion_status = 'Reassigned',
            last_updated = NOW()
        WHERE task_id = %s
          AND COALESCE(completion_status, 'Assigned')
                NOT IN ('Completed', 'Cancelled', 'Reassigned')
        """,
        (task_id,),
    )

    assignment_id = None
    for _ in range(100):
        candidate_id = _next_assignment_id(cur)
        cur.execute(
            """
            INSERT INTO task_assignments (
                assignment_id,
                task_id,
                employee_id,
                project_id,
                assignment_date,
                assignment_method,
                completion_status,
                created_at,
                last_updated
            )
            VALUES (
                %s, %s, %s, %s, CURRENT_DATE, 'Manual',
                CASE WHEN %s = 'Completed' THEN 'Completed' ELSE 'Assigned' END,
                NOW(), NOW()
            )
            ON CONFLICT (assignment_id) DO NOTHING
            RETURNING assignment_id
            """,
            (candidate_id, task_id, employee_id, task["project_id"], task["status"]),
        )
        inserted = cur.fetchone()
        if inserted:
            assignment_id = inserted["assignment_id"]
            break
    if assignment_id is None:
        raise HTTPException(status_code=503, detail="Could not allocate a unique assignment ID.")

    cur.execute(
        """
        UPDATE tasks
        SET assigned_to = %s,
            assigned_date = CURRENT_DATE,
            last_updated = NOW()
        WHERE task_id = %s
        """,
        (employee_id, task_id),
    )
    return assignment_id


def _task_reference_types(cur, task_id):
    cur.execute(
        """
        SELECT
            EXISTS(SELECT 1 FROM task_assignments WHERE task_id = %s) AS assignment_history,
            EXISTS(SELECT 1 FROM schedules WHERE related_id = %s) AS scheduled_events,
            EXISTS(SELECT 1 FROM feedback WHERE related_task_id = %s) AS feedback_records,
            EXISTS(
                SELECT 1 FROM task_reassignment_recommendations WHERE task_id = %s
            ) AS reassignment_recommendations,
            EXISTS(
                SELECT 1 FROM tasks child
                WHERE child.task_id <> %s AND child.parent_task_id = %s
            ) AS child_tasks,
            EXISTS(
                SELECT 1
                FROM tasks other_task,
                     unnest(string_to_array(COALESCE(other_task.dependent_task_ids, ''), ',')) AS ref
                WHERE other_task.task_id <> %s AND BTRIM(ref) = %s
            ) AS dependent_task_references,
            EXISTS(
                SELECT 1
                FROM tasks other_task,
                     unnest(string_to_array(COALESCE(other_task.blocking_task_ids, ''), ',')) AS ref
                WHERE other_task.task_id <> %s AND BTRIM(ref) = %s
            ) AS blocking_task_references,
            EXISTS(
                SELECT 1
                FROM tasks other_task,
                     unnest(string_to_array(COALESCE(other_task.related_tasks, ''), ',')) AS ref
                WHERE other_task.task_id <> %s AND BTRIM(ref) = %s
            ) AS related_task_references
        """,
        (
            task_id,
            task_id,
            task_id,
            task_id,
            task_id,
            task_id,
            task_id,
            task_id,
            task_id,
            task_id,
            task_id,
            task_id,
        ),
    )
    references = dict(cur.fetchone())
    return [name.replace("_", " ") for name, exists in references.items() if exists]


# ---------------------------------------------------------------------------
# Existing task-assignment / ML endpoints
# ---------------------------------------------------------------------------

@router.get("/tasks")
def list_tasks():
    """Open tasks for the existing task-assignment selector."""
    try:
        rows = get_open_tasks()
        for row in rows:
            if row.get("due_date"):
                row["due_date"] = row["due_date"].isoformat()
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/score")
def score(task_id: str, employee_id: str):
    """Score one task/employee pair."""
    try:
        return score_pair(task_id, employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/recommend/{task_id}")
def recommend(task_id: str, top_n: int = Query(3, ge=1, le=50)):
    """Return the top employee recommendations for a task."""
    try:
        return recommend_top_n(task_id, top_n=top_n)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/tasks", status_code=201)
def create_task(payload: TaskCreate):
    task_name = payload.task_name.strip()
    if not task_name:
        raise HTTPException(status_code=422, detail="task_name cannot be blank.")

    values = payload.dict()
    values["task_name"] = task_name

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _validate_project(cur, values["project_id"])
                _validate_employee(cur, values["assigned_to"])

                task_id = None
                for _ in range(100):
                    candidate_id = _next_task_id(cur)
                    cur.execute(
                        """
                        INSERT INTO tasks (
                            task_id,
                            task_name,
                            task_description,
                            project_id,
                            priority,
                            status,
                            completion_percentage,
                            story_points,
                            due_date,
                            required_skills,
                            created_at,
                            last_updated,
                            actual_completion_date
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s,
                            CASE WHEN %s = 'Completed' THEN 100 ELSE 0 END,
                            %s, %s, %s, NOW(), NOW(),
                            CASE WHEN %s = 'Completed' THEN CURRENT_DATE ELSE NULL END
                        )
                        ON CONFLICT (task_id) DO NOTHING
                        RETURNING task_id
                        """,
                        (
                            candidate_id,
                            values["task_name"],
                            values["task_description"],
                            values["project_id"],
                            values["priority"],
                            values["status"],
                            values["status"],
                            values["story_points"],
                            values["due_date"],
                            values["required_skills"],
                            values["status"],
                        ),
                    )
                    inserted = cur.fetchone()
                    if inserted:
                        task_id = inserted["task_id"]
                        break
                if task_id is None:
                    raise HTTPException(status_code=503, detail="Could not allocate a unique task ID.")

                if values["assigned_to"] is not None:
                    _apply_assignment(cur, task_id, values["assigned_to"])

                task = _fetch_task(cur, task_id)
        return {"task": task}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create task: {exc}")


@router.put("/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdate):
    values = payload.dict(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="At least one supported task field is required.")
    if "task_name" in values and (values["task_name"] is None or not values["task_name"].strip()):
        raise HTTPException(status_code=422, detail="task_name cannot be blank.")

    column_map = {
        "task_name": "task_name",
        "task_description": "task_description",
        "project_id": "project_id",
        "priority": "priority",
        "story_points": "story_points",
        "due_date": "due_date",
        "required_skills": "required_skills",
    }

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT task_id FROM tasks WHERE task_id = %s FOR UPDATE", (task_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail=f"Task {task_id} was not found.")

                if "project_id" in values:
                    _validate_project(cur, values["project_id"])

                has_assignment_update = "assigned_to" in values
                assigned_to = values.pop("assigned_to", None)
                if values:
                    assignments = [f"{column_map[field]} = %s" for field in values]
                    params = list(values.values()) + [task_id]
                    cur.execute(
                        f"""
                        UPDATE tasks
                        SET {', '.join(assignments)}, last_updated = NOW()
                        WHERE task_id = %s
                        """,
                        params,
                    )

                if has_assignment_update:
                    _apply_assignment(cur, task_id, assigned_to)

                task = _fetch_task(cur, task_id)
        return {"task": task}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not update task: {exc}")


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT task_id FROM tasks WHERE task_id = %s FOR UPDATE", (task_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail=f"Task {task_id} was not found.")

                references = _task_reference_types(cur, task_id)
                if references:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Task cannot be deleted while related records exist: "
                            + ", ".join(references)
                            + "."
                        ),
                    )

                cur.execute("DELETE FROM tasks WHERE task_id = %s RETURNING task_id", (task_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail=f"Task {task_id} was not found.")
        return {"deleted": True, "task_id": task_id}
    except HTTPException:
        raise
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Could not delete task because a database constraint prevents deletion: {exc}",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not delete task: {exc}")


@router.post("/tasks/{task_id}/assign")
def assign_task_to_employee(task_id: str, payload: TaskAssignmentRequest):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                assignment_id = _apply_assignment(cur, task_id, payload.employee_id)
                task = _fetch_task(cur, task_id)
        return {
            "task": task,
            "assignment": (
                {
                    "assignment_id": assignment_id,
                    "task_id": task_id,
                    "employee_id": payload.employee_id,
                }
                if assignment_id
                else None
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not assign task: {exc}")


# ---------------------------------------------------------------------------
# Kanban board endpoints
# ---------------------------------------------------------------------------

BOARD_STATUSES = (
    "Not Started",
    "In Progress",
    "In Review",
    "Blocked",
    "Completed",
)

KANBAN_STATUS_TO_DB = {
    "todo": "Not Started",
    "in_progress": "In Progress",
    "in_review": "In Review",
    "blocked": "Blocked",
    "done": "Completed",
    "Not Started": "Not Started",
    "In Progress": "In Progress",
    "In Review": "In Review",
    "Blocked": "Blocked",
    "Completed": "Completed",
}


def _iso(value):
    """Convert date/datetime values to JSON-friendly strings."""
    return value.isoformat() if value is not None else None


@router.get("/board_projects")
def get_board_projects():
    """
    Return projects for the project selector.

    Projects are returned even when they currently have no tasks.
    """
    sql = """
        SELECT
            p.project_id,
            p.project_name,
            p.current_status,
            p.completion_percentage,
            p.actual_end_date,
            p.project_manager_id,
            COUNT(t.task_id)::int AS task_count
        FROM projects p
        LEFT JOIN tasks t ON t.project_id = p.project_id
        GROUP BY p.project_id, p.project_name, p.project_manager_id
        ORDER BY p.project_name NULLS LAST, p.project_id
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()

        return [dict(row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load projects: {exc}")


@router.get("/board_employees")
def get_board_employees():
    """Return employees for the employee filter and assignee selector."""
    sql = """
        SELECT
            e.employee_id,
            e.first_name,
            e.last_name,
            e.role,
            EXISTS (
                SELECT 1
                FROM projects p
                WHERE p.project_manager_id = e.employee_id
            ) AS is_project_manager
        FROM employees e
        ORDER BY e.first_name NULLS LAST, e.last_name NULLS LAST, e.employee_id
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()

        result = []
        for row in rows:
            item = dict(row)
            item["full_name"] = " ".join(
                part for part in (item.get("first_name"), item.get("last_name")) if part
            ).strip() or item["employee_id"]
            result.append(item)

        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load employees: {exc}")


@router.get("/board")
def get_kanban_board(
    project_ids: Optional[list[str]] = Query(default=None),
    include_other_tasks: bool = False,
    project_view: Literal["active", "previous"] = "active",
    employee_id: Optional[str] = None,
    unassigned_only: bool = False,
    date_filter: str = "all",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search: Optional[str] = None,
    status_filter: Optional[TaskStatus] = None,
    priority_filter: Optional[TaskPriority] = None,
    high_priority_only: bool = False,
    sort_by: str = "due_date",
    sort_order: str = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    Return filtered tasks, status counts and pagination metadata.

    Project selection is required. Other Tasks are rows with project_id IS NULL.
    For an employee who manages projects, visibility is the union of:
      - tasks assigned directly to that employee
      - tasks belonging to projects managed by that employee.
    """
    selected_projects = list(dict.fromkeys(project_ids or []))

    # No selection means an intentionally empty board.
    if not selected_projects and not include_other_tasks:
        return {
            "tasks": [],
            "status_counts": {status: 0 for status in BOARD_STATUSES},
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": 0,
                "total_pages": 0,
            },
        }

    conditions = []
    params = []

    project_parts = []
    if selected_projects:
        project_parts.append("t.project_id = ANY(%s)")
        params.append(selected_projects)
    if include_other_tasks:
        project_parts.append("t.project_id IS NULL")

    conditions.append("(" + " OR ".join(project_parts) + ")")

    if project_view == "previous":
        conditions.append(
            "p.current_status = 'Completed' "
            "AND p.completion_percentage = 100 "
            "AND p.actual_end_date IS NOT NULL"
        )
    else:
        conditions.append(
            "(t.project_id IS NULL OR p.current_status IS DISTINCT FROM 'Completed')"
        )

    if employee_id:
        conditions.append(
            """
            (
                t.assigned_to = %s
                OR t.project_id IN (
                    SELECT p.project_id
                    FROM projects p
                    WHERE p.project_manager_id = %s
                )
            )
            """
        )
        params.extend([employee_id, employee_id])

    if unassigned_only:
        conditions.append("t.assigned_to IS NULL")

    # Use the Indian business date for date-based filters.
    ist_today = "(NOW() AT TIME ZONE 'Asia/Kolkata')::date"

    if date_filter == "today":
        conditions.append(f"t.due_date = {ist_today}")
    elif date_filter == "this_week":
        conditions.append(
            f"t.due_date >= date_trunc('week', {ist_today})::date "
            f"AND t.due_date < (date_trunc('week', {ist_today})::date + INTERVAL '7 days')"
        )
    elif date_filter == "overdue":
        conditions.append(
            f"t.due_date < {ist_today} AND t.status <> 'Completed'"
        )
    elif date_filter == "upcoming":
        conditions.append(
            f"t.due_date > {ist_today} "
            f"AND t.due_date <= ({ist_today} + INTERVAL '7 days')"
        )
    elif date_filter == "due_soon":
        conditions.append(
            f"t.due_date >= {ist_today} "
            f"AND t.due_date <= ({ist_today} + INTERVAL '3 days') "
            "AND t.status <> 'Completed'"
        )
    elif date_filter == "custom":
        if not start_date or not end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date and end_date are required for custom date filtering.",
            )
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date cannot be after end_date.",
            )
        conditions.append("t.due_date BETWEEN %s AND %s")
        params.extend([start_date, end_date])
    elif date_filter != "all":
        raise HTTPException(
            status_code=400,
            detail="date_filter must be all, today, this_week, overdue, upcoming, due_soon, or custom.",
        )

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append("(t.task_name ILIKE %s OR t.task_id ILIKE %s)")
        params.extend([term, term])

    if status_filter:
        conditions.append("t.status = %s")
        params.append(status_filter)

    if priority_filter:
        conditions.append("t.priority = %s")
        params.append(priority_filter)

    if high_priority_only:
        conditions.append("t.priority IN ('Critical', 'High')")

    where_clause = " AND ".join(f"({condition})" for condition in conditions)

    # Never interpolate user-provided sort values into SQL.
    sort_columns = {
        "due_date": "t.due_date",
        "priority": "t.priority",
        "task_name": "t.task_name",
        "created_at": "t.created_at",
        "last_updated": "t.last_updated",
        "status": "t.status",
    }
    if sort_by not in sort_columns:
        raise HTTPException(status_code=400, detail="Invalid sort_by value.")
    if sort_order.lower() not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_order must be asc or desc.")

    order_clause = (
        f"{sort_columns[sort_by]} {sort_order.upper()} NULLS LAST, t.task_id ASC"
    )

    offset = (page - 1) * page_size

    base_from = """
        FROM tasks t
        LEFT JOIN projects p ON p.project_id = t.project_id
        LEFT JOIN employees e ON e.employee_id = t.assigned_to
    """

    tasks_sql = f"""
        SELECT
            t.task_id,
            t.task_name,
            t.task_description,
            t.project_id,
            p.project_name,
            t.priority,
            t.task_type,
            t.required_role,
            t.required_skills,
            t.assigned_to,
            NULLIF(
                TRIM(CONCAT_WS(' ', e.first_name, e.last_name)),
                ''
            ) AS assignee_name,
            t.status,
            t.completion_percentage,
            t.story_points,
            t.estimated_hours,
            t.start_date,
            t.due_date,
            t.actual_completion_date,
            t.created_at,
            t.last_updated
        {base_from}
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT %s OFFSET %s
    """

    count_sql = f"""
        SELECT COUNT(*)::int AS total
        {base_from}
        WHERE {where_clause}
    """

    status_sql = f"""
        SELECT t.status, COUNT(*)::int AS task_count
        {base_from}
        WHERE {where_clause}
        GROUP BY t.status
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(count_sql, params)
                total = cur.fetchone()["total"]

                cur.execute(status_sql, params)
                status_rows = cur.fetchall()

                task_params = params + [page_size, offset]
                cur.execute(tasks_sql, task_params)
                task_rows = cur.fetchall()

        status_counts = {status: 0 for status in BOARD_STATUSES}
        for row in status_rows:
            if row["status"] in status_counts:
                status_counts[row["status"]] = row["task_count"]

        tasks = []
        for row in task_rows:
            item = dict(row)
            for field in (
                "start_date",
                "due_date",
                "actual_completion_date",
                "created_at",
                "last_updated",
            ):
                item[field] = _iso(item.get(field))
            tasks.append(item)

        return {
            "tasks": tasks,
            "status_counts": status_counts,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load board tasks: {exc}")


# ---------------------------------------------------------------------------
# Existing status update route (kept compatible with current frontend)
# ---------------------------------------------------------------------------

@router.post("/tasks/{task_id}/status")
def update_task_status(task_id: str, payload: TaskStatusUpdate):
    """Update a task to one of the five statuses confirmed in the database."""
    raw_status = payload.status
    if not raw_status:
        raise HTTPException(status_code=400, detail="Missing 'status' in request body")

    db_status = KANBAN_STATUS_TO_DB.get(raw_status)
    if db_status not in BOARD_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Allowed values: {', '.join(BOARD_STATUSES)}",
        )

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tasks
                    SET status = %s,
                        last_updated = NOW(),
                        completion_percentage = CASE
                            WHEN %s = 'Completed' THEN 100
                            WHEN status = 'Completed'
                                AND %s <> 'Completed'
                                AND completion_percentage = 100 THEN 0
                            ELSE completion_percentage
                        END,
                        actual_completion_date = CASE
                            WHEN %s = 'Completed' THEN COALESCE(actual_completion_date, CURRENT_DATE)
                            WHEN status = 'Completed' AND %s <> 'Completed' THEN NULL
                            ELSE actual_completion_date
                        END
                    WHERE task_id = %s
                    RETURNING task_id
                    """,
                    (
                        db_status,
                        db_status,
                        db_status,
                        db_status,
                        db_status,
                        task_id,
                    ),
                )
                updated = cur.fetchone()
                if not updated:
                    raise HTTPException(status_code=404, detail=f"Task {task_id} was not found.")
                task = _fetch_task(cur, task_id)

        return {"status": "success", "task": task}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
