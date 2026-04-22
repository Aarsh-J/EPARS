"""
02_team_formations.py — Generate team_formations.csv (V3 schema).
Uses skill-coverage algorithm for team composition.
Also backfills projects.csv with team_member_ids, team_size, project_manager_id.

Runs before task_assignments so task assignments can use team member pools.
Performance outcome columns (actual_performance_score, met_deadline, etc.)
are backfilled in 06_backfill.py once task/project data exists.
"""

import os, random, json
import numpy as np
import pandas as pd
from datetime import date, timedelta
from collections import Counter
from config import (
    SENIOR_LEVELS, SENIORITY_BOOST, SENIORITY_ORDER,
    FORMATION_METHOD, FORMATION_WEIGHTS,
    TEAM_STATUS, TEAM_STATUS_W, TEAM_NAMES,
    DEPT_SKILLS,
    clamp, rand_date, rand_datetime, normal_pct, get_emp_skills,
)

random.seed(42)
np.random.seed(42)

NUM_TEAMS = int(os.environ.get("NUM_TEAMS", 100))
OUT_DIR   = os.environ.get("OUT_DIR", "./output")


# ─── Team composition algorithm (5-phase) ────────────────────────────────────

def _weight(emp_lookup: dict, eid: str) -> float:
    row = emp_lookup.get(eid, {})
    return max(0.1, row.get("technical_proficiency_score", 50) *
                     row.get("collaboration_score", 5) / 50)


def build_team(emp_df: pd.DataFrame, required_skills: list,
               team_size: int) -> tuple:
    """
    5-phase algorithm:
      1. Distribute team_size slots across required skills
      2. Build per-skill candidate pools
      3. Weighted-random fill (weight = tech_score × collab_score)
      4. No duplicate employees
      5. Guarantee at least one Senior/Lead/Principal as lead
    Returns: (lead_id, [member_ids])  — lead NOT in member_ids
    """
    all_emp_ids = emp_df["employee_id"].tolist()
    emp_lookup  = emp_df.set_index("employee_id").to_dict("index")

    # Phase 1: slot distribution
    n_skills = max(1, len(required_skills))
    base, remainder = divmod(team_size, n_skills)
    slots = [base + (1 if i < remainder else 0) for i in range(n_skills)]
    for idx in range(len(slots) - 1):
        delta = random.choice([-1, 0, 1])
        if slots[idx] + delta >= 1 and slots[idx + 1] - delta >= 1:
            slots[idx]     += delta
            slots[idx + 1] -= delta

    # Phase 2: per-skill candidate pools
    skill_pools: dict = {}
    for skill in required_skills:
        pool = [eid for eid in all_emp_ids
                if skill in get_emp_skills(emp_lookup.get(eid, {}))]
        if not pool:
            pool = all_emp_ids[:]
        skill_pools[skill] = pool

    # Phase 3 & 4: weighted fill, no duplicates
    picked, globally_picked = [], set()
    for skill, n_slots in zip(required_skills, slots):
        pool = [e for e in skill_pools[skill] if e not in globally_picked]
        if not pool:
            pool = [e for e in all_emp_ids if e not in globally_picked]
        if not pool:
            pool = all_emp_ids[:]
        weights = np.array([_weight(emp_lookup, e) for e in pool], dtype=float)
        weights /= weights.sum()
        n_pick  = min(n_slots, len(pool))
        chosen  = list(np.random.choice(pool, size=n_pick, replace=False, p=weights))
        picked.extend(chosen)
        globally_picked.update(chosen)

    # Deduplicate and trim
    seen, final_members = set(), []
    for e in picked:
        if e not in seen:
            seen.add(e)
            final_members.append(e)
    final_members = final_members[:team_size]

    # Pad if short
    while len(final_members) < team_size:
        extras = [e for e in all_emp_ids if e not in set(final_members)]
        if not extras:
            break
        final_members.append(random.choice(extras))

    # Phase 5: guarantee senior lead
    def lead_score(eid):
        row    = emp_lookup.get(eid, {})
        s_boost= SENIORITY_BOOST.get(row.get("seniority_level", "Junior"), 0)
        return (
            s_boost * 30
            + row.get("leadership_potential", 40) * 0.4
            + row.get("collaboration_score", 5) * 2
            + row.get("historical_performance_score", 70) * 0.05
            + np.random.normal(0, 2)
        )

    seniors = [e for e in final_members
               if emp_lookup.get(e, {}).get("seniority_level") in SENIOR_LEVELS]
    if seniors:
        lead_id = max(seniors, key=lead_score)
    else:
        best_pool = [e for e in all_emp_ids
                     if emp_lookup.get(e, {}).get("seniority_level") in SENIOR_LEVELS
                     and e not in set(final_members)]
        if best_pool:
            new_lead = max(best_pool, key=lead_score)
            worst    = min(final_members, key=lead_score)
            final_members.remove(worst)
            final_members.append(new_lead)
            lead_id  = new_lead
        else:
            lead_id  = max(final_members, key=lead_score)

    if lead_id in final_members:
        final_members.remove(lead_id)
    return lead_id, final_members


