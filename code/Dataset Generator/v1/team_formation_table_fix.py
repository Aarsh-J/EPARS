"""
fix_team_formation.py
---------------------
Regenerates team assignments with proper skill-based logic.

TEAM FORMATION LOGIC:
  Phase 1 - Slot Allocation:
    - Divide team slots proportionally across required skills (randomized ±1)
    - Total slots always sums to exact team_size

  Phase 2 - Pool Building (30x per skill slot):
    - For each skill, build pool of top 30x slot-count employees who have that skill
    - Employee CAN appear in multiple skill pools (skill overlap handled)

  Phase 3 - Slot Filling:
    - Fill each skill slot via weighted-random from that skill's pool
    - Once picked, employee removed from all other pools (no duplicates in team)
    - Fallback to general pool if skill has insufficient candidates

  Phase 4 - Seniority Guarantee:
    - If no Senior/Lead/Principal in team → replace lowest scorer with best
      available senior from any skill pool

  Phase 5 - Lead Selection:
    - Scored on: skill_coverage(0.25) + seniority(0.20) + leadership_potential(0.20)
                 + success_ratio(0.15) + collaboration(0.10) + workload_penalty(0.10)
    - Gaussian noise added so lead isn't deterministic every time
    - Must be Senior/Lead/Principal; fallback to best overall if none qualify

SCORES: All recomputed as formula value + gaussian noise

TABLES MODIFIED:
  team_formations, projects, tasks, task_assignments,
  performance_reviews, schedules

TABLES UNTOUCHED:
  employees, workload_history, burnout_indicators, feedback

ROW COUNTS: Guaranteed identical to input.

USAGE:
    python fix_team_formation.py \
        --employees   employees.csv \
        --projects    projects.csv \
        --tasks       tasks.csv \
        --teams       team_formations.csv \
        --assignments task_assignments.csv \
        --reviews     performance_reviews.csv \
        --schedules   schedules.csv \
        --feedback    feedback.csv \
        --output_dir  ./fixed
        --seed        42        (optional, for reproducibility)
        --dry_run               (optional, no files written)
"""

import csv
import json
import random
import argparse
import os
import copy
from collections import defaultdict, Counter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SENIORITY_RANK    = {'Junior': 1, 'Mid': 2, 'Senior': 3, 'Lead': 4, 'Principal': 5}
SENIOR_LEVELS     = {'Senior', 'Lead', 'Principal'}
POOL_MULTIPLIER   = 30   # pool size = slots_for_skill * POOL_MULTIPLIER

# ---------------------------------------------------------------------------
# Noise helper
# ---------------------------------------------------------------------------

def noisy(value, noise_pct=0.10, min_val=0.0, max_val=100.0):
    """Formula value + gaussian noise, clamped to range."""
    std = abs(value) * noise_pct
    return round(max(min_val, min(max_val, random.gauss(value, std))), 2)

# ---------------------------------------------------------------------------
# Skill helpers
# ---------------------------------------------------------------------------

def parse_skills(skill_str):
    if not skill_str:
        return set()
    return {s.strip() for s in skill_str.split(',') if s.strip()}

def skill_match_pct(emp_skills, required_skills):
    if not required_skills:
        return 100.0
    return len(emp_skills & required_skills) / len(required_skills) * 100.0

def team_skill_coverage(members, required_skills):
    if not required_skills:
        return 100.0
    covered = set()
    for emp in members:
        covered |= emp['all_skills'] & required_skills
    return len(covered) / len(required_skills) * 100.0

# ---------------------------------------------------------------------------
# Load / write helpers
# ---------------------------------------------------------------------------

def load_csv(path):
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames[:]
        rows   = list(reader)
    return rows, fields

