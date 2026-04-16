# V3 Dataset Generation — Formula Reference

Non-obvious calculated columns only. Columns whose derivation is self-evident
(e.g., `days_overdue`, `rework_count`, `overtime_hours`, `completion_percentage`)
are intentionally excluded.

---

## Employees

### `technical_proficiency_score` (0–100 float)
Measures how technically capable the employee is based on breadth and depth of skills.

```
skill_factor   = min(len(primary_skills) / 5, 1.0) × 100   # saturates at 5 skills
cert_bonus     = min(cert_count × 8, 20)                    # max 20 pts from certs
seniority_base = {Junior:35, Mid:52, Senior:68, Lead:80, Principal:90}

score = seniority_base × 0.55 + skill_factor × 0.35 + cert_bonus × 0.10
      + Normal(0, 6)   → clamped [5, 100]
```

**Why:** Seniority dominates (55%) as a proxy for years of practice; skill breadth adds
diversity signal; certifications give a small verified-knowledge boost.

---

### `domain_expertise_score` (0–100 float)
Measures deep knowledge in the employee's function, not raw technical skill.

```
yoe_factor     = min(years_of_experience / 20, 1.0) × 100  # saturates at 20 yrs
seniority_base = {Junior:25, Mid:45, Senior:62, Lead:78, Principal:90}

score = yoe_factor × 0.50 + seniority_base × 0.35 + historical_performance_score × 0.15
      + Normal(0, 6)   → clamped [5, 100]
```

**Why:** Time-in-field (YoE) is the strongest predictor of domain mastery; seniority level
reinforces this; historical performance adds a quality-of-experience signal.

---

### `leadership_potential` (0–100 float)
Predicts how likely the employee is to grow into a leadership role.

```
seniority_base    = {Junior:20, Mid:38, Senior:58, Lead:75, Principal:88}
success_norm      = min(successful_project_count / 20, 1.0) × 100
collab_norm       = (collaboration_score / 10) × 100

score = seniority_base × 0.45 + success_norm × 0.30 + collab_norm × 0.25
      + Normal(0, 7)   → clamped [5, 100]
```

**Why:** Seniority sets the ceiling (45%); track record of successful deliveries shows
accountability (30%); high collaboration indicates the interpersonal skills needed to lead (25%).

---

### `burnout_risk_score` (0–100 float)
Estimates cumulative burnout risk from workload and recovery patterns.

```
overtime_factor = min(recent_overtime_hours / 20, 1.0) × 60   # max 60 pts at 20h OT
leave_factor    = min(days_since_last_leave / 180, 1.0) × 40   # max 40 pts at 6 months

score = overtime_factor × 0.55 + leave_factor × 0.45
      + Normal(0, 8)   → clamped [0, 100]
```

**Why:** Recent overtime is the dominant driver (55%) — it reflects acute overload.
Days without leave captures chronic depletion (45%). Weights are asymmetric because
short-term spike exposure is more acutely damaging than gradual leave avoidance.

---

## Projects

### `scope_creep_indicator` (0–100 float)
Measures unplanned growth in project scope relative to initial plan.

```
ms_growth_factor = overdue_milestones / max(total_milestones, 1) × 100
complexity_base  = {Low:12, Medium:28, High:50, Very High:68}

score = ms_growth_factor × 0.50 + complexity_base × 0.40
      + Normal(0, 8)   → clamped [0, 80]
```

**Why:** Overdue milestones are the strongest observable signal of scope growth; complexity
sets a baseline since larger projects inherently accumulate more scope drift.

---

### `delay_risk_score` (0–100 float)
Probability-weighted risk that the project will miss its deadline.

```
ms_penalty       = overdue_milestones × 15           # each overdue milestone = 15 pts
schedule_penalty = max(0, -days_ahead_behind) × 1.5  # being behind multiplies risk
scope_contrib    = scope_creep_indicator × 0.30

score = ms_penalty + schedule_penalty + scope_contrib
      + Normal(0, 8)   → clamped [5, 95]
```

**Why:** Milestone slippage is the most direct indicator; schedule deficit compounds it;
scope creep adds future delay probability.

