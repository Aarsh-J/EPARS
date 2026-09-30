"""
generate_surrogate_data.py
────────────────────────────────────────────────────────────────────────────────
Builds training data for a team-formation SURROGATE regressor.

Label:   the REAL team_score computed by team_recommender.py's full
         pipeline (Model3's validated R2=0.851 regressor + verified
         formulas) for a given candidate team — real, non-noisy.
Features: cheap team/project attributes that DON'T require calling
         Model3 per task — the whole point being that once trained,
         team quality can be estimated directly from composition
         without running the expensive per-task scoring first.

Since the label is computed on demand (not scarce historical data),
training data isn't limited to the 606 historically-noisy team rows —
generates as many examples as needed by sampling diverse candidate
teams across many projects and scoring them for real.

Per project: fetch each task's top-M candidates from Model3 ONCE (the
one genuinely expensive step), then derive several diverse candidate
teams from that same fetch (Hungarian+local-search result, a few
randomized-greedy snapshots, a couple of deliberately-random low-quality
assignments for score spread) — reusing the expensive fetch across many
labeled examples instead of paying for it once per example.

Run:  python generate_surrogate_data.py
"""

import os
import random
import warnings

import numpy as np
import pandas as pd

import team_recommender as tr

warnings.filterwarnings("ignore")

OUT_DIR = os.path.join(tr.BASE_DIR, "artifacts")
os.makedirs(OUT_DIR, exist_ok=True)

N_PROJECTS = 300
TEAMS_PER_PROJECT = 10
TOP_M = 5
SEED = 42


def _cheap_team_features(assignment: dict, project_id: str) -> dict:
    """Team/project attributes computable WITHOUT calling Model3 per
    task — this is the whole point of the surrogate."""
    lookup = tr._get_employee_lookup()
    emp_profile, _, _, _ = tr.m3_scheduler._load()  # (employees, tasks, projects, regressor)
    profile_idx = emp_profile.set_index("employee_id")

    member_ids = [c["employee_id"] for c in assignment.values()]
    n = len(member_ids)

    # From raw employees.csv (via team_recommender's own lookup) — real
    # formulas already verified against the dataset generator.
    records = [lookup[eid] for eid in member_ids if eid in lookup]
    seniority_vals = [r["seniority_rank"] for r in records if r["seniority_rank"] is not None]
    avg_seniority = np.mean(seniority_vals) if seniority_vals else 0.0
    seniority_diversity = len(set(seniority_vals))
    avg_burnout_raw = np.mean([r["burnout"] for r in records]) if records else 30.0

    required_skills = tr._project_required_skills(project_id)
    team_skills = set()
    for r in records:
        team_skills |= r["skills"]
    skill_coverage = (
        100.0 if not required_skills
        else len(team_skills & required_skills) / len(required_skills) * 100.0
    )

    hist_pairs = tr._load_historical_pairs()
    import itertools
    member_pairs = list(itertools.combinations(sorted(set(member_ids)), 2))
    past_overlap = (
        sum(1 for p in member_pairs if p in hist_pairs) / len(member_pairs)
        if member_pairs else 0.0
    ) * 100.0

    # From Model3's own preprocessed employee_profile.csv — already
    # engineered, no extra joins needed.
    prof_cols = [
        "technical_proficiency_score", "domain_expertise_score",
        "historical_performance_score", "average_task_completion_rate",
        "collaboration_score", "burnout_risk_score", "overall_burnout_risk",
        "job_satisfaction", "schedule_load_ratio", "health_risk", "on_time_rate",
    ]
    member_profiles = profile_idx.loc[profile_idx.index.intersection(member_ids)]
    prof_means = {f"mean_{c}": member_profiles[c].mean() for c in prof_cols}
    prof_mins = {f"min_{c}": member_profiles[c].min() for c in ["collaboration_score", "average_task_completion_rate"]}

    # Project-level: aggregate this project's own tasks (numeric already).
    tasks = tr.get_project_tasks(project_id)
    task_cols = ["priority", "complexity", "estimated_hours", "story_points",
                 "n_required_skills", "planned_duration_days", "n_dependencies",
                 "risk_level", "business_impact", "delay_risk_score"]
    task_means = {f"proj_mean_{c}": tasks[c].mean() for c in task_cols}

    features = {
        "n_tasks": n,
        "avg_seniority": avg_seniority,
        "seniority_diversity": seniority_diversity,
        "avg_burnout_raw": avg_burnout_raw,
        "skill_coverage_cheap": skill_coverage,
        "past_overlap_cheap": past_overlap,
        **prof_means, **prof_mins, **task_means,
    }
    return features