# ─── Score helpers ────────────────────────────────────────────────────────────

def calc_skill_diversity(emp_lookup: dict, all_ids: list) -> float:
    """
    skill_diversity_score:
      unique skills across all members / (team_size × 3 expected avg skills)
      clamped to 0-100
    """
    unique_skills = set()
    for eid in all_ids:
        unique_skills.update(get_emp_skills(emp_lookup.get(eid, {})))
    max_possible = max(len(all_ids) * 3, 1)
    raw = (len(unique_skills) / max_possible) * 100
    return clamp(round(raw + np.random.normal(0, 5), 1), 10.0, 100.0)


def calc_experience_balance(emp_lookup: dict, all_ids: list) -> float:
    """
    experience_balance_score:
      Based on coefficient of variation (CV) of years_of_experience.
      Ideal CV ≈ 0.5 (healthy mix of junior and senior).
      score = 100 × (1 - |CV - 0.5| × 1.5), clamped 10-100
    """
    yoe_vals = [emp_lookup.get(e, {}).get("years_of_experience", 3.0) for e in all_ids]
    if len(yoe_vals) < 2:
        return 70.0
    mean_yoe = np.mean(yoe_vals)
    if mean_yoe < 0.1:
        return 70.0
    cv    = np.std(yoe_vals) / mean_yoe
    ideal = 0.5
    score = 100 * (1 - abs(cv - ideal) * 1.5)
    return clamp(round(score + np.random.normal(0, 5), 1), 10.0, 100.0)


def calc_collaborative_history(emp_lookup: dict, all_ids: list) -> float:
    """
    collaborative_history_score:
      Proxy from avg collaboration_score of team members (scaled 0-100).
      + small random variance to simulate actual co-history.
    """
    scores = [emp_lookup.get(e, {}).get("collaboration_score", 5) for e in all_ids]
    avg    = np.mean(scores) / 10.0 * 100
    return clamp(round(avg + np.random.normal(0, 10), 1), 10.0, 100.0)


def calc_workload_balance(emp_lookup: dict, all_ids: list) -> float:
    """
    workload_balance_score:
      Based on variance of remaining capacity across team members.
      remaining_capacity = weekly_capacity × (1 - current_project_count × 0.30)
      Lower variance → higher balance score.
    """
    caps = []
    for e in all_ids:
        row = emp_lookup.get(e, {})
        wk_cap   = row.get("weekly_capacity_hours", 40)
        proj_cnt = row.get("current_project_count", 1)
        remaining= wk_cap * max(0.0, 1 - proj_cnt * 0.30)
        caps.append(remaining)
    if len(caps) < 2 or np.mean(caps) < 0.1:
        return 70.0
    cv    = np.std(caps) / max(np.mean(caps), 1)
    score = max(0.0, 100 - cv * 80)
    return clamp(round(score + np.random.normal(0, 5), 1), 10.0, 100.0)


