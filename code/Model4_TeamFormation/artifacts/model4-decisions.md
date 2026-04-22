# Model 4 — Design Decisions & Feature Reference

This document captures all design decisions, feature audit outcomes, and formula corrections
discussed during development. It serves as the authoritative reference for what the model
does, what it uses, and why certain choices were made.

---

## 1. What This Model Actually Does

**Problem type:** Regression
**Question answered:** *"Given this team's composition and member history, how successfully will they execute this project?"*
**Output:** A predicted performance score (0–100) representing expected project outcome quality.

**This is NOT:**
- An individual employee performance predictor
- A team member selector (that is a planned upstream agentic feature)
- A real-time project monitor

---

## 2. Target Variable

**Column:** `actual_performance_score` (from `team_formations`)

**Formula (from dataset generator):**
```
q_norm   = quality_rating / 10 × 100
dl_norm  = 100 if met_deadline else 50
ba_norm  = max(0, 100 - max(budget_adherence - 100, 0) × 1.5)
sat_norm = stakeholder_satisfaction / 10 × 100

score = q_norm × 0.35 + dl_norm × 0.30 + ba_norm × 0.20 + sat_norm × 0.15
      + Normal(0, 3) → clamped [20, 100]
```

**Why it's a valid training target:**
- Captures the four dimensions of project success: quality, deadline, budget, stakeholder satisfaction
- Only available for completed projects — these become training data
- Rows where it is null = ongoing/new projects = inference targets

**Key point:** The inputs to this formula (`quality_rating`, `met_deadline`, etc.) are POST-completion outcomes. They are never used as model features — only as the label during training.

---

## 3. Training vs Inference Data

| Data state | `actual_performance_score` | Used for |
|---|---|---|
| Completed project, score known | Not null | Training (labeled data) |
| Ongoing / new project, score unknown | Null | Inference (prediction target) |

**The model learns from history and predicts for the future. Features must be available at team formation time — before the project runs.**

---

## 4. Feature Audit — What to Use, Drop, or Recompute

### 4.1 Features to RECOMPUTE

#### `collaborative_history_score`

**Problem:** Dataset generator used individual `collaboration_score` average as a proxy. This measures personal collaboration style, not actual shared history between these specific members.

**Correct formula:**
```
For every pair (A, B) in the team:
    check if B appears in A's past_team_members (or vice versa)

collaborative_history_score = (pairs with prior history / total possible pairs) × 100
```

**Source:** `past_team_members` column in `employees.csv`
**When:** Computed during feature extraction, per team
**Replaces:** The `collaborative_history_score` column read directly from `team_formations`

---

### 4.2 Features to DROP

#### `predicted_success_rate` (from `team_formations`)
**Reason:** Circular — it is a weighted combination of other features already in the model:
```
score = skill_coverage × 0.30 + avg_perf × 0.25 + skill_diversity × 0.15
      + exp_balance × 0.10 + collab_history × 0.08 + avg_seniority × 0.07
      + workload_balance × 0.05
```
Including it alongside its own components causes multicollinearity and inflates apparent model performance.

---

#### `avg_team_compatibility` (from `task_assignments`)
**Reason:** `team_compatibility_score` formula is:
```
score = collab_norm × 0.65 + history_proxy × 0.35
where history_proxy = Normal(70, 15)  ← pure random noise
```
35% of this score is random by design. Averaging noise across team members adds no signal.

---

#### `delay_risk_score`, `budget_overrun_risk`, `scope_creep_indicator` (from `projects`)
**Reason:** All three are derived from execution-state columns:
- `delay_risk_score` ← `overdue_milestones`, `days_ahead_behind`
- `budget_overrun_risk` ← `consumed_resources`
- `scope_creep_indicator` ← `overdue_milestones`

At team formation time (before the project runs), these are all near-zero or at their default baseline — they carry no predictive signal about team quality.

---

