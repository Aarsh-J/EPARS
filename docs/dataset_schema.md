# Employee Performance Analyzer — Simplified Schema Specification (V3)

## Legend
- 🎲 **GENERATE** — randomly generated value (seed data)
- 🧮 **CALCULATE** — must be derived/computed from other generated values; do NOT generate randomly

## Score Scale Rule
- **0–100 float** → calculated/computed scores (formulas, aggregations, ML outputs)
- **0–10 integer** → human-given ratings (reviewer scores, survey responses, satisfaction ratings)

---

## 1. EMPLOYEES TABLE (employees.csv)

### Core Identity
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| employee_id | string | 🎲 GENERATE | Unique identifier | EMP001, EMP002 |
| first_name | string | 🎲 GENERATE | First name | John, Sarah, Raj |
| last_name | string | 🎲 GENERATE | Last name | Smith, Kumar, Garcia |
| email | string | 🧮 CALCULATE | Derived from first_name + last_name | john.smith@company.com |
| department | string | 🎲 GENERATE | Department name | Engineering, Sales, HR, Finance, Design |
| role | string | 🧮 CALCULATE | Consistent with department | Software Engineer, Designer, Analyst |
| seniority_level | string | 🎲 GENERATE | Experience level | Junior, Mid, Senior, Lead, Principal |
| employment_type | string | 🎲 GENERATE | Contract type | Full-time, Part-time, Contract |
| hire_date | date | 🎲 GENERATE | Date hired | 2020-01-15 |
| years_of_experience | int | 🧮 CALCULATE | From hire_date + seniority_level | 1, 2, 5 |
| current_salary | float | 🧮 CALCULATE | Based on seniority_level + department | 50000, 75000, 120000 |

### Skills & Competencies
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| primary_skills | string (comma-sep) | 🧮 CALCULATE | Must match role + department | Python,Java,SQL |
| secondary_skills | string (comma-sep) | 🎲 GENERATE | Additional skills | Communication, Excel |
| certifications | string (comma-sep) | 🎲 GENERATE | Professional certs (nullable) | AWS Certified, PMP, null |
| technical_proficiency_score | float (0-100) | 🧮 CALCULATE | From primary_skills count + certifications + seniority_level | 35.0, 78.0, 92.0 |
| domain_expertise_score | float (0-100) | 🧮 CALCULATE | From department + years_of_experience + seniority_level | 42.0, 65.0, 89.0 |

### Availability & Capacity
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| weekly_capacity_hours | int | 🧮 CALCULATE | From employment_type (Full=40, Part=20, Contract=30) | 40, 20, 30 |
| is_available | boolean | 🧮 CALCULATE | From current_project_count vs capacity | True, False |
| current_project_count | integer | 🎲 GENERATE | Active projects count | 0, 1, 2, 3 |
| preferred_work_hours | string | 🎲 GENERATE | Preferred schedule | 9am-5pm, 10am-6pm, Flexible |
| remote_work_status | string | 🎲 GENERATE | Work location | Remote, Hybrid, Office |

### Performance & Well-being
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| historical_performance_score | float (0-100) | 🎲 GENERATE | Baseline performance seed | 45.5, 78.3, 92.1 |
| productivity_trend | string | 🧮 CALCULATE | From recent workload_history productivity_score trend | Increasing, Stable, Decreasing |
| average_task_completion_rate | float (0-100) | 🧮 CALCULATE | Aggregated from task_assignments.on_time_completion | 65.5, 85.0, 95.2 |
| collaboration_score | integer (0-10) | 🎲 GENERATE | Human-rated baseline; updated from performance_reviews | 5, 7, 9 |
| leadership_potential | float (0-100) | 🧮 CALCULATE | From seniority_level + successful_project_count + collaboration_score | 40.0, 65.0, 90.0 |
| stress_level | string | 🧮 CALCULATE | Bucketed from burnout_risk_score (0-33=Low, 34-66=Medium, 67+=High) | Low, Medium, High |
| burnout_risk_score | float (0-100) | 🧮 CALCULATE | From recent_overtime_hours + days_since_last_leave + workload_history stress signals | 10.5, 45.2, 78.9 |
| recent_overtime_hours | float | 🧮 CALCULATE | Aggregated from workload_history.overtime_hours (last 30 days) | 0.0, 5.5, 15.0 |
| days_since_last_leave | integer | 🎲 GENERATE | Days since last vacation | 10, 45, 120, 365 |

### Team & Collaboration History
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| preferred_team_size | string | 🎲 GENERATE | Ideal team size | Small (2-4), Medium (5-8), Large (9+) |
| past_team_members | string (comma-sep) | 🧮 CALCULATE | Derived from team_formations.member_ids history | EMP002,EMP005,EMP012 |
| successful_project_count | integer | 🧮 CALCULATE | Count from projects where outcome=success | 5, 12, 28 |
| failed_project_count | integer | 🧮 CALCULATE | Count from projects where outcome=failed | 0, 1, 3 |

### Timestamps
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| created_at | datetime | 🧮 CALCULATE | Same as hire_date (datetime format) | 2023-06-01 09:00:00 |
| last_updated | datetime | 🎲 GENERATE | Recent timestamp | 2024-01-15 14:30:00 |

---

## 2. PROJECTS TABLE (projects.csv)

### Core Project Information
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| project_id | string | 🎲 GENERATE | Unique identifier | PRJ001, PRJ002 |
| project_name | string | 🎲 GENERATE | Project title | Mobile App Redesign, Q1 Campaign |
| project_description | string | 🎲 GENERATE | Detailed description | Complete overhaul of mobile UI/UX |
| project_type | string | 🎲 GENERATE | Category | Product Development, Marketing, Internal, Research |
| department | string | 🎲 GENERATE | Owning department | Engineering, Marketing, Sales |
| priority | string | 🎲 GENERATE | Importance level | Low, Medium, High, Critical |
| budget | float | 🎲 GENERATE | Total approved budget | 50000.0, 250000.0, 1000000.0 |
| complexity_level | string | 🎲 GENERATE | Overall difficulty | Low, Medium, High, Very High |

