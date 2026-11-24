# Employee Performance Analyzer - Dataset Schema Specification

## Overview
This document specifies all CSV files needed for your synthetic dataset generation, including column names, data types, descriptions, and sample value ranges.

---

## 1. EMPLOYEES TABLE (employees.csv)

### Core Identity Columns
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| employee_id | string | Unique identifier (e.g., "EMP001") | EMP001, EMP002, ... |
| first_name | string | Employee first name | John, Sarah, Raj, Maria |
| last_name | string | Employee last name | Smith, Johnson, Kumar, Garcia |
| email | string | Work email | john.smith@company.com |
| department | string | Department name | Engineering, Sales, Marketing, HR, Finance, Design, Operations |
| role | string | Job role/title | Software Engineer, Manager, Designer, Analyst, Developer, Team Lead, Senior Engineer |
| seniority_level | string | Experience level | Junior, Mid, Senior, Lead, Principal |
| employment_type | string | Employment status | Full-time, Part-time, Contract |
| hire_date | date (YYYY-MM-DD) | Date employee was hired | 2020-01-15, 2022-06-30 |
| years_of_experience | float | Total years of experience | 0.5, 2.5, 5.0, 10.5 |
| current_salary | integer | Annual salary in currency | 50000, 75000, 120000 |

### Skills & Competencies
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| primary_skills | string (comma-separated) | Main technical/domain skills | Python,Java,SQL; Marketing,Analytics; Design,Figma |
| secondary_skills | string (comma-separated) | Additional skills | Communication,Leadership; Excel,PowerPoint |
| certifications | string (comma-separated) | Professional certifications | AWS Certified,PMP; Scrum Master,Google Analytics |
| languages_known | string (comma-separated) | Languages spoken | English,Spanish,French |
| technical_proficiency_score | float | Overall technical skill rating (0-10) | 3.5, 7.8, 9.2 |
| domain_expertise_score | float | Domain knowledge rating (0-10) | 4.2, 6.5, 8.9 |

### Availability & Capacity
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| weekly_capacity_hours | float | Max work hours per week | 40.0, 35.0, 20.0 |
| is_available | boolean | Currently available for assignment | True, False |
| current_project_count | integer | Number of active projects | 0, 1, 2, 3 |
| preferred_work_hours | string | Preferred working schedule | 9am-5pm, 10am-6pm, Flexible |
| timezone | string | Work timezone | UTC, EST, PST, IST |
| remote_work_status | string | Work location preference | Remote, Hybrid, Office |

### Performance & Well-being Indicators
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| historical_performance_score | float | Past performance average (0-100) | 45.5, 78.3, 92.1 |
| productivity_trend | string | Recent productivity pattern | Increasing, Stable, Decreasing |
| average_task_completion_rate | float | % of tasks completed on time (0-100) | 65.5, 85.0, 95.2 |
| collaboration_score | float | Team collaboration rating (0-10) | 5.5, 7.8, 9.2 |
| communication_effectiveness | float | Communication quality (0-10) | 6.0, 8.5, 9.0 |
| leadership_potential | float | Leadership capability rating (0-10) | 4.0, 6.5, 9.0 |
| stress_level | string | Current stress indicator | Low, Medium, High |
| burnout_risk_score | float | Predicted burnout risk (0-100) | 10.5, 45.2, 78.9 |
| recent_overtime_hours | float | Overtime hours in last month | 0.0, 5.5, 15.0, 25.0 |
| days_since_last_leave | integer | Days since last vacation | 10, 45, 120, 365 |
| work_life_balance_score | float | Self-reported balance (0-10) | 4.5, 6.8, 9.0 |

### Team & Collaboration History
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| preferred_team_size | string | Ideal team composition | Small (2-4), Medium (5-8), Large (9+) |
| past_team_members | string (comma-separated) | IDs of previous teammates | EMP002,EMP005,EMP012 |
| successful_project_count | integer | Number of successful projects | 5, 12, 28 |
| failed_project_count | integer | Number of failed projects | 0, 1, 3 |
| cross_functional_experience | boolean | Has worked across departments | True, False |
| mentoring_experience | boolean | Has mentored others | True, False |

### Timestamps
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| last_updated | datetime (YYYY-MM-DD HH:MM:SS) | Last record update | 2024-01-15 14:30:00 |
| created_at | datetime (YYYY-MM-DD HH:MM:SS) | Record creation time | 2023-06-01 09:00:00 |

---

## 2. TASKS TABLE (tasks.csv)

### Core Task Information
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| task_id | string | Unique task identifier | TSK001, TSK002, ... |
| task_name | string | Descriptive task name | Implement user authentication, Design landing page |
| task_description | string | Detailed description | Build OAuth2 authentication system with JWT |
| task_type | string | Category of task | Development, Design, Testing, Research, Documentation, Meeting |
| project_id | string | Associated project ID | PRJ001, PRJ002, ... |
| priority | string | Task urgency | Low, Medium, High, Critical |
| complexity | string | Task difficulty | Simple, Moderate, Complex, Very Complex |
| estimated_hours | float | Expected time to complete | 2.0, 8.0, 40.0, 80.0 |
| actual_hours | float | Actual time spent (null if incomplete) | 2.5, 10.0, 45.0, null |
| story_points | integer | Agile estimation points | 1, 2, 3, 5, 8, 13 |

