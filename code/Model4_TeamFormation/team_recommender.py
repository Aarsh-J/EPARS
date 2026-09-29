"""
team_recommender.py
────────────────────────────────────────────────────────────────────────────────
Model 4 — Team Formation via Search + Composite Scoring
────────────────────────────────────────────────────────────────────────────────
NOT a trained supervised regressor. Reason: team_formations.csv's outcome
columns (actual_performance_score, met_deadline, quality_rating) are
generated in the dataset generator as pure `np.random.normal(...)` noise,
independent of team composition (verified against
Dataset Generator/Task_Performance_Feedback .py — see project notes). No
real historical team-level outcome exists to train against, so this module
does not attempt to predict one. Building it as a trained regressor on
that target would just be fitting noise (which is what the first version
of this model, scored on that target, was actually doing — R² was never
real signal, just small-sample variance).

Instead, Model 4 answers a different, well-posed question: given a
project already broken into tasks, and Model3 already able to score any
employee against any task (scheduler.py's novel_pair_regressor,
validated R²=0.851), *which combination* of one employee per task forms
the best TEAM — accounting for effects Model3 can't see, because it
scores one task/employee pair at a time with no visibility into who else
is on the team (skill coverage across the whole project, workload
balance across the group, seniority mix, and whether these people have
worked well together before).

Pipeline:
  1. For each task in the project, get top-M candidates from Model3's
     scheduler.recommend_top_n() — unchanged, no retraining.
  2. Solve an initial assignment (Hungarian algorithm) maximizing the
     sum of per-task scores, subject to no employee double-booked
     across tasks in this team.
  3. Local-search improvement: try swapping in each task's alternate
     candidates; keep any swap that improves the TEAM-level composite
     score (not just the per-task score). This is where team-composition
     effects actually get to influence the pick.
  4. Team-level score components — all computed from REAL, verified
     formulas (not the noisy fields):
       - skill_coverage: fraction of the project's required_skills
         covered by the union of the team's skills (same formula
         verified in Dataset Generator/team_formation_table_fix.py)
       - experience_balance: seniority-level diversity (same formula)
       - workload_balance: 100 - average burnout_risk_score across
         the team (same formula)
       - past_overlap_ratio: fraction of the team's member-pairs who
         have actually worked together before, from real
         team_formations.csv history (NOT the noisy
         collaborative_history_score column)
     combined with the mean per-task composite score from scheduler.py.

Weights below are a starting point, not a tuned optimum — same honesty
as scheduler.py's own WEIGHTS. There is no real historical team-outcome
label to tune them against; revisit if/when one exists. skill_coverage
is currently computed but excluded from active scoring (see
INCLUDE_SKILL_COVERAGE below) — being staged in deliberately, not cut.

Returns the top `num_teams` distinct teams for a project (default 3),
ranked best-first. For small projects every valid team is enumerated, so
these are the true top N. For realistic project sizes (double digits of
tasks), an exhaustive search isn't viable (see EXACT_SEARCH_MAX_COMBINATIONS)
so this runs several independent searches from different starting points
and returns the best distinct results found — a good set, not a provable
top N, at that scale.

Run:  python team_recommender.py --project-id PRJ001 --num-teams 3
"""

import os
import sys
import json
import argparse
import itertools
import warnings
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL3_DIR = os.path.join(BASE_DIR, "../Model3_TaskAssignment")
DATASET_DIR = os.path.join(BASE_DIR, "../../dataset")

sys.path.insert(0, MODEL3_DIR)
import scheduler as m3_scheduler  # noqa: E402  (Model3's Layer 3 — reused unmodified)

# Full intended weighting — sums to 1.0. Kept here as the reference
# version even while skill_coverage is switched off below, so re-enabling
# it later is a one-line change, not a redesign.
FULL_TEAM_WEIGHTS = {
    "task_fit": 0.55,          # mean of scheduler.py's per-task composite_score
    "skill_coverage": 0.20,    # project-wide required-skill coverage
    "experience_balance": 0.10,
    "workload_balance": 0.10,
    "past_overlap": 0.05,
}