#### `resource_consumption_ratio` (`consumed_resources / allocated_resources`)
**Reason:** `consumed_resources ≈ 0` at formation time. Ratio is meaningless.

---

#### `milestone_completion_rate` (`completed_milestones / total_milestones`)
**Reason:** `completed_milestones = 0` at formation time. Ratio is meaningless.

---

#### Outcome / leakage columns (from `team_formations`)
These are only known after project completion — using them would be data leakage:
- `met_deadline`
- `quality_rating`
- `budget_adherence`
- `stakeholder_satisfaction`
- `collaboration_effectiveness`
- `completion_time_days`
- `team_feedback_score`
- `project_completed`

---

### 4.3 Features Confirmed VALID

All features below are available at team formation time and carry genuine signal.

**From `team_formations` (direct):**
| Feature | Signal |
|---|---|
| `team_size` | Size affects coordination overhead |
| `skill_diversity_score` | Breadth of unique capabilities |
| `experience_balance_score` | Junior/senior mix health |
| `collaborative_history_score` | ⚠️ Recomputed (see 4.1) |
| `workload_balance_score` | Even distribution of load |
| `skill_utilization_rate` | Are members assigned to matching skills |
| `resource_utilization` | Resource allocation efficiency |
| `formation_method_encoded` | Manual vs AI-recommended formation |

**From `employees` (aggregated per team):**
| Feature | Signal |
|---|---|
| `avg_technical_proficiency` | Team's avg technical capability |
| `avg_domain_expertise` | Team's avg domain knowledge |
| `avg_historical_performance` | Team's avg past performance |
| `avg_collaboration_score` | Team's avg interpersonal skill |
| `avg_leadership_potential` | Leadership quality in team |
| `avg_burnout_risk` | Avg risk of member burnout |
| `max_burnout_risk` | Flag any critically burnt-out member |
| `avg_task_completion_rate` | Reliability of task delivery |
| `avg_years_experience` | Team's avg experience |
| `std_years_experience` | Experience spread (diversity signal) |
| `pct_senior_or_above` | Proportion of senior+ members |
| `pct_available` | How many members are currently free |
| `total_successful_projects` | Team's combined delivery track record |
| `avg_failed_projects` | Team's combined failure history |
| `n_unique_roles` | Role diversity in team |
| `n_unique_departments` | Cross-functional flag |

**From `projects` (formation-time safe only):**
| Feature | Signal |
|---|---|
| `project_complexity_encoded` | How hard the project is |
| `project_priority_encoded` | Business urgency |
| `success_probability` | Project-level optimism score |

**From `performance_reviews` (per-member historical avg):**
| Feature | Signal |
|---|---|
| `avg_member_review_score` | Formal assessed performance |
| `avg_member_productivity_score` | Formal assessed productivity |
| `avg_member_collaboration_review` | Formally reviewed collaboration |
| `pct_members_promotion_ready` | Proportion of high performers |

**From `workload_history` (last 30 days):**
| Feature | Signal |
|---|---|
| `avg_workload_intensity` | Current load level |
| `avg_productivity_vs_avg` | Performance vs personal baseline |
| `avg_workload_vs_capacity` | How stretched members are |
| `pct_members_overtime` | Proportion working beyond capacity |
| `team_burnout_risk_today` | Current team-level burnout risk |

**From `task_assignments` (historical per-member avg):**
| Feature | Signal |
|---|---|
| `avg_skill_match_score` | How well members are matched to tasks |
| `avg_overall_suitability` | Composite assignment fitness |
| `avg_assignment_efficiency` | How efficiently members execute |
| `pct_assignments_successful` | Historical success rate of assignments |

**From `feedback` (team-level):**
| Feature | Signal |
|---|---|
| `avg_feedback_overall_rating` | Peer/manager perception of team |
| `avg_feedback_collaboration` | Collaboration quality via feedback |
| `avg_feedback_communication` | Communication quality via feedback |

---

## 5. Cold-Start Handling