### Timeline & Status
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| start_date | date | 🎲 GENERATE | Project start | 2024-01-01 |
| planned_end_date | date | 🧮 CALCULATE | start_date + duration based on complexity_level | 2024-06-30 |
| actual_end_date | date | 🧮 CALCULATE | Null if ongoing; set when current_status=Completed | 2024-06-28, null |
| current_status | string | 🎲 GENERATE | Project state | Planning, Active, On Hold, Completed, Cancelled |
| completion_percentage | float (0-100) | 🧮 CALCULATE | From completed_milestones / total_milestones | 0.0, 45.0, 85.0, 100.0 |
| is_on_schedule | boolean | 🧮 CALCULATE | From days_ahead_behind >= 0 | True, False |
| days_ahead_behind | float | 🧮 CALCULATE | Planned vs actual progress delta | -10, 0, 5 |

### Team & Resources
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| project_manager_id | string | 🧮 CALCULATE | FK to employees (Senior/Lead seniority) | EMP005 |
| team_member_ids | string (comma-sep) | 🧮 CALCULATE | FK list from team_formations.member_ids | EMP001,EMP003,EMP007 |
| team_size | integer | 🧮 CALCULATE | Count of team_member_ids | 3, 5, 10 |
| required_skills | string (comma-sep) | 🎲 GENERATE | Skills needed | Python,React,AWS |
| allocated_resources | float | 🧮 CALCULATE | Sum of team members' weekly_capacity_hours × project_duration_weeks | 500.0, 2000.0 |
| consumed_resources | float | 🧮 CALCULATE | Aggregated from workload_history.total_hours_worked for this project | 250.0, 1800.0 |

### Risk & Performance Metrics
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| success_probability | float (0-100) | 🧮 CALCULATE | From team skill match + complexity + schedule adherence | 45.0, 75.0, 95.0 |
| delay_risk_score | float (0-100) | 🧮 CALCULATE | From overdue_milestones + scope_creep_indicator + days_ahead_behind | 15.0, 50.0, 85.0 |
| budget_overrun_risk | float (0-100) | 🧮 CALCULATE | From consumed_resources / allocated_resources + scope_creep_indicator | 20.0, 45.0, 70.0 |
| quality_risk_score | float (0-100) | 🧮 CALCULATE | From team skill match score + task rework rates + complexity_level | 10.0, 35.0, 60.0 |
| scope_creep_indicator | float (0-100) | 🧮 CALCULATE | From task count growth vs original plan + overdue_milestones | 5.0, 25.0, 55.0 |
| stakeholder_satisfaction | integer (0-10) | 🎲 GENERATE | Human survey rating post-project (null if ongoing) | 6, 8, 9, null |
| roi_estimate | float | 🎲 GENERATE | Expected ROI % | 50.0, 150.0, 300.0 |

### Milestone Tracking
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| total_milestones | integer | 🎲 GENERATE | Planned milestone count | 3, 5, 8, 12 |
| completed_milestones | integer | 🧮 CALCULATE | From task completions aligned to milestones | 0, 2, 5 |
| overdue_milestones | integer | 🧮 CALCULATE | Milestones past due_date and not completed | 0, 1, 2 |
| next_milestone_date | date | 🎲 GENERATE | Next upcoming milestone date | 2024-02-15, null |
| next_milestone_risk | float (0-100) | 🧮 CALCULATE | From current delay_risk_score + blocked_tasks near milestone | 15.0, 45.0, 75.0 |

### Timestamps
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| created_at | datetime | 🧮 CALCULATE | Same as start_date (datetime format) | 2023-12-01 09:00:00 |
| last_updated | datetime | 🎲 GENERATE | Recent timestamp | 2024-01-20 11:30:00 |

---

## 3. TASKS TABLE (tasks.csv)

### Core Task Information
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| task_id | string | 🎲 GENERATE | Unique identifier | TSK001, TSK002 |
| task_name | string | 🎲 GENERATE | Task title | Implement auth, Design landing page |
| task_description | string | 🎲 GENERATE | Detailed description | Build OAuth2 with JWT |
| task_type | string | 🎲 GENERATE | Category | Development, Design, Testing, Research, Documentation |
| project_id | string | 🧮 CALCULATE | FK to projects | PRJ001, PRJ002 |
| priority | string | 🎲 GENERATE | Urgency | Low, Medium, High, Critical |
| complexity | string | 🎲 GENERATE | Difficulty | Simple, Moderate, Complex, Very Complex |
| estimated_hours | float | 🧮 CALCULATE | From complexity + task_type | 2.0, 8.0, 40.0, 80.0 |
| actual_hours | float | 🧮 CALCULATE | Null if incomplete; derived from efficiency + estimated_hours | 2.5, 10.0, null |
| story_points | integer | 🧮 CALCULATE | From complexity (Simple=1-2, Moderate=3-5, Complex=8-13) | 1, 2, 3, 5, 8, 13 |

### Skills & Requirements
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| required_skills | string (comma-sep) | 🧮 CALCULATE | Must align with project.required_skills + task_type | Python,Django; Figma,UI/UX |
| required_role | string | 🧮 CALCULATE | Consistent with task_type + required_skills | Developer, Designer, Analyst |
| required_seniority | string | 🧮 CALCULATE | Based on complexity (Complex → Senior) | Junior, Mid, Senior |

