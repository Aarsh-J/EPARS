"""
04a_team_formations.py — Generate team_formations.csv
Uses 5-phase skill-coverage algorithm for team composition.
predicted_success_rate is computed from measurable team factors (not random).
Runs BEFORE task_assignments so assignments can pull from team pools.
"""

import os, random, json
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config import (
    SENIOR_LEVELS, SENIORITY_BOOST,
    FORMATION_METHOD, FORMATION_WEIGHTS,
    TEAM_STATUS, TEAM_STATUS_W, DISSOLVE_REASON, TEAM_NAMES,
    DEPT_SKILLS,
    clamp, rand_date, rand_datetime, normal_score, normal_pct, get_emp_skills,
)

random.seed(42)
np.random.seed(42)

NUM_TEAMS = int(os.environ.get("NUM_TEAMS", 100))
OUT_DIR   = os.environ.get("OUT_DIR", "./output")

FEEDBACK_SUMMARIES = [
    "Great collaboration and clear communication throughout",
    "Strong technical execution but documentation needs improvement",
    "Team worked well under pressure, met all major milestones",
    "Communication gaps slowed progress in early sprints",
    "Excellent cross-functional coordination and knowledge sharing",
    "Skill balance was ideal for the project requirements",
    "Some workload imbalance noted, but team adapted quickly",
    "High cohesion team, delivered above expectations",
    None,
]
LESSONS_LEARNED = [
    "Need daily standups for better alignment",
    "Clear role definitions improved efficiency significantly",
    "Earlier risk identification would have prevented delays",
    "Async communication tools reduced meeting overhead",
    "Pair programming improved code quality noticeably",
    "Regular retrospectives helped resolve conflicts early",
    "Cross-training team members reduced single points of failure",
    None,
]


# ─── 5-Phase Team Formation Algorithm ────────────────────────────────────────
def build_team(emp_df: pd.DataFrame, required_skills: list[str],
               team_size: int, used_in_team: set) -> tuple[str, list[str]]:
    """
    Phase 1: Determine skill slots — distribute team_size across required skills.
    Phase 2: For each skill, build candidate pool (employees who have it).
    Phase 3: Weighted-random fill per slot (weight = tech_score * collab_score).
    Phase 4: No duplicates — remove picked employee from all remaining pools.
    Phase 5: Guarantee at least one Senior/Lead/Principal.
              If none in final team, swap out lowest-scoring non-senior for
              best available senior scored on: skill_coverage, seniority_boost,
              leadership_potential, success_history, collaboration, workload.

    Returns: (lead_id, [member_ids])  — lead NOT in member_ids list.
    """
    all_emp_ids = emp_df["employee_id"].tolist()
    emp_lookup  = emp_df.set_index("employee_id").to_dict("index")

    # Helper: employee score weight for sampling
    def weight(eid):
        row = emp_lookup[eid]
        return max(0.1, row.get("technical_proficiency_score", 5) *
                        row.get("collaboration_score", 5))

    # ── Phase 1: skill slots ──────────────────────────────────────────────────
    n_skills = max(1, len(required_skills))
    base, remainder = divmod(team_size, n_skills)
    slots = [base + (1 if i < remainder else 0) for i in range(n_skills)]
    # randomise slot sizes slightly (±1) while keeping sum = team_size
    for idx in range(len(slots) - 1):
        delta = random.choice([-1, 0, 1])
        if slots[idx] + delta >= 1 and slots[idx + 1] - delta >= 1:
            slots[idx]     += delta
            slots[idx + 1] -= delta

    # ── Phase 2: candidate pools per skill ───────────────────────────────────
    skill_pools: dict[str, list[str]] = {}
    for skill in required_skills:
        pool = [
            eid for eid in all_emp_ids
            if eid not in used_in_team and skill in get_emp_skills(emp_lookup[eid])
        ]
        # fallback: any available employee for this skill slot
        if not pool:
            pool = [eid for eid in all_emp_ids if eid not in used_in_team]
        # cap pool size at 30x slot count to keep variety
        cap = max(len(pool), slots[required_skills.index(skill)] * 30)
        top_pool = sorted(pool, key=weight, reverse=True)[:cap]
        skill_pools[skill] = top_pool

    # ── Phase 3 & 4: weighted-random fill, no duplicates ─────────────────────
    picked: list[str] = []
    globally_picked: set = set()

    for skill, n_slots in zip(required_skills, slots):
        pool = [e for e in skill_pools[skill] if e not in globally_picked]
        if not pool:
            # fallback to anyone not yet picked
            pool = [e for e in all_emp_ids
                    if e not in globally_picked and e not in used_in_team]
        if not pool:
            pool = [e for e in all_emp_ids if e not in globally_picked]

        weights = np.array([weight(e) for e in pool], dtype=float)
        weights /= weights.sum()

        n_pick = min(n_slots, len(pool))
        chosen = list(np.random.choice(pool, size=n_pick, replace=False, p=weights))
        picked.extend(chosen)
        globally_picked.update(chosen)

    # deduplicate and trim to team_size
    seen, final_members = set(), []
    for e in picked:
        if e not in seen:
            seen.add(e)
            final_members.append(e)
    final_members = final_members[:team_size]

    # pad if short
    while len(final_members) < team_size:
        extras = [e for e in all_emp_ids
                  if e not in set(final_members) and e not in used_in_team]
        if not extras:
            extras = [e for e in all_emp_ids if e not in set(final_members)]
        if not extras:
            break
        final_members.append(random.choice(extras))

    # ── Phase 5: guarantee Senior/Lead/Principal lead ─────────────────────────
    def lead_score(eid):
        row = emp_lookup[eid]
        s_boost = SENIORITY_BOOST.get(row.get("seniority_level", "Junior"), 0)
        return (
            s_boost * 30
            + row.get("leadership_potential",    5) * 5
            + row.get("collaboration_score",      5) * 3
            + row.get("historical_performance_score", 70) * 0.1
            + np.random.normal(0, 3)          # small noise so it's not deterministic
        )

    seniors_in_team = [e for e in final_members
                       if emp_lookup[e].get("seniority_level") in SENIOR_LEVELS]

    if seniors_in_team:
        lead_id = max(seniors_in_team, key=lead_score)
    else:
        # swap out lowest-scoring member for best available senior
        best_senior_pool = [
            e for e in all_emp_ids
            if emp_lookup[e].get("seniority_level") in SENIOR_LEVELS
            and e not in set(final_members)
        ]
        if best_senior_pool:
            new_lead = max(best_senior_pool, key=lead_score)
            # remove lowest-scoring current member
            worst = min(final_members, key=lead_score)
            final_members.remove(worst)
            final_members.append(new_lead)
            lead_id = new_lead
        else:
            # No senior available — pick best from team anyway
            lead_id = max(final_members, key=lead_score)

    final_members.remove(lead_id)
    return lead_id, final_members