**Scenario:** New employee with no history in `performance_reviews`, `workload_history`, `task_assignments`.

**Impact:** Only affects team-level averages slightly (e.g., `avg_historical_performance` will be based on fewer members).

**Handling:** SimpleImputer (median strategy) in the training pipeline handles any resulting nulls at the feature level. For better accuracy, substitute with department + seniority level average before aggregating.

**Not a concern:** A "new team" (never existed before) is fine — features are computed fresh from member records, not looked up by `team_id`.

---

## 6. ML Model Scope & Boundaries

| Responsibility | ML Model | Agentic Layer |
|---|---|---|
| Predict team success score | ✅ | ❌ |
| Filter eligible employees | ❌ | ✅ (planned) |
| Select team members + lead | ❌ | ✅ (planned) |
| Enforce HR policies | ❌ | ✅ |
| Explain recommendation in NL | ❌ | ✅ |
| Real-time availability check | ❌ | ✅ |
| Rerank multiple candidate teams | Via score | ✅ with policy context |

**The ML model stops at the score. Everything downstream is the agentic layer's responsibility.**

---

## 7. Planned: Team Member Selection (Agentic Layer)

When implemented, the flow will be:

```
Input: project_id OR direct fields
  (department, priority, budget, complexity_level,
   start_date, planned_end_date, team_size,
   required_skills, allocated_resources)
        ↓
Hard filter employees:
  - is_available == True
  - skill overlap with required_skills
  - burnout_risk_score < threshold
  - sufficient weekly capacity
        ↓
Score each candidate (weighted):
  - Skill match vs required_skills     35%
  - historical_performance_score       25%
  - workload_vs_capacity (inverted)    20%
  - experience vs complexity           10%
  - collaboration_score                10%
        ↓
Select top team_size candidates
Team lead = highest leadership_potential with seniority ≥ Senior
        ↓
Build feature row for assembled team
        ↓
Feed into ML model → predicted_performance_score
        ↓
Return: member IDs, team lead ID, score, tier, risk flags
```

**No new ML model needed** — this is rule-based logic. The existing Model 4 acts as the scorer at the end of this pipeline.

---

## 8. Output Format (ML Model)

```json
{
  "team_id": "TEAM042",
  "project_id": "PRJ017",
  "predicted_performance_score": 81.4,
  "confidence_band": { "low": 74.2, "high": 88.6 },
  "performance_tier": "High",
  "top_contributing_features": [
    { "feature": "avg_skill_match_score", "importance": 0.142 },
    { "feature": "collaborative_history_score", "importance": 0.118 },
    { "feature": "avg_burnout_risk", "importance": 0.097 }
  ],
  "risk_flags": {
    "high_burnout_member": true,
    "low_skill_utilization": false,
    "workload_imbalance": false,
    "low_availability": false
  },
  "model_metadata": {
    "model_type": "RandomForestRegressor",
    "model_version": "1.0",
    "training_r2": 0.79,
    "test_rmse": 7.3
  }
}
```

**Performance tiers:**
- `Low`: score < 60
- `Medium`: 60 ≤ score < 75
- `High`: 75 ≤ score < 88
- `Exceptional`: score ≥ 88

**Risk flag thresholds:**
- `high_burnout_member`: `max_burnout_risk` ≥ 70
- `low_skill_utilization`: `skill_utilization_rate` < 60
- `workload_imbalance`: `workload_balance_score` < 50
- `low_availability`: `pct_available` < 0.5

---

## 9. Feature Count Summary

| Source | Features kept | Features dropped |
|---|---|---|
| team_formations | 8 | 10 (leakage + circular) |
| employees | 16 | PII + past_team_members (used for recompute) |
| projects | 3 | 5 (execution-state, not formation-time) |
| performance_reviews | 4 | — |
| workload_history | 5 | — |
| task_assignments | 4 | 1 (noisy by design) |
| feedback | 3 | — |
| **Total** | **~38 features** | **~16 dropped** |