### Assignment & Status
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| assigned_to | string | 🧮 CALCULATE | FK to employees (null if unassigned) | EMP001, null |
| assigned_date | date | 🧮 CALCULATE | >= project.start_date | 2024-01-10, null |
| status | string | 🎲 GENERATE | Current state | Not Started, In Progress, In Review, Completed, Blocked |
| completion_percentage | float (0-100) | 🧮 CALCULATE | From status (Completed=100, In Review=75-90, In Progress=10-74) | 0.0, 35.0, 100.0 |

### Timeline & Deadlines
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| start_date | date | 🧮 CALCULATE | >= project.start_date, respects dependent_task_ids | 2024-01-15 |
| due_date | date | 🧮 CALCULATE | start_date + estimated_hours/8 + buffer_days | 2024-01-30 |
| actual_completion_date | date | 🧮 CALCULATE | Null if not Completed; >= start_date | 2024-01-28, null |
| is_overdue | boolean | 🧮 CALCULATE | due_date < today AND status != Completed | True, False |
| days_overdue | integer | 🧮 CALCULATE | today - due_date if overdue, else negative (days early) | -2, 0, 5, 15 |
| buffer_days | integer | 🎲 GENERATE | Planned buffer | 1, 2, 5 |

### Dependencies
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| dependent_task_ids | string (comma-sep) | 🎲 GENERATE | Tasks that must finish first (nullable) | TSK003,TSK007, null |
| blocking_task_ids | string (comma-sep) | 🧮 CALCULATE | Inverse of dependent_task_ids | TSK015, null |
| parent_task_id | string | 🎲 GENERATE | Parent task if subtask (nullable) | TSK001, null |

### Quality & Performance
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| quality_score | integer (0-10) | 🎲 GENERATE | Human reviewer quality rating (null if incomplete) | 6, 8, null |
| rework_required | boolean | 🎲 GENERATE | Whether revision was needed | True, False |
| rework_count | integer | 🧮 CALCULATE | 0 if rework_required=False; 1-3 if True | 0, 1, 2, 3 |
| review_rating | integer (0-10) | 🎲 GENERATE | Human reviewer assessment (null if incomplete) | 7, 8, null |
| stakeholder_satisfaction | integer (0-10) | 🎲 GENERATE | Human client rating (null if incomplete) | 6, 8, null |

### Risk & Impact
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| risk_level | string | 🧮 CALCULATE | From complexity + is_overdue + blocking_task_ids count | Low, Medium, High |
| business_impact | string | 🎲 GENERATE | Business importance | Low, Medium, High, Critical |
| delay_risk_score | float (0-100) | 🧮 CALCULATE | From days_overdue + blocked_tasks + deadline_pressure | 15.0, 45.0, 78.0 |

### Collaboration
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| requires_collaboration | boolean | 🧮 CALCULATE | team_size_required > 1 | True, False |
| team_size_required | integer | 🧮 CALCULATE | From complexity + task_type | 1, 2, 3, 5 |

### Timestamps
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| created_at | datetime | 🧮 CALCULATE | Same as assigned_date or project.start_date | 2024-01-01 09:00:00 |
| last_updated | datetime | 🎲 GENERATE | Recent timestamp | 2024-01-15 14:30:00 |

---

## 4. TASK_ASSIGNMENTS TABLE (task_assignments.csv)

### Assignment Identification
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| assignment_id | string | 🎲 GENERATE | Unique identifier | ASG001, ASG002 |
| task_id | string | 🧮 CALCULATE | FK to tasks | TSK001, TSK023 |
| employee_id | string | 🧮 CALCULATE | FK to employees | EMP001, EMP015 |
| project_id | string | 🧮 CALCULATE | FK to projects (via task) | PRJ001, PRJ005 |

### Assignment Details
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| assignment_date | date | 🧮 CALCULATE | >= task.start_date and >= project.start_date | 2024-01-10 |
| assignment_method | string | 🎲 GENERATE | How assigned | Manual, AI-Recommended, Auto-Scheduled |
| assigned_by | string | 🧮 CALCULATE | FK to employees (manager/lead role) | EMP005, SYSTEM |
| acceptance_status | string | 🎲 GENERATE | Employee response | Pending, Accepted, Declined, Renegotiated |
| acceptance_date | date | 🧮 CALCULATE | assignment_date + 0-2 days if Accepted; null if Pending | 2024-01-11, null |

### Suitability Scores
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| skill_match_score | float (0-100) | 🧮 CALCULATE | Overlap of employee.primary_skills vs task.required_skills | 45.0, 75.0, 92.0 |
| availability_match_score | float (0-100) | 🧮 CALCULATE | From employee.is_available + current_project_count + weekly_capacity_hours | 60.0, 85.0, 100.0 |
| workload_compatibility_score | float (0-100) | 🧮 CALCULATE | From workload_history intensity vs remaining capacity | 50.0, 75.0, 90.0 |
| experience_match_score | float (0-100) | 🧮 CALCULATE | employee.years_of_experience vs task.required_seniority | 55.0, 80.0, 95.0 |
| overall_suitability_score | float (0-100) | 🧮 CALCULATE | Weighted avg of above 4 scores | 60.0, 78.0, 93.0 |
| team_compatibility_score | float (0-100) | 🧮 CALCULATE | From employee.past_team_members overlap + collaboration_score | 65.0, 82.0, 94.0 |

### Assignment Outcome
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| assignment_success | boolean | 🧮 CALCULATE | True if completion_status=Completed AND on_time_completion=True | True, False, null |
| completion_status | string | 🎲 GENERATE | Final status | Completed, Reassigned, Cancelled, In Progress |
| reassignment_count | integer | 🧮 CALCULATE | Count of prior assignments for same task_id | 0, 1, 2 |
| reassignment_reason | string | 🧮 CALCULATE | Null if reassignment_count=0; else Overload/Skill Mismatch/Leave | Overload, null |