### Skills & Requirements
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| required_skills | string (comma-separated) | Skills needed for task | Python,Django,PostgreSQL; Figma,UI/UX |
| required_role | string | Preferred employee role | Developer, Designer, Analyst, Manager |
| required_seniority | string | Minimum experience level | Junior, Mid, Senior |
| required_certifications | string (comma-separated) | Necessary certifications | AWS Certified,Security+; null |
| technical_complexity_score | float | Technical difficulty (0-10) | 3.5, 6.8, 9.5 |

### Assignment & Status
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| assigned_to | string | Current assignee ID | EMP001, EMP023, null |
| assigned_date | date (YYYY-MM-DD) | When task was assigned | 2024-01-10, null |
| status | string | Current task state | Not Started, In Progress, In Review, Completed, Blocked |
| completion_percentage | float | Progress completion (0-100) | 0.0, 35.0, 75.0, 100.0 |

### Timeline & Deadlines
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| start_date | date (YYYY-MM-DD) | Task start date | 2024-01-15 |
| due_date | date (YYYY-MM-DD) | Task deadline | 2024-01-30 |
| actual_completion_date | date (YYYY-MM-DD) | When completed (null if not done) | 2024-01-28, null |
| is_overdue | boolean | Past deadline flag | True, False |
| days_overdue | integer | Days past deadline (negative if early) | -2, 0, 5, 15 |
| buffer_days | integer | Planned buffer before deadline | 1, 2, 5 |

### Dependencies & Relationships
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| dependent_task_ids | string (comma-separated) | Tasks that must finish first | TSK003,TSK007 |
| blocking_task_ids | string (comma-separated) | Tasks blocked by this | TSK015,TSK022 |
| related_tasks | string (comma-separated) | Related/similar tasks | TSK004,TSK009 |
| parent_task_id | string | Parent task if this is subtask | TSK001, null |
| has_subtasks | boolean | Whether task has children | True, False |

### Performance & Quality Metrics
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| quality_score | float | Task quality rating (0-10, null if incomplete) | 6.5, 8.2, 9.8, null |
| rework_required | boolean | Needed revision | True, False |
| rework_count | integer | Number of times revised | 0, 1, 2, 3 |
| review_rating | float | Reviewer assessment (0-10) | 7.0, 8.5, 9.5, null |
| stakeholder_satisfaction | float | Client/stakeholder rating (0-10) | 6.0, 8.0, 10.0, null |

### Risk & Impact Indicators
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| risk_level | string | Potential risk assessment | Low, Medium, High |
| business_impact | string | Impact on business | Low, Medium, High, Critical |
| delay_risk_score | float | Probability of delay (0-100) | 15.0, 45.0, 78.0 |
| technical_debt_added | boolean | Creates technical debt | True, False |

### Collaboration Metrics
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| requires_collaboration | boolean | Needs multiple people | True, False |
| team_size_required | integer | Number of people needed | 1, 2, 3, 5 |
| communication_frequency | string | Update frequency needed | Daily, Weekly, As needed |
| meeting_hours_required | float | Estimated meeting time | 0.0, 2.0, 5.0, 10.0 |

### Timestamps
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| created_at | datetime (YYYY-MM-DD HH:MM:SS) | Task creation time | 2024-01-01 09:00:00 |
| last_updated | datetime (YYYY-MM-DD HH:MM:SS) | Last modification | 2024-01-15 14:30:00 |

---

## 3. PROJECTS TABLE (projects.csv)

### Core Project Information
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| project_id | string | Unique project identifier | PRJ001, PRJ002, ... |
| project_name | string | Project title | Mobile App Redesign, Q1 Marketing Campaign |
| project_description | string | Detailed description | Complete overhaul of mobile application UI/UX |
| project_type | string | Category | Product Development, Marketing, Internal, Research, Client Project |
| client_id | string | Client identifier (null for internal) | CLT001, null |
| department | string | Owning department | Engineering, Marketing, Sales, Design |
| priority | string | Project importance | Low, Medium, High, Critical |
| budget | float | Project budget in currency | 50000.0, 250000.0, 1000000.0 |
| complexity_level | string | Overall difficulty | Low, Medium, High, Very High |

### Timeline & Status
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| start_date | date (YYYY-MM-DD) | Project start date | 2024-01-01 |
| planned_end_date | date (YYYY-MM-DD) | Expected completion | 2024-06-30 |
| actual_end_date | date (YYYY-MM-DD) | Actual completion (null if ongoing) | 2024-06-28, null |
| current_status | string | Project state | Planning, Active, On Hold, Completed, Cancelled |
| completion_percentage | float | Overall progress (0-100) | 0.0, 45.0, 85.0, 100.0 |
| is_on_schedule | boolean | Meeting timeline | True, False |
| days_ahead_behind | integer | Schedule variance (negative = behind) | -10, 0, 5 |

### Team & Resources
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| project_manager_id | string | Manager's employee ID | EMP005 |
| team_member_ids | string (comma-separated) | All team member IDs | EMP001,EMP003,EMP007,EMP012 |
| team_size | integer | Number of team members | 3, 5, 10, 15 |
| required_skills | string (comma-separated) | Skills needed for project | Python,React,AWS; Marketing,Analytics |
| allocated_resources | float | Total person-hours allocated | 500.0, 2000.0, 5000.0 |
| consumed_resources | float | Person-hours used so far | 250.0, 1800.0, 5200.0 |

### Performance & Risk Metrics
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| success_probability | float | Predicted success rate (0-100) | 45.0, 75.0, 95.0 |
| delay_risk_score | float | Risk of timeline slip (0-100) | 15.0, 50.0, 85.0 |
| budget_overrun_risk | float | Risk of exceeding budget (0-100) | 20.0, 45.0, 70.0 |
| quality_risk_score | float | Risk of quality issues (0-100) | 10.0, 35.0, 60.0 |
| scope_creep_indicator | float | Unplanned growth measure (0-100) | 5.0, 25.0, 55.0 |
| stakeholder_satisfaction | float | Overall satisfaction (0-10) | 6.0, 8.0, 9.5 |

