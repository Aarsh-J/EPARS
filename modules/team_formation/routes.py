"""
modules/team_formation/routes.py
====================================
Model4 (team formation + composition anomaly detector) exposed over HTTP.
Same shape as modules/task_assignment/routes.py: a listing endpoint for the
selector UI plus scoring endpoints that expose the score breakdown.
Recommendations are temporary; only the explicit confirmation endpoint writes.
"""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg2.errors import SerializationFailure, UniqueViolation

from ..ml.team_formation_features import list_projects_with_open_tasks
from ..ml.team_formation_predict import (
    InfeasibleTeamFormationError,
    TeamFormationSearchExhaustedError,
    check_composition,
    recommend_teams,
)
from .persistence import ConfirmationError, confirm_team_formation

router = APIRouter(prefix="/team_formation", tags=["team_formation"])
logger = logging.getLogger(__name__)


class TeamFormationConfirmationRequest(BaseModel):
    recommendation: dict
    team_lead_id: str = Field(..., min_length=1, max_length=20)

    class Config:
        extra = "forbid"


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
    task_ids: str | None = Query(
        None,
        description=(
            "Optional comma-separated task_ids; if provided, it must include every "
            "open project task."
        ),
    ),
):
    """Recommend fixed-size rosters with one eligible assignee per open task."""
    try:
        ids = [t.strip() for t in task_ids.split(",") if t.strip()] if task_ids else None
        return recommend_teams(project_id, top_m=top_m, num_teams=num_teams, task_ids=ids)
    except TeamFormationSearchExhaustedError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except InfeasibleTeamFormationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm/{project_id}", status_code=201)
def confirm(project_id: str, payload: TeamFormationConfirmationRequest):
    """Persist a manager-approved recommendation and selected team lead."""
    try:
        return confirm_team_formation(
            project_id,
            payload.recommendation,
            payload.team_lead_id,
        )
    except ConfirmationError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except HTTPException:
        raise
    except (SerializationFailure, UniqueViolation) as e:
        logger.info("Concurrent Team Formation confirmation conflict for %s: %s", project_id, e)
        raise HTTPException(
            status_code=409,
            detail="Concurrent confirmation conflict; reload the project and retry.",
        ) from e
    except Exception as e:
        logger.exception("Team formation confirmation failed for project %s", project_id)
        raise HTTPException(
            status_code=500,
            detail="Team formation confirmation failed; the transaction was rolled back.",
        ) from e


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
