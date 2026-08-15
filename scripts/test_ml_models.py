"""
Throwaway harness: sanity-checks live inference against a few real employees.
Run: python scripts/test_ml_models.py [employee_id ...]
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR / "epars_agent" / "agent"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_connection
from modules.ml.predict import predict_performance, predict_burnout


def pick_employee_ids(n=3):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT employee_id FROM employees ORDER BY employee_id LIMIT %s", (n,))
            return [r["employee_id"] for r in cur.fetchall()]


if __name__ == "__main__":
    ids = sys.argv[1:] or pick_employee_ids()
    for emp_id in ids:
        print(f"\n=== {emp_id} ===")
        try:
            perf = predict_performance(emp_id)
            print("performance:", perf)
        except Exception as e:
            print("performance FAILED:", repr(e))
        try:
            burn = predict_burnout(emp_id)
            print("burnout:", burn)
        except Exception as e:
            print("burnout FAILED:", repr(e))