### Milestone Tracking
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| total_milestones | integer | Number of milestones | 3, 5, 8, 12 |
| completed_milestones | integer | Milestones achieved | 0, 2, 5 |
| overdue_milestones | integer | Missed milestone count | 0, 1, 2 |
| next_milestone_date | date (YYYY-MM-DD) | Upcoming milestone | 2024-02-15, null |
| next_milestone_risk | float | Risk for next milestone (0-100) | 15.0, 45.0, 75.0 |

### Communication & Collaboration
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| communication_frequency | string | Update schedule | Daily, Weekly, Bi-weekly |
| meeting_hours_per_week | float | Weekly meeting time | 2.0, 5.0, 10.0 |
| collaboration_tools | string (comma-separated) | Tools used | Slack,Jira,Confluence; Teams,Azure |
| documentation_quality | float | Doc completeness (0-10) | 5.0, 7.5, 9.5 |

### Outcome & Impact
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| business_value | string | Expected business impact | Low, Medium, High, Critical |
| roi_estimate | float | Expected ROI percentage | 50.0, 150.0, 300.0 |
| strategic_importance | float | Strategic value (0-10) | 4.0, 7.0, 10.0 |
| customer_impact | string | Effect on customers | None, Minor, Moderate, Major |

### Timestamps
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| created_at | datetime (YYYY-MM-DD HH:MM:SS) | Project creation | 2023-12-01 09:00:00 |
| last_updated | datetime (YYYY-MM-DD HH:MM:SS) | Last modification | 2024-01-20 11:30:00 |

---

## 4. WORKLOAD_HISTORY TABLE (workload_history.csv)

### Record Identification
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| record_id | string | Unique record identifier | WH001, WH002, ... |
| employee_id | string | Employee identifier | EMP001, EMP002, ... |
| date | date (YYYY-MM-DD) | Date of measurement | 2024-01-15 |
| week_number | integer | Week of year | 1, 2, 3, ..., 52 |
| month | string | Month name | January, February, March |
| year | integer | Year | 2023, 2024 |

### Work Hours & Activity
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| total_hours_worked | float | Hours worked that day/period | 6.5, 8.0, 10.5, 12.0 |
| regular_hours | float | Standard working hours | 8.0, 7.5, 6.0 |
| overtime_hours | float | Extra hours worked | 0.0, 1.5, 3.0, 4.5 |
| billable_hours | float | Client-billable hours | 5.0, 7.0, 8.0 |
| non_billable_hours | float | Internal work hours | 1.0, 2.0, 3.0 |
| meeting_hours | float | Time in meetings | 1.0, 2.5, 4.0, 6.0 |
| focused_work_hours | float | Deep work time | 3.0, 5.0, 6.5 |
| context_switching_count | integer | Number of task switches | 5, 10, 15, 25 |

### Task & Project Load
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| active_tasks_count | integer | Number of concurrent tasks | 2, 3, 5, 8 |
| active_projects_count | integer | Number of concurrent projects | 1, 2, 3 |
| tasks_completed | integer | Tasks finished that day | 0, 1, 2, 3, 5 |
| tasks_started | integer | New tasks started | 0, 1, 2, 3 |
| blocked_tasks_count | integer | Tasks blocked/waiting | 0, 1, 2 |
| high_priority_tasks | integer | Critical tasks in queue | 0, 1, 2, 3 |

### Workload Intensity Metrics
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| workload_intensity_score | float | Overall workload measure (0-100) | 35.0, 65.0, 85.0, 95.0 |
| task_density | float | Tasks per hour | 0.5, 1.0, 1.5, 2.0 |
| deadline_pressure_score | float | Urgency measure (0-100) | 25.0, 50.0, 75.0, 90.0 |
| multitasking_level | string | Concurrent work level | Low, Medium, High |
| cognitive_load_estimate | float | Mental effort required (0-10) | 4.0, 6.5, 8.5, 9.5 |

### Productivity Indicators
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| productivity_score | float | Daily productivity (0-100) | 45.0, 70.0, 85.0, 95.0 |
| efficiency_ratio | float | Output/Input ratio | 0.6, 0.85, 1.0, 1.2 |
| task_completion_rate | float | % of planned tasks done | 50.0, 75.0, 100.0 |
| quality_of_work | float | Work quality measure (0-10) | 6.0, 7.5, 9.0 |
| rework_time_hours | float | Time spent on corrections | 0.0, 0.5, 1.5, 3.0 |

### Communication & Collaboration
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| emails_sent | integer | Emails sent | 5, 10, 20, 35 |
| emails_received | integer | Emails received | 15, 30, 50, 80 |
| chat_messages_sent | integer | Instant messages sent | 20, 50, 100, 150 |
| meetings_attended | integer | Number of meetings | 1, 2, 3, 5, 8 |
| collaboration_hours | float | Time working with others | 1.0, 3.0, 5.0 |

### Stress & Well-being Indicators
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| stress_level | string | Self-reported stress | Low, Medium, High, Very High |
| stress_score | float | Calculated stress metric (0-100) | 15.0, 45.0, 75.0, 90.0 |
| fatigue_level | string | Tiredness indicator | Low, Medium, High |
| work_life_balance_today | float | Daily balance score (0-10) | 4.0, 6.5, 8.0, 9.5 |
| late_hours_indicator | boolean | Worked past 6pm | True, False |
| weekend_work_indicator | boolean | Worked on weekend | True, False |
| break_time_minutes | float | Rest/break duration | 15.0, 30.0, 60.0 |