def write_csv(rows, fields, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written: {path}  ({len(rows)} rows)")

def load_employees(path):
    employees = {}
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            row['all_skills'] = parse_skills(row['primary_skills']) | parse_skills(row['secondary_skills'])
            employees[row['employee_id']] = row
    return employees

def load_projects(path):
    projects = {}
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            row['required_skills_set'] = parse_skills(row['required_skills'])
            projects[row['project_id']] = row
    return projects

# ---------------------------------------------------------------------------
# Employee scoring helpers
# ---------------------------------------------------------------------------

def safe_float(val, default=0.0):
    try:
        return float(val)
    except:
        return default

def member_score(emp, required_skills):
    """Score employee as a team member for a project."""
    sm    = skill_match_pct(emp['all_skills'], required_skills) if required_skills else 50.0
    sr    = SENIORITY_RANK.get(emp.get('seniority_level', 'Mid'), 2)
    avail = 1.0 if str(emp.get('is_available', 'True')).lower() == 'true' else 0.6
    return sm * 0.65 + sr * 5 * 0.25 + avail * 10 * 0.10

def lead_score(emp, required_skills):
    """
    Score employee as a potential team lead.
    Formula: skill_coverage(0.25) + seniority(0.20) + leadership(0.20)
             + success_ratio(0.15) + collaboration(0.10) + workload_penalty(0.10)
    All components normalized to 0-100, then gaussian noise added.
    """
    # Skill coverage (0-100)
    skill_cov = skill_match_pct(emp['all_skills'], required_skills) if required_skills else 50.0

    # Seniority (normalized to 0-100)
    sr        = SENIORITY_RANK.get(emp.get('seniority_level', 'Mid'), 2)
    seniority = (sr / 5.0) * 100.0

    # Leadership potential (already 0-10 → scale to 0-100)
    leadership = safe_float(emp.get('leadership_potential', 5.0)) * 10.0

    # Success ratio (0-100): successful / (successful + failed), penalize 0-project history
    succ  = safe_float(emp.get('successful_project_count', 0))
    fail  = safe_float(emp.get('failed_project_count', 0))
    total = succ + fail
    success_ratio = (succ / total * 100.0) if total > 0 else 50.0

    # Collaboration score (already 0-10 → scale to 0-100)
    collab = safe_float(emp.get('collaboration_score', 7.0)) * 10.0

    # Workload penalty (0-100): lower burnout + fewer current projects = better
    burnout      = safe_float(emp.get('burnout_risk_score', 30.0))          # 0-100
    curr_proj    = safe_float(emp.get('current_project_count', 1.0))        # 0-3 typical
    workload_ok  = max(0.0, 100.0 - burnout - (curr_proj * 10.0))

    raw = (skill_cov   * 0.25 +
           seniority   * 0.20 +
           leadership  * 0.20 +
           success_ratio * 0.15 +
           collab      * 0.10 +
           workload_ok * 0.10)

    return noisy(raw, noise_pct=0.08)

# ---------------------------------------------------------------------------
# Phase 1: Slot allocation
# ---------------------------------------------------------------------------

def allocate_slots(n_skills, team_size):
    """
    Distribute team_size slots across n_skills.
    Base = team_size / n_skills, randomize ±1 per slot, total must = team_size.
    """
    if n_skills == 0:
        return []

    base   = team_size // n_skills
    extra  = team_size  % n_skills

    # Start with base slots for each skill
    slots  = [base] * n_skills

    # Distribute the remainder randomly
    extras = list(range(n_skills))
    random.shuffle(extras)
    for i in extras[:extra]:
        slots[i] += 1

    # Now randomize ±1 (swap between slots to keep total constant)
    for _ in range(n_skills):
        i, j = random.sample(range(n_skills), 2)
        if slots[i] > 1:          # don't drop any slot to 0
            slots[i] -= 1
            slots[j] += 1

    return slots

# ---------------------------------------------------------------------------
# Phase 2+3: Pool building and slot filling
# ---------------------------------------------------------------------------

def build_skill_pool(skill, employees, n_slots):
    """
    All employees who have `skill`, scored as members, sorted desc.
    Pool capped at POOL_MULTIPLIER * n_slots (or all available if fewer).
    """
    pool = []
    for emp_id, emp in employees.items():
        if skill in emp['all_skills']:
            pool.append((member_score(emp, {skill}), emp_id, emp))
    pool.sort(key=lambda x: x[0], reverse=True)
    cap = max(n_slots, POOL_MULTIPLIER * n_slots)
    return pool[:cap]

def weighted_pick(pool, exclude_ids):
    """Pick one employee from pool (weighted by score), excluding already-picked."""
    candidates = [(s, eid, emp) for s, eid, emp in pool if eid not in exclude_ids]
    if not candidates:
        return None
    weights = [s + 1.0 for s, _, _ in candidates]
    chosen  = random.choices(candidates, weights=weights, k=1)[0]
    return chosen

# ---------------------------------------------------------------------------
# Phase 4: Seniority guarantee
# ---------------------------------------------------------------------------

def ensure_senior(members, skill_pools, exclude_ids, required_skills):
    """
    If no Senior/Lead/Principal in team, replace lowest-scored member
    with best available senior from any skill pool.
    """
    has_senior = any(e['seniority_level'] in SENIOR_LEVELS for e in members)
    if has_senior:
        return members

    # Find best available senior across all pools
    best_senior = None
    best_score  = -1
    for pool in skill_pools:
        for score, emp_id, emp in pool:
            if emp_id not in exclude_ids and emp['seniority_level'] in SENIOR_LEVELS:
                if score > best_score:
                    best_score  = score
                    best_senior = emp
                break  # pool is sorted, first valid is best

    if best_senior is None:
        return members   # no senior available anywhere, keep as-is

    # Replace lowest-scored member (who is not already a senior)
    scored_members = [(member_score(e, required_skills), e) for e in members
                      if e['seniority_level'] not in SENIOR_LEVELS]
    if not scored_members:
        return members

    scored_members.sort(key=lambda x: x[0])
    worst_emp = scored_members[0][1]
    return [best_senior if e['employee_id'] == worst_emp['employee_id'] else e
            for e in members]

# ---------------------------------------------------------------------------
# Phase 5: Lead selection
# ---------------------------------------------------------------------------

def select_lead(members, required_skills):
    """
    Score all members as lead candidates.
    Prefer Senior/Lead/Principal; fallback to highest scorer if none qualify.
    """
    seniors = [e for e in members if e['seniority_level'] in SENIOR_LEVELS]
    pool    = seniors if seniors else members

    scored  = [(lead_score(e, required_skills), e) for e in pool]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]

