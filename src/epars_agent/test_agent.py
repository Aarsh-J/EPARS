"""
ePARS Agent — Step 3 Test Script
===================================
Runs 4 test queries covering all agent capabilities.
Use this to verify Step 3 is working before building the API.

Usage:
    cd epars_agent
    python test_agent.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agent"))

from epars_agent import run_agent

# ── Test cases — edit these IDs to ones that exist in your DB ─────────────────
# You can find real IDs by opening pgAdmin and browsing the tables,
# or by running: SELECT task_id FROM tasks LIMIT 5;  in psql

TEST_TASK_ID     = "TSK0010"   # a task that is NOT yet completed
TEST_EMPLOYEE_ID = "EMP042"    # any employee ID
TEST_PROJECT_ID  = "PRJ005"    # any project ID

TESTS = [
    {
        "name": "Task Assignment",
        "query": f"Assign task {TEST_TASK_ID} to the best available employee",
    },
    {
        "name": "Burnout Check",
        "query": f"Check the burnout status of employee {TEST_EMPLOYEE_ID} and recommend any interventions",
    },
    {
        "name": "Workload Check",
        "query": f"What is the current workload of employee EMP001 and are they available for new tasks?",
    },
    {
        "name": "Skill-based Search",
        "query": "Find the best available Python developer with senior seniority for a high priority task",
    },
]


def run_tests():
    print("\n" + "=" * 65)
    print("ePARS Agent — Step 3 Test Suite")
    print("=" * 65)

    passed = 0
    failed = 0

    for i, test in enumerate(TESTS, 1):
        print(f"\n[Test {i}/{len(TESTS)}] {test['name']}")
        print(f"Query: {test['query']}")
        print("-" * 65)

        try:
            result = run_agent(test["query"])

            print(f"\n✓ Agent completed in {len(result['steps'])} steps")
            print(f"\nFINAL ANSWER:\n{result['output']}")

            # Save full trace to a file for inspection
            trace_path = f"test_trace_{i}_{test['name'].lower().replace(' ', '_')}.json"
            with open(trace_path, "w") as f:
                json.dump(result, f, indent=2, default=str)
            print(f"\n[Trace saved to {trace_path}]")

            passed += 1

        except Exception as e:
            print(f"\n✗ Test failed: {e}")
            failed += 1

        print("\n" + "=" * 65)

    print(f"\nResults: {passed} passed, {failed} failed out of {len(TESTS)} tests")

    if failed == 0:
        print("\n✓ Step 3 complete! Agent is working end-to-end.")
        print("  Next: run the FastAPI server with  python api.py")
    else:
        print("\n✗ Some tests failed. Check the errors above.")
        print("  Common fixes:")
        print("  - Make sure ANTHROPIC_API_KEY is set in your .env")
        print("  - Make sure ChromaDB is populated (run ingest_policies.py)")
        print("  - Make sure the test IDs exist in your database")


if __name__ == "__main__":
    run_tests()
