"""
modules/ml/team_formation_predict.py
========================================
Model4: team formation, ported from preprocessor:code/Model4_TeamFormation/
team_recommender.py onto the live DB (see team_formation_features.py).

Two parts, same as on the preprocessor branch:
  (a) search + composite team scoring — reuses Model3 (task_assignment_predict.
      recommend_top_n) for per-task candidates, then searches for the best
      one-employee-per-task TEAM (Hungarian seed + local search; exact
      enumeration for small projects).
  (b) a TRAINED unsupervised component — an Isolation Forest
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
import random

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from .loader import get_team_composition_model
from .task_assignment_predict import recommend_top_n
from . import team_formation_features as tff

# Full intended weighting — sums to 1.0. skill_coverage is computed and reported
# but switched off (INCLUDE_SKILL_COVERAGE=False), exactly as on the preprocessor
# branch; flip it to True to re-enable (other weights auto-renormalise).
FULL_TEAM_WEIGHTS = {
    "task_fit": 0.45,
    "skill_coverage": 0.20,
    "experience_balance": 0.10,
    "workload_balance": 0.10,
    "past_overlap": 0.05,
    "composition_typicality": 0.10,
}
INCLUDE_SKILL_COVERAGE = False


def _active_team_weights() -> dict:
    if INCLUDE_SKILL_COVERAGE:
        return dict(FULL_TEAM_WEIGHTS)
    remaining = {k: v for k, v in FULL_TEAM_WEIGHTS.items() if k != "skill_coverage"}
    total = sum(remaining.values())
    return {k: v / total for k, v in remaining.items()}


TEAM_WEIGHTS = _active_team_weights()

# Above this many combinations, skip exhaustive search for Hungarian + local search.
EXACT_SEARCH_MAX_COMBINATIONS = 20_000
RESTARTS_PER_REQUESTED_TEAM = 8

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
    def __init__(self, project_id: str, tasks: list):
        self.project_id = project_id
        self.records = tff.load_employee_records()
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

def _team_features(ctx: _Ctx, assignment: dict) -> dict:
    member_ids = [c["employee_id"] for c in assignment.values()]
    recs = [ctx.records[e] for e in member_ids if e in ctx.records]
    n = len(recs)

    team_skills: set = set()
    for r in recs:
        team_skills |= r["skills"]
    skill_coverage = (
        100.0 if not ctx.required_skills
        else len(team_skills & ctx.required_skills) / len(ctx.required_skills) * 100.0
    )

    levels = [r["sr"] for r in recs]
    experience_balance = min(100.0, len(set(levels)) / max(len(levels), 1) * 100 * 1.5) if levels else 0.0

    avg_burnout = (sum(r["burn"] for r in recs) / n) if n else 30.0
    workload_balance = max(0.0, 100.0 - avg_burnout)

    pairs = list(itertools.combinations(sorted(set(member_ids)), 2))
    past_overlap = (sum(1 for p in pairs if p in ctx.hist_pairs) / len(pairs) if pairs else 0.0) * 100.0

    return {
        "task_fit": sum(c["composite_score"] for c in assignment.values()) / len(assignment),
        "skill_coverage": skill_coverage,
        "experience_balance": experience_balance,
        "workload_balance": workload_balance,
        "past_overlap": past_overlap,
        "composition_typicality": ctx.typicality(member_ids),
    }


def _team_score(features: dict) -> float:
    return sum(TEAM_WEIGHTS[k] * features[k] for k in TEAM_WEIGHTS)


# ── Search ────────────────────────────────────────────────────────────────────

def _initial_assignment(candidates_per_task: dict) -> dict:
    """Hungarian: maximise sum of per-task composite_score, no employee double-booked."""
    task_ids = list(candidates_per_task)
    all_ids = sorted({c["employee_id"] for cands in candidates_per_task.values() for c in cands})
    emp_idx = {e: i for i, e in enumerate(all_ids)}

    cost = np.full((len(task_ids), len(all_ids)), 1000.0)
    for t_i, tid in enumerate(task_ids):
        for c in candidates_per_task[tid]:
            cost[t_i, emp_idx[c["employee_id"]]] = -c["composite_score"]

    rows, cols = linear_sum_assignment(cost)
    assignment = {}
    for t_i, e_i in zip(rows, cols):
        tid, eid = task_ids[t_i], all_ids[e_i]
        match = next((c for c in candidates_per_task[tid] if c["employee_id"] == eid), None)
        assignment[tid] = match or candidates_per_task[tid][0]
    for tid in task_ids:  # rectangular matrix can drop tasks; never drop silently
        assignment.setdefault(tid, candidates_per_task[tid][0])
    return assignment


def _randomized_greedy_assignment(candidates_per_task: dict, rng: random.Random) -> dict:
    task_ids = list(candidates_per_task)
    rng.shuffle(task_ids)
    pool = [c for cands in candidates_per_task.values() for c in cands]
    used, assignment = set(), {}
    for tid in task_ids:
        cands = candidates_per_task[tid]
        pick = next((c for c in cands if c["employee_id"] not in used), None) \
            or next((c for c in pool if c["employee_id"] not in used), None) \
            or cands[0]
        assignment[tid] = pick
        used.add(pick["employee_id"])
    return assignment


def _local_search(ctx: _Ctx, assignment: dict, candidates_per_task: dict, max_rounds: int = 10) -> dict:
    current = dict(assignment)
    current_score = _team_score(_team_features(ctx, current))

    for _ in range(max_rounds):
        used = {c["employee_id"] for c in current.values()}

        # Score every roster this round could try in ONE forest call, so the
        # per-swap evaluations below are cache hits.
        trials = []
        for tid, cands in candidates_per_task.items():
            for alt in cands:
                if alt["employee_id"] in used:
                    continue
                trials.append([alt["employee_id"] if t == tid else current[t]["employee_id"] for t in current])
        ctx.prime_typicality(trials)

        improved = False
        for tid, cands in candidates_per_task.items():
            for alt in cands:
                if alt["employee_id"] == current[tid]["employee_id"] or alt["employee_id"] in used:
                    continue
                trial = dict(current)
                trial[tid] = alt
                trial_score = _team_score(_team_features(ctx, trial))
                if trial_score > current_score:
                    current, current_score, improved = trial, trial_score, True
                    break
            if improved:
                break
        if not improved:
            break
    return current


def _roster_key(assignment: dict) -> frozenset:
    """Teams are distinct by WHO is on them. The same people with two tasks
    swapped is the same team, so only the best task mapping per roster is kept."""
    return frozenset(c["employee_id"] for c in assignment.values())


def _format_result(ctx: _Ctx, search_mode: str, n_tasks: int, assignment: dict) -> dict:
    features = _team_features(ctx, assignment)
    b = get_team_composition_model()
    unusual = features["composition_typicality"] < b["anomaly_threshold"]
    result = {
        "project_id": ctx.project_id,
        "search_mode": search_mode,
        "n_tasks": n_tasks,
        "team_score": round(_team_score(features), 1),
        "unusual_composition": bool(unusual),
        "score_breakdown": {k: round(v, 1) for k, v in features.items()},
        "assignments": [
            {"task_id": t, "employee_id": c["employee_id"], "task_composite_score": c["composite_score"]}
            for t, c in assignment.items()
        ],
    }
    if unusual:
        result["composition_notes"] = _explain_unusual([c["employee_id"] for c in assignment.values()], ctx.records)
    return result


# ── Public entry point ────────────────────────────────────────────────────────

def recommend_teams(project_id: str, top_m: int = 5, num_teams: int = 3, task_ids: list | None = None) -> list:
    """
    Up to `num_teams` distinct teams (one employee per open task), best first.

    Exact mode (top_m ** n_tasks <= 20,000): every valid team is enumerated, so
    the results are the true top N. Heuristic mode (bigger projects): several
    Hungarian/greedy-seeded local searches, de-duplicated — a good set, not a
    provable top N.

    Raises ValueError for an unknown project / no open tasks / no feasible team.
    """
    top_m = max(1, int(top_m))
    num_teams = max(1, int(num_teams))

    tasks = tff.get_project_tasks(project_id, task_ids=task_ids)
    if not tasks:
        raise ValueError(
            f"No open tasks found for project_id={project_id!r}"
            + (f" matching task_ids={task_ids}" if task_ids else "")
            + " (unknown project, or all its tasks are Completed/Cancelled)."
        )

    # Per-task candidates from Model3 (unchanged).
    candidates_per_task = {t["task_id"]: recommend_top_n(t["task_id"], top_n=top_m) for t in tasks}
    n_tasks = len(candidates_per_task)

    ctx = _Ctx(project_id, tasks)
    search_mode = "exact" if top_m ** n_tasks <= EXACT_SEARCH_MAX_COMBINATIONS else "hungarian+local_search"

    if search_mode == "exact":
        task_ids_ordered = list(candidates_per_task)
        combos = []
        for combo in itertools.product(*(candidates_per_task[t] for t in task_ids_ordered)):
            eids = [c["employee_id"] for c in combo]
            if len(set(eids)) == len(eids):  # reject double-booked combos
                combos.append(combo)
        if not combos:
            raise ValueError(
                f"No valid distinct-employee team exists for {project_id} with top_m={top_m} — try a larger top_m."
            )
        ctx.prime_typicality([[c["employee_id"] for c in combo] for combo in combos])
        scored = []
        for combo in combos:
            a = dict(zip(task_ids_ordered, combo))
            scored.append((_team_score(_team_features(ctx, a)), a))
        scored.sort(key=lambda x: x[0], reverse=True)
        top, seen_rosters = [], set()
        for _, a in scored:
            key = _roster_key(a)
            if key in seen_rosters:
                continue
            seen_rosters.add(key)
            top.append(a)
            if len(top) == num_teams:
                break
    else:
        rng = random.Random(42)  # fixed seed -> reproducible restarts
        n_restarts = max(num_teams * RESTARTS_PER_REQUESTED_TEAM, 10)
        starts = [_initial_assignment(candidates_per_task)]
        starts += [_randomized_greedy_assignment(candidates_per_task, rng) for _ in range(n_restarts - 1)]

        seen = {}
        for start in starts:
            final = _local_search(ctx, start, candidates_per_task)
            eids = [c["employee_id"] for c in final.values()]
            if len(final) != n_tasks or len(eids) != len(set(eids)):
                continue  # local search never repairs a pre-existing double-booking: discard
            key = _roster_key(final)
            if key not in seen or _team_score(_team_features(ctx, final)) > _team_score(_team_features(ctx, seen[key])):
                seen[key] = final

        if not seen:
            raise ValueError(
                f"No valid distinct-employee team found for {project_id} with top_m={top_m} — try a larger top_m."
            )
        top = sorted(seen.values(), key=lambda a: _team_score(_team_features(ctx, a)), reverse=True)[:num_teams]

    return [_format_result(ctx, search_mode, n_tasks, a) for a in top]