### Performance Trends
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| productivity_vs_avg | float | % vs personal average | -15.0, 0.0, 10.0, 25.0 |
| workload_vs_capacity | float | % of capacity used | 60.0, 85.0, 100.0, 120.0 |
| burnout_risk_today | float | Daily burnout risk (0-100) | 10.0, 35.0, 65.0, 85.0 |
| engagement_score | float | Work engagement (0-10) | 5.0, 7.0, 8.5, 9.5 |

### Notes & Context
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| special_circumstances | string | Notable events | Holiday, Training Day, Client Visit, null |
| out_of_office | boolean | Was on leave | True, False |
| worked_from | string | Work location | Office, Home, Remote, Client Site |

---

## 5. TASK_ASSIGNMENTS TABLE (task_assignments.csv)

### Assignment Identification
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| assignment_id | string | Unique assignment ID | ASG001, ASG002, ... |
| task_id | string | Task being assigned | TSK001, TSK023, ... |
| employee_id | string | Assigned employee | EMP001, EMP015, ... |
| project_id | string | Related project | PRJ001, PRJ005, ... |

### Assignment Details
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| assignment_date | date (YYYY-MM-DD) | When assigned | 2024-01-10 |
| assignment_method | string | How assigned | Manual, AI-Recommended, Auto-Scheduled |
| assigned_by | string | Who assigned (manager ID) | EMP005, SYSTEM |
| acceptance_status | string | Employee response | Pending, Accepted, Declined, Renegotiated |
| acceptance_date | date (YYYY-MM-DD) | When accepted | 2024-01-11, null |

### Suitability & Matching Scores
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| skill_match_score | float | Skill alignment (0-100) | 45.0, 75.0, 92.0 |
| availability_match_score | float | Schedule fit (0-100) | 60.0, 85.0, 100.0 |
| workload_compatibility_score | float | Capacity alignment (0-100) | 50.0, 75.0, 90.0 |
| experience_match_score | float | Experience fit (0-100) | 55.0, 80.0, 95.0 |
| overall_suitability_score | float | Combined match (0-100) | 60.0, 78.0, 93.0 |
| team_compatibility_score | float | Team fit rating (0-100) | 65.0, 82.0, 94.0 |

### Assignment Outcome
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| assignment_success | boolean | Was assignment successful | True, False, null (if ongoing) |
| completion_status | string | Final status | Completed, Reassigned, Cancelled, In Progress |
| reassignment_count | integer | Times reassigned | 0, 1, 2 |
| reassignment_reason | string | Why reassigned | Overload, Skill Mismatch, Leave, null |

### Performance Metrics
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| time_to_complete | float | Hours taken to finish | 5.0, 15.0, 40.0, null |
| quality_rating | float | Quality of work (0-10) | 6.5, 8.0, 9.5, null |
| on_time_completion | boolean | Met deadline | True, False, null |
| efficiency_score | float | Expected vs actual time ratio | 0.8, 1.0, 1.2 |

### Feedback & Learning
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| employee_feedback | string | Employee comments | "Good match", "Too complex", "Enjoyed it", null |
| manager_feedback | string | Manager assessment | "Excellent work", "Needs improvement", null |
| assignment_satisfaction | float | Employee rating (0-10) | 5.0, 7.5, 9.0, null |
| would_recommend_again | boolean | Suitable for future | True, False, null |

### Timestamps
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| created_at | datetime (YYYY-MM-DD HH:MM:SS) | Record creation | 2024-01-10 09:00:00 |
| last_updated | datetime (YYYY-MM-DD HH:MM:SS) | Last update | 2024-01-15 14:30:00 |

---

## 6. TEAM_FORMATIONS TABLE (team_formations.csv)

### Team Identification
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| team_id | string | Unique team identifier | TEAM001, TEAM002, ... |
| team_name | string | Team name | Alpha Squad, Design Dream Team, Backend Crew |
| project_id | string | Associated project | PRJ001, PRJ005, ... |
| formation_date | date (YYYY-MM-DD) | When team was formed | 2024-01-05 |
| formation_method | string | How formed | Manual, AI-Recommended, Hybrid |

### Team Composition
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| team_lead_id | string | Team leader | EMP005, EMP012, ... |
| member_ids | string (comma-separated) | All team member IDs | EMP001,EMP003,EMP007,EMP015 |
| team_size | integer | Number of members | 3, 5, 7, 10, 15 |
| role_distribution | string (JSON format) | Roles in team | {"Developer":3,"Designer":1,"QA":1} |
| seniority_mix | string (JSON format) | Experience levels | {"Junior":1,"Mid":2,"Senior":1} |

### Team Characteristics
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| skill_diversity_score | float | Skill variety (0-100) | 45.0, 70.0, 90.0 |
| experience_balance_score | float | Experience distribution (0-100) | 55.0, 75.0, 85.0 |
| collaborative_history_score | float | Past collaboration quality (0-100) | 40.0, 70.0, 95.0 |
| communication_compatibility | float | Communication fit (0-100) | 60.0, 80.0, 92.0 |
| workload_balance_score | float | Load distribution (0-100) | 50.0, 75.0, 90.0 |
| timezone_compatibility | float | Schedule alignment (0-100) | 65.0, 85.0, 100.0 |

