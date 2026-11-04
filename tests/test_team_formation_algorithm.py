from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from modules.ml import team_formation_predict as predictor
from modules.team_formation import routes as team_formation_routes


def candidate(task_id, employee_id, score=80):
    return {
        "task_id": task_id,
        "employee_id": employee_id,
        "composite_score": score,
        "predicted_delay_risk": 10,
        "real_skill_match": 90,
    }


def task(task_id, hours=4, assigned_to=None, project_id="PRJ001"):
    return {
        "task_id": task_id,
        "task_name": task_id,
        "project_id": project_id,
        "status": "Not Started",
        "required_skills": "",
        "estimated_hours": hours,
        "assigned_to": assigned_to,
    }


def employee(employee_id, capacity=40):
    return {
        "employee_id": employee_id,
        "employee_name": employee_id,
        "department": "Engineering",
        "seniority_level": "Mid",
        "years_of_experience": 4,
        "primary_skills": "",
        "secondary_skills": "",
        "technical_proficiency_score": 70,
        "collaboration_score": 70,
        "burnout_risk_score": 20,
        "weekly_capacity_hours": capacity,
    }


def prepared_data(tasks, employees, team_size, workloads=None):
    return {
        "project": {
            "project_id": "PRJ001",
            "project_name": "Project",
            "current_status": "Active",
            "team_size": team_size,
            "open_task_count": len(tasks),
        },
        "tasks": tasks,
        "employees": employees,
        "existing_workloads": workloads or {},
    }


