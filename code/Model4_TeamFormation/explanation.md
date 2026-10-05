# Model 4 — Team Formation (with Composition Anomaly Detector)

Part of **ePARS** (Employee Performance Analyzer and Recommendation System), Team 126.
Location in repo: `code/Model4_TeamFormation/`

---

## 1. What Model 4 does (in one paragraph)

Given a project that is already broken into tasks, Model 4 recommends the **best team**: one employee per task. It reuses Model 3 to score every employee against every task, then searches for the combination of people that works best **as a team**, not just task by task. The newest part is a **trained ML model (Isolation Forest)** that checks whether a candidate team's composition looks like how teams are actually staffed at the company, or is an unusual outlier.

---

## 2. Why this design

| Problem | Decision |
|---|---|
| Model 3 scores one employee-task pair at a time and cannot see who else is on the team. | Model 4 adds a team-level search and scoring layer on top of Model 3. |
| `team_formations.csv` outcome columns (`actual_performance_score`, `met_deadline`, `quality_rating`) are generated as pure random noise in the dataset generator. | We do **not** train a model to predict team success. It would only fit noise (or copy a formula we already have). |
| We still want a genuine ML model in the pipeline. | Train an **unsupervised** model on the real *rosters* in `team_formations.csv` (who was put together), which needs no outcome label. |

**Key idea:** the model answers *"Is this team composition typical or unusual compared with the ~1000 historical teams?"*, not *"How good will this team be?"*.

---

## 3. The pipeline

```
Project (list of tasks)
        │
        ▼
[1] Model 3 (scheduler.py)
    For every task → top-5 candidate employees with a composite_score
        │
        ▼
[2] Initial assignment (Hungarian algorithm)
    One employee per task, maximising the sum of task scores, nobody double-booked
        │
        ▼
[3] Search for better teams
    • Small projects: enumerate every valid combination (exact top-N)
    • Larger projects: Hungarian seed + random-greedy restarts + local search (swap candidates,
      keep a swap if the TEAM score improves)
        │
        ▼
[4] Team scoring (each candidate team)
    task_fit + experience_balance + workload_balance + past_overlap
    + composition_typicality  ← trained Isolation Forest (NEW)
        │
        ▼
[5] Output: top-N distinct teams, each with team_score, score_breakdown,
    unusual_composition flag, and the task → employee assignments
```

### Team score components

| Component | Weight (skill coverage off) | What it measures |
|---|---|---|
| `task_fit` | 0.45 | Mean of Model 3's per-task `composite_score` |
| `experience_balance` | 0.10 | Seniority diversity within the team |
| `workload_balance` | 0.10 | 100 − average `burnout_risk_score` |
| `past_overlap` | 0.05 | Fraction of member pairs that have worked together before |
| `composition_typicality` | 0.10 | **Isolation Forest score, 0–100 (100 = typical roster)** |
| `skill_coverage` | 0.20 in full config | Fraction of required project skills covered. Currently computed and reported but **switched off** (`INCLUDE_SKILL_COVERAGE = False`) |

When `skill_coverage` is off, the remaining weights are renormalised automatically so `team_score` stays on a 0–100 scale. These weights are **starting points, not tuned values**, because there is no real outcome label to tune against.

---

## 4. The trained model: composition anomaly detector

### Algorithm
- **Isolation Forest** (scikit-learn), unsupervised.
- Isolation Forest isolates points with random splits. Unusual points are isolated in fewer splits and get lower scores.
- 100 trees, `random_state=42`, features standardised with `StandardScaler`.

### Training data
- The ~1000 historical teams in `dataset/team_formations.csv`.
- A team's members are `member_ids` plus `team_lead_id` (so `team_size` = members + lead).
- **No outcome columns are used.** Only who was on the team.

### Features (15, computed from `employees.csv`)

| Group | Features |
|---|---|
| Department mix | `dominant_dept_share`, `n_dept_ratio` |
| Seniority | `seniority_mean`, `seniority_std`, `frac_Junior`, `frac_Mid`, `frac_Senior`, `frac_Lead`, `frac_Principal` |
| Experience / ability | `yoe_mean`, `yoe_std`, `tech_mean`, `collab_mean` |
| Load | `burnout_mean` |
| Skills | `skill_breadth_per_member` |

Design choices:
- **Same function for training and inference.** `team_features()` in `composition_model.py` builds features for historical teams (training) and for candidate teams (inference), so there is no scale mismatch.
- **Team size is not a feature.** Candidate teams have one person per task and may be larger or smaller than the historical 3–10. Every feature is a ratio or mean, so teams of different sizes stay comparable.
- **`past_overlap` is not a feature.** Every historical pair has by definition worked together, which would leak into training.