# By request: build/validate the core model with skill_coverage OUT of
# active scoring first, add it back in once the rest is confirmed working.
# skill_coverage is still computed and reported in every result's
# score_breakdown — it just doesn't influence which team wins while this
# is False. Flip to True to re-enable (remaining weights auto-renormalize
# to keep summing to 1.0, so team_score stays on a comparable 0-100 scale
# either way).
INCLUDE_SKILL_COVERAGE = False


def _active_team_weights() -> dict:
    if INCLUDE_SKILL_COVERAGE:
        return dict(FULL_TEAM_WEIGHTS)
    remaining = {k: v for k, v in FULL_TEAM_WEIGHTS.items() if k != "skill_coverage"}
    total = sum(remaining.values())
    return {k: v / total for k, v in remaining.items()}


TEAM_WEIGHTS = _active_team_weights()
SENIORITY_RANK = {"Junior": 1, "Mid": 2, "Senior": 3, "Lead": 4, "Principal": 5}

# Above this, exact/brute-force team search is skipped in favor of the
# Hungarian + local-search heuristic (see module docstring, point 2-3).
EXACT_SEARCH_MAX_COMBINATIONS = 20_000

# How many distinct starting points to try in heuristic mode when asked
# for num_teams results — more restarts = better chance of finding
# num_teams genuinely distinct good teams, at a roughly linear time cost.
RESTARTS_PER_REQUESTED_TEAM = 8


_raw_employees = None
_historical_pairs = None


def _load_raw_employees():
    global _raw_employees
    if _raw_employees is None:
        path = os.path.join(DATASET_DIR, "employees.csv")
        df = pd.read_csv(path)
        df["all_skills_set"] = (
            df["primary_skills"].fillna("") + "," + df["secondary_skills"].fillna("")
        ).apply(lambda s: set(x.strip().lower() for x in s.split(",") if x.strip()))
        _raw_employees = df.set_index("employee_id")
    return _raw_employees


_employee_lookup = None


def _get_employee_lookup() -> dict:
    """employee_id -> plain-dict record (skills set, seniority rank,
    burnout score). Exact-mode search evaluates thousands of candidate
    teams, and repeated pandas .loc / Series.mean() calls per team
    (the original _team_features implementation) cost ~1.1ms each —
    17s for a 6-task project's 15,625 combinations. Plain dict lookups
    + Python loops over a handful of team members are orders of
    magnitude cheaper; this cache is built once per process."""
    global _employee_lookup
    if _employee_lookup is None:
        raw_emp = _load_raw_employees()
        lookup = {}
        for eid, row in raw_emp.iterrows():
            lookup[eid] = {
                "skills": row["all_skills_set"],
                "seniority_rank": SENIORITY_RANK.get(row.get("seniority_level")),
                "burnout": row.get("burnout_risk_score", 30.0) if pd.notna(row.get("burnout_risk_score")) else 30.0,
            }
        _employee_lookup = lookup
    return _employee_lookup


def _load_historical_pairs():
    """Every member-pair that has EVER co-occurred in a formed team —
    a real, verifiable synergy proxy (unlike the noisy
    collaborative_history_score column)."""
    global _historical_pairs
    if _historical_pairs is None:
        tf = pd.read_csv(os.path.join(DATASET_DIR, "team_formations.csv"))
        pairs = set()
        for _, row in tf.iterrows():
            members = [m.strip() for m in str(row["member_ids"]).split(",")]
            lead = row.get("team_lead_id")
            if pd.notna(lead):
                members = list(set(members + [lead]))
            pairs.update(itertools.combinations(sorted(members), 2))
        _historical_pairs = pairs
    return _historical_pairs


def get_project_tasks(project_id: str) -> pd.DataFrame:
    _, tasks, _, _ = m3_scheduler._load()
    proj_tasks = tasks[tasks["project_id"] == project_id]
    if proj_tasks.empty:
        raise ValueError(f"No tasks found for project_id={project_id!r}.")
    return proj_tasks


def get_candidates_per_task(project_id: str, top_m: int = 5) -> dict:
    """task_id -> list of candidate dicts from Model3's scheduler (unchanged)."""
    tasks = get_project_tasks(project_id)
    candidates = {}
    for task_id in tasks["task_id"]:
        candidates[task_id] = m3_scheduler.recommend_top_n(task_id, top_n=top_m)
    return candidates


