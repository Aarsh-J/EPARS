import unittest
from datetime import date
from unittest.mock import patch

from fastapi import HTTPException

from modules.team_formation import routes


class FakeCursor:
    def __init__(self, *, project=None, updated=None, manager_exists=True):
        self.project = project or {
            "start_date": date(2026, 1, 1),
            "planned_end_date": date(2026, 12, 31),
        }
        self.updated = updated or {}
        self.manager_exists = manager_exists
        self.query = None
        self.params = None
        self.queries = []
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params):
        self.query = query
        self.params = params
        self.queries.append(query)
        compact_query = " ".join(query.split())
        if "SELECT start_date, planned_end_date" in compact_query:
            self.result = self.project
        elif "SELECT 1 FROM employees" in compact_query:
            self.result = {"exists": 1} if self.manager_exists else None
        elif compact_query.startswith("UPDATE projects"):
            self.result = self.updated

    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.fake_cursor


class TeamFormationProjectEditTests(unittest.TestCase):
    def test_patch_updates_supported_fields_and_returns_authoritative_values(self):
        updated = {
            "project_id": "PRJ001",
            "project_name": "Updated project",
            "project_description": "Updated description",
            "current_status": "Active",
            "team_size": 4,
            "priority": "High",
            "department": "Engineering",
            "start_date": date(2026, 2, 1),
            "planned_end_date": date(2026, 11, 30),
            "project_manager_id": "EMP007",
            "required_skills": "Python, SQL",
        }
        cursor = FakeCursor(updated=updated)
        payload = routes.ProjectUpdateRequest(
            project_name=" Updated project ",
            project_description=" Updated description ",
            current_status=" Active ",
            team_size=4,
            priority=" High ",
            start_date="2026-02-01",
            planned_end_date="2026-11-30",
            project_manager_id="EMP007",
            required_skills="Python, SQL",
        )
        with patch.object(routes, "get_connection", return_value=FakeConnection(cursor)):
            result = routes.update_project("PRJ001", payload)

        self.assertEqual(result, updated)
        update_query = next(query for query in cursor.queries if query.lstrip().startswith("UPDATE projects"))
        for field in payload.model_fields_set:
            self.assertIn(f"{field} = %s", update_query)
        self.assertEqual(
            cursor.params,
            [
                "Updated project",
                "Updated description",
                "Active",
                4,
                "High",
                date(2026, 2, 1),
                date(2026, 11, 30),
                "EMP007",
                "Python, SQL",
                "PRJ001",
            ],
        )
        self.assertEqual(cursor.queries[0].lstrip().split()[0], "SELECT")
        self.assertIn("SELECT 1 FROM employees", cursor.queries[1])

    def test_patch_rejects_empty_update(self):
        with self.assertRaises(HTTPException) as raised:
            routes.update_project("PRJ001", routes.ProjectUpdateRequest())

        self.assertEqual(raised.exception.status_code, 422)

    def test_patch_rejects_invalid_team_size_before_database_access(self):
        with patch.object(routes, "get_connection") as get_connection:
            with self.assertRaises(HTTPException) as raised:
                routes.update_project(
                    "PRJ001",
                    routes.ProjectUpdateRequest(team_size=0),
                )

        self.assertEqual(raised.exception.status_code, 422)
        get_connection.assert_not_called()

    def test_patch_reports_missing_project(self):
        cursor = FakeCursor(project=None)
        cursor.project = None
        with patch.object(routes, "get_connection", return_value=FakeConnection(cursor)):
            with self.assertRaises(HTTPException) as raised:
                routes.update_project(
                    "MISSING",
                    routes.ProjectUpdateRequest(project_name="Updated"),
                )

        self.assertEqual(raised.exception.status_code, 404)

    def test_patch_rejects_reversed_project_dates(self):
        cursor = FakeCursor(project={
            "start_date": date(2026, 9, 1),
            "planned_end_date": date(2026, 12, 1),
        })
        with patch.object(routes, "get_connection", return_value=FakeConnection(cursor)):
            with self.assertRaises(HTTPException) as raised:
                routes.update_project(
                    "PRJ001",
                    routes.ProjectUpdateRequest(start_date="2027-01-01"),
                )

        self.assertEqual(raised.exception.status_code, 422)
        self.assertFalse(any(query.lstrip().startswith("UPDATE projects") for query in cursor.queries))

    def test_patch_rejects_unknown_project_manager(self):
        cursor = FakeCursor(manager_exists=False)
        with patch.object(routes, "get_connection", return_value=FakeConnection(cursor)):
            with self.assertRaises(HTTPException) as raised:
                routes.update_project(
                    "PRJ001",
                    routes.ProjectUpdateRequest(project_manager_id="EMP999"),
                )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertFalse(any(query.lstrip().startswith("UPDATE projects") for query in cursor.queries))


if __name__ == "__main__":
    unittest.main()