### Performance Metrics
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| quality_rating | integer (0-10) | 🎲 GENERATE | Human quality rating for this assignment (null if incomplete) | 6, 8, null |
| on_time_completion | boolean | 🧮 CALCULATE | actual_completion_date <= task.due_date | True, False, null |
| efficiency_score | float (0-100) | 🧮 CALCULATE | task.estimated_hours / task.actual_hours × 100 (null if incomplete) | 80.0, 100.0, 120.0 |

### Feedback
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| assignment_satisfaction | integer (0-10) | 🧮 CALCULATE | Correlated with skill_match_score + workload_compatibility_score | 5, 7, 9 |

### Timestamps
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| created_at | datetime | 🧮 CALCULATE | Same as assignment_date (datetime) | 2024-01-10 09:00:00 |
| last_updated | datetime | 🎲 GENERATE | Recent timestamp | 2024-01-15 14:30:00 |

---

## 5. TEAM_FORMATIONS TABLE (team_formations.csv)

### Team Identification
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| team_id | string | 🎲 GENERATE | Unique identifier | TEAM001, TEAM002 |
| team_name | string | 🎲 GENERATE | Team name | Alpha Squad, Backend Crew |
| project_id | string | 🧮 CALCULATE | FK to projects | PRJ001, PRJ005 |
| formation_date | date | 🧮 CALCULATE | >= project.start_date | 2024-01-05 |
| formation_method | string | 🎲 GENERATE | How formed | Manual, AI-Recommended, Hybrid |

### Team Composition
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| team_lead_id | string | 🧮 CALCULATE | FK to employees with Senior/Lead seniority | EMP005, EMP012 |
| member_ids | string (comma-sep) | 🧮 CALCULATE | FK list to employees | EMP001,EMP003,EMP007 |
| team_size | integer | 🧮 CALCULATE | Count of member_ids | 3, 5, 7, 10 |
| role_distribution | string (JSON) | 🧮 CALCULATE | Derived from member_ids → employee.role | {"Developer":3,"Designer":1} |
| seniority_mix | string (JSON) | 🧮 CALCULATE | Derived from member_ids → employee.seniority_level | {"Junior":1,"Mid":2,"Senior":1} |

### Team Characteristics
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| skill_diversity_score | float (0-100) | 🧮 CALCULATE | Unique skills across members / total possible skills | 45.0, 70.0, 90.0 |
| experience_balance_score | float (0-100) | 🧮 CALCULATE | From variance of members' years_of_experience | 55.0, 75.0, 85.0 |
| collaborative_history_score | float (0-100) | 🧮 CALCULATE | From past_team_members overlap weighted by prior outcomes | 40.0, 70.0, 95.0 |
| workload_balance_score | float (0-100) | 🧮 CALCULATE | From variance of members' workload_vs_capacity | 50.0, 75.0, 90.0 |

### Performance & Success Metrics
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| predicted_success_rate | float (0-100) | 🧮 CALCULATE | From skill_diversity + experience_balance + collaborative_history + workload_balance | 55.0, 75.0, 90.0 |
| actual_performance_score | float (0-100) | 🧮 CALCULATE | Null if ongoing; weighted avg of quality_rating + met_deadline + budget_adherence + stakeholder_satisfaction | 65.0, 82.0, null |
| collaboration_effectiveness | float (0-100) | 🧮 CALCULATE | From avg member collaboration_score + team_feedback_score | 60.0, 78.0, 92.0 |

### Project Outcomes
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| project_completed | boolean | 🧮 CALCULATE | From project.current_status = Completed | True, False, null |
| completion_time_days | float | 🧮 CALCULATE | project.actual_end_date - formation_date (null if ongoing) | 30.0, 60.0, null |
| met_deadline | boolean | 🧮 CALCULATE | actual_end_date <= project.planned_end_date | True, False, null |
| quality_rating | integer (0-10) | 🧮 CALCULATE | Avg of task quality_scores for this team (null if ongoing) | 6, 8, null |
| budget_adherence | float (%) | 🧮 CALCULATE | project.consumed_resources / project.budget × 100 | 85.0, 100.0, 115.0, null |
| stakeholder_satisfaction | integer (0-10) | 🎲 GENERATE | Human survey rating post-project (null if ongoing) | 6, 8, 9, null |

### Optimization Indicators
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| resource_utilization | float (0-100) | 🧮 CALCULATE | consumed_resources / allocated_resources × 100 | 70.0, 85.0, 95.0 |
| skill_utilization_rate | float (0-100) | 🧮 CALCULATE | Overlap of member skills vs project.required_skills | 65.0, 80.0, 92.0 |

### Feedback
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| team_feedback_score | integer (0-10) | 🎲 GENERATE | Human aggregated team feedback rating (null if ongoing) | 5, 7, 9, null |

### Status & Lifecycle
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| team_status | string | 🧮 CALCULATE | From project.current_status | Active, Completed, Disbanded, On Hold |
| dissolution_date | date | 🧮 CALCULATE | Same as project.actual_end_date (null if ongoing) | 2024-06-30, null |
| dissolution_reason | string | 🧮 CALCULATE | From project outcome | Project Complete, Reorganization, null |

### Timestamps
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| created_at | datetime | 🧮 CALCULATE | Same as formation_date | 2024-01-05 09:00:00 |
| last_updated | datetime | 🎲 GENERATE | Recent timestamp | 2024-01-20 11:30:00 |

---

## 6. SCHEDULES TABLE (schedules.csv)

### Schedule Identification
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| schedule_id | string | 🎲 GENERATE | Unique identifier | SCH001, SCH002 |
| employee_id | string | 🧮 CALCULATE | FK to employees | EMP001, EMP023 |
| event_type | string | 🎲 GENERATE | Type of event | Task, Meeting, Focus Time, Break, Training, Leave |
| related_id | string | 🧮 CALCULATE | FK to task/meeting (null if not applicable) | TSK001, null |
| event_title | string | 🎲 GENERATE | Event description | Sprint Planning, Code Review, Focus Block |

