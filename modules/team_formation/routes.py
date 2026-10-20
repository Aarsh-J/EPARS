"""
modules/team_formation/routes.py
====================================
Model4 (team formation + composition anomaly detector) exposed over HTTP.
Same shape as modules/task_assignment/routes.py: a listing endpoint for the
selector UI plus scoring endpoints that expose the score breakdown.
Read-only — nothing here writes to the database.
"""

from fastapi import APIRouter, HTTPException, Query

from ..ml.team_formation_features import list_projects_with_open_tasks
from ..ml.team_formation_predict import check_composition, recommend_teams

router = APIRouter(prefix="/team_formation", tags=["team_formation"])


@router.get("/projects")
def list_projects(limit: int = 200):
    """Projects that have open tasks, for the selector UI."""
    try:
        return list_projects_with_open_tasks(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommend/{project_id}")
def recommend(
    project_id: str,
    num_teams: int = Query(3, ge=1, le=5),
    top_m: int = Query(5, ge=1, le=10),
    task_ids: str | None = Query(None, description="Optional comma-separated task_ids to restrict the team to"),
):
    """Best teams (one employee per open task) for a project, ranked best-first."""
    try:
        ids = [t.strip() for t in task_ids.split(",") if t.strip()] if task_ids else None
        return recommend_teams(project_id, top_m=top_m, num_teams=num_teams, task_ids=ids)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/composition")
def composition(employee_ids: str = Query(..., description="Comma-separated employee_ids, at least 2")):
    """How typical is this exact roster vs historical teams? Advisory flag + reasons."""
    try:
        ids = [e.strip() for e in employee_ids.split(",") if e.strip()]
        return check_composition(ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
