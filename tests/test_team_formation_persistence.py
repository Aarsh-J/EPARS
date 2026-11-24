import unittest
from unittest.mock import patch

from fastapi import HTTPException
from psycopg2.errors import SerializationFailure

from modules.team_formation import persistence
from modules.team_formation import routes as team_formation_routes
from modules.task_assignment import routes as task_assignment_routes


def recommendation():
    return {
        "project_id": "PRJ001",
        "project_status": "Active",
        "candidate_limit": 5,
        "team_size": 2,
        "team_member_ids": ["EMP001", "EMP002"],
        "assignments": [
            {
                "task_id": "TSK001",
                "task_status": "Not Started",
                "task_assigned_to": None,
                "task_estimated_hours": 3,
                "task_required_skills": "python",
                "employee_id": "EMP001",
                "composite_score": 99,
            },
            {
                "task_id": "TSK002",
                "task_status": "In Progress",
                "task_assigned_to": "EMP001",
                "task_estimated_hours": 4,
                "task_required_skills": "sql",
                "employee_id": "EMP002",
                "composite_score": 88,
            },
        ],
        "team_score": 99,
        "score_breakdown": {"untrusted": 100},
    }


class FakeCursor:
    def __init__(
        self,
        *,
        duplicate=False,
        existing_formation=None,
        project=None,
        tasks=None,
        employees=None,
    ):
        self.duplicate = duplicate
        self.existing_formation = existing_formation
        self.project = project or {
            "project_id": "PRJ001",
            "project_name": "Example",
            "current_status": "Active",
            "team_size": 2,
        }
        self.tasks = tasks or [
            {
                "task_id": "TSK001",
                "status": "Not Started",
                "assigned_to": None,
                "estimated_hours": 3,
                "required_skills": "python",
            },
            {
                "task_id": "TSK002",
                "status": "In Progress",
                "assigned_to": "EMP001",
                "estimated_hours": 4,
                "required_skills": "sql",
            },
        ]
        self.employees = employees or ["EMP001", "EMP002"]
        self.calls = []
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        sql = " ".join(query.split())
        self.calls.append((sql, params))
        if "FROM projects" in sql and "FOR UPDATE" in sql:
            self.result = self.project
        elif "FROM tasks" in sql and "FOR UPDATE" in sql:
            self.result = self.tasks
        elif "FROM employees" in sql:
            roster = params[0]
            self.result = [
                {"employee_id": employee_id}
                for employee_id in roster
                if employee_id in self.employees
            ]
        elif "FROM team_formations" in sql and "FOR UPDATE" in sql:
            self.result = self.existing_formation or (
                {"team_id": "TEAM0001"} if self.duplicate else None
            )
        elif "MAX(SUBSTRING(team_id" in sql:
            self.result = {"max_num": 12}
        else:
            self.result = None

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc, _traceback):
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False

    def cursor(self):
        return self.fake_cursor