### Timing Details
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| date | date | 🎲 GENERATE | Event date | 2024-01-15 |
| start_time | time | 🎲 GENERATE | Start time | 09:00:00, 14:30:00 |
| end_time | time | 🧮 CALCULATE | start_time + duration_minutes | 10:00:00, 16:00:00 |
| duration_minutes | float | 🎲 GENERATE | Event duration | 30, 60, 90, 120 |

### Priority & Flexibility
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| priority | string | 🎲 GENERATE | Event importance | Low, Medium, High, Critical |
| is_flexible | boolean | 🎲 GENERATE | Can be rescheduled | True, False |
| buffer_minutes | float | 🎲 GENERATE | Buffer time before/after event | 0, 15, 30, 60 |

### Conflicts & Optimization
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| conflict_with_ids | string (comma-sep) | 🧮 CALCULATE | SCH IDs overlapping in time for same employee (null if none) | SCH005,SCH012, null |
| optimization_score | float (0-100) | 🧮 CALCULATE | From conflict presence + preferred_work_hours alignment + workload_intensity | 45.0, 70.0, 90.0 |
| recommended_time | time | 🧮 CALCULATE | M3 output — optimal slot avoiding conflicts + preferred hours | 10:00:00, null |

### Attendance & Outcome
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| attendance_status | string | 🎲 GENERATE | Outcome of scheduled event | Scheduled, Completed, Missed, Rescheduled, Cancelled |
| actual_start_time | time | 🧮 CALCULATE | Null if not Completed; slight variance from start_time | 09:05:00, null |
| actual_end_time | time | 🧮 CALCULATE | actual_start_time + actual_duration_minutes | 10:10:00, null |
| actual_duration_minutes | float | 🧮 CALCULATE | Null if not Completed; variance from duration_minutes | 35, 65, null |
| productivity_during | float (0-100) | 🧮 CALCULATE | From event_type + workload_intensity at that time (null if not Completed) | 55.0, 70.0, null |

### Collaboration Details
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| involves_team | boolean | 🧮 CALCULATE | True if participant_count > 1 | True, False |
| participant_ids | string (comma-sep) | 🎲 GENERATE | Other attendees (null if solo) | EMP002,EMP007, null |
| participant_count | float | 🧮 CALCULATE | Count of participant_ids + 1 (self) | 1, 3, 5, 10 |
| meeting_type | string | 🧮 CALCULATE | Null if event_type != Meeting | One-on-One, Team Meeting, null |

### Location & Mode
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| location | string | 🎲 GENERATE | Where event occurs | Office, Home, Conference Room A, Virtual |
| is_remote | boolean | 🧮 CALCULATE | From employee.remote_work_status + location | True, False |
| meeting_link | string | 🧮 CALCULATE | Null if is_remote=False; URL if True | https://zoom.us/j/123456, null |

### Timestamps
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| created_at | datetime | 🧮 CALCULATE | Same as date (datetime format) | 2024-01-10 09:00:00 |
| last_updated | datetime | 🎲 GENERATE | Recent timestamp | 2024-01-12 14:30:00 |

---

## 7. WORKLOAD_HISTORY TABLE (workload_history.csv)

### Record Identification
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| record_id | string | 🎲 GENERATE | Unique identifier | WH001, WH002 |
| employee_id | string | 🧮 CALCULATE | FK to employees | EMP001, EMP002 |
| date | date | 🎲 GENERATE | Date of record | 2024-01-15 |
| week_number | float | 🧮 CALCULATE | ISO week number from date | 1, 2, ..., 52 |

### Work Hours & Activity
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| total_hours_worked | float | 🎲 GENERATE | Total hours that day | 6.5, 8.0, 10.5, 12.0 |
| overtime_hours | float | 🧮 CALCULATE | max(0, total_hours_worked - 8) | 0.0, 1.5, 3.0, 4.5 |
| billable_hours | float | 🧮 CALCULATE | total_hours_worked × billable_ratio (based on employment_type) | 5.0, 7.0, 8.0 |
| non_billable_hours | float | 🧮 CALCULATE | total_hours_worked - billable_hours | 1.0, 2.0, 3.0 |
| meeting_hours | float | 🧮 CALCULATE | Sum of meeting durations from schedules that day / 60 | 1.0, 2.5, 4.0 |
| focused_work_hours | float | 🧮 CALCULATE | total_hours_worked - meeting_hours - break_time_minutes/60 | 3.0, 5.0, 6.5 |
| context_switching_count | integer | 🎲 GENERATE | Number of task switches that day | 5, 10, 15, 25 |

### Task & Project Load
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| active_tasks_count | integer | 🧮 CALCULATE | Count of In Progress tasks assigned to employee that day | 2, 3, 5, 8 |
| active_projects_count | integer | 🧮 CALCULATE | Count of distinct projects from active tasks | 1, 2, 3 |
| tasks_completed | integer | 🧮 CALCULATE | Count of tasks moved to Completed that day | 0, 1, 2, 3 |
| tasks_started | integer | 🧮 CALCULATE | Count of tasks moved to In Progress that day | 0, 1, 2, 3 |
| blocked_tasks_count | integer | 🧮 CALCULATE | Count of Blocked tasks assigned to employee | 0, 1, 2 |
| high_priority_tasks | integer | 🧮 CALCULATE | Count of High/Critical priority active tasks | 0, 1, 2, 3 |

