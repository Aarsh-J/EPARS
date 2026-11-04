"""
modules/ml/team_formation_predict.py
========================================
Model4: team formation, using prepared live-DB data from team_formation_features.

The allocation layer:
  (a) uses the Model 3 top-N list as the complete eligible-pair set;
  (b) searches fixed-size rosters that cover every task and can each receive
      at least one task; and
  (c) assigns remaining tasks greedily to reduce projected workload imbalance.
Roster search and task allocation are separate functions. The bounded search
order and greedy workload allocation are heuristics, not a global optimum.

The existing TRAINED unsupervised component — an Isolation Forest
      (ml_models/team_composition_bundle.pkl) that scores how typical a
      candidate team's composition is vs the historical rosters in
      team_formations. Folded into team_score and surfaced as an advisory flag.

Why there is no supervised "predict team success" model: team_formations'
outcome columns are generated as random noise, so any such model would only fit
noise. See docs/MODEL4_TEAM_FORMATION.md.

State: everything mutable lives in a per-request _Ctx (employee records,
typicality cache, required skills), so concurrent API requests never share
caches and burnout scores are always current. Only the (rarely changing)
historical-pairs table is TTL-cached in team_formation_features.

Public API
    recommend_teams(project_id, top_m=5, num_teams=3, task_ids=None) -> list[dict]
    check_composition(employee_ids) -> dict
"""

import itertools
import math
from collections.abc import Callable

import numpy as np
import pandas as pd

from .loader import get_team_composition_model
from .task_assignment_predict import recommend_top_n
from . import team_formation_features as tff

TEAM_WEIGHTS = {
    "task_fit": 0.45,
    "skill_coverage": 0.20,
    "experience_balance": 0.10,
    "workload_balance": 0.10,
    "historical_cooccurrence": 0.05,
    "composition_typicality": 0.10,
}

MAX_ROSTER_SEARCH_NODES = 200_000


class InfeasibleTeamFormationError(ValueError):
    """The candidate graph cannot produce the requested roster and allocation."""


class TeamFormationSearchExhaustedError(RuntimeError):
    """The bounded roster search stopped before establishing feasibility."""


# How many "why is it unusual" feature notes to return for a flagged team.
_MAX_NOTES = 3
_FEATURE_LABELS = {
    "dominant_dept_share": "share of the team from its largest department",
    "n_dept_ratio": "distinct departments per member",
    "seniority_mean": "average seniority level (1=Junior..5=Principal)",
    "seniority_std": "spread of seniority levels",
    "frac_Junior": "fraction Junior", "frac_Mid": "fraction Mid", "frac_Senior": "fraction Senior",
    "frac_Lead": "fraction Lead", "frac_Principal": "fraction Principal",
    "yoe_mean": "average years of experience", "yoe_std": "spread of years of experience",
    "tech_mean": "average technical proficiency", "collab_mean": "average collaboration score",
    "burnout_mean": "average burnout risk score",
    "skill_breadth_per_member": "distinct skills per member",
}


# ── Composition model (bundle) helpers ────────────────────────────────────────

def _feature_frame(teams: list, records: dict) -> pd.DataFrame:
    cols = get_team_composition_model()["feature_columns"]
    return pd.DataFrame([tff.team_features(t, records) for t in teams])[cols]


def _typicality_many(teams: list, records: dict) -> np.ndarray:
    """0-100 typicality for many rosters in ONE forest call (100 = typical)."""
    b = get_team_composition_model()
    raw = b["forest"].score_samples(b["scaler"].transform(_feature_frame(teams, records)))
    scaled = (raw - b["score_lo"]) / (b["score_hi"] - b["score_lo"]) * 100.0
    return np.clip(scaled, 0.0, 100.0)