### Performance & Success Metrics
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| predicted_success_rate | float | AI success prediction (0-100) | 55.0, 75.0, 90.0 |
| actual_performance_score | float | Real performance (0-100, null if ongoing) | 65.0, 82.0, 94.0, null |
| team_productivity_score | float | Productivity measure (0-100) | 60.0, 78.0, 92.0 |
| team_cohesion_score | float | Unity/cohesion (0-10) | 5.5, 7.5, 9.0 |
| conflict_incidents | integer | Number of conflicts | 0, 1, 2, 3 |
| collaboration_effectiveness | float | How well team works (0-10) | 6.0, 7.8, 9.2 |

### Project Outcomes
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| project_completed | boolean | Project finished | True, False, null |
| completion_time_days | float | Days to complete | 30.0, 60.0, 120.0, null |
| met_deadline | boolean | On-time delivery | True, False, null |
| quality_rating | float | Deliverable quality (0-10) | 6.5, 8.0, 9.5, null |
| budget_adherence | float | % of budget used | 85.0, 100.0, 115.0, null |
| stakeholder_satisfaction | float | Client rating (0-10) | 6.0, 8.0, 9.5, null |

### Optimization Indicators
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| team_efficiency_ratio | float | Output/Input ratio | 0.8, 1.0, 1.3 |
| resource_utilization | float | % of capacity used | 70.0, 85.0, 95.0 |
| skill_utilization_rate | float | % of skills used effectively | 65.0, 80.0, 92.0 |
| improvement_opportunities | integer | Areas to optimize | 0, 2, 5 |

### Feedback & Learning
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| team_feedback_summary | string | Overall team feedback | "Great collaboration", "Communication issues", null |
| lessons_learned | string | Key takeaways | "Need daily standups", "Clear roles helped", null |
| would_reform_team | boolean | Recommend same team | True, False, null |

### Status & Lifecycle
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| team_status | string | Current state | Active, Completed, Disbanded, On Hold |
| dissolution_date | date (YYYY-MM-DD) | When team ended | 2024-06-30, null |
| dissolution_reason | string | Why disbanded | Project Complete, Reorganization, null |

### Timestamps
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| created_at | datetime (YYYY-MM-DD HH:MM:SS) | Record creation | 2024-01-05 09:00:00 |
| last_updated | datetime (YYYY-MM-DD HH:MM:SS) | Last update | 2024-01-20 11:30:00 |

---

## 7. PERFORMANCE_REVIEWS TABLE (performance_reviews.csv)

### Review Identification
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| review_id | string | Unique review identifier | REV001, REV002, ... |
| employee_id | string | Employee being reviewed | EMP001, EMP023, ... |
| reviewer_id | string | Manager conducting review | EMP005, EMP012, ... |
| review_period_start | date (YYYY-MM-DD) | Period start date | 2023-07-01 |
| review_period_end | date (YYYY-MM-DD) | Period end date | 2023-12-31 |
| review_date | date (YYYY-MM-DD) | When review conducted | 2024-01-15 |
| review_type | string | Type of review | Annual, Quarterly, Project-based, Probationary |

### Performance Scores
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| overall_performance_score | float | Final score (0-100) | 55.0, 72.0, 88.0, 95.0 |
| normalized_performance_score | float | Peer-adjusted score (0-100) | 52.0, 70.0, 86.0, 93.0 |
| technical_competence_score | float | Technical skills (0-10) | 5.5, 7.0, 8.5, 9.5 |
| domain_knowledge_score | float | Domain expertise (0-10) | 6.0, 7.5, 9.0 |
| problem_solving_score | float | Problem-solving ability (0-10) | 6.5, 8.0, 9.5 |
| innovation_score | float | Innovation/creativity (0-10) | 5.0, 7.0, 9.0 |
| quality_of_work_score | float | Work quality (0-10) | 6.5, 8.0, 9.5 |
| productivity_score | float | Output quantity (0-10) | 6.0, 7.5, 9.0 |

### Behavioral & Soft Skills
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| communication_score | float | Communication effectiveness (0-10) | 6.0, 7.5, 9.0 |
| collaboration_score | float | Teamwork quality (0-10) | 6.5, 8.0, 9.5 |
| leadership_score | float | Leadership capability (0-10) | 5.0, 7.0, 9.0 |
| initiative_score | float | Proactiveness (0-10) | 5.5, 7.0, 8.5 |
| adaptability_score | float | Change management (0-10) | 6.0, 7.5, 9.0 |
| reliability_score | float | Dependability (0-10) | 7.0, 8.5, 9.5 |
| time_management_score | float | Time management (0-10) | 6.0, 7.5, 9.0 |

### Quantitative Metrics
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| tasks_completed | integer | Total tasks finished | 25, 50, 100, 150 |
| projects_completed | integer | Total projects finished | 2, 3, 5, 8 |
| average_task_quality | float | Mean quality rating (0-10) | 7.0, 8.0, 9.0 |
| on_time_delivery_rate | float | % completed on time | 65.0, 85.0, 95.0 |
| productivity_vs_peers | float | % vs peer average | -10.0, 0.0, 15.0, 30.0 |
| total_hours_worked | float | Hours in period | 800.0, 1000.0, 1200.0 |
| overtime_hours | float | Extra hours | 0.0, 20.0, 50.0, 100.0 |
| utilization_rate | float | % of capacity used | 70.0, 85.0, 95.0 |