WIDE_POOL_SIZE = 100  # fetched once per task — same cost as top_m=5, since
# scheduler.py's regressor.predict() scores the WHOLE company regardless
# of how many results are truncated to; only the truncation point differs.


def _mediocre_or_poor_assignment(wide_candidates_per_task: dict, rng: random.Random,
                                  rank_lo: int, rank_hi: int) -> dict:
    """Deliberately picks from the middle/bottom of each task's full
    ranked candidate list (not just the top-5), to generate genuinely
    low-quality teams. Without this, every generated example — even the
    'random' ones — was secretly still good, because every candidate
    came from a top-5-per-task pool. Confirmed by testing: within-project
    team_score range was only 1-4 points without this."""
    used = set()
    assignment = {}
    task_ids = list(wide_candidates_per_task.keys())
    rng.shuffle(task_ids)
    for task_id in task_ids:
        pool = wide_candidates_per_task[task_id]
        lo, hi = min(rank_lo, len(pool) - 1), min(rank_hi, len(pool))
        band = pool[lo:hi] if hi > lo else pool[-1:]
        rng.shuffle(band)
        pick = next((c for c in band if c["employee_id"] not in used), None)
        if pick is None:
            pick = next((c for c in pool if c["employee_id"] not in used), pool[0])
        assignment[task_id] = pick
        used.add(pick["employee_id"])
    return assignment


def generate():
    rng = random.Random(SEED)
    _, tasks_df, projects_df, _ = tr.m3_scheduler._load()
    all_project_ids = tasks_df["project_id"].unique().tolist()
    rng.shuffle(all_project_ids)
    sample_projects = all_project_ids[:N_PROJECTS]

    rows = []
    for i, pid in enumerate(sample_projects):
        try:
            tasks_for_proj = tr.get_project_tasks(pid)
            wide_candidates_per_task = {
                task_id: tr.m3_scheduler.recommend_top_n(task_id, top_n=WIDE_POOL_SIZE)
                for task_id in tasks_for_proj["task_id"]
            }
        except ValueError:
            continue  # e.g. no tasks found — skip

        candidates_per_task = {t: c[:TOP_M] for t, c in wide_candidates_per_task.items()}
        n_tasks = len(candidates_per_task)
        variants = []

        # 1. Hungarian + local search on the top-M pool (high quality —
        #    same as production search)
        initial = tr._initial_assignment(candidates_per_task)
        variants.append(tr._local_search(initial, candidates_per_task, pid))

        # 2. Randomized-greedy + local search on top-M (diverse, still decent)
        for _ in range(2):
            start = tr._randomized_greedy_assignment(candidates_per_task, rng)
            variants.append(tr._local_search(start, candidates_per_task, pid))

        # 3. Randomized-greedy on top-M, WITHOUT local search (medium)
        for _ in range(2):
            variants.append(tr._randomized_greedy_assignment(candidates_per_task, rng))

        # 4. Mid-ranked picks (ranks ~20-50 of 100) — mediocre teams
        for _ in range(2):
            variants.append(_mediocre_or_poor_assignment(wide_candidates_per_task, rng, 20, 50))

        # 5. Low-ranked picks (ranks ~70-100 of 100) — genuinely poor teams
        for _ in range(3):
            variants.append(_mediocre_or_poor_assignment(wide_candidates_per_task, rng, 70, 100))

        for assignment in variants[:TEAMS_PER_PROJECT]:
            eids = [c["employee_id"] for c in assignment.values()]
            if len(assignment) != n_tasks or len(eids) != len(set(eids)):
                continue  # invalid — skip, same validation as recommend_teams()

            label_features = tr._team_features(assignment, pid)
            label_score = tr._team_score(label_features)

            cheap_features = _cheap_team_features(assignment, pid)
            cheap_features["team_score"] = label_score
            cheap_features["project_id"] = pid
            rows.append(cheap_features)

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(sample_projects)} projects processed, {len(rows)} rows so far")

    df = pd.DataFrame(rows)
    out_path = os.path.join(OUT_DIR, "surrogate_training_data.csv")
    df.to_csv(out_path, index=False)
    print(f"\nSaved {len(df)} rows, {df.shape[1]} columns -> {out_path}")
    print(f"team_score distribution:\n{df['team_score'].describe()}")
    return df


if __name__ == "__main__":
    generate()