def _explain_unusual(employee_ids: list, records: dict) -> list:
    """The features that deviate most from historical teams (z-score vs the
    training mean/std stored in the scaler) — so a flag comes with a reason."""
    b = get_team_composition_model()
    X = _feature_frame([employee_ids], records)
    z = b["scaler"].transform(X)[0]
    mean, scale = b["scaler"].mean_, b["scaler"].scale_
    order = np.argsort(-np.abs(z))[:_MAX_NOTES]
    notes = []
    for i in order:
        name = b["feature_columns"][i]
        if abs(z[i]) < 1.5:
            continue
        notes.append({
            "feature": name,
            "meaning": _FEATURE_LABELS.get(name, name),
            "this_team": round(float(X.iloc[0, i]), 2),
            "typical": round(float(mean[i]), 2),
            "std_devs_from_typical": round(float(z[i]), 1),
        })
    return notes


def check_composition(employee_ids: list) -> dict:
    """Standalone check: how typical is this exact roster? (no project needed)"""
    ids = [e.strip() for e in dict.fromkeys(employee_ids) if e and e.strip()]
    if len(ids) < 2:
        raise ValueError("Provide at least 2 employee_ids.")
    records = tff.load_employee_records()
    known = [i for i in ids if i in records]
    unknown = [i for i in ids if i not in records]
    if len(known) < 2:
        raise ValueError(f"Fewer than 2 known employee_ids (unknown: {unknown}).")

    b = get_team_composition_model()
    typ = float(_typicality_many([known], records)[0])
    unusual = typ < b["anomaly_threshold"]
    result = {
        "employee_ids": known,
        "composition_typicality": round(typ, 1),
        "unusual_composition": bool(unusual),
        "anomaly_threshold": round(b["anomaly_threshold"], 1),
        "unknown_employee_ids": unknown,
    }
    if unusual:
        result["composition_notes"] = _explain_unusual(known, records)
    return result


# ── Per-request context ───────────────────────────────────────────────────────

class _Ctx:
    def __init__(
        self,
        project_id: str,
        tasks: list,
        employees: list[dict],
        existing_workloads: dict[str, dict] | None = None,
    ):
        self.project_id = project_id
        self.tasks = {task["task_id"]: task for task in tasks}
        self.existing_workloads = existing_workloads or {}
        self.records = {}
        self.employee_profiles = {}
        for employee in employees:
            employee_id = employee["employee_id"]
            self.employee_profiles[employee_id] = employee
            level = employee.get("seniority_level")
            self.records[employee_id] = {
                "dept": employee.get("department"),
                "level": level,
                "sr": tff.SENIORITY_RANK.get(level, 2),
                "yoe": float(employee.get("years_of_experience") or 0),
                "tech": float(employee.get("technical_proficiency_score") or 50),
                "collab": float(employee.get("collaboration_score") or 50),
                "burn": (
                    float(employee["burnout_risk_score"])
                    if employee.get("burnout_risk_score") is not None
                    else 30.0
                ),
                "skills": tff._split_skills(
                    employee.get("primary_skills"),
                    employee.get("secondary_skills"),
                ),
                "skills_available": (
                    employee.get("primary_skills") is not None
                    and employee.get("secondary_skills") is not None
                ),
                "composition_available": (
                    bool(employee.get("department"))
                    and level in tff.SENIORITY_RANK
                    and employee.get("primary_skills") is not None
                    and employee.get("secondary_skills") is not None
                    and all(
                        _finite_score(employee.get(field)) is not None
                        for field in (
                            "years_of_experience",
                            "technical_proficiency_score",
                            "collaboration_score",
                            "burnout_risk_score",
                        )
                    )
                ),
            }
        self.hist_pairs = tff.load_historical_pairs()
        self.typ_cache: dict = {}
        self.required_skills = set()
        for t in tasks:
            self.required_skills |= tff._split_skills(t.get("required_skills"))

    def prime_typicality(self, rosters: list) -> None:
        keys = [frozenset(r) for r in rosters]
        todo = list({k for k in keys if k not in self.typ_cache})
        if todo:
            scores = _typicality_many([list(k) for k in todo], self.records)
            self.typ_cache.update(zip(todo, (float(x) for x in scores)))

    def typicality(self, member_ids) -> float:
        key = frozenset(member_ids)
        if key not in self.typ_cache:
            self.prime_typicality([list(key)])
        return self.typ_cache[key]