# ─── Compute predicted_success_rate from team factors ────────────────────────
def compute_predicted_success(
    emp_df: pd.DataFrame,
    lead_id: str,
    member_ids: list[str],
    required_skills: list[str],
    skill_div: float,
    exp_balance: float,
    collab_hist: float,
    comm_compat: float,
    wl_balance: float,
) -> float:
    """
    Weighted combination of real team attributes with small gaussian noise.
    Correlated with actual_performance_score since both derive from team quality.
    """
    emp_lookup = emp_df.set_index("employee_id").to_dict("index")
    all_ids = [lead_id] + member_ids

    # Skill coverage
    covered = set()
    req_set = set(required_skills)
    for eid in all_ids:
        covered |= get_emp_skills(emp_lookup.get(eid, {})) & req_set
    skill_cov = (len(covered) / max(len(req_set), 1)) * 100

    # Avg seniority score
    sen_scores = [SENIORITY_BOOST.get(emp_lookup.get(e, {}).get("seniority_level", "Junior"), 0)
                  for e in all_ids]
    avg_seniority = (sum(sen_scores) / max(len(sen_scores), 1)) * 100

    # Avg performance
    avg_perf = np.mean([emp_lookup.get(e, {}).get("historical_performance_score", 70)
                        for e in all_ids])

    # Weighted formula
    pred = (
        skill_cov       * 0.30 +
        avg_perf        * 0.25 +
        skill_div       * 0.15 +
        exp_balance     * 0.10 +
        collab_hist     * 0.08 +
        avg_seniority   * 0.07 +
        wl_balance      * 0.05 +
        np.random.normal(0, 4)   # realistic noise
    )
    return clamp(round(pred, 1), 20.0, 100.0)