# ---------------------------------------------------------------------------
# Main team selection entry point
# ---------------------------------------------------------------------------

def select_team(project, employees, team_size):
    """
    Returns (lead_emp, [all members including lead])
    Implements all 5 phases.
    """
    required   = project['required_skills_set']
    skill_list = list(required)

    # --- Phase 1: Slot allocation ---
    if skill_list:
        slots = allocate_slots(len(skill_list), team_size)
    else:
        slots      = [team_size]
        skill_list = ['__general__']

    # --- Phase 2: Build pools per skill ---
    skill_pools = []
    for skill, n_slots in zip(skill_list, slots):
        if skill == '__general__':
            pool = [(member_score(emp, required), eid, emp)
                    for eid, emp in employees.items()]
            pool.sort(key=lambda x: x[0], reverse=True)
            pool = pool[:max(n_slots, POOL_MULTIPLIER * n_slots)]
        else:
            pool = build_skill_pool(skill, employees, n_slots)
        skill_pools.append((skill, n_slots, pool))

    # --- Phase 3: Fill slots ---
    selected_ids = set()
    members      = []

    for skill, n_slots, pool in skill_pools:
        filled = 0
        while filled < n_slots:
            picked = weighted_pick(pool, selected_ids)
            if picked is None:
                # Fallback: pick from general employee pool
                general = [(member_score(emp, required), eid, emp)
                           for eid, emp in employees.items()
                           if eid not in selected_ids]
                if not general:
                    break
                general.sort(key=lambda x: x[0], reverse=True)
                weights = [s + 1.0 for s, _, _ in general]
                picked  = random.choices(general, weights=weights, k=1)[0]

            _, emp_id, emp = picked
            selected_ids.add(emp_id)
            members.append(emp)
            filled += 1

    # --- Phase 4: Seniority guarantee ---
    members = ensure_senior(members, [p for _, _, p in skill_pools],
                            selected_ids - {e['employee_id'] for e in members},
                            required)

    # --- Phase 5: Lead selection ---
    lead_emp = select_lead(members, required)

    return lead_emp, members

# ---------------------------------------------------------------------------
# Score recomputation (formula + noise)
# ---------------------------------------------------------------------------

def recompute_team_scores(members, required_skills):
    coverage    = team_skill_coverage(members, required_skills)
    avg_sm      = (sum(skill_match_pct(e['all_skills'], required_skills)
                       for e in members) / len(members)) if members else 50.0
    seniority_v = [SENIORITY_RANK.get(e.get('seniority_level', 'Mid'), 2) for e in members]
    exp_balance = min(100.0, len(set(seniority_v)) / max(len(seniority_v), 1) * 100 * 1.5)
    burn_avg    = sum(safe_float(e.get('burnout_risk_score', 30)) for e in members) / len(members)
    wl_balance  = max(0.0, 100.0 - burn_avg)
    return {
        'skill_diversity_score':    noisy(coverage,    0.08),
        'skill_utilization_rate':   noisy(avg_sm,      0.08),
        'experience_balance_score': noisy(exp_balance, 0.10),
        'workload_balance_score':   noisy(wl_balance,  0.10),
    }