# ── Team scoring ──────────────────────────────────────────────────────────────

def _finite_score(value) -> float | None:
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return score if math.isfinite(score) else None


def _workload_balance_score(ctx: _Ctx, assignment: dict, member_ids: list[str]) -> float | None:
    """Score projected-load equality; missing estimates or baselines stay unavailable."""
    base = {}
    for employee_id in member_ids:
        workload = ctx.existing_workloads.get(employee_id)
        if not isinstance(workload, dict):
            return None
        if workload.get("missing_estimated_hours_count", 0):
            return None
        hours = _known_hours(workload.get("estimated_hours"))
        if hours is None:
            return None
        base[employee_id] = hours

    for task_id, task in ctx.tasks.items():
        employee_id = task.get("assigned_to")
        hours = _known_hours(task.get("estimated_hours"))
        if employee_id in base:
            if hours is None:
                return None
            base[employee_id] = max(0.0, base[employee_id] - hours)

    for task_id, candidate in assignment.items():
        task = ctx.tasks.get(task_id)
        if task is None:
            return None
        hours = _known_hours(task.get("estimated_hours"))
        employee_id = candidate.get("employee_id")
        if hours is None or employee_id not in base:
            return None
        base[employee_id] += hours

    profiles = ctx.employee_profiles
    capacities = [_valid_capacity(profiles.get(employee_id, {})) for employee_id in member_ids]
    if all(capacity is not None for capacity in capacities):
        projected_loads = [
            base[employee_id] / capacity
            for employee_id, capacity in zip(member_ids, capacities)
        ]
    else:
        projected_loads = [base[employee_id] for employee_id in member_ids]

    maximum = max(projected_loads, default=0.0)
    if maximum == 0:
        return 100.0
    return 100.0 * min(projected_loads) / maximum


def _team_features(ctx: _Ctx, assignment: dict, roster: set[str] | list[str]) -> dict:
    member_ids = sorted(set(roster))
    recs = [ctx.records[e] for e in member_ids if e in ctx.records]
    complete_roster = len(recs) == len(member_ids)

    team_skills: set = set()
    for r in recs:
        team_skills |= r["skills"]
    skill_coverage = (
        None
        if not ctx.required_skills
        or not complete_roster
        or any(not record["skills_available"] for record in recs)
        else len(team_skills & ctx.required_skills) / len(ctx.required_skills) * 100.0
    )

    levels = [r["sr"] for r in recs if r["level"] in tff.SENIORITY_RANK]
    experience_balance = min(100.0, len(set(levels)) / max(len(levels), 1) * 100 * 1.5) if levels else 0.0
    if not complete_roster or len(levels) != len(member_ids):
        experience_balance = None

    pairs = list(itertools.combinations(sorted(set(member_ids)), 2))
    historical_cooccurrence = (
        sum(1 for pair in pairs if pair in ctx.hist_pairs) / len(pairs) * 100.0
        if pairs and ctx.hist_pairs is not None
        else None
    )
    task_scores = [_finite_score(candidate.get("composite_score")) for candidate in assignment.values()]
    task_fit = (
        sum(task_scores) / len(task_scores)
        if task_scores and all(score is not None for score in task_scores)
        else None
    )

    return {
        "task_fit": task_fit,
        "skill_coverage": skill_coverage,
        "experience_balance": experience_balance,
        "workload_balance": _workload_balance_score(ctx, assignment, member_ids),
        "historical_cooccurrence": historical_cooccurrence,
        "composition_typicality": (
            _finite_score(ctx.typicality(member_ids))
            if complete_roster
            and all(record["composition_available"] for record in recs)
            else None
        ),
    }


def _team_score(features: dict) -> float | None:
    values = {key: _finite_score(features.get(key)) for key in TEAM_WEIGHTS}
    if any(value is None for value in values.values()):
        return None
    return sum(TEAM_WEIGHTS[key] * values[key] for key in TEAM_WEIGHTS)