---

### `budget_overrun_risk` (0–100 float)
Likelihood that spend will exceed the approved budget.

```
resource_excess = max(consumed_ratio - 0.50, 0) × 200   # kicks in above 50% burn rate
scope_contrib   = scope_creep_indicator × 0.30

score = resource_excess × 0.55 + scope_contrib × 0.50
      + Normal(0, 8)   → clamped [5, 90]
```

**Why:** Over 50% resource consumption relative to the remaining timeline is the tipping
point; scope creep historically correlates with unbudgeted work additions.

---

### `quality_risk_score` (0–100 float)
Risk that deliverables will not meet quality standards.

```
complexity_base = {Low:10, Medium:22, High:42, Very High:58}

score = complexity_base + scope_creep_indicator × 0.30
      + Normal(0, 10)  → clamped [5, 90]
```

**Why:** Higher complexity reduces predictability and increases defect probability.
Scope creep degrades quality because added features often bypass normal review cycles.

---

### `success_probability` (0–100 float)
Estimated probability of overall project success.

```
complexity_penalty = {Low:5, Medium:15, High:28, Very High:42}
schedule_bonus     = 10 if is_on_schedule else 0

score = 90 - complexity_penalty + schedule_bonus
      + Normal(0, 10)  → clamped [10, 98]
```

**Why:** Starts at 90% (optimistic base) and is discounted by complexity risk; being on
schedule provides a positive signal that execution is under control.

---

### `next_milestone_risk` (0–100 float)
Localised risk that the upcoming milestone will be missed.

```
score = delay_risk_score × 0.75 + overdue_milestones × 5
      + Normal(0, 8)   → clamped [5, 95]
```

**Why:** Propagates current delay risk as the primary signal; each already-overdue milestone
adds 5 additional points because sequential dependency amplifies slippage.

---

## Task Assignments

### `skill_match_score` (0–100 float)
Overlap between employee skills and what the task requires.

```
emp_skills  = primary_skills ∪ secondary_skills  (as sets)
task_skills = required_skills                     (as set)

score = |emp_skills ∩ task_skills| / max(|task_skills|, 1) × 100
```

**Why:** Simple intersection ratio; denominator is task requirements not employee skills so
an employee with broader skills than needed still scores 100 on a matching task.

---

### `availability_match_score` (0–100 float)
How well the employee's current workload allows taking on new work.

```
base = {
  not is_available OR current_project_count >= 3 → 25
  current_project_count == 0 → 95
  current_project_count == 1 → 78
  current_project_count == 2 → 58
}
score = base + Normal(0, 8)   → clamped [0, 100]
```

**Why:** Project count is used as a proxy for current load; the non-linear step function
reflects that the third concurrent project causes disproportionate context-switching cost.

---

### `workload_compatibility_score` (0–100 float)
Whether taking this task would push the employee into burnout territory.

```
remaining_capacity = max(0, weekly_capacity_hours - current_project_count × 15) / weekly_capacity_hours × 100
anti_burnout       = 100 - burnout_risk_score

score = remaining_capacity × 0.70 + anti_burnout × 0.30
      + Normal(0, 8)   → clamped [0, 100]
```

**Why:** Capacity headroom is the dominant signal; burnout risk moderates it because an
employee near burnout should receive lower compatibility even if nominally available.

---

### `experience_match_score` (0–100 float)
How well the employee's seniority aligns with the task's seniority requirement.

```
seniority_order = {Junior:1, Mid:2, Senior:3, Lead:4, Principal:5}
delta = employee_seniority_num - required_seniority_num

delta >= 0 → min(80 + delta × 5, 100)   # over-qualified is fine
delta == -1 → 50                          # slightly under-qualified
delta <= -2 → 20                          # significantly under-qualified
+ Normal(0, 7)   → clamped [5, 100]
```

**Why:** Over-qualification is preferable to under-qualification; the steep penalty at
delta ≤ -2 reflects that assigning a Junior to a Senior-required task creates high rework risk.

---

### `overall_suitability_score` (0–100 float)
Composite assignment fitness score used for AI-recommended assignments.