### Workload Intensity
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| workload_intensity_score | float (0-100) | 🧮 CALCULATE | From active_tasks_count + overtime_hours + high_priority_tasks | 35.0, 65.0, 85.0 |
| deadline_pressure_score | float (0-100) | 🧮 CALCULATE | From high_priority_tasks + blocked_tasks + proximity to due dates | 25.0, 50.0, 75.0 |

### Productivity Indicators
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| productivity_score | float (0-100) | 🧮 CALCULATE | From tasks_completed + quality_of_work + efficiency_ratio normalized | 45.0, 70.0, 85.0 |
| efficiency_ratio | float (0-100) | 🧮 CALCULATE | tasks_completed / total_hours_worked normalized against baseline | 60.0, 85.0, 100.0, 120.0 |
| task_completion_rate | float (0-100) | 🧮 CALCULATE | tasks_completed / (tasks_completed + active_tasks_count) × 100 | 50.0, 75.0, 100.0 |
| quality_of_work | integer (0-10) | 🧮 CALCULATE | Avg of human quality_score of tasks completed that day | 6, 7, 9 |
| rework_time_hours | float | 🧮 CALCULATE | Hours spent on rework tasks that day | 0.0, 0.5, 1.5, 3.0 |

### Collaboration
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| meetings_attended | integer | 🧮 CALCULATE | Count of Completed meeting schedules that day | 1, 2, 3, 5 |
| collaboration_hours | float | 🧮 CALCULATE | Sum of duration for events where involves_team=True | 1.0, 3.0, 5.0 |

### Stress & Well-being
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| stress_level | string | 🧮 CALCULATE | Bucketed from workload_intensity + deadline_pressure + overtime | Low, Medium, High, Very High |
| weekend_work_indicator | boolean | 🧮 CALCULATE | True if date is Saturday or Sunday | True, False |
| break_time_minutes | float | 🎲 GENERATE | Rest/break duration that day | 15.0, 30.0, 60.0 |

### Performance Trends
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| productivity_vs_avg | float (%) | 🧮 CALCULATE | (productivity_score - rolling avg) / rolling avg × 100 | -15.0, 0.0, 10.0, 25.0 |
| workload_vs_capacity | float (%) | 🧮 CALCULATE | total_hours_worked / (weekly_capacity_hours / 5) × 100 | 60.0, 85.0, 100.0, 120.0 |
| burnout_risk_today | float (0-100) | 🧮 CALCULATE | From stress_level + overtime_hours + workload_vs_capacity + deadline_pressure_score | 10.0, 35.0, 65.0, 85.0 |

### Context
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| special_circumstances | string | 🎲 GENERATE | Notable context (nullable) | Holiday, Training Day, Client Visit, null |
| out_of_office | boolean | 🎲 GENERATE | Was on leave that day | True, False |
| worked_from | string | 🧮 CALCULATE | From employee.remote_work_status + schedules.location | Office, Home, Remote, Client Site |

### Timestamps
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| created_at | datetime | 🧮 CALCULATE | Same as date (datetime format) | 2024-01-15 09:00:00 |

---

## 8. PERFORMANCE_REVIEWS TABLE (performance_reviews.csv)

### Review Identification
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| review_id | string | 🎲 GENERATE | Unique identifier | REV001, REV002 |
| employee_id | string | 🧮 CALCULATE | FK to employees | EMP001, EMP023 |
| reviewer_id | string | 🧮 CALCULATE | FK to employees (manager/lead) | EMP005, EMP012 |
| review_period_start | date | 🎲 GENERATE | Period start | 2023-07-01 |
| review_period_end | date | 🧮 CALCULATE | review_period_start + period length based on review_type | 2023-12-31 |
| review_date | date | 🧮 CALCULATE | Slightly after review_period_end | 2024-01-15 |
| review_type | string | 🎲 GENERATE | Type | Annual, Quarterly, Project-based, Probationary |

### Performance Scores
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| overall_performance_score | float (0-100) | 🧮 CALCULATE | Weighted avg of all score components | 55.0, 72.0, 88.0 |
| normalized_performance_score | float (0-100) | 🧮 CALCULATE | Peer-adjusted overall_performance_score | 52.0, 70.0, 86.0 |
| technical_competence_score | integer (0-10) | 🎲 GENERATE | Human reviewer rating of technical skills | 5, 7, 9 |
| domain_knowledge_score | integer (0-10) | 🎲 GENERATE | Human reviewer rating of domain expertise | 6, 7, 9 |
| problem_solving_score | integer (0-10) | 🎲 GENERATE | Human reviewer rating of problem-solving | 6, 8, 9 |
| quality_of_work_score | integer (0-10) | 🎲 GENERATE | Human reviewer rating of work quality | 6, 8, 9 |
| productivity_score | integer (0-10) | 🎲 GENERATE | Human reviewer rating of output quantity | 6, 7, 9 |

### Behavioral & Soft Skills
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| communication_score | integer (0-10) | 🎲 GENERATE | Human reviewer rating | 6, 7, 9 |
| collaboration_score | integer (0-10) | 🎲 GENERATE | Human reviewer rating | 6, 8, 9 |
| leadership_score | integer (0-10) | 🎲 GENERATE | Human reviewer rating | 5, 7, 9 |
| initiative_score | integer (0-10) | 🎲 GENERATE | Human reviewer rating of proactiveness | 5, 7, 8 |
| time_management_score | integer (0-10) | 🎲 GENERATE | Human reviewer rating | 6, 7, 9 |