# ── Roster selection and task allocation ─────────────────────────────────────

def _candidate_ids(candidates_per_task: dict) -> set[str]:
    return {
        candidate["employee_id"]
        for candidates in candidates_per_task.values()
        for candidate in candidates
    }


def _has_member_task_matching(roster: set[str], candidates_per_task: dict) -> bool:
    """Whether every roster member can receive at least one distinct task."""
    task_to_member = {}

    def place(member_id: str, visited_tasks: set[str]) -> bool:
        for task_id, candidates in candidates_per_task.items():
            if task_id in visited_tasks or not any(
                candidate["employee_id"] == member_id for candidate in candidates
            ):
                continue
            visited_tasks.add(task_id)
            assigned_member = task_to_member.get(task_id)
            if assigned_member is None or place(assigned_member, visited_tasks):
                task_to_member[task_id] = member_id
                return True
        return False

    members_by_options = sorted(
        roster,
        key=lambda member: sum(
            any(candidate["employee_id"] == member for candidate in candidates)
            for candidates in candidates_per_task.values()
        ),
    )
    return all(place(member_id, set()) for member_id in members_by_options)


def _select_rosters(
    candidates_per_task: dict,
    team_size: int,
    employee_priority: dict[str, tuple],
    limit: int,
) -> tuple[list[set[str]], bool]:
    """Search candidate-member subsets that cover tasks and admit member matching.

    Visits at most MAX_ROSTER_SEARCH_NODES recursive search nodes and stops
    earlier after finding `limit` rosters. The boolean is true only when the
    node budget stopped an unfinished search. Finding no rosters with that
    boolean false proves infeasibility; finding none with it true is unknown.
    Search order is heuristic and does not rank all feasible rosters globally.
    """
    task_ids = sorted(candidates_per_task)
    employee_ids = sorted(
        _candidate_ids(candidates_per_task),
        key=lambda employee_id: employee_priority.get(employee_id, ()),
    )
    task_members = {
        task_id: {candidate["employee_id"] for candidate in candidates}
        for task_id, candidates in candidates_per_task.items()
    }
    results = []
    chosen = set()
    nodes = 0
    truncated = False

    def search(start: int, covered_tasks: set[str]) -> None:
        nonlocal nodes, truncated
        if len(results) >= limit or truncated:
            return
        nodes += 1
        if nodes > MAX_ROSTER_SEARCH_NODES:
            truncated = True
            return

        remaining_slots = team_size - len(chosen)
        if remaining_slots == 0:
            if len(covered_tasks) == len(task_ids) and _has_member_task_matching(
                chosen, candidates_per_task
            ):
                results.append(set(chosen))
            return
        if len(employee_ids) - start < remaining_slots:
            return

        remaining = set(employee_ids[start:])
        if any(not (task_members[task_id] & (chosen | remaining)) for task_id in task_ids):
            return
        if any(
            not (task_members[task_id] & remaining)
            for task_id in task_ids
            if task_id not in covered_tasks
        ):
            return

        last_start = len(employee_ids) - remaining_slots
        for index in range(start, last_start + 1):
            employee_id = employee_ids[index]
            chosen.add(employee_id)
            newly_covered = {
                task_id for task_id in task_ids if employee_id in task_members[task_id]
            }
            search(index + 1, covered_tasks | newly_covered)
            chosen.remove(employee_id)
            if len(results) >= limit or truncated:
                return

    search(0, set())
    return results, truncated


def _valid_capacity(employee: dict) -> float | None:
    capacity = employee.get("weekly_capacity_hours")
    if capacity is None:
        return None
    try:
        value = float(capacity)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def _known_hours(value) -> float | None:
    if value is None:
        return None
    try:
        hours = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return hours if math.isfinite(hours) and hours >= 0 else None