```
score = skill_match_score      × 0.35
      + availability_match_score  × 0.25
      + workload_compat_score   × 0.20
      + experience_match_score  × 0.20
      + Normal(0, 3)            → clamped [5, 100]
```

**Why:** Skill fit is weighted highest (35%) as the most reliable predictor of success;
availability and workload each contribute to delivery risk; experience provides calibration.

---

### `team_compatibility_score` (0–100 float)
Likelihood of smooth collaboration with existing team members.

```
collab_norm    = (collaboration_score / 10) × 100
history_proxy  = Normal(70, 15)   # proxy for past co-team history

score = collab_norm × 0.65 + history_proxy × 0.35
      + Normal(0, 6)   → clamped [5, 100]
```

**Why:** The employee's general collaboration score is the strongest available predictor;
the history proxy approximates past co-team overlap which is not yet computed at assignment time.

---

### `assignment_satisfaction` (0–10 integer)
Self-reported satisfaction with the assignment, correlated with fit quality.

```
raw   = (skill_match_score + workload_compatibility_score) / 20   # average as 0–10 scale
score = round(raw + Normal(0, 1))   → clamped [1, 10]
```

**Why:** People are more satisfied when assigned to tasks that match their skills and don't
overload them; both components equally weighted because skill mismatch and overload are
equally demoralising.

---

## Schedules

### `optimization_score` (0–100 float)
How well the scheduled event fits the employee's preferred working pattern.

```
conflict_penalty = 30 if has_conflict else 0
pref_bonus       = 15 if start_time falls within preferred_work_hours window else 0

score = 100 - conflict_penalty + pref_bonus
      + Normal(0, 8)   → clamped [10, 100]
```

**Why:** Schedule conflicts are the primary quality degrader; aligning events to preferred
hours reduces cognitive load and improves attendance and productivity outcomes.

---

## Workload History

### `workload_intensity_score` (0–100 float)
Daily intensity of the work burden — task load, urgency, and overtime combined.

```
task_contrib     = min(active_tasks_count / 8, 1.0) × 40
overtime_contrib = min(overtime_hours / 4, 1.0) × 30
hipri_contrib    = min(high_priority_tasks / 3, 1.0) × 30

score = task_contrib + overtime_contrib + hipri_contrib
      + Normal(0, 5)   → clamped [0, 100]
```

**Why:** Three equal-weight pillars: volume (tasks), duration (overtime), urgency (high-priority).
Each pillar is capped so no single dimension can monopolise the score.

---

### `deadline_pressure_score` (0–100 float)
Urgency stress from approaching and blocked tasks.

```
hipri_contrib   = min(high_priority_tasks / 3, 1.0) × 50
blocked_contrib = min(blocked_tasks_count / 2, 1.0) × 20
intensity_part  = workload_intensity_score × 0.30

score = hipri_contrib + blocked_contrib + intensity_part
      + Normal(0, 8)   → clamped [0, 100]
```

**Why:** High-priority tasks create the most acute deadline pressure (50%); blocked tasks
add frustration pressure (20%); overall intensity provides ambient background pressure (30%).

---

### `efficiency_ratio` (0–140 float)
Output per unit of time invested; values above 100 indicate above-baseline efficiency.

```
score = tasks_completed × 10 / max(total_hours_worked, 0.1) × 10
      + Normal(0, 5)   → clamped [20, 140]
```

**Why:** The ×10 tuning factors are calibrated so that completing 1 task in 8 hours yields
approximately 100 (baseline). Values above 100 are valid and represent high efficiency days.

---

### `productivity_score` (0–100 float)
Overall daily productivity considering output quantity, quality, and efficiency.

```
tcr           = tasks_completed / max(tasks_completed + active_tasks, 1) × 100
quality_norm  = (quality_of_work / 10) × 100
eff_norm      = min(efficiency_ratio / 150, 1.0) × 100
stress_penalty = stress_today × 0.25

score = tcr × 0.35 + quality_norm × 0.35 + eff_norm × 0.15
      + base_perf × 0.15 - stress_penalty
      + Normal(0, 5)   → clamped [10, 100]
```