class TeamFormationAlgorithmTests(unittest.TestCase):
    def setUp(self):
        self.tasks = [task("T1"), task("T2"), task("T3"), task("T4")]
        self.candidates = {
            "T1": [candidate("T1", "A", 95), candidate("T1", "B", 85)],
            "T2": [candidate("T2", "A", 94), candidate("T2", "B", 84)],
            "T3": [candidate("T3", "A", 93)],
            "T4": [candidate("T4", "B", 92)],
        }
        self.employees = [employee("A"), employee("B")]
        self.workloads = {
            "A": {"estimated_hours": 0.0},
            "B": {"estimated_hours": 0.0},
        }

    def allocate(self, tasks=None, candidates=None, roster=None, employees=None, workloads=None):
        tasks = self.tasks if tasks is None else tasks
        candidates = self.candidates if candidates is None else candidates
        roster = {"A", "B"} if roster is None else roster
        employees = self.employees if employees is None else employees
        workloads = self.workloads if workloads is None else workloads
        assignment = predictor._allocate_tasks(
            tasks,
            candidates,
            roster,
            {item["employee_id"]: item for item in employees},
            workloads,
        )
        predictor._validate_allocation(tasks, candidates, roster, assignment, len(roster))
        return assignment

    def test_valid_allocation_supports_multiple_tasks_per_employee(self):
        assignment = self.allocate()
        assigned_ids = [item["employee_id"] for item in assignment.values()]

        self.assertEqual(set(assignment), {"T1", "T2", "T3", "T4"})
        self.assertEqual(len(assigned_ids), 4)
        self.assertEqual(set(assigned_ids), {"A", "B"})
        self.assertGreater(max(assigned_ids.count("A"), assigned_ids.count("B")), 1)

    def test_roster_has_exact_size_and_every_member_gets_a_task(self):
        roster = {"A", "B"}
        assignment = self.allocate(roster=roster)

        self.assertEqual(len(roster), 2)
        self.assertEqual(
            {item["employee_id"] for item in assignment.values()},
            roster,
        )

    def test_every_task_is_assigned_once(self):
        assignment = self.allocate()
        self.assertEqual(len(assignment), len(self.tasks))
        self.assertEqual(set(assignment), {item["task_id"] for item in self.tasks})

    def test_invalid_employee_task_pair_is_rejected(self):
        assignment = {
            "T1": candidate("T1", "A"),
            "T2": candidate("T2", "B"),
            "T3": candidate("T3", "B"),
            "T4": candidate("T4", "B"),
        }
        with self.assertRaisesRegex(ValueError, "ineligible employee"):
            predictor._validate_allocation(
                self.tasks, self.candidates, {"A", "B"}, assignment, 2
            )

    def test_empty_model3_candidate_list_is_infeasible(self):
        with self.assertRaisesRegex(
            predictor.InfeasibleTeamFormationError,
            "no eligible candidates.*T1",
        ):
            predictor._candidate_lists(
                [task("T1")],
                5,
                candidate_provider=lambda _task_id, _limit: [],
            )

    def test_team_size_greater_than_task_count_is_infeasible(self):
        with self.assertRaisesRegex(
            predictor.InfeasibleTeamFormationError,
            "only 1 open tasks",
        ):
            predictor._build_recommendations(
                "PRJ001",
                [task("T1")],
                {"T1": [candidate("T1", "A")]},
                [employee("A")],
                {},
                team_size=2,
                num_teams=1,
            )

    def test_insufficient_eligible_employees_is_infeasible(self):
        tasks = [task("T1"), task("T2"), task("T3")]
        candidates = {item["task_id"]: [candidate(item["task_id"], "A")] for item in tasks}
        with self.assertRaisesRegex(
            predictor.InfeasibleTeamFormationError,
            "Only 1 employees have eligible",
        ):
            predictor._build_recommendations(
                "PRJ001", tasks, candidates, [employee("A")], {}, 2, 1
            )

    def test_candidate_graph_without_a_covering_roster_is_infeasible(self):
        tasks = [task("T1"), task("T2"), task("T3")]
        candidates = {
            "T1": [candidate("T1", "A")],
            "T2": [candidate("T2", "B")],
            "T3": [candidate("T3", "C")],
        }
        with self.assertRaises(predictor.InfeasibleTeamFormationError) as raised:
            predictor._build_recommendations(
                "PRJ001",
                tasks,
                candidates,
                [employee("A"), employee("B"), employee("C")],
                {},
                2,
                1,
            )
        self.assertIn("cannot cover every open task", str(raised.exception))
        self.assertNotIsInstance(
            raised.exception, predictor.TeamFormationSearchExhaustedError
        )

    def test_candidate_graph_without_distinct_member_tasks_is_infeasible(self):
        tasks = [task("T1"), task("T2"), task("T3"), task("T4")]
        candidates = {
            "T1": [candidate("T1", "A"), candidate("T1", "B")],
            "T2": [candidate("T2", "C")],
            "T3": [candidate("T3", "C")],
            "T4": [candidate("T4", "C")],
        }
        with self.assertRaisesRegex(
            predictor.InfeasibleTeamFormationError,
            "cannot cover every open task",
        ):
            predictor._build_recommendations(
                "PRJ001",
                tasks,
                candidates,
                [employee("A"), employee("B"), employee("C")],
                {},
                3,
                1,
            )

    def test_existing_project_task_hours_are_removed_before_reallocation(self):
        tasks = [
            task("T1", hours=10, assigned_to="A"),
            task("T2", hours=10),
        ]
        existing = {
            "A": {"estimated_hours": 10.0},
            "B": {"estimated_hours": 0.0},
        }
        base = predictor._projected_base_workloads(tasks, {"A", "B"}, existing)

        self.assertEqual(base, {"A": 0.0, "B": 0.0})

    def test_missing_hours_and_capacity_are_not_fabricated(self):
        tasks = [task("T1", hours=None), task("T2", hours=5)]
        candidates = {
            "T1": [candidate("T1", "A"), candidate("T1", "B")],
            "T2": [candidate("T2", "A"), candidate("T2", "B")],
        }
        employees = [employee("A", capacity=None), employee("B", capacity=0)]
        assignment = self.allocate(
            tasks=tasks,
            candidates=candidates,
            roster={"A", "B"},
            employees=employees,
            workloads={"A": {"estimated_hours": None}, "B": {"estimated_hours": 3}},
        )

        self.assertEqual(set(assignment), {"T1", "T2"})
        self.assertIsNone(predictor._valid_capacity(employees[0]))
        self.assertIsNone(predictor._valid_capacity(employees[1]))
        self.assertIsNone(predictor._known_hours(None))

    def test_valid_weekly_capacities_normalize_workload_objective(self):
        spread = predictor._workload_objective(
            {"A", "B"},
            {"A": 10.0, "B": 20.0},
            {"A": employee("A", 20), "B": employee("B", 80)},
        )

        self.assertEqual(spread, (0.25, 10.0))

    def test_mixed_capacities_compare_hours_then_known_capacity_utilization(self):
        spread = predictor._workload_objective(
            {"A", "B", "C", "D"},
            {"A": 10.0, "B": 20.0, "C": 15.0, "D": 14.0},
            {
                "A": employee("A", 10),
                "B": employee("B", 80),
                "C": employee("C", None),
                "D": employee("D", 0),
            },
        )

        self.assertEqual(spread, (10.0, 0.75))

    def test_search_exhaustion_has_distinct_api_status(self):
        with patch.object(
            team_formation_routes,
            "recommend_teams",
            side_effect=predictor.TeamFormationSearchExhaustedError("search exhausted"),
        ):
            with self.assertRaises(HTTPException) as raised:
                team_formation_routes.recommend("PRJ001", task_ids=None)

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail, "search exhausted")

    def test_allocation_is_stable_to_task_and_candidate_order_and_uses_scores(self):
        tasks = [task("T2"), task("T1")]
        candidates = {
            "T1": [candidate("T1", "B", 75), candidate("T1", "A", 99)],
            "T2": [candidate("T2", "A", 70), candidate("T2", "B", 98)],
        }
        first = self.allocate(
            tasks=tasks,
            candidates=candidates,
            roster={"A", "B"},
        )
        reordered = self.allocate(
            tasks=list(reversed(tasks)),
            candidates={
                "T1": list(reversed(candidates["T1"])),
                "T2": list(reversed(candidates["T2"])),
            },
            roster={"A", "B"},
        )

        first_result = {
            task_id: (item["employee_id"], item["composite_score"])
            for task_id, item in first.items()
        }
        reordered_result = {
            task_id: (item["employee_id"], item["composite_score"])
            for task_id, item in reordered.items()
        }
        self.assertEqual(first_result, reordered_result)
        self.assertEqual(first_result, {"T1": ("A", 99), "T2": ("B", 98)})

    def test_search_budget_exhaustion_is_not_reported_as_infeasibility(self):
        tasks = [task("T1"), task("T2")]
        candidates = {
            "T1": [candidate("T1", "A"), candidate("T1", "B")],
            "T2": [candidate("T2", "A"), candidate("T2", "B")],
        }
        with patch.object(predictor, "MAX_ROSTER_SEARCH_NODES", 0):
            with self.assertRaises(
                predictor.TeamFormationSearchExhaustedError
            ) as raised:
                predictor._build_recommendations(
                    "PRJ001",
                    tasks,
                    candidates,
                    [employee("A"), employee("B")],
                    {},
                    team_size=2,
                    num_teams=1,
                )

        self.assertNotIsInstance(
            raised.exception, predictor.InfeasibleTeamFormationError
        )

    def test_model3_candidate_limit_and_scores_are_preserved(self):
        task_rows = [task("T1")]
        prepared = prepared_data(task_rows, [employee("A")], 1)
        model3_row = candidate("T1", "A", 88)
        provider_calls = []

        def provider(task_id, top_n):
            provider_calls.append((task_id, top_n))
            return [model3_row]

        with (
            patch.object(predictor.tff, "prepare_team_formation_data", return_value=prepared),
            patch.object(predictor.tff, "load_historical_pairs", return_value=set()),
            patch.object(
                predictor,
                "_format_result",
                side_effect=lambda _ctx, _mode, _n, assignment, roster, **kwargs: {
                    "team_member_ids": sorted(roster),
                    "assignments": list(assignment.values()),
                    "candidate_limit": kwargs["candidate_limit"],
                    "project_status": kwargs["project_status"],
                },
            ),
        ):
            result = predictor.recommend_teams(
                "PRJ001", top_m=7, num_teams=1, candidate_provider=provider
            )

        self.assertEqual(provider_calls, [("T1", 7)])
        self.assertEqual(result[0]["team_member_ids"], ["A"])
        self.assertEqual(result[0]["assignments"][0]["composite_score"], 88)
        self.assertEqual(result[0]["candidate_limit"], 7)
        self.assertEqual(result[0]["project_status"], "Active")

    def test_final_validation_rejects_bad_heuristic_allocation(self):
        tasks = [task("T1"), task("T2")]
        prepared = prepared_data(tasks, [employee("A"), employee("B")], 1)
        candidates = {
            "T1": [candidate("T1", "A")],
            "T2": [candidate("T2", "A")],
        }
        with (
            patch.object(predictor.tff, "prepare_team_formation_data", return_value=prepared),
            patch.object(predictor, "recommend_top_n", side_effect=lambda task_id, _top_n: candidates[task_id]),
            patch.object(
                predictor,
                "_allocate_tasks",
                return_value={"T1": candidate("T1", "B"), "T2": candidate("T2", "A")},
            ),
        ):
            with self.assertRaisesRegex(ValueError, "Generated allocation failed validation"):
                predictor.recommend_teams("PRJ001", top_m=5, num_teams=1)

    def test_empty_prepared_task_list_is_infeasible(self):
        prepared = prepared_data([], self.employees, 2)
        with patch.object(predictor.tff, "prepare_team_formation_data", return_value=prepared):
            with self.assertRaisesRegex(
                predictor.InfeasibleTeamFormationError,
                "No open tasks found",
            ):
                predictor.recommend_teams("PRJ001")

    def test_subset_task_recommendation_is_rejected(self):
        tasks = [task("T1"), task("T2")]
        prepared = prepared_data(tasks, [employee("A"), employee("B")], 1)
        candidate_provider = Mock()
        with (
            patch.object(predictor.tff, "prepare_team_formation_data", return_value=prepared),
            self.assertRaisesRegex(
                predictor.InfeasibleTeamFormationError,
                "must include every open project task",
            ),
        ):
            predictor.recommend_teams(
                "PRJ001",
                task_ids=["T1"],
                candidate_provider=candidate_provider,
            )

        candidate_provider.assert_not_called()