def _workload_objective(
    roster: set[str],
    projected_hours: dict[str, float],
    employee_by_id: dict[str, dict],
) -> tuple[float, float]:
    """Return a lexicographic workload objective without imputing capacity.

    With valid capacity for every member, compare utilization spread first and
    estimated-hours spread second. If any capacity is missing/invalid, compare
    estimated-hours spread across the whole roster first; utilization spread
    among only the members with valid capacities is a secondary tie-breaker.
    These components are never combined arithmetically across different units.
    """
    hours = [projected_hours[employee_id] for employee_id in roster]
    capacities = {
        employee_id: _valid_capacity(employee_by_id[employee_id])
        for employee_id in roster
    }
    valid_members = [employee_id for employee_id in roster if capacities[employee_id]]

    if len(valid_members) == len(roster):
        ratios = [
            projected_hours[employee_id] / capacities[employee_id]
            for employee_id in roster
        ]
        return max(ratios) - min(ratios), max(hours) - min(hours)

    ratio_spread = 0.0
    if len(valid_members) > 1:
        ratios = [
            projected_hours[employee_id] / capacities[employee_id]
            for employee_id in valid_members
        ]
        ratio_spread = max(ratios) - min(ratios)
    return max(hours) - min(hours), ratio_spread


def _projected_base_workloads(
    tasks: list[dict],
    employee_ids: set[str],
    existing_workloads: dict[str, dict],
) -> dict[str, float]:
    base = {
        employee_id: (
            _known_hours(existing_workloads.get(employee_id, {}).get("estimated_hours"))
            or 0.0
        )
        for employee_id in employee_ids
    }
    for task in tasks:
        employee_id = task.get("assigned_to")
        hours = _known_hours(task.get("estimated_hours"))
        if employee_id in base and hours is not None:
            base[employee_id] = max(0.0, base[employee_id] - float(hours))
    return base


def _allocate_tasks(
    tasks: list[dict],
    candidates_per_task: dict,
    roster: set[str],
    employee_by_id: dict[str, dict],
    existing_workloads: dict[str, dict],
) -> dict[str, dict]:
    """Allocate all tasks to a fixed roster, balancing known projected workload."""
    task_ids = sorted(task["task_id"] for task in tasks)
    roster_candidates = {
        task_id: [
            candidate
            for candidate in candidates_per_task[task_id]
            if candidate["employee_id"] in roster
        ]
        for task_id in task_ids
    }
    for candidates in roster_candidates.values():
        candidates.sort(
            key=lambda candidate: (
                -float(candidate.get("composite_score") or 0),
                candidate["employee_id"],
            )
        )
    if any(not candidates for candidates in roster_candidates.values()):
        raise InfeasibleTeamFormationError(
            "The selected roster has no eligible candidate for at least one open task."
        )

    task_by_id = {task["task_id"]: task for task in tasks}
    task_to_employee = {}
    base_projected_hours = _projected_base_workloads(
        tasks, roster, existing_workloads
    )

    def match_member(employee_id: str, visited_tasks: set[str]) -> bool:
        def matching_preference(task_id: str) -> tuple:
            projected = base_projected_hours.copy()
            for assigned_task, assigned_employee in task_to_employee.items():
                if assigned_task in visited_tasks or assigned_task == task_id:
                    continue
                hours = _known_hours(task_by_id[assigned_task].get("estimated_hours"))
                if hours is not None:
                    projected[assigned_employee] += hours
            hours = _known_hours(task_by_id[task_id].get("estimated_hours"))
            if hours is not None:
                projected[employee_id] += hours
            model_score = next(
                candidate["composite_score"]
                for candidate in roster_candidates[task_id]
                if candidate["employee_id"] == employee_id
            )
            return (
                _workload_objective(roster, projected, employee_by_id),
                -float(model_score or 0),
                task_id,
            )

        eligible_tasks = sorted(
            (
                task_id
                for task_id, candidates in roster_candidates.items()
                if any(c["employee_id"] == employee_id for c in candidates)
            ),
            key=lambda task_id: (
                len(roster_candidates[task_id]),
                matching_preference(task_id),
            ),
        )
        for task_id in eligible_tasks:
            if task_id in visited_tasks:
                continue
            visited_tasks.add(task_id)
            prior_employee = task_to_employee.get(task_id)
            if prior_employee is None or match_member(prior_employee, visited_tasks):
                task_to_employee[task_id] = employee_id
                return True
        return False

    for employee_id in sorted(
        roster,
        key=lambda member: (
            sum(
                any(c["employee_id"] == member for c in candidates)
                for candidates in roster_candidates.values()
            ),
            member,
        ),
    ):
        if not match_member(employee_id, set()):
            raise InfeasibleTeamFormationError(
                "The candidate graph cannot assign at least one distinct task to every roster member."
            )

    assignment = {
        task_id: next(
            candidate for candidate in roster_candidates[task_id]
            if candidate["employee_id"] == employee_id
        )
        for task_id, employee_id in task_to_employee.items()
    }
    projected_hours = base_projected_hours.copy()
    for task_id, candidate in assignment.items():
        hours = _known_hours(task_by_id[task_id].get("estimated_hours"))
        if hours is not None:
            projected_hours[candidate["employee_id"]] += float(hours)

    remaining_tasks = sorted(
        (task for task in tasks if task["task_id"] not in assignment),
        key=lambda task: (
            _known_hours(task.get("estimated_hours")) is None,
            -(_known_hours(task.get("estimated_hours")) or 0),
            task["task_id"],
        ),
    )
    for task in remaining_tasks:
        task_id = task["task_id"]
        candidates = roster_candidates[task_id]
        hours = _known_hours(task.get("estimated_hours"))
        scored_options = []
        for candidate in candidates:
            employee_id = candidate["employee_id"]
            if hours is not None:
                projected_hours[employee_id] += float(hours)
            objective = _workload_objective(roster, projected_hours, employee_by_id)
            if hours is not None:
                projected_hours[employee_id] -= float(hours)
            scored_options.append((
                objective,
                -float(candidate.get("composite_score") or 0),
                employee_id,
                candidate,
            ))
        _, _, employee_id, selected = min(scored_options, key=lambda option: option[:3])
        assignment[task_id] = selected
        if hours is not None:
            projected_hours[employee_id] += float(hours)
    return assignment