### Output
- `typicality()` returns **0–100** (100 = very typical). The raw Isolation Forest score is rescaled so the 1st–99th percentile of historical teams maps to 0–100.
- `is_anomalous()` is `True` when typicality is below the **5th percentile of the training teams** (about 23–24).
- In the recommender, the result appears as:
  - `score_breakdown["composition_typicality"]`
  - `unusual_composition` (true or false) on each recommended team

---

## 5. Validation results

There is no outcome label, so validation checks whether the detector separates **real** rosters from **random** ones.

| Check | Result |
|---|---|
| Held-out real teams flagged unusual (20% hold-out) | ~6% (expected ~5% by threshold design) |
| Synthetic random-roster teams flagged unusual | ~80% |
| AUC, held-out real vs random rosters | ~0.97 |
| Best recommended teams for test projects PRJ003 and PRJ001 | Not flagged; typicality ~45–78 |
| Runtime | ~2–3 s per project (exact mode for 6 tasks, heuristic for 14 tasks) |

Exact numbers vary slightly by run and library version. Retrain locally and use your own printout.

---

## 6. What the model catches, and what it does not

**What it catches**
- A single team of mixed departments (for example a Design person, a Finance person and an HR person mixed together) when historical teams are almost always from one department.
- Odd seniority skews, such as all Principals or all Juniors.

**Why it works on this dataset:** in `team_formations.csv`, the largest department makes up ~96% of a team on average. A random roster has ~38%. The model learns this staffing pattern.

**What it does not do**
- It does **not** predict team success or quality. It measures similarity to past staffing decisions.
- The historical teams are **simulated**, so "typical" means "typical of the generator". With real company data the learned patterns would be richer.
- About 5% of real historical teams will themselves be flagged, by construction.
- A candidate team larger than 10 is not penalised for size.
- It is a soft signal (10% of the score plus a flag), not a hard rule.

---

## 7. Files

| File | Purpose |
|---|---|
| `composition_model.py` | `team_features()`, `CompositionModel` (`typicality`, `typicality_many`, `is_anomalous`), loads the saved artifact |
| `train_composition_model.py` | Builds features, fits and validates the Isolation Forest, saves the artifact |
| `artifacts/composition_model.joblib` | Saved scaler, forest and thresholds. Regenerate with the training script |
| `team_recommender.py` | Search and team scoring. Calls the composition model for every candidate team |

Dependencies: `pandas`, `numpy`, `scipy`, `scikit-learn`, `joblib`.

---

## 8. How to run

All commands are run from `code/Model4_TeamFormation`.

```bash
cd code/Model4_TeamFormation

# 1. Train (creates artifacts/composition_model.joblib, prints validation)
python train_composition_model.py

# 2. Recommend teams
python team_recommender.py --project-id PRJ001 --num-teams 3
```

Run order matters: **train first, then recommend.** Retrain on each machine, because a pickled scikit-learn model can break across versions.

Model 3's existing artifacts must be present (`scheduler.py` and its `.pkl` and `.csv` files). Model 1–3 do not need to be rerun first. If `employees.csv` or `team_formations.csv` change, retrain Model 3 if it depends on them, then retrain this model before running the recommender.

### Example output (abridged)

```json
{
  "project_id": "PRJ001",
  "search_mode": "hungarian+local_search",
  "team_score": 69.3,
  "unusual_composition": false,
  "score_breakdown": {
    "task_fit": 71.0,
    "skill_coverage": 100.0,
    "experience_balance": 53.6,
    "workload_balance": 96.4,
    "past_overlap": 9.9,
    "composition_typicality": 77.9
  },
  "assignments": [{ "task_id": "...", "employee_id": "...", "task_composite_score": 0.0 }]
}
```

---

## 9. Likely questions

**Why not train a model to predict team performance?**
The outcome columns in `team_formations.csv` are random noise. Any model trained on them would fit noise or copy the formula we already have. That model would not be necessary.

**Why Isolation Forest?**
It is unsupervised, so it needs no labels. It works well on tabular features, is fast, and gives a score for any new team.

**Why does it matter if the pipeline already scores skills, seniority and burnout?**
Those components each score one dimension. The forest judges the **whole composition** at once. A team can look fine on every individual metric and still be a roster nobody would normally staff.

**Is the 0.10 weight justified?**
It is a starting point. Without outcome labels there is nothing to tune it against. Revisit it if real team-outcome data becomes available.

**Why is `skill_coverage` off?**
It was staged in deliberately: validate the core model first, then enable it with `INCLUDE_SKILL_COVERAGE = True`. The other weights renormalise automatically.

---

## 10. Possible future work

- Re-enable `skill_coverage` and review the weights together.
- Retrain on real historical staffing data when available, and add features such as role or department combinations.
- Calibrate the weight and the anomaly threshold once real team-outcome labels exist.
- Show the `unusual_composition` flag and the typicality score in the UI, with a short explanation of which features made the team unusual.