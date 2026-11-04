# Team Formation Changes

## Overview

This document summarizes the major feature changes, supporting fixes, and future work for the Employee Performance Analyser and Recommendation System (EPARS) team formation workflow.

This milestone improves the existing team formation and task assignment pipeline without retraining, replacing, or changing the underlying ML models.

## 1. Major Feature Changes

### 1.1 Team formation data preparation

- Added dedicated backend data-preparation functions to retrieve project context, open project tasks, employee profiles, and existing employee workloads.
- Exposed the configured project team size through project data returned to the frontend.
- Calculated existing workload from employees' currently open tasks using the task's current assignee, rather than assignment-history records.
- Included assigned open tasks in recommendation input so the workflow can account for and reallocate them.
- Kept missing workload estimates and missing or invalid capacity information explicit rather than inventing values.

### 1.2 Team formation and task allocation

- Uses the configured `projects.team_size` rather than deriving team size from the number of tasks.
- Supports multiple tasks per employee while ensuring every selected team member receives at least one task.
- Requires every open project task to be assigned exactly once.
- Restricts assignments to employee-task pairs returned by the existing Model 3 task-assignment recommender.
- Uses workload-aware allocation and stable ordering to reduce avoidable allocation-order effects.
- Distinguishes bounded roster-search exhaustion from proven infeasibility. Search-budget exhaustion is reported explicitly rather than incorrectly claiming that no feasible team exists.
- Returns explicit errors when a team cannot be formed without violating required constraints.

### 1.3 Team scoring refinements

The team score uses six weighted components:

| Component | Weight |
|---|---:|
| Task fit | 45% |
| Skill coverage | 20% |
| Experience balance | 10% |
| Workload balance | 10% |
| Historical co-occurrence | 5% |
| Composition typicality | 10% |

- Enabled skill coverage as an active scoring component.
- Calculates task fit from Model 3 scores for the tasks actually assigned to the team.
- Evaluates workload balance using projected workload, accounting for existing workload and proposed assignments; it is not an inverse burnout score.
- Treats historical co-occurrence as recorded historical team membership, not proof of successful collaboration.
- Treats Isolation Forest output as a composition-typicality signal, not a direct prediction of team quality, compatibility, or success.
- Identifies unavailable scoring components in the API. The overall score is not presented as valid when required components are unavailable.

### 1.4 Manager confirmation and persistence

- Keeps recommendations unpersisted until the manager explicitly confirms them.
- Allows the manager to select a team lead from the recommended roster.
- Revalidates the recommendation against authoritative project, task, employee, and Model 3 eligibility data during confirmation.
- Validates project team size, roster uniqueness, task coverage, assignment eligibility, and team-lead selection.
- Persists the team formation and task assignments within a database transaction.
- Copies authoritative `projects.team_size` into `team_formations.team_size` without modifying the project setting.
- Prevents a second active AI-recommended formation for the same project.
- Reuses the existing assignment helper to preserve established assignment-history behavior.

### 1.5 Frontend workflow

- Displays the backend recommendation, including roster IDs, assignments, team size, score components, weights, and unavailable-score details.
- Removes fabricated sample fallbacks and placeholder employee or task details.
- Adds team-lead selection restricted to the recommended roster and an explicit confirmation action.
- Handles loading, empty, error, and confirmation-conflict states.
- Prevents repeated confirmation submissions and ignores stale recommendation responses after the selected project changes.
- Displays IDs when the API does not supply employee or task names rather than fabricating details.

## 2. Minor Fixes and Reliability Improvements

- Fixed an allocation path that could select an employee who was not eligible for the current task.
- Added handling for empty candidate lists and final assignment eligibility validation.
- Changed team-level feature calculations to use unique roster members, avoiding double-counting employees assigned multiple tasks.
- Corrected workload scoring to reflect projected workload fairness rather than burnout risk.
- Enabled skill coverage and retained fixed scoring weights rather than silently renormalizing them.
- Clarified historical co-occurrence and Isolation Forest composition typicality in API documentation and score terminology.
- Made workload comparison explicit when capacity data is missing or invalid; no capacity values are imputed.
- Distinguished search-budget exhaustion from proven infeasibility and mapped them to different API error responses.
- Stabilized task and candidate ordering to reduce order-dependent allocation results.
- Rejected subset-task recommendations because confirmation requires all currently open project tasks to be assigned.
- Broadened duplicate-confirmation prevention to cover any active AI-recommended formation for the project, not only an identical roster and team lead.
- Added or updated tests for data preparation, allocation constraints, scoring, API behavior, confirmation validation, duplicate prevention, and transaction rollback.
- Updated API contract documentation and agent-facing descriptions to reflect the workflow and score terminology.

## 3. Future Work

The following are proposed improvements. They were not implemented or validated as part of this milestone.

### 3.1 Workload and risk prediction

- Improve productivity, overload, burnout, and project-delay prediction using more representative real-world data.
- Review feature engineering and temporal features for workload trends, deadline pressure, task overlap, and overtime.
- Evaluate model calibration and performance across employee roles and project types.

### 3.2 Performance scoring and feedback

- Improve the reliability and consistency of performance review scoring.
- Investigate feedback normalization and methods to reduce bias in feedback-derived signals.
- Validate performance scores against appropriate human-reviewed outcomes.

### 3.3 Task scheduling and workload optimization

- Improve task-duration, employee-efficiency, and task-urgency predictions using observed project execution data.
- Evaluate scheduling objectives and constraints against operational requirements, including capacity, deadlines, dependencies, and changing priorities.
- Measure schedule quality using completion time, lateness, workload distribution, and reassignment frequency.

### 3.4 Team formation models

- Explore a dedicated employee-role suitability model rather than relying only on Model 3 candidate scores for task fit.
- Investigate a supervised team-composition model using outcome-verified historical project data.
- Improve collaboration signals by distinguishing successful collaboration from simple historical co-occurrence.
- Evaluate skill coverage and experience balance against project outcomes and manager assessments.
- Continue treating Isolation Forest as an anomaly or historical composition-typicality signal unless evidence supports a different role.

### 3.5 Dataset quality and model evaluation

- Reduce dependence on synthetic data by collecting representative, appropriately governed organizational data.
- Audit datasets for target leakage, inconsistent timestamps, impossible values, missing fields, and class imbalance.
- Add and validate derived features only where reliable source data supports them.
- Establish model-specific evaluation metrics, validation splits, baselines, and drift monitoring.
- Validate recommendations with managers and real project outcomes before using them for consequential employee decisions.

## 4. Scope and Implementation Notes

- This milestone focused on team formation data preparation, allocation, scoring, API integration, persistence, and frontend confirmation.
- Existing ML models, model artifacts, training data, and prediction logic were intentionally left unchanged.
- The existing Model 3 task-assignment predictor and Isolation Forest model, including its existing feature schema, were retained.
- Future-work items are recommendations for subsequent development, not claims about completed functionality.
- The frontend currently shows employee and task IDs when corresponding display names are not provided by the API.
- Automated tests and mocked frontend checks were run during the milestone. Mocked tests do not establish correctness under live production database concurrency; deployment-level verification remains necessary.
