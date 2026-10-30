"""
ePARS comprehensive end-to-end chatbot test suite.

Based on the existing test_agent.py interface and agent/tools.py:
    from epars_agent import run_agent
    result = run_agent(query)  # {"input": ..., "output": ..., "steps": [...]}

IMPORTANT — FULL E2E MODE:
- This suite sends real queries to the live agent.
- Queries marked WRITE may change PostgreSQL records or a connected calendar.
- Database writes are NOT automatically rolled back. Review the query list and use
  a test/staging database and test calendar whenever possible.
- Calendar create/reschedule/cancel questions are included, but they only succeed
  when the task/employee pair has the required assignment/event state.
- The optional cleanup pass attempts to cancel a calendar event for the configured
  task/employee pair. It does not undo task assignments or burnout-alert records.

Run from the directory that contains the `agent/` folder:
    python test_agent_comprehensive.py
    python test_agent_comprehensive.py --list
    python test_agent_comprehensive.py --category "Employee profile and stored ML scores"
    python test_agent_comprehensive.py --limit 10
    python test_agent_comprehensive.py --cleanup-calendar

Configure IDs using environment variables or edit the constants below:
    EPARS_TEST_EMPLOYEE_ID, EPARS_TEST_TASK_ID, EPARS_TEST_PROJECT_ID
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Preserve the same import approach used by the original test_agent.py.
sys.path.insert(0, str(Path(__file__).resolve().parent / "agent"))
from epars_agent import run_agent

TEST_TASK_ID = os.getenv("EPARS_TEST_TASK_ID", "TSK0010")
TEST_EMPLOYEE_ID = os.getenv("EPARS_TEST_EMPLOYEE_ID", "EMP042")
TEST_PROJECT_ID = os.getenv("EPARS_TEST_PROJECT_ID", "PRJ005")
SECOND_EMPLOYEE_ID = os.getenv("EPARS_TEST_EMPLOYEE_ID_2", "EMP001")
THIRD_EMPLOYEE_ID = os.getenv("EPARS_TEST_EMPLOYEE_ID_3", "EMP002")
FOURTH_EMPLOYEE_ID = os.getenv("EPARS_TEST_EMPLOYEE_ID_4", "EMP003")

# Calendar times are generated relative to now to avoid stale dates.
def future_times():
    start = datetime.now().astimezone().replace(second=0, microsecond=0) + timedelta(days=7)
    end = start + timedelta(hours=1)
    return start.isoformat(), end.isoformat()

CAL_START, CAL_END = future_times()
CAL_RESCHEDULE_START = (
    datetime.fromisoformat(CAL_START) + timedelta(days=1, hours=2)
).isoformat()
CAL_RESCHEDULE_END = (
    datetime.fromisoformat(CAL_END) + timedelta(days=1, hours=2)
).isoformat()

# "write" indicates the query may modify the database and/or external calendar.
# The suite records execution and tool traces; it does not assume a natural-language
# answer is correct merely because run_agent returned successfully.
TESTS = [
    # 1–10: employee profile and stored ML outputs (read-only)
    {"name": "Employee profile", "category": "Employee profile and stored ML scores", "effect": "read", "query": f"Show the employee profile for {TEST_EMPLOYEE_ID}, including role, seniority, skills, capacity, and availability."},
    {"name": "Employee profile second ID", "category": "Employee profile and stored ML scores", "effect": "read", "query": f"Retrieve the profile of employee {SECOND_EMPLOYEE_ID}."},
    {"name": "Stored ML scores", "category": "Employee profile and stored ML scores", "effect": "read", "query": f"Show the latest stored performance and burnout ML scores for employee {TEST_EMPLOYEE_ID}."},
    {"name": "Performance score live", "category": "Employee profile and stored ML scores", "effect": "read", "query": f"Calculate a fresh performance score for employee {TEST_EMPLOYEE_ID} using the live model."},
    {"name": "Burnout score live", "category": "Employee profile and stored ML scores", "effect": "read", "query": f"Calculate a fresh burnout risk score for employee {TEST_EMPLOYEE_ID} using the live model."},
    {"name": "Workload employee", "category": "Employee profile and stored ML scores", "effect": "read", "query": f"What is the current workload of employee {TEST_EMPLOYEE_ID}, including active tasks and capacity?"}, 
    {"name": "Workload second employee", "category": "Employee profile and stored ML scores", "effect": "read", "query": f"Is employee {SECOND_EMPLOYEE_ID} available to take on another task based on current workload?"},
    {"name": "Profile and score explanation", "category": "Employee profile and stored ML scores", "effect": "read", "query": f"Summarize the strengths, performance indicators, and risk factors for employee {TEST_EMPLOYEE_ID}."},
    {"name": "Compare employee profiles", "category": "Employee profile and stored ML scores", "effect": "read", "query": f"Compare the skills, seniority, capacity, and availability of employees {TEST_EMPLOYEE_ID} and {SECOND_EMPLOYEE_ID}."},
    {"name": "Unknown employee handling", "category": "Edge cases and robustness", "effect": "read", "query": "Retrieve the profile and ML scores for employee EMP99999 and explain if the record is unavailable."},

    # 11–18: task details and ML-based employee recommendations (read-only)
    {"name": "Task details", "category": "Task recommendations and suitability", "effect": "read", "query": f"Show the details, priority, status, deadline, and required skills for task {TEST_TASK_ID}."},
    {"name": "Recommend employees for task", "category": "Task recommendations and suitability", "effect": "read", "query": f"Recommend the top three employees for task {TEST_TASK_ID} and explain the ranking."},
    {"name": "Score employee-task pair", "category": "Task recommendations and suitability", "effect": "read", "query": f"Score employee {TEST_EMPLOYEE_ID} for task {TEST_TASK_ID} and explain the suitability."},
    {"name": "Find Python developers", "category": "Task recommendations and suitability", "effect": "read", "query": "Find the best available Python developer with senior seniority for a high-priority task."},
    {"name": "Find data science skills", "category": "Task recommendations and suitability", "effect": "read", "query": "Find available employees with machine learning, Python, and data analysis skills."},
    {"name": "Find junior backend skills", "category": "Task recommendations and suitability", "effect": "read", "query": "Find a junior employee with backend development skills who has capacity for new work."},
    {"name": "Alternative candidate comparison", "category": "Task recommendations and suitability", "effect": "read", "query": f"Compare employees {TEST_EMPLOYEE_ID}, {SECOND_EMPLOYEE_ID}, and {THIRD_EMPLOYEE_ID} for suitability for task {TEST_TASK_ID}."},
    {"name": "Unknown task handling", "category": "Edge cases and robustness", "effect": "read", "query": "Recommend employees for task TSK99999 and explain what happens if the task does not exist."},

    # 19–25: assignment and workload changes (WRITE: assignment may update task_assignments,
    # tasks, and employees; do not run against production without authorization)
    {"name": "Assign task best employee", "category": "Task assignment and scheduling", "effect": "write", "query": f"Assign task {TEST_TASK_ID} to the best available employee based on skills, workload, and performance."},
    {"name": "Assign task to explicit employee", "category": "Task assignment and scheduling", "effect": "write", "query": f"Assign task {TEST_TASK_ID} to employee {TEST_EMPLOYEE_ID}."},
    {"name": "Reassignment request", "category": "Task assignment and scheduling", "effect": "write", "query": f"Reassign task {TEST_TASK_ID} to employee {SECOND_EMPLOYEE_ID} if they are a better fit."},
    {"name": "Avoid overloaded employee", "category": "Task assignment and scheduling", "effect": "read", "query": f"Should task {TEST_TASK_ID} be assigned to employee {TEST_EMPLOYEE_ID}, considering their current workload and burnout risk? Do not make the assignment."},
    {"name": "Scheduling rationale", "category": "Task assignment and scheduling", "effect": "read", "query": f"Recommend an assignment and scheduling plan for task {TEST_TASK_ID}, but do not modify any records."},
    {"name": "Task assignment missing task", "category": "Edge cases and robustness", "effect": "write", "query": "Try to assign nonexistent task TSK99999 to employee EMP99999 and report the validation result."},
    {"name": "Task details after assignment", "category": "Task assignment and scheduling", "effect": "read", "query": f"Check the current status and assignment details of task {TEST_TASK_ID}."},

    # 26–32: team formation (normally recommendation-only; composition check is read-only)
    {"name": "Recommend project teams", "category": "Team formation", "effect": "read", "query": f"Recommend the best team compositions for project {TEST_PROJECT_ID}, balancing skills, performance, and workload."},
    {"name": "Check team composition", "category": "Team formation", "effect": "read", "query": f"Evaluate the team composition for employees {TEST_EMPLOYEE_ID}, {SECOND_EMPLOYEE_ID}, and {THIRD_EMPLOYEE_ID}."},
    {"name": "Team with diverse skills", "category": "Team formation", "effect": "read", "query": f"Recommend a team for project {TEST_PROJECT_ID} with complementary skills and balanced workload."},
    {"name": "Team size comparison", "category": "Team formation", "effect": "read", "query": f"Suggest suitable team options of different sizes for project {TEST_PROJECT_ID}."},
    {"name": "Team formation constraints", "category": "Team formation", "effect": "read", "query": f"Recommend a team for project {TEST_PROJECT_ID}, avoiding employees who are overloaded or at high burnout risk."},
    {"name": "Team composition missing employee", "category": "Edge cases and robustness", "effect": "read", "query": "Evaluate team composition for employees EMP042, EMP001, and EMP99999."},
    {"name": "Team recommendation explanation", "category": "Team formation", "effect": "read", "query": f"Explain the factors that determine the recommended team for project {TEST_PROJECT_ID}."},

    # 33–39: burnout detection and interventions
    {"name": "Burnout status", "category": "Burnout detection and intervention", "effect": "read", "query": f"Check the burnout status of employee {TEST_EMPLOYEE_ID} and recommend interventions."},
    {"name": "Burnout risk trend", "category": "Burnout detection and intervention", "effect": "read", "query": f"Review employee {TEST_EMPLOYEE_ID}'s burnout risk and explain the main indicators behind it."},
    {"name": "Burnout intervention policy", "category": "Burnout detection and intervention", "effect": "read", "query": f"Based on employee {TEST_EMPLOYEE_ID}'s burnout risk, suggest appropriate interventions without creating an alert."},
    {"name": "Burnout alert write", "category": "Burnout detection and intervention", "effect": "write", "query": f"Record a burnout alert for employee {TEST_EMPLOYEE_ID} with burnout score 0.85, urgency high, and recommended action: manager review and workload reduction."},
    {"name": "High burnout next steps", "category": "Burnout detection and intervention", "effect": "read", "query": f"Employee {TEST_EMPLOYEE_ID} may be at high burnout risk. Recommend safe next steps and explain which information supports the recommendation."},
    {"name": "Burnout vs workload", "category": "Burnout detection and intervention", "effect": "read", "query": f"Compare the workload and burnout risk for employees {TEST_EMPLOYEE_ID} and {SECOND_EMPLOYEE_ID}."},
    {"name": "Burnout unknown employee", "category": "Edge cases and robustness", "effect": "read", "query": "Check burnout status for employee EMP99999 and report any missing-data limitations."},

    # 40–46: RAG and policy retrieval
    {"name": "Retrieve leave policy", "category": "HR policy RAG", "effect": "read", "query": "What does the company HR policy say about annual leave and requesting time off? Cite the relevant policy content if available."},
    {"name": "Overtime policy", "category": "HR policy RAG", "effect": "read", "query": "Retrieve the company policy on overtime limits and approval requirements."},
    {"name": "Burnout policy", "category": "HR policy RAG", "effect": "read", "query": "What company policies or SOPs apply when an employee is at risk of burnout?"},
    {"name": "Performance review policy", "category": "HR policy RAG", "effect": "read", "query": "Find the policy describing performance reviews, rating criteria, and review frequency."},
    {"name": "Task allocation policy", "category": "HR policy RAG", "effect": "read", "query": "Retrieve policies relevant to task allocation, workload balancing, and employee capacity."},
    {"name": "Policy synthesis", "category": "HR policy RAG", "effect": "read", "query": f"Using company policy and the available data for employee {TEST_EMPLOYEE_ID}, recommend a compliant workload intervention."},
    {"name": "Unrelated policy query", "category": "HR policy RAG", "effect": "read", "query": "Does the policy knowledge base contain guidance on employee task assignment? If not, say so rather than inventing a policy."},

    # 47–54: agentic multi-step reasoning
    {"name": "Full employee risk review", "category": "Agentic multi-step workflows", "effect": "read", "query": f"Review employee {TEST_EMPLOYEE_ID}'s profile, stored ML scores, live burnout risk, and workload, then summarize the key risks."},
    {"name": "Task recommendation with policy", "category": "Agentic multi-step workflows", "effect": "read", "query": f"For task {TEST_TASK_ID}, recommend suitable employees and explain the choice using current workload and relevant company policies. Do not assign it."},
    {"name": "Project staffing analysis", "category": "Agentic multi-step workflows", "effect": "read", "query": f"Analyze staffing for project {TEST_PROJECT_ID}, recommend a team, and identify workload or burnout concerns."},
    {"name": "Performance and burnout comparison", "category": "Agentic multi-step workflows", "effect": "read", "query": f"Combine stored performance scores, live performance prediction, burnout prediction, and workload for employee {TEST_EMPLOYEE_ID}. Explain discrepancies if any."},
    {"name": "Explain recommendation tradeoffs", "category": "Agentic multi-step workflows", "effect": "read", "query": f"Recommend the best candidate for task {TEST_TASK_ID}, explaining trade-offs between skill match, availability, performance, and burnout risk."},
    {"name": "Ask before making changes", "category": "Agentic multi-step workflows", "effect": "read", "query": f"Determine whether task {TEST_TASK_ID} should be reassigned based on the data, but only recommend an action and do not change the database or calendar."},
    {"name": "Conflicting constraints", "category": "Agentic multi-step workflows", "effect": "read", "query": f"Recommend a candidate for task {TEST_TASK_ID} who has the required skills but avoid anyone who appears overloaded; explain if no good candidate exists."},
    {"name": "Insufficient context", "category": "Edge cases and robustness", "effect": "read", "query": "Please optimize the team."},

    # 55–60: calendar operations. These require a real assignment and calendar credentials.
    {"name": "Create calendar event", "category": "Calendar integration", "effect": "write", "query": f"Create a calendar event for task {TEST_TASK_ID} assigned to employee {TEST_EMPLOYEE_ID}, from {CAL_START} to {CAL_END}."},
    {"name": "Reschedule calendar event", "category": "Calendar integration", "effect": "write", "query": f"Reschedule the calendar event for task {TEST_TASK_ID} and employee {TEST_EMPLOYEE_ID} to {CAL_RESCHEDULE_START} through {CAL_RESCHEDULE_END}."},
    {"name": "Cancel calendar event", "category": "Calendar integration", "effect": "write", "query": f"Cancel the calendar event for task {TEST_TASK_ID} and employee {TEST_EMPLOYEE_ID}."},
    {"name": "Calendar event missing", "category": "Edge cases and robustness", "effect": "write", "query": "Cancel the calendar event for task TSK99999 and employee EMP99999, and report the result."},
    {"name": "Calendar request without mutation", "category": "Calendar integration", "effect": "read", "query": f"Tell me whether task {TEST_TASK_ID} and employee {TEST_EMPLOYEE_ID} have a linked calendar event. Do not create, reschedule, or cancel anything."},
    {"name": "Calendar timing explanation", "category": "Calendar integration", "effect": "read", "query": f"Suggest a reasonable one-hour calendar slot next week for task {TEST_TASK_ID}, but do not create an event."},

    # 61–70: boundary cases, accuracy, and response quality
    {"name": "Empty skills search", "category": "Edge cases and robustness", "effect": "read", "query": "Find available employees for a task when the required skills are not specified; ask me for the missing information if necessary."},
    {"name": "Ambiguous employee request", "category": "Edge cases and robustness", "effect": "read", "query": "Tell me whether the employee is overloaded."},
    {"name": "Unsupported model request", "category": "Edge cases and robustness", "effect": "read", "query": "Predict the exact date an employee will resign using the available EPARS data."},
    {"name": "Explain data limitations", "category": "Edge cases and robustness", "effect": "read", "query": f"What limitations should I consider when interpreting the performance and burnout predictions for employee {TEST_EMPLOYEE_ID}?"},
    {"name": "No invented records", "category": "Edge cases and robustness", "effect": "read", "query": "List employee EMP99999's name, skills, performance score, and workload. Clearly identify fields that are unavailable."},
    {"name": "Tool-use transparency", "category": "Edge cases and robustness", "effect": "read", "query": f"Check the profile and workload of employee {TEST_EMPLOYEE_ID}, and summarize which system data you were able to retrieve."},
    {"name": "Duplicate assignment caution", "category": "Edge cases and robustness", "effect": "read", "query": f"Check whether task {TEST_TASK_ID} is already assigned before recommending any assignment. Do not modify records."},
    {"name": "Read-only confirmation", "category": "Edge cases and robustness", "effect": "read", "query": f"Give me a read-only summary of task {TEST_TASK_ID}, its current assignee, and the assignee's workload."},
    {"name": "Direct policy retrieval", "category": "HR policy RAG", "effect": "read", "query": "Search the policy knowledge base for rules on employee workload limits and summarize only what the retrieved documents support."},
    {"name": "End-to-end final summary", "category": "Agentic multi-step workflows", "effect": "read", "query": f"Prepare an end-to-end summary for task {TEST_TASK_ID}: task details, top employee recommendations, workload risks, relevant policy considerations, and next steps. Do not make changes."},
]


def safe_filename(text):
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in text).strip("_")


def run_tests(category=None, limit=None, pause=0.0, cleanup_calendar=False):
    selected = [t for t in TESTS if category is None or t["category"].lower() == category.lower()]
    if limit is not None:
        selected = selected[:limit]

    output_dir = Path("test_traces")
    output_dir.mkdir(exist_ok=True)
    summary = {
        "started_at": datetime.now().astimezone().isoformat(),
        "configured_ids": {
            "task_id": TEST_TASK_ID,
            "employee_id": TEST_EMPLOYEE_ID,
            "project_id": TEST_PROJECT_ID,
        },
        "total": len(selected),
        "passed": 0,
        "failed": 0,
        "results": [],
        "warning": "A successful run_agent call is not proof of answer accuracy. Review traces and side effects.",
    }

    print("\\n" + "=" * 78)
    print("ePARS Comprehensive End-to-End Test Suite")
    print(f"Running {len(selected)} of {len(TESTS)} tests")
    print(f"Configured task={TEST_TASK_ID}, employee={TEST_EMPLOYEE_ID}, project={TEST_PROJECT_ID}")
    print("WARNING: WRITE tests can persist real database/calendar changes.")
    print("=" * 78)

    for index, test in enumerate(selected, 1):
        print(f"\\n[Test {index}/{len(selected)}] {test['name']} [{test['effect'].upper()}]")
        print(f"Category: {test['category']}")
        print(f"Query: {test['query']}")
        if test["effect"] == "write":
            print("!!! WRITE TEST: this query may persist database or calendar changes !!!")
        started = time.time()
        record = {
            "index": index,
            "name": test["name"],
            "category": test["category"],
            "effect": test["effect"],
            "query": test["query"],
            "status": "failed",
        }
        try:
            result = run_agent(test["query"])
            record["status"] = "passed"
            record["duration_seconds"] = round(time.time() - started, 2)
            record["output"] = result.get("output", "")
            record["steps"] = result.get("steps", [])
            record["tool_step_count"] = len(record["steps"])
            summary["passed"] += 1
            print(f"Agent returned in {record['duration_seconds']}s; tool steps: {record['tool_step_count']}")
            print(f"FINAL ANSWER:\\n{record['output']}")
            trace_path = output_dir / f"trace_{index:02d}_{safe_filename(test['name'])}.json"
            trace_path.write_text(json.dumps({"test": test, "result": result}, indent=2, default=str), encoding="utf-8")
            record["trace_file"] = str(trace_path)
            print(f"Trace saved: {trace_path}")
        except Exception as exc:
            record["duration_seconds"] = round(time.time() - started, 2)
            record["error"] = repr(exc)
            summary["failed"] += 1
            print(f"FAILED: {exc}")
        summary["results"].append(record)
        if pause:
            time.sleep(pause)

    if cleanup_calendar:
        # Best-effort cleanup for the configured pair only. The underlying tool
        # deletes a real calendar event and clears google_event_id in PostgreSQL.
        print("\\n[Cleanup] Attempting to cancel the configured task/employee calendar event.")
        cleanup_query = (
            f"Cancel the calendar event for task {TEST_TASK_ID} and employee "
            f"{TEST_EMPLOYEE_ID}. This is a cleanup operation."
        )
        try:
            cleanup_result = run_agent(cleanup_query)
            summary["calendar_cleanup"] = {
                "attempted": True,
                "query": cleanup_query,
                "output": cleanup_result.get("output", ""),
                "steps": cleanup_result.get("steps", []),
            }
            print(summary["calendar_cleanup"]["output"])
        except Exception as exc:
            summary["calendar_cleanup"] = {"attempted": True, "error": repr(exc)}
            print(f"Calendar cleanup failed: {exc}")
    else:
        summary["calendar_cleanup"] = {
            "attempted": False,
            "note": "Run with --cleanup-calendar to attempt cancellation for the configured task/employee pair."
        }

    summary["finished_at"] = datetime.now().astimezone().isoformat()
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print("\\n" + "=" * 78)
    print(f"Finished: {summary['passed']} returned successfully, {summary['failed']} raised errors, {summary['total']} total.")
    print(f"Summary saved to: {summary_path}")
    print("Review test_traces/summary.json and individual traces; successful execution does not guarantee correctness.")
    print("=" * 78)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run comprehensive EPARS chatbot end-to-end tests.")
    parser.add_argument("--list", action="store_true", help="List tests without executing them.")
    parser.add_argument("--category", help="Run only an exact category name.")
    parser.add_argument("--limit", type=int, help="Run only the first N selected tests.")
    parser.add_argument("--pause", type=float, default=0.0, help="Seconds to pause between tests.")
    parser.add_argument(
        "--cleanup-calendar",
        action="store_true",
        help="After tests, attempt to cancel the calendar event for the configured task/employee pair.",
    )
    args = parser.parse_args()

    if args.list:
        for i, test in enumerate(TESTS, 1):
            print(f"{i:02d}. [{test['effect'].upper():5}] [{test['category']}] {test['name']}: {test['query']}")
        print(f"\\n{len(TESTS)} total tests.")
        return

    if args.category:
        categories = {t["category"].lower() for t in TESTS}
        if args.category.lower() not in categories:
            print("Unknown category. Available categories:")
            for item in sorted({t["category"] for t in TESTS}):
                print(f"  - {item}")
            raise SystemExit(2)

    run_tests(category=args.category, limit=args.limit, pause=max(0.0, args.pause), cleanup_calendar=args.cleanup_calendar)


if __name__ == "__main__":
    main()