class TeamFormationScoringTests(unittest.TestCase):
    def test_six_dimensions_are_enabled_with_fixed_weights(self):
        self.assertEqual(
            predictor.TEAM_WEIGHTS,
            {
                "task_fit": 0.45,
                "skill_coverage": 0.20,
                "experience_balance": 0.10,
                "workload_balance": 0.10,
                "historical_cooccurrence": 0.05,
                "composition_typicality": 0.10,
            },
        )
        self.assertAlmostEqual(sum(predictor.TEAM_WEIGHTS.values()), 1.0)

    def test_all_six_components_are_calculated_when_inputs_are_available(self):
        ctx = self.make_context(history=set())
        assignment = {
            "T1": candidate("T1", "A", 80),
            "T2": candidate("T2", "B", 90),
        }
        with patch.object(ctx, "typicality", return_value=75.0):
            features = predictor._team_features(ctx, assignment, {"A", "B"})

        self.assertEqual(set(features), set(predictor.TEAM_WEIGHTS))
        self.assertTrue(all(value is not None for value in features.values()))
        self.assertEqual(features["historical_cooccurrence"], 0.0)

    def make_context(self, task_rows=None, employees=None, workloads=None, history=None):
        task_rows = task_rows or [
            {**task("T1", hours=5), "required_skills": "python,sql"},
            {**task("T2", hours=5), "required_skills": "python,sql"},
        ]
        employees = employees or [
            {**employee("A"), "primary_skills": "python"},
            {**employee("B"), "primary_skills": "sql"},
        ]
        with patch.object(predictor.tff, "load_historical_pairs", return_value=history):
            return predictor._Ctx(
                "PRJ001",
                task_rows,
                employees,
                workloads or {
                    "A": {"estimated_hours": 10, "missing_estimated_hours_count": 0},
                    "B": {"estimated_hours": 20, "missing_estimated_hours_count": 0},
                },
            )

    def test_score_uses_exact_weighted_displayed_components(self):
        features = {
            "task_fit": 80.04,
            "skill_coverage": 90.05,
            "experience_balance": 70.06,
            "workload_balance": 60.04,
            "historical_cooccurrence": 50.05,
            "composition_typicality": 40.06,
        }
        displayed = {key: round(value, 1) for key, value in features.items()}
        expected = round(
            sum(predictor.TEAM_WEIGHTS[key] * displayed[key] for key in displayed),
            1,
        )
        ctx = SimpleNamespace(project_id="PRJ001", tasks={})

        with (
            patch.object(predictor, "_team_features", return_value=features),
            patch.object(predictor, "get_team_composition_model", return_value={"anomaly_threshold": 0}),
        ):
            result = predictor._format_result(
                ctx, "test", 2, {"T1": candidate("T1", "A", 80)}, {"A"}
            )

        self.assertEqual(set(result["score_breakdown"]), set(predictor.TEAM_WEIGHTS))
        self.assertEqual(result["score_weights"], predictor.TEAM_WEIGHTS)
        self.assertEqual(result["team_score"], expected)
        self.assertEqual(result["score_unavailable_components"], [])

    def test_skill_coverage_changes_weighted_score(self):
        full = {key: 50.0 for key in predictor.TEAM_WEIGHTS}
        partial = {**full, "skill_coverage": 0.0}

        self.assertEqual(
            predictor._team_score(full) - predictor._team_score(partial),
            10.0,
        )

    def test_workload_component_uses_projected_hours_and_capacity(self):
        ctx = self.make_context()
        ctx.employee_profiles["A"]["weekly_capacity_hours"] = 40
        ctx.employee_profiles["B"]["weekly_capacity_hours"] = 40
        assignment = {
            "T1": candidate("T1", "A", 80),
            "T2": candidate("T2", "B", 80),
        }

        features = predictor._team_features(ctx, assignment, {"A", "B"})

        # Existing hours (10, 20) plus assigned estimates (5, 5) yield (15, 25).
        self.assertEqual(features["workload_balance"], 60.0)

    def test_composition_and_scores_use_unique_roster_members(self):
        ctx = self.make_context(history={("A", "B")})
        assignment = {
            "T1": candidate("T1", "A", 80),
            "T2": candidate("T2", "A", 90),
        }
        observed_roster = []

        def typicality(member_ids):
            observed_roster.extend(member_ids)
            return 65.0

        with patch.object(ctx, "typicality", side_effect=typicality):
            features = predictor._team_features(
                ctx, assignment, {"A", "B"}
            )

        self.assertEqual(observed_roster, ["A", "B"])
        self.assertEqual(features["task_fit"], 85.0)
        self.assertEqual(features["historical_cooccurrence"], 100.0)
        self.assertNotIn("past_overlap", features)

    def test_missing_component_data_is_null_not_imputed(self):
        employees = [
            {**employee("A"), "primary_skills": "python"},
            {**employee("B"), "seniority_level": None, "primary_skills": "sql"},
        ]
        workloads = {
            "A": {"estimated_hours": 10, "missing_estimated_hours_count": 1},
            "B": {"estimated_hours": 20, "missing_estimated_hours_count": 0},
        }
        ctx = self.make_context(
            task_rows=[
                {**task("T1", hours=None), "required_skills": ""},
                {**task("T2", hours=5), "required_skills": ""},
            ],
            employees=employees,
            workloads=workloads,
            history=None,
        )
        assignment = {
            "T1": {**candidate("T1", "A"), "composite_score": None},
            "T2": candidate("T2", "B", 80),
        }
        with patch.object(ctx, "typicality", return_value=70.0):
            features = predictor._team_features(ctx, assignment, {"A", "B"})

        for component in (
            "task_fit",
            "skill_coverage",
            "experience_balance",
            "workload_balance",
            "historical_cooccurrence",
            "composition_typicality",
        ):
            self.assertIsNone(features[component])
        self.assertIsNone(predictor._team_score(features))

    def test_skill_coverage_is_unavailable_for_missing_skill_profiles(self):
        employees = [
            {**employee("A"), "primary_skills": None, "secondary_skills": None},
            {**employee("B"), "primary_skills": "sql"},
        ]
        ctx = self.make_context(
            employees=employees,
            history=set(),
        )
        assignment = {
            "T1": candidate("T1", "A"),
            "T2": candidate("T2", "B"),
        }
        with patch.object(ctx, "typicality", return_value=70.0):
            features = predictor._team_features(ctx, assignment, {"A", "B"})

        self.assertIsNone(features["skill_coverage"])

    def test_unavailable_components_make_response_score_null(self):
        features = {
            key: 70.0 for key in predictor.TEAM_WEIGHTS
        }
        features["workload_balance"] = None
        with (
            patch.object(predictor, "_team_features", return_value=features),
            patch.object(predictor, "get_team_composition_model", return_value={"anomaly_threshold": 0}),
        ):
            result = predictor._format_result(
                SimpleNamespace(project_id="PRJ001", tasks={}),
                "test",
                1,
                {"T1": candidate("T1", "A")},
                {"A"},
            )

        self.assertIsNone(result["team_score"])
        self.assertIsNone(result["score_breakdown"]["workload_balance"])
        self.assertEqual(result["score_unavailable_components"], ["workload_balance"])
        self.assertIn("composition_typicality", result["score_breakdown"])


if __name__ == "__main__":
    unittest.main()
