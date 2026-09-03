## EPARS Burnout Monitor — Isolated Test Case Template
Fill in the placeholders below, run section by section.
Rule of thumb: NEVER reuse a task_id/indicator_id/assignment_id that already exists in the DB — that's what turns a test into a data-recovery project. Pick a block (e.g. 95001, 95002, ...) and only go up from there. Before using this: confirm you're running against the DB you intend to (local vs Supabase) — see the DATABASE_URL check from earlier if unsure.


## STEP 0 — Pre-flight: confirm your chosen IDs are genuinely unused

Replace TSK95001 / BI95001 / ASG95001 throughout this file with your chosen test IDs before running. All three checks below should return 0 rows before you proceed.
```sql
SELECT * FROM tasks             WHERE task_id       = 'TSK95001';
SELECT * FROM burnout_indicators WHERE indicator_id  = 'BI95001';
SELECT * FROM task_assignments  WHERE assignment_id  = 'ASG95001';
```

## STEP 1 — Set up the test case
Swap 'EMP001' for whichever of your 4 real accounts you're testing with, and adjust the task fields to match the scenario you want (see the TC1–TC8 list from earlier for reassign / reschedule / none / rejection / threshold / double-booking scenarios).
```sql
INSERT INTO burnout_indicators (indicator_id, employee_id, assessment_date, overall_burnout_risk, burnout_category)
VALUES ('BI95001', 'EMP001', CURRENT_DATE, 85.0, 'Critical');

INSERT INTO tasks (task_id, task_name, task_type, priority, complexity, estimated_hours,
                    required_skills, status, completion_percentage, due_date)
VALUES ('TSK95001', 'Test Reassign Task', 'Documentation', 'High', 'Moderate', 6.0,
        'Documentation', 'In Progress', 20.0, CURRENT_DATE + 3);

INSERT INTO task_assignments (assignment_id, task_id, employee_id, completion_status)
VALUES ('ASG95001', 'TSK95001', 'EMP001', 'In Progress');
```


## STEP 2 — Run burnout_monitor.py now, from your terminal
Note the new assignment_id it creates on reassign (printed in the output),and which employee it went to — you'll need both for cleanup below.
```
python burnout_monitor.py
```


## STEP 3 — Inspect before cleaning up (optional but recommended)

Confirms exactly what changed before you delete it.
```sql
SELECT * FROM task_assignments WHERE task_id = 'TSK95001' ORDER BY assignment_id;
SELECT * FROM tasks            WHERE task_id = 'TSK95001';
SELECT current_project_count   FROM employees WHERE employee_id = '<candidate_id_from_output>';
```


## STEP 4 — Revert: delete everything this test created

Because these IDs never existed before this test, cleanup is exact no history to reconstruct, no ambiguity.
```sql
BEGIN;

DELETE FROM task_assignments WHERE task_id = 'TSK95001';
DELETE FROM tasks            WHERE task_id = 'TSK95001';
DELETE FROM burnout_indicators WHERE indicator_id = 'BI95001';

-- Only needed if the decision was "reassign" or "reschedule" and it succeeded, undo the +1 current_project_count bump on whichever real employee the task landed on (check STEP 2's output for the employee_id).

UPDATE employees
SET current_project_count = current_project_count - 1
WHERE employee_id = '<candidate_id_from_output>';

COMMIT;   -- swap to ROLLBACK if STEP 3's inspection looked wrong
```


## STEP 5 — Calendar cleanup (manual, outside SQL)
 
If the test employee was one of your 4 real accounts, a real Google Calendar event was created on the candidate's calendar. SQL can't touch this — delete it manually from the relevant Gmail account, or write a small script calling cancel_calendar_event(task_id, employee_id) from calendar_client.py before you run STEP 4's DELETE (it needs the task_assignments row to still exist to look up the google_event_id).