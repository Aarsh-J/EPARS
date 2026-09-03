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