def recompute_assignment_scores(emp, task_required, proj_required):
    combined  = task_required | proj_required
    sm        = skill_match_pct(emp['all_skills'], combined) if combined else 75.0
    exp_score = min(100.0, safe_float(emp.get('years_of_experience', 3.0)) * 8.0)
    avail     = safe_float(emp.get('average_task_completion_rate', 80.0))
    overall   = sm * 0.50 + exp_score * 0.30 + avail * 0.20
    return {
        'skill_match_score':         noisy(sm,        0.08),
        'experience_match_score':    noisy(exp_score, 0.10),
        'overall_suitability_score': noisy(overall,   0.08),
    }

# ---------------------------------------------------------------------------
# Fix 1: team_formations
# ---------------------------------------------------------------------------

def fix_team_formations(tf_rows, tf_fields, employees, projects):
    fixed            = []
    project_team_map = {}
    changed          = 0

    for row in tf_rows:
        new_row = copy.copy(row)
        proj_id = row['project_id']
        project = projects.get(proj_id)

        if not project or not project['required_skills_set']:
            fixed.append(new_row)
            orig_members = [m.strip() for m in row['member_ids'].split(',') if m.strip()]
            if proj_id not in project_team_map:
                project_team_map[proj_id] = {'lead': row['team_lead_id'], 'members': orig_members}
            continue

        try:
            team_size = max(3, round(safe_float(row['team_size'], 5)))
        except:
            team_size = 5

        lead_emp, members = select_team(project, employees, team_size)
        member_ids = [e['employee_id'] for e in members]
        lead_id    = lead_emp['employee_id']

        # Ensure lead is in member list
        if lead_id not in member_ids:
            member_ids[0] = lead_id
            members[0]    = lead_emp

        scores = recompute_team_scores(members, project['required_skills_set'])

        if row['member_ids'] != ','.join(member_ids):
            changed += 1

        new_row.update({
            'team_lead_id':      lead_id,
            'member_ids':        ','.join(member_ids),
            'team_size':         len(member_ids),
            'seniority_mix':     json.dumps(dict(Counter(e['seniority_level'] for e in members))),
            'role_distribution': json.dumps(dict(Counter(e['role'].split()[0] for e in members))),
            **scores
        })

        fixed.append(new_row)
        project_team_map[proj_id] = {'lead': lead_id, 'members': member_ids}

    print(f"  [team_formations]     rows={len(tf_rows)}  teams_reformed={changed}")
    return fixed, tf_fields, project_team_map

# ---------------------------------------------------------------------------
# Fix 2: projects
# ---------------------------------------------------------------------------

def fix_projects(proj_rows, proj_fields, project_team_map):
    fixed = []
    changed = 0

    for row in proj_rows:
        new_row   = copy.copy(row)
        team_info = project_team_map.get(row['project_id'])

        if team_info:
            new_mgr     = team_info['lead']
            new_members = ','.join(team_info['members'])
            if row['project_manager_id'] != new_mgr or row['team_member_ids'] != new_members:
                changed += 1
            new_row['project_manager_id'] = new_mgr
            new_row['team_member_ids']    = new_members
            new_row['team_size']          = len(team_info['members'])

        fixed.append(new_row)

    print(f"  [projects]            rows={len(proj_rows)}  updated={changed}")
    return fixed, proj_fields

# ---------------------------------------------------------------------------
# Fix 3: tasks
# ---------------------------------------------------------------------------

def fix_tasks(task_rows, task_fields, project_team_map):
    fixed = []
    changed = 0

    for row in task_rows:
        new_row   = copy.copy(row)
        team_info = project_team_map.get(row['project_id'])

        if team_info and team_info['members']:
            new_assignee = random.choice(team_info['members'])
            if row['assigned_to'] != new_assignee:
                changed += 1
            new_row['assigned_to'] = new_assignee

        fixed.append(new_row)

    print(f"  [tasks]               rows={len(task_rows)}  reassigned={changed}")
    return fixed, task_fields