def _validate_allocation(
    tasks: list[dict],
    candidates_per_task: dict,
    roster: set[str],
    assignment: dict[str, dict],
    team_size: int,
) -> None:
    expected_tasks = [task["task_id"] for task in tasks]
    if len(expected_tasks) != len(set(expected_tasks)):
        raise ValueError("Prepared open-task data contains duplicate task IDs.")
    if len(roster) != team_size:
        raise ValueError(f"Allocation has {len(roster)} roster members; expected {team_size}.")
    if len(assignment) != len(expected_tasks) or set(assignment) != set(expected_tasks):
        raise ValueError("Allocation must assign every open task exactly once.")

    assigned_members = set()
    for task_id, candidate in assignment.items():
        employee_id = candidate.get("employee_id")
        if employee_id not in roster:
            raise ValueError(f"Task {task_id!r} is assigned outside the selected roster.")
        if not any(
            item.get("employee_id") == employee_id
            for item in candidates_per_task[task_id]
        ):
            raise ValueError(
                f"Task {task_id!r} is assigned to ineligible employee {employee_id!r}."
            )
        assigned_members.add(employee_id)

    if assigned_members != roster:
        missing = sorted(roster - assigned_members)
        raise ValueError(f"Selected roster members have no assigned task: {missing}.")


def _employee_priority(
    candidates_per_task: dict,
    employees: list[dict],
    tasks: list[dict],
    existing_workloads: dict[str, dict],
) -> dict[str, tuple]:
    employee_by_id = {employee["employee_id"]: employee for employee in employees}
    employee_ids = _candidate_ids(candidates_per_task)
    base = _projected_base_workloads(tasks, employee_ids, existing_workloads)
    scores = {employee_id: [] for employee_id in employee_ids}
    for candidates in candidates_per_task.values():
        for candidate in candidates:
            scores[candidate["employee_id"]].append(
                float(candidate.get("composite_score") or 0)
            )
    return {
        employee_id: (
            base.get(employee_id, 0.0),
            -sum(scores[employee_id]) / max(len(scores[employee_id]), 1),
            employee_id,
        )
        for employee_id in employee_ids
        if employee_id in employee_by_id
    }