def calc_predicted_success(emp_df: pd.DataFrame, lead_id: str, member_ids: list,
                            required_skills: list, skill_div: float,
                            exp_balance: float, collab_hist: float,
                            wl_balance: float) -> float:
    """
    predicted_success_rate:
      = skill_coverage(30%) + avg_perf(25%) + skill_diversity(15%)
        + exp_balance(10%) + collab_hist(8%) + avg_seniority(7%)
        + wl_balance(5%) + Normal(0, 4) noise
    """
    emp_lookup = emp_df.set_index("employee_id").to_dict("index")
    all_ids    = [lead_id] + member_ids
    req_set    = set(required_skills)

    covered = set()
    for eid in all_ids:
        covered |= get_emp_skills(emp_lookup.get(eid, {})) & req_set
    skill_cov   = (len(covered) / max(len(req_set), 1)) * 100

    avg_perf    = np.mean([emp_lookup.get(e, {}).get("historical_performance_score", 70)
                           for e in all_ids])

    sen_scores  = [SENIORITY_BOOST.get(emp_lookup.get(e, {}).get("seniority_level", "Junior"), 0)
                   for e in all_ids]
    avg_seniority = (sum(sen_scores) / max(len(sen_scores), 1)) * 100

    pred = (
        skill_cov     * 0.30 +
        avg_perf      * 0.25 +
        skill_div     * 0.15 +
        exp_balance   * 0.10 +
        collab_hist   * 0.08 +
        avg_seniority * 0.07 +
        wl_balance    * 0.05 +
        np.random.normal(0, 4)
    )
    return clamp(round(pred, 1), 20.0, 100.0)