# ---------------------------------------------------------------------------
# Fix 4: task_assignments
# ---------------------------------------------------------------------------

def fix_task_assignments(ta_rows, ta_fields, employees, tasks_map, projects, project_team_map):
    fixed = []
    changed = 0

    for row in ta_rows:
        new_row   = copy.copy(row)
        proj_id   = row['project_id']
        team_info = project_team_map.get(proj_id)

        if not team_info or not team_info['members']:
            fixed.append(new_row)
            continue

        task_req = parse_skills(tasks_map.get(row.get('task_id', ''), {}).get('required_skills', ''))
        proj_req = projects.get(proj_id, {}).get('required_skills_set', set())
        combined = task_req | proj_req

        # Score team members for this specific task, pick from top half
        scored = []
        for emp_id in team_info['members']:
            emp = employees.get(emp_id)
            if emp:
                sm = skill_match_pct(emp['all_skills'], combined) if combined else 50.0
                scored.append((sm, emp_id, emp))

        if scored:
            scored.sort(reverse=True)
            top_half          = scored[:max(1, len(scored) // 2)]
            _, chosen_id, chosen_emp = random.choice(top_half)

            if row['employee_id'] != chosen_id:
                changed += 1

            new_row['employee_id'] = chosen_id
            new_row.update(recompute_assignment_scores(chosen_emp, task_req, proj_req))

        fixed.append(new_row)

    print(f"  [task_assignments]    rows={len(ta_rows)}  reassigned={changed}")
    return fixed, ta_fields

# ---------------------------------------------------------------------------
# Fix 5: performance_reviews
# ---------------------------------------------------------------------------

def fix_performance_reviews(pr_rows, pr_fields, emp_project_map, project_team_map, employees):
    fixed       = []
    changed     = 0
    senior_emps = [eid for eid, e in employees.items()
                   if e.get('seniority_level') in SENIOR_LEVELS]

    for row in pr_rows:
        new_row   = copy.copy(row)
        emp_id    = row['employee_id']
        proj_id   = emp_project_map.get(emp_id)
        team_info = project_team_map.get(proj_id) if proj_id else None

        if team_info:
            lead         = team_info['lead']
            new_reviewer = lead if lead != emp_id else (
                random.choice(senior_emps) if senior_emps else row['reviewer_id'])
        else:
            new_reviewer = random.choice(senior_emps) if senior_emps else row['reviewer_id']

        if row['reviewer_id'] != new_reviewer:
            changed += 1
        new_row['reviewer_id'] = new_reviewer
        fixed.append(new_row)

    print(f"  [performance_reviews] rows={len(pr_rows)}  reviewer_updated={changed}")
    return fixed, pr_fields

# ---------------------------------------------------------------------------
# Fix 6: schedules
# ---------------------------------------------------------------------------

def fix_schedules(sch_rows, sch_fields, project_team_map, emp_project_map):
    fixed = []
    changed = 0

    for row in sch_rows:
        new_row = copy.copy(row)

        if (str(row.get('involves_team', 'False')).lower() == 'true'
                and row.get('event_type') == 'Meeting'
                and row.get('participant_ids', '').strip()):

            emp_id    = row['employee_id']
            proj_id   = emp_project_map.get(emp_id)
            team_info = project_team_map.get(proj_id) if proj_id else None

            if team_info:
                available  = [m for m in team_info['members'] if m != emp_id]
                orig_count = len([p for p in row['participant_ids'].split(',') if p.strip()])
                count      = min(orig_count, len(available))

                if count > 0:
                    new_parts = random.sample(available, count)
                    new_str   = ','.join(new_parts)
                    if row['participant_ids'] != new_str:
                        changed += 1
                    new_row['participant_ids']  = new_str
                    new_row['participant_count'] = count

        fixed.append(new_row)

    print(f"  [schedules]           rows={len(sch_rows)}  meetings_updated={changed}")
    return fixed, sch_fields

# ---------------------------------------------------------------------------
# Build emp -> project map from task_assignments
# ---------------------------------------------------------------------------

def build_emp_project_map(ta_rows):
    emp_proj_count = defaultdict(Counter)
    for row in ta_rows:
        if row['employee_id'] and row['project_id']:
            emp_proj_count[row['employee_id']][row['project_id']] += 1
    return {emp: counts.most_common(1)[0][0] for emp, counts in emp_proj_count.items()}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--employees',   required=True)
    parser.add_argument('--projects',    required=True)
    parser.add_argument('--tasks',       required=True)
    parser.add_argument('--teams',       required=True)
    parser.add_argument('--assignments', required=True)
    parser.add_argument('--reviews',     required=True)
    parser.add_argument('--schedules',   required=True)
    parser.add_argument('--feedback',    required=True)
    parser.add_argument('--output_dir',  default='./fixed')
    parser.add_argument('--dry_run',     action='store_true')
    parser.add_argument('--seed',        type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    print("\n=== Loading ===")
    employees  = load_employees(args.employees)
    projects   = load_projects(args.projects)
    tf_rows,   tf_fields   = load_csv(args.teams)
    ta_rows,   ta_fields   = load_csv(args.assignments)
    task_rows, task_fields = load_csv(args.tasks)
    proj_rows, proj_fields = load_csv(args.projects)
    pr_rows,   pr_fields   = load_csv(args.reviews)
    sch_rows,  sch_fields  = load_csv(args.schedules)
    fb_rows,   fb_fields   = load_csv(args.feedback)
    tasks_map  = {r['task_id']: r for r in task_rows}

    print(f"  employees={len(employees)}  projects={len(projects)}  teams={len(tf_rows)}")
    print(f"  tasks={len(task_rows)}  assignments={len(ta_rows)}  reviews={len(pr_rows)}")
    print(f"  schedules={len(sch_rows)}  feedback={len(fb_rows)}")

    print("\n=== Fixing ===")
    fixed_tf,    tf_fields,   project_team_map = fix_team_formations(tf_rows, tf_fields, employees, projects)
    fixed_proj,  proj_fields                   = fix_projects(proj_rows, proj_fields, project_team_map)
    fixed_tasks, task_fields                   = fix_tasks(task_rows, task_fields, project_team_map)
    fixed_ta,    ta_fields                     = fix_task_assignments(ta_rows, ta_fields, employees, tasks_map, projects, project_team_map)
    emp_project_map                            = build_emp_project_map(fixed_ta)
    fixed_pr,    pr_fields                     = fix_performance_reviews(pr_rows, pr_fields, emp_project_map, project_team_map, employees)
    fixed_sch,   sch_fields                    = fix_schedules(sch_rows, sch_fields, project_team_map, emp_project_map)

    print("\n=== Row Count Validation ===")
    all_ok = True
    for orig, fixed, name in [
        (tf_rows,   fixed_tf,    'team_formations'),
        (proj_rows, fixed_proj,  'projects'),
        (task_rows, fixed_tasks, 'tasks'),
        (ta_rows,   fixed_ta,    'task_assignments'),
        (pr_rows,   fixed_pr,    'performance_reviews'),
        (sch_rows,  fixed_sch,   'schedules'),
        (fb_rows,   fb_rows,     'feedback'),
    ]:
        ok     = len(orig) == len(fixed)
        all_ok = all_ok and ok
        print(f"  {name}: {len(orig)} -> {len(fixed)}  {'OK' if ok else '*** MISMATCH ***'}")

    if not all_ok:
        print("\nAborting: row count mismatch detected.")
        return

    if args.dry_run:
        print("\n[DRY RUN] No files written.")
        return

    print(f"\n=== Writing to {args.output_dir}/ ===")
    write_csv(fixed_tf,    tf_fields,    os.path.join(args.output_dir, 'team_formations.csv'))
    write_csv(fixed_proj,  proj_fields,  os.path.join(args.output_dir, 'projects.csv'))
    write_csv(fixed_tasks, task_fields,  os.path.join(args.output_dir, 'tasks.csv'))
    write_csv(fixed_ta,    ta_fields,    os.path.join(args.output_dir, 'task_assignments.csv'))
    write_csv(fixed_pr,    pr_fields,    os.path.join(args.output_dir, 'performance_reviews.csv'))
    write_csv(fixed_sch,   sch_fields,   os.path.join(args.output_dir, 'schedules.csv'))
    write_csv(fb_rows,     fb_fields,    os.path.join(args.output_dir, 'feedback.csv'))

    print("\n=== Done ===")
    print("Untouched: employees.csv, workload_history.csv, burnout_indicators.csv")

if __name__ == '__main__':
    main()