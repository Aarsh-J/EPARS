"""Manager-confirmed Team Formation persistence."""

import math
import sys
from pathlib import Path

from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = REPO_ROOT / "src" / "epars_agent" / "agent"
SRC_DIR = REPO_ROOT / "src"
for candidate in (str(AGENT_DIR), str(SRC_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

try:
    from db import get_connection
except ModuleNotFoundError:  # pragma: no cover - non-legacy import path
    from epars_agent.agent.db import get_connection

from ..ml.team_formation_predict import (
    InfeasibleTeamFormationError,
    _candidate_lists,
)
from ..task_assignment.routes import _apply_assignment


class ConfirmationError(ValueError):
    """A manager-confirmation request is invalid or stale."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


class ProjectNotFoundError(ConfirmationError):
    def __init__(self, project_id: str):
        super().__init__(f"Project {project_id!r} was not found.", 404)


class DuplicateConfirmationError(ConfirmationError):
    def __init__(self):
        super().__init__(
            "This project already has an active AI formation.",
            409,
        )


def _validate_recommendation_shape(
    project_id: str,
    recommendation: dict,
    team_lead_id: str,
) -> tuple[list[str], list[dict], int]:
    if not isinstance(recommendation, dict):
        raise ConfirmationError("recommendation must be an object.")
    if recommendation.get("project_id") != project_id:
        raise ConfirmationError("Recommendation does not belong to the requested project.")
    roster = recommendation.get("team_member_ids")
    if not isinstance(roster, list) or not roster:
        raise ConfirmationError("Recommendation must include a non-empty team_member_ids list.")
    if any(not isinstance(member_id, str) or not member_id.strip() for member_id in roster):
        raise ConfirmationError("Recommendation contains a missing or invalid employee ID.")
    if len(roster) != len(set(roster)):
        raise ConfirmationError("Recommendation contains duplicate employees.")
    if not isinstance(team_lead_id, str) or team_lead_id not in roster:
        raise ConfirmationError("Selected team lead must belong to the recommended roster.")

    assignments = recommendation.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        raise ConfirmationError("Recommendation must include task assignments.")
    task_ids = []
    for assignment in assignments:
        if not isinstance(assignment, dict):
            raise ConfirmationError("Recommendation contains an invalid assignment record.")
        task_id = assignment.get("task_id")
        employee_id = assignment.get("employee_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ConfirmationError("Recommendation contains an assignment without a task ID.")
        if not isinstance(employee_id, str) or not employee_id.strip():
            raise ConfirmationError("Recommendation contains an assignment without an employee ID.")
        task_ids.append(task_id)
        if employee_id not in roster:
            raise ConfirmationError(
                f"Task {task_id!r} is assigned to employee {employee_id!r} outside the roster."
            )
    if len(task_ids) != len(set(task_ids)):
        raise ConfirmationError("Recommendation contains duplicate task assignments.")
    if set(assignment["employee_id"] for assignment in assignments) != set(roster):
        raise ConfirmationError("Every roster member must receive at least one task.")

    team_size = recommendation.get("team_size")
    if isinstance(team_size, bool) or not isinstance(team_size, int) or team_size != len(roster):
        raise ConfirmationError("Recommendation team_size does not match its unique roster.")
    candidate_limit = recommendation.get("candidate_limit")
    if (
        isinstance(candidate_limit, bool)
        or not isinstance(candidate_limit, int)
        or not 1 <= candidate_limit <= 10
    ):
        raise ConfirmationError("Recommendation has an invalid candidate_limit.")
    if "project_status" not in recommendation:
        raise ConfirmationError("Recommendation is missing its project state.")
    task_snapshot_fields = (
        "task_status",
        "task_assigned_to",
        "task_estimated_hours",
        "task_required_skills",
    )
    if any(
        field not in assignment
        for assignment in assignments
        for field in task_snapshot_fields
    ):
        raise ConfirmationError("Recommendation is missing task state; regenerate it.")
    return roster, assignments, candidate_limit


def _valid_project_team_size(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(numeric) or not numeric.is_integer() or numeric < 1:
        return None
    return int(numeric)


def confirm_team_formation(
    project_id: str,
    recommendation: dict,
    team_lead_id: str,
) -> dict:
    """Validate a recommendation against live data and persist it atomically."""
    roster, assignments, candidate_limit = _validate_recommendation_shape(
        project_id, recommendation, team_lead_id
    )
    assignments_by_task = {assignment["task_id"]: assignment for assignment in assignments}
    member_ids = sorted(member_id for member_id in roster if member_id != team_lead_id)
    stored_member_ids = ",".join(member_ids)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            cur.execute(
                """
                SELECT project_id, project_name, current_status, team_size
                FROM projects
                WHERE project_id = %s
                FOR UPDATE
                """,
                (project_id,),
            )
            project = cur.fetchone()
            if not project:
                raise ProjectNotFoundError(project_id)
            authoritative_team_size = _valid_project_team_size(project.get("team_size"))
            if authoritative_team_size is None:
                raise ConfirmationError(
                    f"Project {project_id!r} has a missing or invalid team_size."
                )
            if authoritative_team_size != len(roster):
                raise ConfirmationError(
                    "Recommendation roster size no longer matches projects.team_size.",
                    409,
                )
            if recommendation.get("project_status") != project.get("current_status"):
                raise ConfirmationError("Project state changed; regenerate the recommendation.", 409)

            cur.execute(
                """
                SELECT task_id, status, assigned_to, estimated_hours, required_skills
                FROM tasks
                WHERE project_id = %s
                  AND (status IS NULL OR status NOT IN ('Completed', 'Cancelled'))
                ORDER BY task_id
                FOR UPDATE
                """,
                (project_id,),
            )
            open_tasks = cur.fetchall()
            current_task_ids = {row["task_id"] for row in open_tasks}
            if current_task_ids != set(assignments_by_task):
                raise ConfirmationError(
                    "Open project tasks changed; regenerate the recommendation.",
                    409,
                )
            task_rows = {row["task_id"]: row for row in open_tasks}
            for task_id, assignment in assignments_by_task.items():
                current = task_rows[task_id]
                try:
                    same_hours = (
                        assignment["task_estimated_hours"] is None
                        and current.get("estimated_hours") is None
                    ) or (
                        assignment["task_estimated_hours"] is not None
                        and current.get("estimated_hours") is not None
                        and float(assignment["task_estimated_hours"])
                        == float(current["estimated_hours"])
                    )
                except (TypeError, ValueError, OverflowError):
                    same_hours = False
                if (
                    assignment["task_status"] != current.get("status")
                    or assignment["task_assigned_to"] != current.get("assigned_to")
                    or not same_hours
                    or assignment["task_required_skills"] != current.get("required_skills")
                ):
                    raise ConfirmationError(
                        f"Task {task_id!r} changed state; regenerate the recommendation.",
                        409,
                    )

            cur.execute(
                """
                SELECT employee_id
                FROM employees
                WHERE employee_id = ANY(%s)
                FOR KEY SHARE
                """,
                (roster,),
            )
            known_employee_ids = {row["employee_id"] for row in cur.fetchall()}
            if known_employee_ids != set(roster):
                unknown = sorted(set(roster) - known_employee_ids)
                raise ConfirmationError(
                    f"Recommendation contains unknown employees: {unknown}."
                )

            try:
                candidates_per_task = _candidate_lists(
                    [{"task_id": task_id} for task_id in sorted(current_task_ids)],
                    candidate_limit,
                )
            except InfeasibleTeamFormationError as exc:
                raise ConfirmationError(
                    f"Recommendation is stale; Model 3 no longer returns candidates: {exc}",
                    409,
                ) from exc
            for task_id, assignment in assignments_by_task.items():
                eligible_ids = {
                    candidate["employee_id"]
                    for candidate in candidates_per_task[task_id]
                }
                if assignment["employee_id"] not in eligible_ids:
                    raise ConfirmationError(
                        f"Employee {assignment['employee_id']!r} is no longer an eligible "
                        f"Model 3 candidate for task {task_id!r}.",
                        409,
                    )

            cur.execute("LOCK TABLE team_formations IN SHARE ROW EXCLUSIVE MODE")
            cur.execute(
                """
                SELECT team_id
                FROM team_formations
                WHERE project_id = %s
                  AND formation_method = 'AI-Recommended'
                  AND team_status = 'Active'
                FOR UPDATE
                """,
                (project_id,),
            )
            if cur.fetchone():
                raise DuplicateConfirmationError()

            assignment_ids = {}
            for task_id in sorted(assignments_by_task):
                assignment_ids[task_id] = _apply_assignment(
                    cur,
                    task_id,
                    assignments_by_task[task_id]["employee_id"],
                    assignment_method="AI-Recommended",
                )

            cur.execute(
                """
                SELECT COALESCE(MAX(SUBSTRING(team_id FROM 5)::BIGINT), 0) AS max_num
                FROM team_formations
                WHERE team_id ~ '^TEAM[0-9]+$'
                """
            )
            team_id = f"TEAM{int(cur.fetchone()['max_num']) + 1:04d}"
            project_name = (project.get("project_name") or project_id).strip()
            team_name = f"{project_name} Team"[:200]
            cur.execute(
                """
                INSERT INTO team_formations (
                    team_id, team_name, project_id, formation_date,
                    formation_method, team_lead_id, member_ids, team_size,
                    team_status, created_at, last_updated
                )
                VALUES (
                    %s, %s, %s, CURRENT_DATE, 'AI-Recommended',
                    %s, %s, %s, 'Active', NOW(), NOW()
                )
                """,
                (
                    team_id,
                    team_name,
                    project_id,
                    team_lead_id,
                    stored_member_ids,
                    authoritative_team_size,
                ),
            )

    return {
        "confirmed": True,
        "team_id": team_id,
        "project_id": project_id,
        "team_size": authoritative_team_size,
        "team_lead_id": team_lead_id,
        "member_ids": member_ids,
        "assignment_ids": assignment_ids,
    }