**Why:** Task completion and quality are equally weighted as direct performance signals (35% each);
efficiency captures how smartly work was done; stress applies a multiplicative penalty because
high stress reliably degrades all performance dimensions.

---

### `burnout_risk_today` (0–100 float)
Daily instantaneous burnout risk estimate based on that day's work signals.

```
overtime_norm   = min(overtime_hours / 4, 1.0) × 100
overcap_norm    = max(workload_vs_capacity - 100, 0) × 0.5   # only above 100% capacity

score = workload_intensity × 0.35 + deadline_pressure × 0.25
      + overtime_norm × 0.25 + overcap_norm × 0.15
      + Normal(0, 5)   → clamped [0, 100]
```

**Why:** Intensity and deadline pressure are the primary daily stress drivers; overtime is
the clearest physiological signal; overcapacity (working beyond scheduled hours) is a lagging
indicator that compounds the others.

---

## Team Formations

### `skill_diversity_score` (0–100 float)
Breadth of unique capabilities across the team relative to team size.

```
unique_skills = |union of all member skill sets|
max_expected  = team_size × 3   (expected avg skills per member)

score = unique_skills / max_expected × 100
      + Normal(0, 5)   → clamped [10, 100]
```

**Why:** Unique skills per member (normalised to 3 per person) captures genuine diversity
without penalising large teams for naturally accumulating redundant skills.

---

### `experience_balance_score` (0–100 float)
How well the team balances junior and senior members — rewards healthy heterogeneity.

```
CV    = std(years_of_experience) / mean(years_of_experience)
ideal = 0.5   (50% coefficient of variation is optimal)

score = 100 × (1 - |CV - ideal| × 1.5)
      + Normal(0, 5)   → clamped [10, 100]
```

**Why:** A CV of 0.5 represents a healthy mix (e.g., 2–10 years range in a team averaging 5).
Both too-homogeneous (all seniors) and too-chaotic (extreme spread) reduce the score.

---

### `collaborative_history_score` (0–100 float)
Proxy for how well team members have worked together in the past.

```
avg_collab_norm = mean(collaboration_score for each member) / 10 × 100

score = avg_collab_norm + Normal(0, 10)   → clamped [10, 100]
```

**Why:** Direct past co-team history requires event data not available at team-formation time.
The individual collaboration score is the best available proxy; noise simulates the variance
in whether past teammates happen to re-appear on the same team.

---

### `workload_balance_score` (0–100 float)
How evenly distributed the current workload burden is across team members.

```
remaining_i = weekly_capacity_hours_i × max(0, 1 - current_project_count_i × 0.30)
CV          = std(remaining) / mean(remaining)

score = max(0, 100 - CV × 80)
      + Normal(0, 5)   → clamped [10, 100]
```

**Why:** High variance in remaining capacity means some members will be overloaded while others
are idle — a structural risk for team delivery. The CV threshold of 100/80 = 1.25 allows for
natural variation without penalising minor imbalances.

---

### `predicted_success_rate` (0–100 float)
Pre-project estimate of the likelihood this team will succeed.

```
skill_coverage = |team_skills ∩ required_skills| / |required_skills| × 100
avg_perf       = mean(historical_performance_score for all members)
avg_seniority  = mean(SENIORITY_BOOST[seniority] for all members) × 100

score = skill_coverage    × 0.30
      + avg_perf          × 0.25
      + skill_diversity   × 0.15
      + exp_balance       × 0.10
      + collab_history    × 0.08
      + avg_seniority     × 0.07
      + workload_balance  × 0.05
      + Normal(0, 4)      → clamped [20, 100]
```

**Why:** Skill coverage is the largest single predictor because a team missing critical skills
will structurally fail regardless of individual quality. Past performance and seniority provide
baseline competence signals; diversity and collaboration add composition quality signals.

---

### `actual_performance_score` (0–100 float, completed teams only)
Post-hoc measurement of how well the team actually performed.