class TeamFormationPersistenceTests(unittest.TestCase):
    def run_confirm(self, rec=None, lead="EMP001", cursor_kwargs=None):
        cursor = FakeCursor(**(cursor_kwargs or {}))
        connection = FakeConnection(cursor)
        candidate_map = {
            "TSK001": [{"employee_id": "EMP001"}],
            "TSK002": [{"employee_id": "EMP002"}],
        }
        with (
            patch.object(persistence, "get_connection", return_value=connection),
            patch.object(persistence, "_candidate_lists", return_value=candidate_map),
            patch.object(
                persistence,
                "_apply_assignment",
                side_effect=lambda _cur, task_id, employee_id, **kwargs: (
                    f"ASG-{task_id}-{employee_id}-{kwargs['assignment_method']}"
                ),
            ) as apply_assignment,
        ):
            result = persistence.confirm_team_formation(
                "PRJ001", recommendation() if rec is None else rec, lead
            )
        return result, cursor, connection, apply_assignment

    def test_success_confirms_team_and_applies_assignments_atomically(self):
        result, cursor, connection, apply_assignment = self.run_confirm()

        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertEqual(result["team_id"], "TEAM0013")
        self.assertEqual(result["team_size"], 2)
        self.assertEqual(result["member_ids"], ["EMP002"])
        self.assertEqual(result["assignment_ids"]["TSK001"], "ASG-TSK001-EMP001-AI-Recommended")
        self.assertEqual(apply_assignment.call_count, 2)
        insert_sql, insert_params = next(
            (sql, params)
            for sql, params in cursor.calls
            if sql.startswith("INSERT INTO team_formations")
        )
        self.assertIn("team_size", insert_sql)
        self.assertEqual(insert_params[-1], 2)
        self.assertFalse(any(sql.startswith("UPDATE projects") for sql, _ in cursor.calls))
        self.assertEqual(cursor.calls[0][0], "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")

    def test_invalid_team_lead_is_rejected_before_database_access(self):
        with self.assertRaisesRegex(persistence.ConfirmationError, "team lead"):
            persistence.confirm_team_formation(
                "PRJ001", recommendation(), "EMP999"
            )

    def test_wrong_roster_size_is_rejected_against_project(self):
        with self.assertRaisesRegex(persistence.ConfirmationError, "team_size"):
            self.run_confirm(
                cursor_kwargs={
                    "project": {
                        "project_id": "PRJ001",
                        "project_name": "Example",
                        "current_status": "Active",
                        "team_size": 3,
                    }
                }
            )

    def test_invalid_authoritative_project_team_size_is_rejected(self):
        with self.assertRaisesRegex(persistence.ConfirmationError, "invalid team_size"):
            self.run_confirm(
                cursor_kwargs={
                    "project": {
                        "project_id": "PRJ001",
                        "project_name": "Example",
                        "current_status": "Active",
                        "team_size": None,
                    }
                }
            )

    def test_duplicate_employees_are_rejected(self):
        rec = recommendation()
        rec["team_member_ids"] = ["EMP001", "EMP001"]
        with self.assertRaisesRegex(persistence.ConfirmationError, "duplicate employees"):
            persistence.confirm_team_formation("PRJ001", rec, "EMP001")

    def test_missing_task_assignment_is_rejected(self):
        rec = recommendation()
        rec["assignments"].pop()
        with self.assertRaisesRegex(persistence.ConfirmationError, "Every roster member"):
            persistence.confirm_team_formation("PRJ001", rec, "EMP001")

    def test_duplicate_task_assignment_is_rejected(self):
        rec = recommendation()
        rec["assignments"][1]["task_id"] = "TSK001"
        with self.assertRaisesRegex(persistence.ConfirmationError, "duplicate task"):
            persistence.confirm_team_formation("PRJ001", rec, "EMP001")

    def test_employee_outside_roster_is_rejected(self):
        rec = recommendation()
        rec["assignments"][1]["employee_id"] = "EMP999"
        with self.assertRaisesRegex(persistence.ConfirmationError, "outside the roster"):
            persistence.confirm_team_formation("PRJ001", rec, "EMP001")

    def test_missing_task_from_live_open_set_is_stale(self):
        with self.assertRaisesRegex(persistence.ConfirmationError, "Open project tasks changed"):
            self.run_confirm(
                cursor_kwargs={
                    "tasks": [
                        {
                            "task_id": "TSK001",
                            "status": "Not Started",
                            "assigned_to": None,
                            "estimated_hours": 3,
                            "required_skills": "python",
                        }
                    ]
                }
            )

    def test_changed_task_snapshot_is_stale(self):
        tasks = FakeCursor().tasks
        tasks[0]["required_skills"] = "rust"
        with self.assertRaisesRegex(persistence.ConfirmationError, "changed state"):
            self.run_confirm(cursor_kwargs={"tasks": tasks})

    def test_changed_project_state_is_stale(self):
        with self.assertRaisesRegex(persistence.ConfirmationError, "Project state changed"):
            self.run_confirm(
                cursor_kwargs={
                    "project": {
                        "project_id": "PRJ001",
                        "project_name": "Example",
                        "current_status": "On Hold",
                        "team_size": 2,
                    }
                }
            )

    def test_unknown_roster_employee_is_rejected(self):
        with self.assertRaisesRegex(persistence.ConfirmationError, "unknown employees"):
            self.run_confirm(cursor_kwargs={"employees": ["EMP001"]})

    def test_ineligible_employee_task_pair_is_rejected(self):
        with patch.object(
            persistence,
            "_candidate_lists",
            return_value={
                "TSK001": [{"employee_id": "EMP002"}],
                "TSK002": [{"employee_id": "EMP002"}],
            },
        ):
            with patch.object(persistence, "get_connection", return_value=FakeConnection(FakeCursor())):
                with self.assertRaisesRegex(persistence.ConfirmationError, "no longer an eligible"):
                    persistence.confirm_team_formation(
                        "PRJ001", recommendation(), "EMP001"
                    )

    def test_duplicate_confirmation_is_rejected(self):
        with self.assertRaises(persistence.DuplicateConfirmationError):
            self.run_confirm(cursor_kwargs={"duplicate": True})

    def test_different_roster_is_rejected_while_project_formation_is_active(self):
        cursor = FakeCursor(
            existing_formation={
                "team_id": "TEAM0001",
                "team_lead_id": "EMP003",
                "member_ids": "EMP004",
            }
        )
        connection = FakeConnection(cursor)
        with (
            patch.object(persistence, "get_connection", return_value=connection),
            patch.object(
                persistence,
                "_candidate_lists",
                return_value={
                    "TSK001": [{"employee_id": "EMP001"}],
                    "TSK002": [{"employee_id": "EMP002"}],
                },
            ),
            patch.object(persistence, "_apply_assignment") as apply_assignment,
        ):
            with self.assertRaisesRegex(
                persistence.DuplicateConfirmationError,
                "already has an active AI formation",
            ):
                persistence.confirm_team_formation(
                    "PRJ001", recommendation(), "EMP001"
                )

        duplicate_check_sql, duplicate_check_params = next(
            (sql, params)
            for sql, params in cursor.calls
            if "FROM team_formations" in sql and "FOR UPDATE" in sql
        )
        self.assertIn("project_id = %s", duplicate_check_sql)
        self.assertNotIn("team_lead_id = %s", duplicate_check_sql)
        self.assertNotIn("member_ids = %s", duplicate_check_sql)
        self.assertEqual(duplicate_check_params, ("PRJ001",))
        self.assertFalse(any(sql.startswith("INSERT INTO team_formations") for sql, _ in cursor.calls))
        apply_assignment.assert_not_called()
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_persistence_failure_rolls_back_all_changes(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        assignment_calls = []

        def fail_second_assignment(_cur, task_id, employee_id, **_kwargs):
            assignment_calls.append((task_id, employee_id))
            if len(assignment_calls) == 2:
                raise RuntimeError("simulated failure")
            return "ASG0001"

        with (
            patch.object(persistence, "get_connection", return_value=connection),
            patch.object(
                persistence,
                "_candidate_lists",
                return_value={
                    "TSK001": [{"employee_id": "EMP001"}],
                    "TSK002": [{"employee_id": "EMP002"}],
                },
            ),
            patch.object(persistence, "_apply_assignment", side_effect=fail_second_assignment),
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                persistence.confirm_team_formation(
                    "PRJ001", recommendation(), "EMP001"
                )

        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertEqual(len(assignment_calls), 2)

    def test_confirmation_route_returns_explicit_created_response(self):
        expected = {"confirmed": True, "team_id": "TEAM0013"}
        request = team_formation_routes.TeamFormationConfirmationRequest(
            recommendation=recommendation(),
            team_lead_id="EMP001",
        )
        with patch.object(
            team_formation_routes,
            "confirm_team_formation",
            return_value=expected,
        ):
            result = team_formation_routes.confirm("PRJ001", request)

        self.assertEqual(result, expected)

    def test_serialization_failure_returns_conflict(self):
        request = team_formation_routes.TeamFormationConfirmationRequest(
            recommendation=recommendation(),
            team_lead_id="EMP001",
        )
        with patch.object(
            team_formation_routes,
            "confirm_team_formation",
            side_effect=SerializationFailure("concurrent update"),
        ):
            with self.assertRaises(HTTPException) as raised:
                team_formation_routes.confirm("PRJ001", request)

        self.assertEqual(raised.exception.status_code, 409)

    def test_apply_assignment_preserves_history_and_sets_current_assignee(self):
        cursor = FakeCursor()
        results = iter([
            {"project_id": "PRJ001", "assigned_to": None, "status": "Not Started"},
            {"max_num": 4},
            {"assignment_id": "ASG0005"},
        ])
        cursor.fetchone = lambda: next(results)
        cursor.execute = unittest.mock.Mock()
        cursor.execute.side_effect = [
            None,  # Lock and fetch task.
            None,  # Validate employee.
            None,  # Mark prior active assignment history reassigned.
            None,  # Get next history ID.
            None,  # Insert new assignment history.
            None,  # Update tasks.assigned_to.
        ]
        with patch.object(task_assignment_routes, "_validate_employee"):
            assignment_id = task_assignment_routes._apply_assignment(
                cursor,
                "TSK001",
                "EMP001",
                assignment_method="AI-Recommended",
            )

        self.assertEqual(assignment_id, "ASG0005")
        insert_call = cursor.execute.call_args_list[3]
        self.assertIn("INSERT INTO task_assignments", insert_call.args[0])
        self.assertEqual(insert_call.args[1][4], "AI-Recommended")
        self.assertIn("completion_status = 'Reassigned'", cursor.execute.call_args_list[1].args[0])
        self.assertIn("SET assigned_to = %s", cursor.execute.call_args_list[4].args[0])

    def test_apply_assignment_reuses_existing_active_history(self):
        cursor = FakeCursor()
        results = iter([
            {"project_id": "PRJ001", "assigned_to": "EMP001", "status": "In Progress"},
            {"assignment_id": "ASG0004"},
        ])
        cursor.fetchone = lambda: next(results)
        cursor.execute = unittest.mock.Mock()
        with patch.object(task_assignment_routes, "_validate_employee"):
            assignment_id = task_assignment_routes._apply_assignment(
                cursor,
                "TSK001",
                "EMP001",
                assignment_method="AI-Recommended",
            )

        self.assertEqual(assignment_id, "ASG0004")
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertNotIn(
            "INSERT INTO task_assignments",
            [call.args[0] for call in cursor.execute.call_args_list],
        )


if __name__ == "__main__":
    unittest.main()