### Quantitative Metrics
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| tasks_completed | integer | 🧮 CALCULATE | Count from task_assignments in review period | 25, 50, 100 |
| projects_completed | integer | 🧮 CALCULATE | Count from projects in review period | 2, 3, 5 |
| average_task_quality | float (0-100) | 🧮 CALCULATE | Mean quality_score of completed tasks in period | 70.0, 80.0, 90.0 |
| on_time_delivery_rate | float (0-100) | 🧮 CALCULATE | % of tasks completed on time in period | 65.0, 85.0, 95.0 |
| productivity_vs_peers | float (%) | 🧮 CALCULATE | Employee productivity vs department avg in period | -10.0, 0.0, 15.0 |
| total_hours_worked | float | 🧮 CALCULATE | Sum from workload_history in review period | 800.0, 1000.0, 1200.0 |
| overtime_hours | float | 🧮 CALCULATE | Sum from workload_history.overtime_hours in period | 0.0, 20.0, 50.0 |

### Narrative Fields (RAG Content)
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| strengths | string | 🎲 GENERATE | Key strengths text | "Technical expertise, Problem solving" |
| achievements | string | 🎲 GENERATE | Notable accomplishments | "Led successful project, Mentored 3 juniors" |
| weaknesses | string | 🎲 GENERATE | Development areas | "Time management, Documentation" |
| improvement_areas | string | 🎲 GENERATE | Focus areas | "Leadership, Technical depth" |
| reviewer_comments | string | 🎲 GENERATE | Manager qualitative feedback | "Strong performer with leadership potential..." |
| recommended_actions | string | 🎲 GENERATE | Specific next steps | "Complete AWS cert, Lead a team project" |

### Feedback & Recommendations
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| self_assessment_score | integer (0-10) | 🎲 GENERATE | Employee's self-rating | 6, 7, 8 |
| peer_feedback_summary | string | 🎲 GENERATE | Aggregated peer input | "Great collaborator, helpful mentor..." |
| promotion_recommended | boolean | 🧮 CALCULATE | From overall_performance_score + leadership_score threshold | True, False |
| salary_increase_percentage | float | 🧮 CALCULATE | From normalized_performance_score + productivity_vs_peers | 0.0, 3.0, 5.0, 10.0 |
| salary_adjustment_recommendation | float | 🧮 CALCULATE | Absolute salary adjustment from salary_increase_percentage | 0.0, 2500.0, 5000.0 |
| training_recommendations | string | 🧮 CALCULATE | From improvement_areas + skill gaps | "Leadership Training, AWS Certification" |
| performance_rating | string | 🧮 CALCULATE | Bucketed from overall_performance_score | Needs Improvement, Meets Expectations, Exceeds Expectations |
| promotion_readiness | string | 🧮 CALCULATE | From leadership_score + performance trend | Not Ready, Ready in 6-12 months, Ready Now |

### Timestamps
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| created_at | datetime | 🧮 CALCULATE | Same as review_date | 2024-01-15 09:00:00 |
| last_updated | datetime | 🎲 GENERATE | Recent timestamp | 2024-01-15 14:30:00 |

---

## 9. BURNOUT_INDICATORS TABLE (burnout_indicators.csv)

### Record Identification
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| indicator_id | string | 🎲 GENERATE | Unique identifier | BI001, BI002 |
| employee_id | string | 🧮 CALCULATE | FK to employees | EMP001, EMP023 |
| assessment_date | date | 🎲 GENERATE | When assessed | 2024-01-15 |
| assessment_type | string | 🎲 GENERATE | Frequency | Daily, Weekly, Monthly, On-Demand |

### Core Burnout Dimensions (Maslach Framework — self-reported)
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| overall_burnout_risk | float (0-100) | 🧮 CALCULATE | Weighted avg of exhaustion + depersonalization + reduced_accomplishment | 15.0, 45.0, 75.0 |
| emotional_exhaustion_score | integer (0-10) | 🎲 GENERATE | Human self-report: feeling emotionally drained | 2, 5, 8 |
| depersonalization_score | integer (0-10) | 🎲 GENERATE | Human self-report: feeling detached/cynical | 1, 4, 7 |
| reduced_accomplishment_score | integer (0-10) | 🎲 GENERATE | Human self-report: low sense of achievement | 2, 5, 8 |
| burnout_category | string | 🧮 CALCULATE | Bucketed from overall_burnout_risk | Low Risk, Moderate Risk, High Risk, Critical |

### Work Environment Factors (self-reported)
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| role_ambiguity | integer (0-10) | 🎲 GENERATE | Human self-report: unclear responsibilities | 1, 4, 7 |
| job_control | integer (0-10) | 🎲 GENERATE | Human self-report: autonomy level | 3, 6, 9 |

### Behavioral Indicators (calculated from other tables)
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| late_hours_frequency | integer | 🧮 CALCULATE | Days worked past standard hours (last 30 days) from workload_history | 0, 5, 10, 20 |
| weekend_work_frequency | integer | 🧮 CALCULATE | Weekends worked (last 8 weeks) from workload_history.weekend_work_indicator | 0, 2, 4, 8 |
| missed_breaks_count | integer | 🧮 CALCULATE | Days with break_time_minutes < 15 (last week) from workload_history | 0, 2, 5, 10 |
| vacation_days_unused | integer | 🧮 CALCULATE | From employee.days_since_last_leave vs standard leave entitlement | 0, 5, 10, 20 |
| sick_days_taken | integer | 🧮 CALCULATE | Count of out_of_office=True days (last 6 months) from workload_history | 0, 2, 5, 12 |
| absence_rate | float (%) | 🧮 CALCULATE | sick_days_taken / total_working_days × 100 | 0.0, 2.5, 5.0, 10.0 |

### Support Factors (self-reported)
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| job_satisfaction | integer (0-10) | 🎲 GENERATE | Human self-report: overall job satisfaction | 4, 6, 8 |
| social_support_score | integer (0-10) | 🎲 GENERATE | Human self-report: support from colleagues | 4, 6, 9 |
| manager_support_score | integer (0-10) | 🎲 GENERATE | Human self-report: support from manager | 4, 7, 9 |
| mental_health_support_needed | boolean | 🎲 GENERATE | Self-reported need for professional support | True, False |