# ─── TEAM FORMATIONS ──────────────────────────────────────────────────────────
def generate_team_formations(employees_df: pd.DataFrame,
                              projects_df: pd.DataFrame,
                              n: int) -> pd.DataFrame:
    proj_meta = {}
    for _, row in projects_df.iterrows():
        proj_meta[row["project_id"]] = {
            "start":      date.fromisoformat(row["start_date"]),
            "end":        date.fromisoformat(row["planned_end_date"]),
            "status":     row["current_status"],
            "req_skills": [s.strip() for s in str(row["required_skills"]).split(",")
                           if s.strip()],
        }
    proj_ids   = projects_df["project_id"].tolist()
    emp_lookup = employees_df.set_index("employee_id").to_dict("index")

    rows = []
    used_names: list = []

    for i in range(1, n + 1):
        team_id   = f"TEAM{i:03d}"
        proj_id   = random.choice(proj_ids)
        meta      = proj_meta[proj_id]
        p_start, p_end, p_status = meta["start"], meta["end"], meta["status"]
        req_skills= meta["req_skills"] or ["Communication"]

        form_date = rand_date(p_start, p_start + timedelta(days=14))
        method    = np.random.choice(FORMATION_METHOD, p=FORMATION_WEIGHTS)
        team_size = random.randint(3, 10)

        lead_id, member_ids = build_team(employees_df, req_skills, team_size)
        all_ids = [lead_id] + member_ids

        # Derived composition
        sen_dist  = Counter(emp_lookup.get(e, {}).get("seniority_level", "Junior")
                            for e in all_ids)
        role_dist = Counter(emp_lookup.get(e, {}).get("role", "Unknown").split()[0]
                            for e in all_ids)

        # Score calculations
        skill_div   = calc_skill_diversity(emp_lookup, all_ids)
        exp_balance = calc_experience_balance(emp_lookup, all_ids)
        collab_hist = calc_collaborative_history(emp_lookup, all_ids)
        wl_balance  = calc_workload_balance(emp_lookup, all_ids)

        pred_success = calc_predicted_success(
            employees_df, lead_id, member_ids, req_skills,
            skill_div, exp_balance, collab_hist, wl_balance
        )

        # skill_utilization_rate: overlap of member skills vs project required_skills
        req_set  = set(req_skills)
        covered  = set()
        for eid in all_ids:
            covered |= get_emp_skills(emp_lookup.get(eid, {})) & req_set
        skill_util = clamp(round(
            (len(covered) / max(len(req_set), 1)) * 100 + np.random.normal(0, 5), 1
        ), 0.0, 100.0)

        # collaboration_effectiveness: avg collab × team_feedback
        avg_collab = np.mean([emp_lookup.get(e, {}).get("collaboration_score", 5)
                              for e in all_ids])
        team_fb_score = int(clamp(round(np.random.normal(7, 1.3)), 1, 10)) \
                        if p_status in ["Completed", "Active"] else None
        collab_eff = clamp(round(
            (avg_collab / 10) * 100 * 0.65
            + (team_fb_score / 10 * 100 if team_fb_score else 65) * 0.35
            + np.random.normal(0, 5), 1
        ), 10.0, 100.0)

        # Outcome columns — filled for completed projects; None for ongoing
        proj_row    = projects_df[projects_df["project_id"] == proj_id].iloc[0]
        completed   = p_status == "Completed" and random.random() > 0.05
        partial     = proj_row["completion_percentage"] > 50 and not completed

        comp_days = round((p_end - form_date).days * random.uniform(0.85, 1.20), 1) \
                    if completed else None

        if completed:
            # Outcome metrics correlated with pred_success so actual_perf has genuine signal
            deadline_prob = clamp(0.40 + pred_success * 0.005, 0.40, 0.90)
            met_deadline  = random.random() < deadline_prob

            quality_mean = clamp(3.0 + pred_success * 0.05, 4.0, 9.5)
            quality_rat  = int(clamp(round(np.random.normal(quality_mean, 1.0)), 1, 10))

            # higher pred → closer to 100 (on budget); lower pred → overrun
            budget_mean = clamp(100 + (70 - pred_success) * 0.15, 90.0, 125.0)
            budget_adh  = clamp(round(np.random.normal(budget_mean, 8), 1), 70.0, 140.0)

            sat_mean = clamp(3.0 + pred_success * 0.05, 4.0, 9.5)
            stkh_sat = int(clamp(round(np.random.normal(sat_mean, 1.0)), 1, 10))

            # actual_performance_score per formulas.md
            q_norm   = quality_rat / 10 * 100
            dl_norm  = 100.0 if met_deadline else 50.0
            ba_norm  = max(0.0, 100 - max(budget_adh - 100, 0) * 1.5)
            sat_norm = stkh_sat / 10 * 100
            actual_perf = clamp(round(
                q_norm   * 0.35
                + dl_norm  * 0.30
                + ba_norm  * 0.20
                + sat_norm * 0.15
                + np.random.normal(0, 3), 1
            ), 20.0, 100.0)
        else:
            met_deadline = None
            quality_rat  = None
            budget_adh   = None
            stkh_sat     = None
            actual_perf  = None

        proj_completed = completed

        # resource_utilization: consumed / allocated from project
        alloc    = proj_row["allocated_resources"]
        consumed = proj_row["consumed_resources"]
        res_util = clamp(round(
            consumed / max(alloc, 1) * 100 + np.random.normal(0, 3), 1
        ), 0.0, 150.0)

        # Team status → project status mapping
        status = "Completed" if p_status == "Completed" \
                 else ("Active" if p_status in ["Active", "Planning"] \
                       else np.random.choice(TEAM_STATUS, p=TEAM_STATUS_W))
        dissolve_date = p_end.isoformat() if status in ["Completed", "Disbanded"] else None
        dissolve_rsn  = ("Project Complete" if status == "Completed"
                         else "Reorganization" if status == "Disbanded" else None)

        base_name  = random.choice(TEAM_NAMES)
        used_names.append(base_name)
        count      = used_names.count(base_name)
        team_name  = base_name if count == 1 else f"{base_name} {count}"

        rows.append({
            # Identification
            "team_id":                    team_id,
            "team_name":                  team_name,
            "project_id":                 proj_id,
            "formation_date":             form_date.isoformat(),
            "formation_method":           method,
            # Composition
            "team_lead_id":               lead_id,
            "member_ids":                 ",".join(member_ids),
            "team_size":                  len(all_ids),
            "role_distribution":          json.dumps(dict(role_dist)),
            "seniority_mix":              json.dumps(dict(sen_dist)),
            # Characteristics
            "skill_diversity_score":      skill_div,
            "experience_balance_score":   exp_balance,
            "collaborative_history_score":collab_hist,
            "workload_balance_score":     wl_balance,
            # Performance
            "predicted_success_rate":     pred_success,
            "actual_performance_score":   actual_perf,
            "collaboration_effectiveness":collab_eff,
            # Outcomes
            "project_completed":          proj_completed,
            "completion_time_days":       comp_days,
            "met_deadline":               met_deadline,
            "quality_rating":             quality_rat,
            "budget_adherence":           budget_adh,
            "stakeholder_satisfaction":   stkh_sat,
            # Optimization
            "resource_utilization":       res_util,
            "skill_utilization_rate":     skill_util,
            # Feedback
            "team_feedback_score":        team_fb_score,
            # Lifecycle
            "team_status":                status,
            "dissolution_date":           dissolve_date,
            "dissolution_reason":         dissolve_rsn,
            # Timestamps
            "created_at":                 f"{form_date} 09:00:00",
            "last_updated":               rand_datetime(rand_date(form_date, date(2025, 4, 1))),
        })

    return pd.DataFrame(rows)