```
q_norm   = quality_rating / 10 × 100
dl_norm  = 100 if met_deadline else 50
ba_norm  = max(0, 100 - max(budget_adherence - 100, 0) × 1.5)
sat_norm = stakeholder_satisfaction / 10 × 100

score = q_norm   × 0.35 + dl_norm  × 0.30
      + ba_norm  × 0.20 + sat_norm × 0.15
      + Normal(0, 3)   → clamped [20, 100]
```

**Why:** Delivery quality (35%) and deadline adherence (30%) are the primary success
dimensions; budget control (20%) and stakeholder satisfaction (15%) are outcome-quality
signals. Budget penalty only kicks in for overruns, not under-spend.

---

### `collaboration_effectiveness` (0–100 float)
How effectively the team coordinated and communicated during the project.

```
avg_collab_norm = mean(collaboration_score for all members) / 10 × 100
team_fb_norm    = team_feedback_score / 10 × 100  (if available, else 65)

score = avg_collab_norm × 0.65 + team_fb_norm × 0.35
      + Normal(0, 5)   → clamped [10, 100]
```

---

## Performance Reviews

### `overall_performance_score` (0–100 float)
Composite reviewer-assessed performance across technical and behavioural dimensions.

```
technical_cluster  = mean(technical_competence, domain_knowledge, problem_solving) × 10
behavioral_cluster = mean(communication, collaboration, leadership, initiative, time_management) × 10
quality_norm       = quality_of_work_score × 10
productivity_norm  = productivity_score × 10

score = technical_cluster  × 0.30
      + behavioral_cluster × 0.25
      + quality_norm       × 0.20
      + productivity_norm  × 0.25
      + Normal(0, 4)       → clamped [0, 100]
```

**Why:** Technical and behavioural clusters are both critical; quality of output is a
direct result metric; productivity measures throughput. All are human-rated (0–10), scaled
to 0–100 before combining.

---

### `normalized_performance_score` (0–100 float)
Peer-adjusted score accounting for department-level grade inflation.

```
score = overall_performance_score - |Normal(2, 2)|   → clamped [0, 100]
```

**Why:** Raw reviewer scores vary by manager leniency; the downward adjustment simulates
calibration in a department-level review where the average is normalised.

---

### `salary_increase_percentage` (0–15 float)
Merit-based salary increase rate.

```
base_pct     = max(0, (overall_performance_score - 60) / 40 × 12)   # 0–12% for scores 60–100
peer_adj     = 1 + (productivity_vs_peers / 100)

pct = base_pct × peer_adj   → clamped [0, 15]
```

**Why:** No increase below 60 (below-expectations threshold); increases linearly up to 12%
for perfect scores; outperforming peers adds a multiplier up to +15% because relative
contribution to team output is separately rewarded.

---

## Burnout Indicators

### `overall_burnout_risk` (0–100 float)
Composite burnout risk using Maslach Burnout Inventory weighting.

```
exhaust_norm  = emotional_exhaustion_score  × 10   (0-10 → 0-100)
deperson_norm = depersonalization_score     × 10
reduced_norm  = reduced_accomplishment_score × 10

score = exhaust_norm  × 0.40
      + deperson_norm × 0.30
      + reduced_norm  × 0.30
      + Normal(0, 5)  → clamped [0, 100]
```

**Why:** Maslach research weights emotional exhaustion as the primary burnout dimension (40%);
depersonalisation and reduced accomplishment contribute equally (30% each) as co-indicators.

---

### `predicted_burnout_30days` / `predicted_burnout_90days` (0–100 float)
Forward projection of burnout risk based on current trajectory.

```
trend_adjustments = {
  Decreasing:         30d: -5,  90d: -12.5
  Stable:             30d:  0,  90d:   0
  Increasing:         30d: +8,  90d: +20
  Rapidly Increasing: 30d: +15, 90d: +37.5
}

predicted_30d = overall_burnout_risk + trend_30 + Normal(0, 4)  → clamped [0, 100]
predicted_90d = overall_burnout_risk + trend_90 + Normal(0, 7)  → clamped [0, 100]
```

**Why:** The 90-day adjustment is 2.5× the 30-day adjustment (compounding trend) with
higher noise to reflect increased uncertainty. Noise standard deviation scales with horizon
because longer-range predictions are inherently less certain.