def _candidate_lists(
    tasks: list[dict],
    top_m: int,
    candidate_provider: Callable[[str, int], list[dict]] | None = None,
) -> dict[str, list[dict]]:
    """Adapter for Model 3; returned pairs define eligibility, without a threshold."""
    provider = candidate_provider or recommend_top_n
    candidates_per_task = {}
    for task in tasks:
        task_id = task["task_id"]
        candidates = provider(task_id, top_m)
        if not candidates:
            raise InfeasibleTeamFormationError(
                f"Model 3 returned no eligible candidates for open task {task_id!r}; "
                "increase the candidate limit or review employee data."
            )
        if any(candidate.get("task_id", task_id) != task_id for candidate in candidates):
            raise ValueError(f"Model 3 returned a candidate for the wrong task {task_id!r}.")
        unique_candidates = {}
        for candidate in candidates:
            employee_id = candidate.get("employee_id")
            if not employee_id:
                raise ValueError(f"Model 3 returned a candidate without employee_id for {task_id!r}.")
            unique_candidates.setdefault(employee_id, candidate)
        candidates_per_task[task_id] = list(unique_candidates.values())
    return candidates_per_task


def _build_recommendations(
    project_id: str,
    tasks: list[dict],
    candidates_per_task: dict[str, list[dict]],
    employees: list[dict],
    existing_workloads: dict[str, dict],
    team_size: int,
    num_teams: int,
    candidate_limit: int = 5,
    project_status: str | None = None,
) -> list[dict]:
    if team_size > len(tasks):
        raise InfeasibleTeamFormationError(
            f"Project team_size is {team_size}, but only {len(tasks)} open tasks exist; "
            "each selected employee must receive at least one task."
        )

    eligible_ids = _candidate_ids(candidates_per_task)
    employee_by_id = {employee["employee_id"]: employee for employee in employees}
    missing_profiles = eligible_ids - employee_by_id.keys()
    if missing_profiles:
        raise ValueError(
            "Model 3 returned employee IDs missing from prepared employee data: "
            f"{sorted(missing_profiles)}."
        )
    if len(eligible_ids) < team_size:
        raise InfeasibleTeamFormationError(
            f"Only {len(eligible_ids)} employees have eligible task pairs; "
            f"team_size requires {team_size}."
        )

    priority = _employee_priority(
        candidates_per_task, employees, tasks, existing_workloads
    )
    rosters, truncated = _select_rosters(
        candidates_per_task, team_size, priority, num_teams
    )
    if not rosters:
        if truncated:
            raise TeamFormationSearchExhaustedError(
                "Roster search exhausted its node budget before determining "
                "whether a feasible roster exists. Retry with fewer eligible "
                "employees/tasks or a larger search budget."
            )
        raise InfeasibleTeamFormationError(
            "The Model 3 candidate graph cannot cover every open task while "
            f"forming a {team_size}-employee roster with at least one task per member. "
            "Increase the candidate limit or review task requirements."
        )

    ctx = _Ctx(project_id, tasks, employees, existing_workloads)
    recommendations = []
    search_mode = "bounded_roster_search+greedy_allocation"
    if truncated:
        search_mode = "search_exhausted_with_feasible_rosters+greedy_allocation"
    for roster in rosters:
        assignment = _allocate_tasks(
            tasks, candidates_per_task, roster, employee_by_id, existing_workloads
        )
        try:
            _validate_allocation(
                tasks, candidates_per_task, roster, assignment, team_size
            )
        except ValueError as exc:
            raise ValueError(f"Generated allocation failed validation: {exc}") from exc
        recommendations.append(
            _format_result(
                ctx,
                search_mode,
                len(tasks),
                assignment,
                roster,
                candidate_limit=candidate_limit,
                project_status=project_status,
            )
        )
    return recommendations