### Predictive Indicators
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| burnout_trend | string | 🧮 CALCULATE | Trajectory from rolling overall_burnout_risk | Decreasing, Stable, Increasing, Rapidly Increasing |
| predicted_burnout_30days | float (0-100) | 🧮 CALCULATE | M1 output — 30-day risk projection | 20.0, 50.0, 80.0 |
| predicted_burnout_90days | float (0-100) | 🧮 CALCULATE | M1 output — 90-day risk projection | 25.0, 55.0, 85.0 |
| intervention_urgency | string | 🧮 CALCULATE | Bucketed from predicted_burnout_30days | None, Monitor, Recommend, Immediate |

### Intervention History
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| interventions_received | integer | 🎲 GENERATE | Number of interventions received | 0, 1, 2, 3 |
| last_intervention_date | date | 🧮 CALCULATE | Null if interventions_received=0 | 2024-01-05, null |
| intervention_effectiveness | integer (0-10) | 🎲 GENERATE | Human rating of intervention quality (null if none received) | 4, 6, 9, null |

### Timestamps
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| created_at | datetime | 🧮 CALCULATE | Same as assessment_date | 2024-01-15 09:00:00 |
| last_updated | datetime | 🎲 GENERATE | Recent timestamp | 2024-01-15 09:00:00 |

---

## 10. FEEDBACK TABLE (feedback.csv)

### Feedback Identification
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| feedback_id | string | 🎲 GENERATE | Unique identifier | FDB001, FDB002 |
| feedback_type | string | 🎲 GENERATE | Type | Task Completion, Project Review, Peer Feedback, Self Assessment |
| provider_id | string | 🧮 CALCULATE | FK to employees (who gave feedback) | EMP005, EMP012 |
| recipient_id | string | 🧮 CALCULATE | FK to employees (who receives feedback) | EMP001, EMP023 |
| feedback_date | date | 🧮 CALCULATE | >= task/project completion date | 2024-01-15 |

### Context & Subject
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| related_task_id | string | 🧮 CALCULATE | FK to tasks (null if project/team level) | TSK001, null |
| related_project_id | string | 🧮 CALCULATE | FK to projects | PRJ001, null |
| related_team_id | string | 🧮 CALCULATE | FK to team_formations (null if individual) | TEAM001, null |
| feedback_category | string | 🎲 GENERATE | Area of feedback | Technical Skills, Communication, Leadership, Quality, Teamwork |

### Feedback Content (RAG Source)
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| feedback_text | string | 🎲 GENERATE | Detailed feedback narrative | "Great attention to detail..." |
| positive_aspects | string (comma-sep) | 🎲 GENERATE | What went well | "Clear communication, On-time delivery" |
| improvement_areas | string (comma-sep) | 🎲 GENERATE | What needs work | "Documentation, Testing coverage" |
| specific_suggestions | string | 🎲 GENERATE | Actionable recommendations | "Add more unit tests, Document API endpoints" |
| action_items | string (comma-sep) | 🎲 GENERATE | Concrete actions for recipient | "Complete training, Review documentation" |

### Ratings (human-given)
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| overall_rating | integer (0-10) | 🎲 GENERATE | Human overall assessment | 5, 7, 8, 9 |
| quality_rating | integer (0-10) | 🎲 GENERATE | Human work quality rating | 6, 7, 9 |
| timeliness_rating | integer (0-10) | 🎲 GENERATE | Human on-time performance rating | 5, 7, 9 |
| collaboration_rating | integer (0-10) | 🎲 GENERATE | Human teamwork rating | 6, 8, 9 |
| communication_rating | integer (0-10) | 🎲 GENERATE | Human communication rating | 6, 7, 9 |

### Impact & Follow-up
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| priority_level | string | 🎲 GENERATE | Urgency of actions | Low, Medium, High |
| follow_up_date | date | 🧮 CALCULATE | feedback_date + 30 days if priority=High, else null | 2024-02-15, null |

### Recipient Response
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| acknowledged | boolean | 🎲 GENERATE | Recipient viewed feedback | True, False |
| acknowledged_date | date | 🧮 CALCULATE | Null if acknowledged=False; feedback_date + 0-5 days | 2024-01-16, null |
| recipient_response | string | 🎲 GENERATE | Recipient's comment (nullable) | "Thank you, will work on documentation", null |
| response_date | date | 🧮 CALCULATE | Null if recipient_response=null | 2024-01-17, null |

### Access Control
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| visibility | string | 🎲 GENERATE | Who can see this feedback | Private, Team, Manager Only, Public |

### Timestamps
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| created_at | datetime | 🧮 CALCULATE | Same as feedback_date | 2024-01-15 09:00:00 |
| last_updated | datetime | 🎲 GENERATE | Recent timestamp | 2024-01-16 14:30:00 |

---

## Generation Order (Dependency Chain)

```
1. employees              — no dependencies
2. projects               — depends on employees
3. tasks                  — depends on projects
4. task_assignments       — depends on tasks + employees + projects
5. schedules              — depends on employees + tasks
6. workload_history       — depends on employees + tasks + schedules
7. team_formations        — depends on projects + employees + workload_history
8. feedback               — depends on employees + tasks + projects + team_formations
9. performance_reviews    — depends on employees + task_assignments + workload_history
10. burnout_indicators    — depends on employees + workload_history
```

---

## Notes
- All FK columns must reference existing IDs from their parent table before generation
- CALCULATE columns must never be independently randomized — recompute if source values change
- Null values are valid where indicated (e.g., incomplete tasks, ongoing projects)
- workload_history: one record per employee per working day
- burnout_indicators: one record per employee per assessment_type period
- Score scale rule: 0-100 float = calculated/computed; 0-10 integer = human-given rating
