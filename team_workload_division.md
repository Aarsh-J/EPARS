# Dataset Generation - Team Workload Division

## Team Distribution: 4 People, 10 Tables

---

## **PERSON 1: EMPLOYEE & WORKLOAD DATA** 
### Focus: Core employee information and time-series workload patterns

### Tables Assigned (3 tables):
1. **employees.csv** (500 rows)
2. **workload_history.csv** (25,000 rows)
3. **burnout_indicators.csv** (2,500 rows)

### Why This Grouping:
- All three tables center around **employee behavior and well-being**
- Share common employee_id references
- Similar temporal patterns (workload → burnout)
- Requires understanding of **stress/capacity metrics**

### Key Relationships:
```
employees.csv (base)
    ├─→ workload_history.csv [employee_id]
    └─→ burnout_indicators.csv [employee_id]
```

### Common Column Patterns:
- **Employee identifiers:** employee_id
- **Workload metrics:** hours worked, overtime, task density
- **Well-being scores:** stress_level, fatigue, burnout_risk
- **Temporal data:** dates, trends over time
- **Capacity indicators:** weekly_capacity_hours, workload_intensity

### Shared Constraints:
- All employee_ids must exist in employees.csv first
- Workload patterns should correlate with burnout indicators
- Timeline consistency: burnout should increase after sustained high workload
- Normal distributions for performance/stress (mean ~75, ~50 respectively)

### Generation Order:
1. **First:** employees.csv (foundation)
2. **Second:** workload_history.csv (daily records per employee)
3. **Third:** burnout_indicators.csv (derived from workload patterns)

### Estimated Time: **6-8 hours**

---

## **PERSON 2: TASK & PROJECT DATA**
### Focus: Work items, project management, and organizational structure

### Tables Assigned (3 tables):
1. **projects.csv** (150 rows)
2. **tasks.csv** (3,000 rows)
3. **schedules.csv** (10,000 rows)

### Why This Grouping:
- All three tables define **what work needs to be done**
- Share project/task hierarchies and dependencies
- Requires understanding of **timelines, deadlines, priorities**
- Common scheduling and resource allocation logic

### Key Relationships:
```
projects.csv (parent)
    ├─→ tasks.csv [project_id]
    └─→ schedules.csv [related_id for tasks]

employees.csv → projects.csv [project_manager_id]
employees.csv → schedules.csv [employee_id]
```

### Common Column Patterns:
- **Identifiers:** project_id, task_id, schedule_id
- **Timeline fields:** start_date, end_date, due_date, duration
- **Priority/Complexity:** priority, complexity, risk_scores
- **Status tracking:** current_status, completion_percentage
- **Resource allocation:** estimated_hours, team_size

### Shared Constraints:
- Task due_dates must be within project start/end dates
- Schedule entries must reference valid task_ids
- Dependencies (dependent_task_ids) must reference existing tasks
- Realistic task distributions: 70% simple-moderate, 30% complex
- Project timeline = earliest task start to latest task end

### Generation Order:
1. **First:** projects.csv (needs employee_ids from Person 1)
2. **Second:** tasks.csv (needs project_ids)
3. **Third:** schedules.csv (needs task_ids and employee_ids)

### Estimated Time: **7-9 hours**

---

## **PERSON 3: TEAM FORMATION & ASSIGNMENT DATA**
### Focus: How people are matched to work and team composition

### Tables Assigned (2 tables):
1. **task_assignments.csv** (5,000 rows)
2. **team_formations.csv** (200 rows)

### Why This Grouping:
- Both tables deal with **matching employees to work**
- Share skill-matching and suitability logic
- Requires understanding of **team dynamics and collaboration**
- Similar outcome tracking (success, performance, satisfaction)

### Key Relationships:
```
task_assignments.csv:
    employees.csv → [employee_id]
    tasks.csv → [task_id]
    projects.csv → [project_id]

team_formations.csv:
    employees.csv → [team_lead_id, member_ids]
    projects.csv → [project_id]
```

### Common Column Patterns:
- **Matching scores:** skill_match_score, suitability_score, compatibility_score
- **Assignment details:** assignment_date, assignment_method
- **Outcome metrics:** assignment_success, completion_status, quality_rating
- **Team composition:** team_size, role_distribution, member_ids
- **Performance tracking:** efficiency_score, productivity_score

### Shared Constraints:
- All employee_ids must exist in employees.csv
- All task_ids/project_ids must exist in respective tables
- Skill matches: if task requires "Python", assigned employee should have "Python" in skills
- Team member_ids must be comma-separated valid employee_ids
- Realistic success rates: ~80% successful assignments, ~20% reassignments

### Generation Order:
1. **First:** team_formations.csv (needs employees and projects from Persons 1 & 2)
2. **Second:** task_assignments.csv (needs teams, tasks, employees)