def _initial_assignment(candidates_per_task: dict) -> dict:
    """Hungarian algorithm: maximize sum of per-task composite_score,
    subject to no employee assigned to more than one task in this team."""
    task_ids = list(candidates_per_task.keys())
    all_candidate_ids = sorted(set(
        c["employee_id"] for cands in candidates_per_task.values() for c in cands
    ))
    emp_idx = {eid: i for i, eid in enumerate(all_candidate_ids)}

    n_tasks, n_emps = len(task_ids), len(all_candidate_ids)
    # Large finite penalty for a (task, employee) pair with no score —
    # keeps the matrix square-able without ever being picked ahead of a
    # real candidate.
    NO_SCORE_PENALTY = -1000.0
    cost = np.full((n_tasks, n_emps), -NO_SCORE_PENALTY)  # cost = -score

    for t_i, task_id in enumerate(task_ids):
        for c in candidates_per_task[task_id]:
            e_i = emp_idx[c["employee_id"]]
            cost[t_i, e_i] = -c["composite_score"]

    row_ind, col_ind = linear_sum_assignment(cost)
    assignment = {}
    for t_i, e_i in zip(row_ind, col_ind):
        task_id = task_ids[t_i]
        eid = all_candidate_ids[e_i]
        match = next((c for c in candidates_per_task[task_id] if c["employee_id"] == eid), None)
        if match is None:
            # No real candidate available for this task within the pool —
            # fall back to its own top-1 even if it collides; the caller
            # validates and discards colliding results (see recommend_teams).
            match = candidates_per_task[task_id][0]
        assignment[task_id] = match

    # scipy's linear_sum_assignment on a rectangular matrix only returns
    # min(n_tasks, n_emps) pairs — if the union of every task's candidate
    # pool is smaller than n_tasks (possible with a small top_m on
    # heavily skill-clustered tasks), some tasks get silently dropped
    # entirely rather than mismatched. Never observed in testing at
    # top_m=5, but fail loudly rather than silently if it happens —
    # dropping a task from a "team" is worse than a duplicate, which at
    # least gets caught by the validation in recommend_teams().
    for task_id in task_ids:
        if task_id not in assignment:
            assignment[task_id] = candidates_per_task[task_id][0]
    return assignment


_required_skills_cache = {}


def _project_required_skills(project_id: str) -> set:
    """project_profile.csv (Model3's derived artifact) doesn't carry a
    required_skills column at all — only the raw per-task field does.
    Aggregating across the project's own tasks is also more precise
    than a project-level summary would be: it's exactly the set of
    skills this specific staffing plan needs to cover.

    Cached per project_id — this is invariant across every candidate
    team evaluated for that project within a search, and search modes
    call this thousands of times (once per candidate combination), so
    recomputing it from a fresh DataFrame filter every call was the
    single largest cost in exact-mode search (~16s of a 32s run on a
    6-task project, confirmed by profiling before this fix)."""
    if project_id not in _required_skills_cache:
        tasks = get_project_tasks(project_id)
        skills = set()
        for val in tasks["required_skills"].fillna(""):
            skills |= set(s.strip().lower() for s in str(val).split(",") if s.strip())
        _required_skills_cache[project_id] = skills
    return _required_skills_cache[project_id]


def _team_features(assignment: dict, project_id: str) -> dict:
    lookup = _get_employee_lookup()
    member_ids = [c["employee_id"] for c in assignment.values()]
    records = [lookup[eid] for eid in member_ids if eid in lookup]
    n = len(records)

    required_skills = _project_required_skills(project_id)
    team_skills = set()
    for r in records:
        team_skills |= r["skills"]
    skill_coverage = (
        100.0 if not required_skills
        else len(team_skills & required_skills) / len(required_skills) * 100.0
    )

    seniority_vals = [r["seniority_rank"] for r in records if r["seniority_rank"] is not None]
    experience_balance = min(
        100.0, len(set(seniority_vals)) / max(len(seniority_vals), 1) * 100 * 1.5
    ) if seniority_vals else 0.0

    avg_burnout = (sum(r["burnout"] for r in records) / n) if n else 30.0
    workload_balance = max(0.0, 100.0 - avg_burnout)

    hist_pairs = _load_historical_pairs()
    member_pairs = list(itertools.combinations(sorted(set(member_ids)), 2))
    past_overlap = (
        sum(1 for p in member_pairs if p in hist_pairs) / len(member_pairs)
        if member_pairs else 0.0
    ) * 100.0

    task_fit_mean = sum(c["composite_score"] for c in assignment.values()) / len(assignment)

    return {
        "task_fit": task_fit_mean,
        "skill_coverage": skill_coverage,
        "experience_balance": experience_balance,
        "workload_balance": workload_balance,
        "past_overlap": past_overlap,
    }


