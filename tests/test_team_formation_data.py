import unittest
from contextlib import contextmanager
from unittest.mock import patch

from modules.ml import team_formation_features as features


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = ""
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.fake_cursor = FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    @contextmanager
    def cursor(self):
        yield self.fake_cursor


def fake_connection(rows):
    return FakeConnection(rows)


class TeamFormationDataTests(unittest.TestCase):
    def test_project_context_returns_valid_team_size_and_empty_task_count(self):
        row = {
            "project_id": "PRJ001",
            "project_name": "Project",
            "current_status": "Planning",
            "team_size": 4,
            "open_task_count": 0,
        }
        with patch.object(features, "get_connection", return_value=fake_connection([row])):
            context = features.get_project_context("PRJ001")

        self.assertEqual(context["team_size"], 4)
        self.assertEqual(context["open_task_count"], 0)

    def test_project_context_rejects_missing_or_invalid_team_size(self):
        invalid_sizes = (None, 0, -1, 2.5, "invalid")
        for team_size in invalid_sizes:
            with self.subTest(team_size=team_size):
                row = {
                    "project_id": "PRJ001",
                    "project_name": "Project",
                    "current_status": "Planning",
                    "team_size": team_size,
                    "open_task_count": 0,
                }
                with patch.object(features, "get_connection", return_value=fake_connection([row])):
                    with self.assertRaisesRegex(ValueError, "invalid team_size"):
                        features.get_project_context("PRJ001")

    def test_project_context_rejects_unknown_project(self):
        with patch.object(features, "get_connection", return_value=fake_connection([])):
            with self.assertRaisesRegex(ValueError, "Unknown project_id"):
                features.get_project_context("MISSING")

    def test_project_list_exposes_database_team_size(self):
        row = {
            "project_id": "PRJ001",
            "project_name": "Project",
            "current_status": "Active",
            "team_size": 3,
            "open_task_count": 2,
        }
        connection = fake_connection([row])
        with patch.object(features, "get_connection", return_value=connection):
            projects = features.list_projects_with_open_tasks()

        self.assertEqual(projects[0]["team_size"], 3)
        self.assertIn("p.team_size", connection.fake_cursor.query)

    def test_open_tasks_include_assignees_and_preserve_missing_estimates(self):
        row = {
            "task_id": "TSK001",
            "task_name": "Assigned task",
            "project_id": "PRJ001",
            "status": "In Progress",
            "required_skills": "Python",
            "estimated_hours": None,
            "assigned_to": "EMP001",
        }
        connection = fake_connection([row])
        with patch.object(features, "get_connection", return_value=connection):
            tasks = features.get_open_project_tasks("PRJ001")

        self.assertEqual(tasks[0]["assigned_to"], "EMP001")
        self.assertIsNone(tasks[0]["estimated_hours"])
        query = connection.fake_cursor.query
        self.assertIn("status IS NULL OR status NOT IN ('Completed', 'Cancelled')", query)
        self.assertNotIn("assigned_to IS NULL", query)

    def test_open_tasks_returns_empty_list_when_project_has_no_open_tasks(self):
        with patch.object(features, "get_connection", return_value=fake_connection([])):
            self.assertEqual(features.get_open_project_tasks("PRJ001"), [])

    def test_employee_profiles_keep_missing_optional_values_explicit(self):
        row = {
            "employee_id": "EMP001",
            "first_name": "Alex",
            "last_name": None,
            "department": None,
            "seniority_level": None,
            "years_of_experience": None,
            "primary_skills": None,
            "secondary_skills": None,
            "technical_proficiency_score": None,
            "collaboration_score": None,
            "burnout_risk_score": None,
            "weekly_capacity_hours": None,
        }
        with patch.object(features, "_fetch_employee_rows", return_value=[row]):
            employees = features.get_employee_profiles()

        employee = employees[0]
        self.assertEqual(employee["employee_name"], "Alex")
        self.assertIsNone(employee["department"])
        self.assertIsNone(employee["technical_proficiency_score"])
        self.assertIsNone(employee["weekly_capacity_hours"])

    def test_employee_fetch_uses_only_existing_profile_columns(self):
        connection = fake_connection([])
        with patch.object(features, "get_connection", return_value=connection):
            self.assertEqual(features._fetch_employee_rows(), [])

        query = connection.fake_cursor.query
        for column in (
            "employee_id", "first_name", "last_name", "department",
            "seniority_level", "years_of_experience", "primary_skills",
            "secondary_skills", "technical_proficiency_score",
            "collaboration_score", "burnout_risk_score", "weekly_capacity_hours",
        ):
            self.assertIn(column, query)

    def test_no_existing_workload_returns_zero_for_requested_employees(self):
        with patch.object(features, "get_connection", return_value=fake_connection([])):
            workloads = features.get_existing_employee_workloads(["EMP001"])

        self.assertEqual(workloads["EMP001"], {
            "estimated_hours": 0.0,
            "task_count": 0,
            "missing_estimated_hours_count": 0,
        })

    def test_workload_sums_open_tasks_across_projects_without_history_join(self):
        rows = [
            {"assigned_to": "EMP001", "estimated_hours": 5},
            {"assigned_to": "EMP001", "estimated_hours": 8},
            {"assigned_to": "EMP001", "estimated_hours": None},
            {"assigned_to": "EMP002", "estimated_hours": 3},
        ]
        connection = fake_connection(rows)
        with patch.object(features, "get_connection", return_value=connection):
            workloads = features.get_existing_employee_workloads(["EMP001", "EMP002", "EMP003"])

        self.assertEqual(workloads["EMP001"], {
            "estimated_hours": 13.0,
            "task_count": 3,
            "missing_estimated_hours_count": 1,
        })
        self.assertEqual(workloads["EMP002"]["estimated_hours"], 3.0)
        self.assertEqual(workloads["EMP003"]["task_count"], 0)
        query = connection.fake_cursor.query
        self.assertIn("assigned_to IS NOT NULL", query)
        self.assertIn("status IS NULL OR status NOT IN ('Completed', 'Cancelled')", query)
        self.assertNotIn("task_assignments", query)
        self.assertNotIn("project_id =", query)

    def test_task_workload_missing_estimate_is_counted_not_invented(self):
        rows = [{"assigned_to": "EMP001", "estimated_hours": None}]
        with patch.object(features, "get_connection", return_value=fake_connection(rows)):
            workload = features.get_existing_employee_workloads(["EMP001"])["EMP001"]

        self.assertEqual(workload["estimated_hours"], 0.0)
        self.assertEqual(workload["missing_estimated_hours_count"], 1)

    def test_preparation_function_returns_separate_data_structures(self):
        project = {"project_id": "PRJ001", "team_size": 2}
        tasks = [{"task_id": "TSK001", "assigned_to": "EMP001"}]
        employees = [{"employee_id": "EMP001"}]
        workloads = {"EMP001": {"estimated_hours": 4.0, "task_count": 1}}
        with (
            patch.object(features, "get_project_context", return_value=project),
            patch.object(features, "get_open_project_tasks", return_value=tasks),
            patch.object(features, "get_employee_profiles", return_value=employees),
            patch.object(features, "get_existing_employee_workloads", return_value=workloads) as fetch_workloads,
        ):
            prepared = features.prepare_team_formation_data("PRJ001")

        self.assertEqual(prepared, {
            "project": project,
            "tasks": tasks,
            "employees": employees,
            "existing_workloads": workloads,
        })
        fetch_workloads.assert_called_once_with(["EMP001"])


if __name__ == "__main__":
    unittest.main()