# ─── Backfill projects with team info ─────────────────────────────────────────
def backfill_projects(projects_df: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    proj_df  = projects_df.copy()
    team_map = {}
    for _, row in teams_df.iterrows():
        pid = row["project_id"]
        if pid not in team_map:
            team_map[pid] = row

    proj_df["project_manager_id"] = proj_df["project_id"].map(
        lambda pid: team_map[pid]["team_lead_id"]
        if pid in team_map else proj_df.loc[proj_df["project_id"] == pid,
                                             "project_manager_id"].values[0]
    )
    proj_df["team_member_ids"] = proj_df["project_id"].map(
        lambda pid: team_map[pid]["member_ids"] if pid in team_map else ""
    )
    proj_df["team_size"] = proj_df["project_id"].map(
        lambda pid: int(team_map[pid]["team_size"]) if pid in team_map else 0
    )
    return proj_df


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading employees and projects...")
    emp_df  = pd.read_csv(f"{OUT_DIR}/employees.csv")
    proj_df = pd.read_csv(f"{OUT_DIR}/projects.csv")
    print(f"  Loaded {len(emp_df)} employees | {len(proj_df)} projects")

    print(f"Generating {NUM_TEAMS} team formations...")
    teams_df = generate_team_formations(emp_df, proj_df, NUM_TEAMS)
    teams_df.to_csv(f"{OUT_DIR}/team_formations.csv", index=False)
    print(f"  OK {len(teams_df)} rows -> team_formations.csv")

    print("Backfilling projects with team info...")
    proj_df = backfill_projects(proj_df, teams_df)
    proj_df.to_csv(f"{OUT_DIR}/projects.csv", index=False)
    print(f"  OK projects.csv updated with team_member_ids / team_size / project_manager_id")

    print("\nSanity checks:")
    tf_done = teams_df[teams_df["actual_performance_score"].notna()]
    corr    = tf_done["predicted_success_rate"].corr(tf_done["actual_performance_score"])
    print(f"  predicted/actual correlation: {corr:.3f}  (target >= 0.30)")
    print(f"  actual_perf filled: {teams_df['actual_performance_score'].notna().sum()}/{len(teams_df)}")

    senior_emp = emp_df[emp_df["seniority_level"].isin(SENIOR_LEVELS)]["employee_id"]
    all_lead   = teams_df["team_lead_id"].isin(senior_emp)
    print(f"  lead_ids are Senior+: {all_lead.all()}  ({all_lead.sum()}/{len(teams_df)})")

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
    if coverages:
        print(f"  avg skill coverage: {sum(coverages)/len(coverages):.1f}%")