def _team_score(features: dict) -> float:
    return sum(TEAM_WEIGHTS[k] * features[k] for k in TEAM_WEIGHTS)


def _local_search(assignment: dict, candidates_per_task: dict, project_id: str,
                   max_rounds: int = 10) -> dict:
    """Hill-climbing: try swapping each task's assignee for one of its
    other candidates; keep the swap if TEAM score improves. Repeat until
    no improving swap is found or max_rounds is hit."""
    current = dict(assignment)
    current_score = _team_score(_team_features(current, project_id))

    for _ in range(max_rounds):
        improved = False
        used_ids = set(c["employee_id"] for c in current.values())

        for task_id, cands in candidates_per_task.items():
            current_pick = current[task_id]
            for alt in cands:
                if alt["employee_id"] == current_pick["employee_id"]:
                    continue
                if alt["employee_id"] in used_ids:
                    continue  # would double-book — skip (kept simple; a
                    # full swap-with-the-holder version is a possible
                    # future improvement if this proves too restrictive)

                trial = dict(current)
                trial[task_id] = alt
                trial_score = _team_score(_team_features(trial, project_id))

                if trial_score > current_score:
                    current = trial
                    current_score = trial_score
                    used_ids = set(c["employee_id"] for c in current.values())
                    improved = True
                    break
            if improved:
                break

        if not improved:
            break

    return current


def _assignment_key(assignment: dict) -> tuple:
    """Canonical form of an assignment, for de-duplicating teams that
    different restarts/searches converged to independently."""
    return tuple(sorted((task_id, c["employee_id"]) for task_id, c in assignment.items()))


def _format_result(project_id: str, search_mode: str, n_tasks: int, assignment: dict) -> dict:
    features = _team_features(assignment, project_id)
    team_score = _team_score(features)
    return {
        "project_id": project_id,
        "search_mode": search_mode,
        "n_tasks": n_tasks,
        "team_score": round(team_score, 1),
        "score_breakdown": {k: round(v, 1) for k, v in features.items()},
        "assignments": [
            {
                "task_id": task_id,
                "employee_id": c["employee_id"],
                "task_composite_score": c["composite_score"],
            }
            for task_id, c in assignment.items()
        ],
    }


def _randomized_greedy_assignment(candidates_per_task: dict, rng: "random.Random") -> dict:
    """A different, non-Hungarian starting point for search diversity:
    shuffle task order, then greedily take each task's best
    still-available candidate. Cheap way to reach a genuinely different
    local optimum than the Hungarian-seeded search does.

    Fallback when a task's own top-M pool is fully claimed: rather than
    force a collision and hope local search repairs it (it doesn't —
    local search only refuses to create NEW collisions, it never
    actively fixes an inherited one, confirmed by testing), fall back
    to the union of every OTHER task's candidate pool, restricted to
    still-unused employees. Costs no extra model calls (all already in
    memory) and keeps every restart valid from the start, so it isn't
    later discarded by the validation check in recommend_teams()."""
    task_ids = list(candidates_per_task.keys())
    rng.shuffle(task_ids)
    all_candidates_pool = [c for cands in candidates_per_task.values() for c in cands]

    used = set()
    assignment = {}
    for task_id in task_ids:
        cands = candidates_per_task[task_id]
        pick = next((c for c in cands if c["employee_id"] not in used), None)
        if pick is None:
            # This task's own top-M is exhausted — borrow from the wider
            # pool (imperfect fit for this specific task, but valid and
            # free; local search may still improve on it).
            pick = next((c for c in all_candidates_pool if c["employee_id"] not in used), None)
        if pick is None:
            # Entire known candidate universe exhausted (only possible
            # with a very small top_m relative to n_tasks) — let this
            # restart collide; recommend_teams() discards invalid results.
            pick = cands[0]
        assignment[task_id] = pick
        used.add(pick["employee_id"])
    return assignment