### Coordination Required:
- **Wait for:** Person 1 (employees) and Person 2 (tasks, projects)
- **Provide to:** Person 4 (for feedback and reviews)

### Estimated Time: **5-6 hours**

---

## **PERSON 4: FEEDBACK & PERFORMANCE EVALUATION DATA**
### Focus: Outcomes, reviews, and continuous improvement

### Tables Assigned (2 tables):
1. **performance_reviews.csv** (800 rows)
2. **feedback.csv** (3,000 rows)

### Why This Grouping:
- Both tables capture **evaluation and assessment**
- Share rating/scoring mechanisms
- Requires understanding of **performance metrics and feedback loops**
- Similar sentiment and qualitative data

### Key Relationships:
```
performance_reviews.csv:
    employees.csv → [employee_id, reviewer_id]

feedback.csv:
    employees.csv → [provider_id, recipient_id]
    tasks.csv → [related_task_id]
    projects.csv → [related_project_id]
    teams.csv → [related_team_id]
```

### Common Column Patterns:
- **Rating scores:** overall_rating, quality_rating, collaboration_rating (0-10 scale)
- **Performance metrics:** performance_score, productivity_score, technical_competence
- **Feedback content:** feedback_text, positive_aspects, improvement_areas
- **Timestamps:** review_date, feedback_date, assessment periods
- **Action items:** development_goals, training_recommendations

### Shared Constraints:
- All employee_ids must exist in employees.csv
- Review scores should correlate with task assignment outcomes
- Feedback sentiment should match quality ratings
- Performance scores should align with task completion rates
- Realistic distributions: most employees 60-85 range, few outliers

### Generation Order:
1. **First:** feedback.csv (needs completed tasks/projects from Person 2)
2. **Second:** performance_reviews.csv (aggregates feedback and outcomes)

### Coordination Required:
- **Wait for:** Persons 1, 2, 3 (needs all base data and outcomes)
- **Uses data from:** Task assignments outcomes, team formation results

### Estimated Time: **4-5 hours**

---

## **COORDINATION & DEPENDENCIES**

### Generation Timeline (Sequential Order):

```
DAY 1:
┌─────────────────────────────────────────────────────┐
│ PERSON 1 (Morning - 4 hours)                        │
│ └─ Generate employees.csv                           │
│    └─ Share with team                               │
└─────────────────────────────────────────────────────┘
         ↓ (employees.csv shared)
┌─────────────────────────────────────────────────────┐
│ PERSON 1 (Afternoon - 4 hours) | PERSON 2 (Start)  │
│ └─ workload_history.csv         | └─ projects.csv   │
│ └─ burnout_indicators.csv       |                   │
└─────────────────────────────────────────────────────┘

DAY 2:
┌─────────────────────────────────────────────────────┐
│ PERSON 2 (Full day - 8 hours)                       │
│ └─ tasks.csv                                        │
│ └─ schedules.csv                                    │
│    └─ Share tasks.csv and projects.csv with team    │
└─────────────────────────────────────────────────────┘
         ↓ (tasks.csv, projects.csv shared)
┌─────────────────────────────────────────────────────┐
│ PERSON 3 (Start - 3 hours)                          │
│ └─ team_formations.csv                              │
└─────────────────────────────────────────────────────┘

DAY 3:
┌─────────────────────────────────────────────────────┐
│ PERSON 3 (Morning - 3 hours) | PERSON 4 (Start)    │
│ └─ task_assignments.csv       | └─ feedback.csv     │
│    └─ Share with Person 4     |                     │
└─────────────────────────────────────────────────────┘
         ↓ (task_assignments.csv shared)
┌─────────────────────────────────────────────────────┐
│ PERSON 4 (Afternoon - 3 hours)                      │
│ └─ performance_reviews.csv                          │
└─────────────────────────────────────────────────────┘

DAY 4 (If needed):
┌─────────────────────────────────────────────────────┐
│ ALL TEAM: Validation & Integration (4 hours)        │
│ └─ Verify referential integrity                     │
│ └─ Check data quality                               │
│ └─ Run integration tests                            │
└─────────────────────────────────────────────────────┘
```

---

## **SHARED FILES & COMMUNICATION**

### What to Share:
1. **Person 1 shares immediately:**
   - `employees.csv` (needed by everyone)
   - List of valid employee_ids

2. **Person 2 shares after completion:**
   - `projects.csv` (needed by Persons 3 & 4)
   - `tasks.csv` (needed by Persons 3 & 4)
   - List of valid project_ids and task_ids

3. **Person 3 shares after completion:**
   - `task_assignments.csv` (needed by Person 4 for performance correlation)
   - `team_formations.csv` (needed by Person 4 for feedback)

4. **Everyone shares:**
   - ID lists (employee_ids, project_ids, task_ids, etc.)
   - Value ranges used (for consistency)

---

## **COMMON CONSTRAINTS (ALL TEAM MEMBERS)**

