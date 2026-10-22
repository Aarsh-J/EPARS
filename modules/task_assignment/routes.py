"""
modules/task_assignment/routes.py
======================================
Model3, Layer 3 (see modules/ml/task_assignment_predict.py) exposed over HTTP.
Response shape mirrors modules/performance/routes.py and modules/burnout/routes.py:
a listing endpoint for the selector UI, plus scoring endpoints that surface the
composite score's component breakdown for transparency (like score_signals /
justification do for performance/burnout).
"""

from fastapi import APIRouter, HTTPException

from ..ml.task_assignment_features import get_open_tasks
from ..ml.task_assignment_predict import recommend_top_n, score_pair

router = APIRouter(prefix="/task_assignment", tags=["task_assignment"])


@router.get("/tasks")
def list_tasks():
    """Open (not completed/cancelled) tasks for the selector UI."""
    try:
        rows = get_open_tasks()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    for row in rows:
        row["due_date"] = row["due_date"].isoformat() if row.get("due_date") else None
    return rows


@router.get("/score")
def score(task_id: str, employee_id: str):
    """Score a single (task, employee) pair — works for pairs with no assignment history."""
    try:
        return score_pair(task_id, employee_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommend/{task_id}")
def recommend(task_id: str, top_n: int = 3):
    """Rank every employee against a task, return the top N candidates."""
    try:
        return recommend_top_n(task_id, top_n=top_n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


KANBAN_STATUS_TO_DB = {
    "todo": "Not Started",
    "in_progress": "In Progress",
    "in_review": "In Review",
    "done": "Completed",
    "Not Started": "Not Started",
    "In Progress": "In Progress",
    "In Review": "In Review",
    "Completed": "Completed",
    "Blocked": "Blocked",
}


@router.post("/tasks/{task_id}/status")
def update_task_status(task_id: str, payload: dict):
    """Update task status in PostgreSQL database using canonical schema values."""
    raw_status = payload.get("status")
    if not raw_status:
        raise HTTPException(status_code=400, detail="Missing 'status' in request body")

    # Map frontend column IDs to the database table's canonical status values
    db_status = KANBAN_STATUS_TO_DB.get(raw_status, raw_status)

    try:
        from db import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tasks SET status = %s, last_updated = NOW() WHERE task_id = %s",
                    (db_status, task_id),
                )
                conn.commit()
        return {"status": "success", "task_id": task_id, "new_status": db_status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