# ─── TEAM FORMATIONS ──────────────────────────────────────────────────────────
def generate_team_formations(employees_df: pd.DataFrame,
                              projects_df: pd.DataFrame,
                              n: int) -> pd.DataFrame:
    proj_meta = {
        row["project_id"]: {
            "start":      date.fromisoformat(row["start_date"]),
            "end":        date.fromisoformat(row["planned_end_date"]),
            "status":     row["current_status"],
            "req_skills": [s.strip() for s in str(row["required_skills"]).split(",") if s.strip()],
        }
        for _, row in projects_df.iterrows()
    }
    proj_ids = projects_df["project_id"].tolist()
    emp_lookup = employees_df.set_index("employee_id").to_dict("index")

    rows = []
    used_team_names: list[str] = []

    for i in range(1, n + 1):
        team_id  = f"TEAM{i:03d}"
        proj_id  = random.choice(proj_ids)
        meta     = proj_meta[proj_id]
        p_start, p_end, p_status = meta["start"], meta["end"], meta["status"]
        req_skills = meta["req_skills"] or ["Communication"]  # fallback

        form_date = rand_date(p_start, p_start + timedelta(days=14))
        method    = np.random.choice(FORMATION_METHOD, p=FORMATION_WEIGHTS)
        team_size = random.randint(3, 12)

        # Build team via 5-phase algorithm
        lead_id, member_ids = build_team(
            employees_df, req_skills, team_size, used_in_team=set()
        )
        all_ids = [lead_id] + member_ids

        # Seniority and role distribution (derived from actual members)
        from collections import Counter
        seniority_counts = Counter(
            emp_lookup[e]["seniority_level"] for e in all_ids if e in emp_lookup
        )
        role_counts = Counter(
            emp_lookup[e]["role"].split()[0] for e in all_ids if e in emp_lookup
        )
        sen_mix_str  = json.dumps(dict(seniority_counts))
        role_dist_str= json.dumps(dict(role_counts))

        # Team characteristic scores
        skill_div   = normal_pct(70, 15)
        exp_balance = normal_pct(72, 14)
        collab_hist = normal_pct(65, 18)
        comm_compat = normal_pct(75, 13)
        wl_balance  = normal_pct(72, 15)
        tz_compat   = normal_pct(80, 15)

        # Predicted success — computed from real team factors
        pred_success = compute_predicted_success(
            employees_df, lead_id, member_ids, req_skills,
            skill_div, exp_balance, collab_hist, comm_compat, wl_balance,
        )

        # Outcomes
        completed  = p_status == "Completed" and random.random() > 0.15
        # actual_performance also filled for active teams with partial progress (>50% complete)
        proj_row    = projects_df[projects_df["project_id"] == proj_id].iloc[0]
        partial_done= proj_row["completion_percentage"] > 50 and not completed

        if completed:
            # Actual performance correlated with predicted + team quality noise
            actual_perf = clamp(
                round(pred_success * 0.7 + np.random.normal(pred_success * 0.3, 8), 1),
                20.0, 100.0
            )
        elif partial_done:
            # Partial signal — noisier
            actual_perf = clamp(
                round(pred_success * 0.6 + np.random.normal(pred_success * 0.35, 12), 1),
                20.0, 100.0
            )
        else:
            actual_perf = None

        team_prod  = normal_pct(74, 13) if (completed or partial_done) else normal_pct(68, 14)
        cohesion   = normal_score(7.2, 1.3)
        conflicts  = random.choices([0, 1, 2, 3], weights=[0.55, 0.28, 0.12, 0.05])[0]
        collab_eff = normal_score(7.3, 1.2)

        comp_days    = round((p_end - form_date).days * random.uniform(0.85, 1.20), 1) \
                       if completed else None
        met_deadline = (random.random() > 0.25) if completed else None
        quality_rat  = normal_score(7.6, 1.2) if completed else None
        budget_adh   = clamp(round(np.random.normal(100, 12), 1), 70, 140) if completed else None
        stkh_sat     = normal_score(7.5, 1.2) if completed else None

        eff_ratio    = clamp(round(np.random.normal(1.0, 0.15), 2), 0.6, 1.5)
        res_util     = normal_pct(82, 12)
        skill_util   = normal_pct(78, 13)
        improve_ops  = random.randint(0, 5)

        status = "Completed" if p_status == "Completed" \
                 else np.random.choice(TEAM_STATUS, p=TEAM_STATUS_W)
        dissolve_date = p_end.isoformat() if status in ["Completed", "Disbanded"] else None
        dissolve_rsn  = random.choice(DISSOLVE_REASON[:2]) \
                        if status in ["Completed", "Disbanded"] else None

        base_name = random.choice(TEAM_NAMES)
        used_team_names.append(base_name)
        count = used_team_names.count(base_name)
        team_name = base_name if count == 1 else f"{base_name} {count}"

        would_reform = (random.random() > 0.3) if completed else None

        rows.append({
            "team_id":                    team_id,
            "team_name":                  team_name,
            "project_id":                 proj_id,
            "formation_date":             form_date.isoformat(),
            "formation_method":           method,
            "team_lead_id":               lead_id,
            "member_ids":                 ",".join(member_ids),
            "team_size":                  len(all_ids),   # lead + members
            "role_distribution":          role_dist_str,
            "seniority_mix":              sen_mix_str,
            "skill_diversity_score":      skill_div,
            "experience_balance_score":   exp_balance,
            "collaborative_history_score":collab_hist,
            "communication_compatibility":comm_compat,
            "workload_balance_score":     wl_balance,
            "timezone_compatibility":     tz_compat,
            "predicted_success_rate":     pred_success,
            "actual_performance_score":   actual_perf,
            "team_productivity_score":    team_prod,
            "team_cohesion_score":        cohesion,
            "conflict_incidents":         conflicts,
            "collaboration_effectiveness":collab_eff,
            "project_completed":          completed,
            "completion_time_days":       comp_days,
            "met_deadline":               met_deadline,
            "quality_rating":             quality_rat,
            "budget_adherence":           budget_adh,
            "stakeholder_satisfaction":   stkh_sat,
            "team_efficiency_ratio":      eff_ratio,
            "resource_utilization":       res_util,
            "skill_utilization_rate":     skill_util,
            "improvement_opportunities":  improve_ops,
            "team_feedback_summary":      random.choice(FEEDBACK_SUMMARIES),
            "lessons_learned":            random.choice(LESSONS_LEARNED),
            "would_reform_team":          would_reform,
            "team_status":                status,
            "dissolution_date":           dissolve_date,
            "dissolution_reason":         dissolve_rsn,
            "created_at":                 rand_datetime(form_date),
            "last_updated":               rand_datetime(
                                              rand_date(form_date, date(2025, 3, 1))
                                          ),
        })

    return pd.DataFrame(rows)