### 1. ID Format Standards:
```python
employee_id = f'EMP{i:03d}'      # EMP001, EMP002, ...
project_id = f'PRJ{i:03d}'       # PRJ001, PRJ002, ...
task_id = f'TSK{i:04d}'          # TSK0001, TSK0002, ...
team_id = f'TEAM{i:03d}'         # TEAM001, TEAM002, ...
# etc.
```

### 2. Date Ranges:
- Hire dates: 2019-01-01 to 2024-12-31
- Project dates: 2022-01-01 to 2025-12-31
- Task dates: Within project date ranges
- Workload history: Last 6-12 months (2024-01-01 to 2024-12-31)

### 3. Score Distributions:
- Performance scores: Normal distribution, mean=75, std=15, range [0-100]
- Risk scores: Skewed low, mean=35, std=20, range [0-100]
- Ratings (0-10): Normal, mean=7.5, std=1.5, range [0-10]

### 4. Random Seeds (for reproducibility):
```python
Faker.seed(42)
random.seed(42)
np.random.seed(42)
```

### 5. Null Value Percentages:
- Optional fields: 10-20% null
- Work in progress: 30-40% null (e.g., completion dates)
- Future fields: 50-70% null (e.g., upcoming reviews)

---

## **QUALITY CHECKS (Each Person Responsible For)**

### Person 1:
- [ ] All employee_ids are unique
- [ ] No negative hours in workload_history
- [ ] Burnout scores correlate with overtime hours
- [ ] All dates are valid and chronological

### Person 2:
- [ ] All project_ids and task_ids are unique
- [ ] Task due_dates fall within project timelines
- [ ] All project_manager_ids exist in employees.csv
- [ ] Task dependencies reference valid task_ids

### Person 3:
- [ ] All assigned employee_ids exist in employees.csv
- [ ] All task_ids and project_ids exist
- [ ] Team member_ids are comma-separated valid IDs
- [ ] Skill matches are realistic (Python task → Python skilled employee)

### Person 4:
- [ ] All employee_ids (reviewer, recipient) exist
- [ ] Review periods are logical (e.g., quarterly, annual)
- [ ] Feedback ratings correlate with performance scores
- [ ] All related_task_ids and related_project_ids exist

---

## **FINAL INTEGRATION (Team Activity)**

### Validation Script (Run Together):
```python
# Check referential integrity
def validate_all_tables():
    # Load all CSVs
    employees = pd.read_csv('employees.csv')
    tasks = pd.read_csv('tasks.csv')
    projects = pd.read_csv('projects.csv')
    # ... load all
    
    # Check 1: All foreign keys exist
    assert all(tasks['assigned_to'].dropna().isin(employees['employee_id']))
    assert all(tasks['project_id'].isin(projects['project_id']))
    
    # Check 2: No orphaned records
    assert len(employees) > 0
    assert len(tasks) > 0
    
    # Check 3: Value ranges
    assert all(employees['historical_performance_score'].between(0, 100))
    
    # Check 4: Dates are logical
    # ... more checks
    
    print("✓ All validation checks passed!")
```

---

## **SUMMARY: Who Does What**

| Person | Tables (Count) | Total Rows | Focus Area | Time |
|--------|---------------|------------|------------|------|
| **Person 1** | employees, workload_history, burnout_indicators (3) | ~28,000 | Employee well-being | 6-8h |
| **Person 2** | projects, tasks, schedules (3) | ~13,150 | Work structure | 7-9h |
| **Person 3** | task_assignments, team_formations (2) | ~5,200 | Matching & teams | 5-6h |
| **Person 4** | performance_reviews, feedback (2) | ~3,800 | Evaluation | 4-5h |

**Total:** 10 tables, ~50,150 rows, 22-28 hours team effort (5-7 hours per person)

---

## **ALTERNATIVE: If You Want Equal Workload**

### Option B: Split by Complexity Instead of Similarity

**Person 1 (High Complexity - 8h):**
- employees.csv
- workload_history.csv (largest table)

**Person 2 (High Complexity - 8h):**
- tasks.csv (complex dependencies)
- schedules.csv (complex time logic)

**Person 3 (Medium Complexity - 6h):**
- projects.csv
- team_formations.csv
- task_assignments.csv

**Person 4 (Medium Complexity - 6h):**
- burnout_indicators.csv
- performance_reviews.csv
- feedback.csv

---

## **RECOMMENDATION**

**Use the original grouping (Option A)** because:
1. ✅ Each person becomes an expert in their domain
2. ✅ Reduces coordination overhead (fewer dependencies to wait for)
3. ✅ Natural grouping by ML model usage
4. ✅ Easier to maintain consistency within related tables
5. ✅ Clear ownership and accountability

The time difference (4-9 hours per person) is acceptable because:
- Person 1 finishes first, can help with validation
- Person 4 starts last, can do final integration
- Real-world projects have unequal task distributions