def _format_result(
    ctx: _Ctx,
    search_mode: str,
    n_tasks: int,
    assignment: dict,
    roster: set[str],
    candidate_limit: int = 5,
    project_status: str | None = None,
) -> dict:
    features = _team_features(ctx, assignment, roster)
    b = get_team_composition_model()
    typicality = features["composition_typicality"]
    unusual = typicality is not None and typicality < b["anomaly_threshold"]
    displayed_features = {
        key: round(value, 1) if value is not None else None
        for key, value in features.items()
    }
    unavailable_components = [
        key for key in TEAM_WEIGHTS if displayed_features[key] is None
    ]
    result = {
        "project_id": ctx.project_id,
        "project_status": project_status,
        "candidate_limit": candidate_limit,
        "search_mode": search_mode,
        "n_tasks": n_tasks,
        "team_size": len(roster),
        "team_member_ids": sorted(roster),
        "team_score": (
            round(_team_score(displayed_features), 1)
            if not unavailable_components
            else None
        ),
        "unusual_composition": bool(unusual),
        "score_breakdown": displayed_features,
        "score_weights": dict(TEAM_WEIGHTS),
        "score_unavailable_components": unavailable_components,
        "assignments": [
            {
                **c,
                "task_id": t,
                "task_status": ctx.tasks.get(t, {}).get("status"),
                "task_assigned_to": ctx.tasks.get(t, {}).get("assigned_to"),
                "task_estimated_hours": ctx.tasks.get(t, {}).get("estimated_hours"),
                "task_required_skills": ctx.tasks.get(t, {}).get("required_skills"),
                "employee_id": c["employee_id"],
                "task_composite_score": c["composite_score"],
            }
            for t, c in assignment.items()
        ],
    }
    if unusual:
        result["composition_notes"] = _explain_unusual(sorted(roster), ctx.records)
    return result


# ── Public entry point ────────────────────────────────────────────────────────

def recommend_teams(
    project_id: str,
    top_m: int = 5,
    num_teams: int = 3,
    task_ids: list | None = None,
    *,
    candidate_provider: Callable[[str, int], list[dict]] | None = None,
) -> list:
    """
    Build up to `num_teams` distinct fixed-size rosters with eligible task allocations.

    Every pair returned by Model 3's top-`top_m` list is eligible; no extra score
    threshold is applied. Roster subsets are searched in a deterministic heuristic
    order and tasks are greedily allocated by projected workload. This does not
    guarantee a globally optimal roster or assignment. Search visits at most
    200,000 recursive nodes or stops after finding `num_teams` rosters. If the
    node budget is reached before any feasible roster is found, a distinct
    TeamFormationSearchExhaustedError is raised rather than claiming infeasibility.
    """
    top_m = max(1, int(top_m))
    num_teams = max(1, int(num_teams))

    prepared = tff.prepare_team_formation_data(project_id)
    tasks = prepared["tasks"]
    if not tasks:
        detail = (
            f" matching task_ids={task_ids}" if task_ids else ""
        )
        raise InfeasibleTeamFormationError(
            f"No open tasks found for project_id={project_id!r}{detail}; "
            "the project may be unknown or all its tasks may be completed/cancelled."
        )
    if task_ids and set(task_ids) != {task["task_id"] for task in tasks}:
        raise InfeasibleTeamFormationError(
            "Team Formation recommendations must include every open project task; "
            "task_ids cannot restrict the recommendation to a subset."
        )

    candidates_per_task = _candidate_lists(tasks, top_m, candidate_provider)
    return _build_recommendations(
        project_id=project_id,
        tasks=tasks,
        candidates_per_task=candidates_per_task,
        employees=prepared["employees"],
        existing_workloads=prepared["existing_workloads"],
        team_size=prepared["project"]["team_size"],
        num_teams=num_teams,
        candidate_limit=top_m,
        project_status=prepared["project"].get("current_status"),
    )