### Areas of Excellence
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| strengths | string (comma-separated) | Key strengths | "Technical expertise,Problem solving,Communication" |
| achievements | string | Notable accomplishments | "Led successful project, Mentored 3 juniors" |
| exceeded_expectations_areas | string (comma-separated) | Areas of excellence | "Innovation,Quality,Collaboration" |

### Areas for Improvement
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| weaknesses | string (comma-separated) | Development areas | "Time management,Public speaking,Documentation" |
| improvement_areas | string (comma-separated) | Focus areas | "Leadership,Technical depth,Process adherence" |
| development_goals | string | Future objectives | "Complete AWS certification, Lead a team project" |

### Feedback & Recommendations
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| manager_comments | string | Detailed feedback | "Strong performer with leadership potential..." |
| self_assessment_score | float | Employee's self-rating (0-10) | 6.0, 7.5, 8.5 |
| peer_feedback_summary | string | Peer input summary | "Great collaborator, helpful mentor..." |
| promotion_readiness | string | Promotion status | Not Ready, Ready in 6-12 months, Ready Now |
| salary_adjustment_recommendation | float | Suggested raise % | 0.0, 3.0, 5.0, 10.0, 15.0 |
| bonus_recommendation | float | Suggested bonus amount | 0.0, 2000.0, 5000.0, 10000.0 |

### Action Items
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| training_recommendations | string (comma-separated) | Suggested courses | "Leadership Training,AWS Certification,Agile Course" |
| next_review_date | date (YYYY-MM-DD) | Next scheduled review | 2024-07-01 |
| follow_up_required | boolean | Needs follow-up | True, False |

### Timestamps
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| created_at | datetime (YYYY-MM-DD HH:MM:SS) | Record creation | 2024-01-15 09:00:00 |
| last_updated | datetime (YYYY-MM-DD HH:MM:SS) | Last update | 2024-01-15 14:30:00 |

---

## 8. SCHEDULES TABLE (schedules.csv)

### Schedule Identification
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| schedule_id | string | Unique schedule entry ID | SCH001, SCH002, ... |
| employee_id | string | Employee identifier | EMP001, EMP023, ... |
| event_type | string | Type of scheduled item | Task, Meeting, Focus Time, Break, Training, Leave |
| related_id | string | Related task/meeting ID | TSK001, MTG005, null |
| event_title | string | Description of event | "Sprint Planning", "Code Review", "Focus Block" |

### Timing Details
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| date | date (YYYY-MM-DD) | Event date | 2024-01-15 |
| start_time | time (HH:MM:SS) | Start time | 09:00:00, 14:30:00 |
| end_time | time (HH:MM:SS) | End time | 10:00:00, 16:00:00 |
| duration_minutes | integer | Total duration | 30, 60, 90, 120, 240 |
| timezone | string | Timezone for event | UTC, EST, PST, IST |

### Priority & Flexibility
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| priority | string | Event importance | Low, Medium, High, Critical |
| is_flexible | boolean | Can be rescheduled | True, False |
| buffer_required | boolean | Needs prep/recovery time | True, False |
| buffer_minutes | integer | Buffer time needed | 0, 15, 30, 60 |

### Conflicts & Optimization
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| has_conflict | boolean | Overlaps with another event | True, False |
| conflict_with_ids | string (comma-separated) | Conflicting schedule IDs | SCH005,SCH012 |
| optimization_score | float | Schedule quality (0-100) | 45.0, 70.0, 90.0 |
| recommended_time | time (HH:MM:SS) | AI-suggested time | 10:00:00, null |

### Attendance & Outcome
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| attendance_status | string | Attendance | Scheduled, Completed, Missed, Rescheduled, Cancelled |
| actual_start_time | time (HH:MM:SS) | When actually started | 09:05:00, null |
| actual_end_time | time (HH:MM:SS) | When actually ended | 10:10:00, null |
| actual_duration_minutes | integer | Real duration | 35, 65, null |
| productivity_during | float | Productivity rating (0-10) | 5.5, 7.0, 9.0, null |

### Collaboration Details
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| involves_team | boolean | Includes others | True, False |
| participant_ids | string (comma-separated) | Other attendees | EMP002,EMP007,EMP012 |
| participant_count | integer | Number of attendees | 1, 3, 5, 10 |
| meeting_type | string | Meeting format | One-on-One, Team Meeting, All-Hands, Training |

### Location & Mode
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| location | string | Where event occurs | Office, Home, Conference Room A, Virtual |
| is_remote | boolean | Virtual event | True, False |
| meeting_link | string | Virtual meeting URL | https://zoom.us/j/123456, null |

### Timestamps
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| created_at | datetime (YYYY-MM-DD HH:MM:SS) | Schedule entry created | 2024-01-10 09:00:00 |
| last_updated | datetime (YYYY-MM-DD HH:MM:SS) | Last modification | 2024-01-12 14:30:00 |

---

## 9. BURNOUT_INDICATORS TABLE (burnout_indicators.csv)

### Record Identification
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| indicator_id | string | Unique indicator record ID | BI001, BI002, ... |
| employee_id | string | Employee identifier | EMP001, EMP023, ... |
| assessment_date | date (YYYY-MM-DD) | When measured | 2024-01-15 |
| assessment_type | string | Type of assessment | Daily, Weekly, Monthly, On-Demand |

### Burnout Risk Scores
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| overall_burnout_risk | float | Overall risk score (0-100) | 15.0, 45.0, 75.0, 90.0 |
| emotional_exhaustion_score | float | Emotional fatigue (0-100) | 20.0, 50.0, 80.0 |
| depersonalization_score | float | Detachment measure (0-100) | 10.0, 40.0, 70.0 |
| reduced_accomplishment_score | float | Low achievement feeling (0-100) | 15.0, 35.0, 65.0 |
| burnout_category | string | Risk level | Low Risk, Moderate Risk, High Risk, Critical |