def recommend_teams(project_id: str, top_m: int = 5, num_teams: int = 3) -> list:
    """
    Main entry point. Returns up to num_teams distinct recommended teams
    for a project, best first, each with its team-level score breakdown
    and per-task assignment.

    Exact mode (small projects): every valid combination is enumerated
    anyway, so the top num_teams by score are the true top num_teams —
    no approximation.

    Heuristic mode (realistic project sizes): runs several independent
    searches from different starting points (the Hungarian-optimal seed,
    plus randomized-greedy restarts) and local-searches each to its own
    optimum, then de-duplicates and ranks the results. This is a search
    over good candidates, not a guarantee of the true top-num_teams —
    honest expectation given the project scale (see module docstring on
    why brute force isn't viable here).
    """
    candidates_per_task = get_candidates_per_task(project_id, top_m=top_m)
    n_tasks = len(candidates_per_task)
    combo_space = top_m ** n_tasks
    search_mode = "exact" if combo_space <= EXACT_SEARCH_MAX_COMBINATIONS else "hungarian+local_search"

    if search_mode == "exact":
        task_ids = list(candidates_per_task.keys())
        scored = []
        for combo in itertools.product(*(candidates_per_task[t] for t in task_ids)):
            eids = [c["employee_id"] for c in combo]
            if len(set(eids)) != len(eids):
                continue  # reject double-booked combos
            assignment = dict(zip(task_ids, combo))
            score = _team_score(_team_features(assignment, project_id))
            scored.append((score, assignment))

        if not scored:
            raise ValueError(
                f"No valid distinct-employee assignment exists for {project_id} "
                f"with top_m={top_m} — try a larger top_m."
            )
        scored.sort(key=lambda x: x[0], reverse=True)
        top_assignments = [a for _, a in scored[:num_teams]]

    else:
        import random
        rng = random.Random(42)  # fixed seed — reproducible restarts run to run

        n_restarts = max(num_teams * RESTARTS_PER_REQUESTED_TEAM, 10)
        starts = [_initial_assignment(candidates_per_task)]
        starts += [_randomized_greedy_assignment(candidates_per_task, rng) for _ in range(n_restarts - 1)]

        seen = {}
        for start in starts:
            final = _local_search(start, candidates_per_task, project_id)

            # _local_search only ever refuses to SWAP INTO an already-used
            # candidate — it never actively repairs a pre-existing
            # collision. _randomized_greedy_assignment's fallback (used
            # when a task's whole top-M pool is already claimed) can
            # produce exactly that kind of collision as its starting
            # point. Rather than trust local search to fix what it isn't
            # designed to fix, validate here and discard anything invalid
            # — confirmed necessary: this caught real double-bookings
            # during testing (PRJ008/PRJ703, top_m=5).
            eids = [c["employee_id"] for c in final.values()]
            if len(final) != n_tasks or len(eids) != len(set(eids)):
                continue

            key = _assignment_key(final)
            if key in seen:
                continue
            seen[key] = final

        ranked = sorted(
            seen.values(),
            key=lambda a: _team_score(_team_features(a, project_id)),
            reverse=True,
        )
        top_assignments = ranked[:num_teams]

    return [_format_result(project_id, search_mode, n_tasks, a) for a in top_assignments]


def recommend_team(project_id: str, top_m: int = 5) -> dict:
    """Convenience wrapper — single best team. See recommend_teams()."""
    return recommend_teams(project_id, top_m=top_m, num_teams=1)[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Model 4 — team recommender demo")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--top-m", type=int, default=5)
    parser.add_argument("--num-teams", type=int, default=3)
    args = parser.parse_args()

    _, tasks, projects, _ = m3_scheduler._load()
    project_id = args.project_id or projects.iloc[0]["project_id"]

    print(f"Recommending top {args.num_teams} teams for project_id={project_id} "
          f"(top_m={args.top_m} candidates/task)...\n")
    results = recommend_teams(project_id, top_m=args.top_m, num_teams=args.num_teams)
    print(f"Found {len(results)} distinct team(s).\n")
    print(json.dumps(results, indent=2))