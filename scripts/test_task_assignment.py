"""
Throwaway harness: sanity-checks Model3/Layer 3 (task_assignment) live
inference against a few real tasks and employees.
Run: python scripts/test_task_assignment.py [task_id]
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR / "epars_agent" / "agent"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_connection
from modules.ml.task_assignment_features import get_open_tasks
from modules.ml.task_assignment_predict import recommend_top_n, score_pair


def pick_task_id():
    tasks = get_open_tasks(limit=1)
    if not tasks:
        raise SystemExit("No open tasks found in the DB.")
    return tasks[0]["task_id"]


def pick_employee_ids(n=2):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT employee_id FROM employees ORDER BY employee_id LIMIT %s", (n,))
            return [r["employee_id"] for r in cur.fetchall()]


if __name__ == "__main__":
    task_id = sys.argv[1] if len(sys.argv) > 1 else pick_task_id()
    print(f"\n=== score_pair for task {task_id} ===")
    for emp_id in pick_employee_ids():
        try:
            print(emp_id, "->", score_pair(task_id, emp_id))
        except Exception as e:
            print(emp_id, "FAILED:", repr(e))

    print(f"\n=== recommend_top_n for task {task_id} ===")
    try:
        for row in recommend_top_n(task_id, top_n=5):
            print(row)
    except Exception as e:
        print("recommend_top_n FAILED:", repr(e))