### Work-Related Factors
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| workload_pressure | float | Workload stress (0-100) | 30.0, 60.0, 85.0 |
| role_ambiguity | float | Unclear responsibilities (0-100) | 15.0, 40.0, 70.0 |
| work_life_conflict | float | Work-life imbalance (0-100) | 25.0, 55.0, 80.0 |
| job_demands | float | Job requirements burden (0-100) | 40.0, 65.0, 90.0 |
| job_control | float | Autonomy/control level (0-100) | 30.0, 60.0, 85.0 |
| role_conflict | float | Conflicting demands (0-100) | 20.0, 45.0, 75.0 |

### Behavioral Indicators
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| late_hours_frequency | integer | Days worked late (last 30 days) | 0, 5, 10, 15, 20 |
| weekend_work_frequency | integer | Weekends worked (last 8 weeks) | 0, 2, 4, 6, 8 |
| missed_breaks_count | integer | Skipped breaks (last week) | 0, 2, 5, 10 |
| vacation_days_unused | integer | Unused leave days | 0, 5, 10, 15, 20 |
| sick_days_taken | integer | Sick days (last 6 months) | 0, 2, 5, 8, 12 |
| absence_rate | float | % of days absent | 0.0, 2.5, 5.0, 10.0 |

### Physical & Mental Health Signals
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| reported_stress_level | string | Self-reported stress | Low, Medium, High, Very High |
| reported_fatigue_level | string | Self-reported fatigue | Low, Medium, High, Severe |
| sleep_quality | string | Sleep assessment | Good, Fair, Poor, Very Poor |
| physical_health_concerns | boolean | Has health issues | True, False |
| mental_health_support_needed | boolean | Needs support | True, False |
| energy_level | float | Energy/vitality (0-10) | 3.0, 5.5, 7.5, 9.0 |

### Engagement & Satisfaction
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| job_satisfaction | float | Job satisfaction (0-10) | 4.0, 6.5, 8.5, 10.0 |
| engagement_score | float | Work engagement (0-10) | 4.5, 7.0, 9.0 |
| motivation_level | float | Motivation measure (0-10) | 3.5, 6.0, 8.5 |
| sense_of_accomplishment | float | Achievement feeling (0-10) | 4.0, 7.0, 9.0 |
| organizational_commitment | float | Company commitment (0-10) | 5.0, 7.5, 9.5 |

### Social & Support Factors
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| social_support_score | float | Support from colleagues (0-10) | 4.0, 6.5, 9.0 |
| manager_support_score | float | Manager support (0-10) | 4.5, 7.0, 9.5 |
| team_cohesion | float | Team unity (0-10) | 5.0, 7.5, 9.0 |
| workplace_relationships | float | Relationship quality (0-10) | 5.5, 7.5, 9.0 |
| isolation_feeling | float | Sense of isolation (0-100) | 5.0, 30.0, 65.0, 90.0 |

### Coping & Resources
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| coping_effectiveness | float | Coping strategy quality (0-10) | 4.0, 6.5, 9.0 |
| resource_adequacy | float | Adequate resources (0-10) | 4.5, 7.0, 9.0 |
| work_recovery_ability | float | Ability to recover (0-10) | 4.0, 6.5, 8.5 |
| resilience_score | float | Resilience measure (0-10) | 5.0, 7.0, 9.0 |

### Predictive Indicators
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| burnout_trend | string | Risk trajectory | Decreasing, Stable, Increasing, Rapidly Increasing |
| predicted_burnout_30days | float | Risk in 30 days (0-100) | 20.0, 50.0, 80.0 |
| predicted_burnout_90days | float | Risk in 90 days (0-100) | 25.0, 55.0, 85.0 |
| intervention_urgency | string | Action needed | None, Monitor, Recommend, Immediate |

### Intervention History
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| interventions_received | integer | Number of interventions | 0, 1, 2, 3 |
| last_intervention_date | date (YYYY-MM-DD) | Most recent intervention | 2024-01-05, null |
| intervention_effectiveness | float | How well interventions worked (0-10) | 4.0, 6.5, 9.0, null |

### Timestamps
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| created_at | datetime (YYYY-MM-DD HH:MM:SS) | Record creation | 2024-01-15 09:00:00 |
| last_updated | datetime (YYYY-MM-DD HH:MM:SS) | Last update | 2024-01-15 09:00:00 |

---

## 10. FEEDBACK TABLE (feedback.csv)

### Feedback Identification
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| feedback_id | string | Unique feedback ID | FDB001, FDB002, ... |
| feedback_type | string | Type of feedback | Task Completion, Project Review, Peer Feedback, Self Assessment |
| provider_id | string | Who gave feedback | EMP005, EMP012, SYSTEM |
| recipient_id | string | Who receives feedback | EMP001, EMP023, ... |
| feedback_date | date (YYYY-MM-DD) | When provided | 2024-01-15 |

### Context & Subject
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| related_task_id | string | Task being reviewed | TSK001, null |
| related_project_id | string | Project being reviewed | PRJ001, null |
| related_team_id | string | Team being reviewed | TEAM001, null |
| feedback_category | string | Feedback area | Technical Skills, Communication, Leadership, Quality, Teamwork |