# ─── Backfill projects with team info ─────────────────────────────────────────
def backfill_projects(projects_df: pd.DataFrame,
                       teams_df: pd.DataFrame) -> pd.DataFrame:
    """
    Update project_manager_id and add team_member_ids + team_size
    from the corresponding team_formations row (first team per project).
    """
    proj_df = projects_df.copy()
    # Build map: project_id → first team row
    team_map = {}
    for _, row in teams_df.iterrows():
        pid = row["project_id"]
        if pid not in team_map:
            team_map[pid] = row

    proj_df["project_manager_id"] = proj_df["project_id"].map(
        lambda pid: team_map[pid]["team_lead_id"] if pid in team_map
                    else proj_df.loc[proj_df["project_id"] == pid, "project_manager_id"].values[0]
    )
    proj_df["team_member_ids"] = proj_df["project_id"].map(
        lambda pid: team_map[pid]["member_ids"] if pid in team_map else ""
    )
    proj_df["team_size"] = proj_df["project_id"].map(
        lambda pid: team_map[pid]["team_size"] if pid in team_map else 0
    )
    return proj_df


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading employees and projects...")
    emp_df  = pd.read_csv(f"{OUT_DIR}/employees.csv")
    proj_df = pd.read_csv(f"{OUT_DIR}/projects.csv")
    print(f"  Loaded {len(emp_df)} employees | {len(proj_df)} projects")

    print(f"Generating {NUM_TEAMS} team formations (5-phase skill algorithm)...")
    teams_df = generate_team_formations(emp_df, proj_df, NUM_TEAMS)
    teams_df.to_csv(f"{OUT_DIR}/team_formations.csv", index=False)
    print(f"  ✓ {len(teams_df)} rows → team_formations.csv")

    print("Backfilling projects with team info...")
    proj_df = backfill_projects(proj_df, teams_df)
    proj_df.to_csv(f"{OUT_DIR}/projects.csv", index=False)
    print(f"  ✓ projects.csv updated with team_member_ids / team_size / project_manager_id")

    # Sanity checks
    print("\nSanity checks:")
    tf_done = teams_df[teams_df["actual_performance_score"].notna()]
    corr = tf_done["predicted_success_rate"].corr(tf_done["actual_performance_score"])
    print(f"  predicted/actual corr: {corr:.3f}  (target >=0.35)")
    print(f"  actual_perf filled: {teams_df['actual_performance_score'].notna().sum()}/{len(teams_df)}")
    print(f"  all lead_ids Senior+: {teams_df['team_lead_id'].isin(emp_df[emp_df['seniority_level'].isin(SENIOR_LEVELS)]['employee_id']).all()}")

    # Skill coverage check
    proj_skills = dict(zip(proj_df["project_id"], proj_df["required_skills"]))
    emp_skill_map = {row["employee_id"]: get_emp_skills(row) for _, row in emp_df.iterrows()}
    coverages = []
    for _, row in teams_df.iterrows():
        req = {s.strip() for s in str(proj_skills.get(row["project_id"], "")).split(",") if s.strip()}
        members = [m.strip() for m in str(row["member_ids"]).split(",") if m.strip()]
        members.append(row["team_lead_id"])
        covered = set()
        for m in members:
            covered |= emp_skill_map.get(m, set()) & req
        if req:
            coverages.append(len(covered) / len(req) * 100)
    print(f"  avg skill coverage: {sum(coverages)/len(coverages):.1f}%")
    print(f"  teams with 100% coverage: {sum(1 for x in coverages if x==100)}/{len(coverages)}")