### Feedback Content
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| feedback_text | string | Detailed feedback | "Great attention to detail and excellent code quality..." |
| positive_aspects | string (comma-separated) | What went well | "Clear communication,On-time delivery,High quality" |
| improvement_areas | string (comma-separated) | What needs work | "Documentation,Testing coverage,Time estimation" |
| specific_suggestions | string | Actionable recommendations | "Consider adding more unit tests, Document API endpoints" |

### Ratings & Scores
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| overall_rating | float | Overall assessment (0-10) | 5.5, 7.0, 8.5, 9.5 |
| quality_rating | float | Work quality (0-10) | 6.0, 7.5, 9.0 |
| timeliness_rating | float | On-time performance (0-10) | 5.5, 7.0, 9.5 |
| collaboration_rating | float | Teamwork quality (0-10) | 6.5, 8.0, 9.5 |
| communication_rating | float | Communication effectiveness (0-10) | 6.0, 7.5, 9.0 |
| innovation_rating | float | Creativity/innovation (0-10) | 5.0, 7.0, 9.0 |

### Sentiment & Tone
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| sentiment | string | Overall sentiment | Very Negative, Negative, Neutral, Positive, Very Positive |
| sentiment_score | float | Sentiment measure (-100 to 100) | -50.0, 0.0, 50.0, 85.0 |
| tone | string | Feedback tone | Constructive, Critical, Encouraging, Mixed |

### Impact & Follow-up
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| actionable | boolean | Has actionable items | True, False |
| action_items | string (comma-separated) | Specific actions | "Complete training,Review documentation,Improve tests" |
| priority_level | string | Urgency of actions | Low, Medium, High |
| follow_up_required | boolean | Needs follow-up | True, False |
| follow_up_date | date (YYYY-MM-DD) | When to follow up | 2024-02-15, null |

### Recipient Response
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| acknowledged | boolean | Recipient viewed feedback | True, False |
| acknowledged_date | date (YYYY-MM-DD) | When viewed | 2024-01-16, null |
| recipient_response | string | Recipient's comment | "Thank you, will work on documentation...", null |
| response_date | date (YYYY-MM-DD) | When responded | 2024-01-17, null |

### Usage & Learning
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| used_for_training | boolean | Used in ML training | True, False |
| used_for_performance_review | boolean | Included in reviews | True, False |
| visibility | string | Who can see feedback | Private, Team, Manager Only, Public |

### Timestamps
| Column Name | Data Type | Description | Sample Values/Range |
|------------|-----------|-------------|-------------------|
| created_at | datetime (YYYY-MM-DD HH:MM:SS) | Feedback created | 2024-01-15 09:00:00 |
| last_updated | datetime (YYYY-MM-DD HH:MM:SS) | Last update | 2024-01-16 14:30:00 |

---

## DATA GENERATION RECOMMENDATIONS

### 1. Data Relationships
- Ensure foreign keys are consistent across tables
- Employee IDs should exist in employees.csv before being referenced elsewhere
- Task IDs should exist in tasks.csv before being referenced in task_assignments.csv
- Maintain referential integrity across all tables

### 2. Realistic Distributions
- **Performance scores**: Use normal distribution centered around 70-75
- **Burnout risk**: Skew towards lower values (most employees should be low-medium risk)
- **Task completion rates**: Average around 80-85%
- **Workload hours**: Typically 35-45 hours/week with occasional spikes
- **Team sizes**: Most common 4-6 people

### 3. Temporal Consistency
- Ensure dates are logically ordered (hire_date < task_assignment_date < task_completion_date)
- Workload history should have daily/weekly entries
- Performance reviews should align with review periods

### 4. Reasonable Value Ranges
- Keep continuous variables within realistic bounds
- Use appropriate variance to avoid perfectly clean data
- Include some missing values (null) where realistic (e.g., incomplete tasks)
- Add occasional outliers to simulate real-world edge cases

### 5. Skill & Role Coherence
- Match skills to roles (e.g., "Python" for "Software Engineer")
- Align task requirements with employee capabilities (with some mismatches)
- Ensure senior employees have higher skill scores and more experience

### 6. Workload Patterns
- Create realistic workload variations (busy periods, slow periods)
- Add seasonality if relevant
- Include occasional crunch times before deadlines
- Model realistic overtime patterns

### 7. Minimum Dataset Sizes
For effective ML training:
- **Employees**: 100-500 records
- **Tasks**: 1,000-5,000 records
- **Projects**: 50-200 records
- **Workload History**: 10,000-50,000 records (daily entries for all employees)
- **Task Assignments**: 2,000-10,000 records
- **Team Formations**: 100-500 records
- **Performance Reviews**: 200-1,000 records
- **Schedules**: 5,000-20,000 records
- **Burnout Indicators**: 1,000-5,000 records
- **Feedback**: 1,000-5,000 records

---

## NOTES

1. **Data Types**:
   - string: Text data (use appropriate length limits)
   - integer: Whole numbers
   - float: Decimal numbers
   - boolean: True/False
   - date: YYYY-MM-DD format
   - datetime: YYYY-MM-DD HH:MM:SS format
   - time: HH:MM:SS format
   - comma-separated: Multiple values separated by commas

2. **Null/Missing Values**:
   - Include realistic missing data where appropriate
   - Not all fields need values for all records
   - Use "null" or leave blank for missing values

3. **CSV Format**:
   - Use commas as delimiters
   - Include headers in first row
   - Enclose text fields with quotes if they contain commas
   - UTF-8 encoding

4. **ID Conventions**:
   - Use consistent prefixes (EMP, TSK, PRJ, etc.)
   - Zero-pad numbers (EMP001, EMP002, etc.)
   - Ensure uniqueness within each table
