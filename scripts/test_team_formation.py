"""
Throwaway harness: sanity-checks Model4 (team formation + composition detector)
live inference against the DB.
Run: python scripts/test_team_formation.py [project_id]
"""
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR / "epars_agent" / "agent"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.ml.team_formation_features import list_projects_with_open_tasks
from modules.ml.team_formation_predict import check_composition, recommend_teams


def pick_project_id():
    projects = list_projects_with_open_tasks(limit=500)
    # a small project (exact search) keeps the demo fast
    small = [p for p in projects if 3 <= p["open_task_count"] <= 6]
    if not (small or projects):
        raise SystemExit("No projects with open tasks found in the DB.")
    return (small or projects)[0]["project_id"]


if __name__ == "__main__":
    project_id = sys.argv[1] if len(sys.argv) > 1 else pick_project_id()
    print(f"\n=== recommend_teams for project {project_id} ===")
    t0 = time.time()
    try:
        teams = recommend_teams(project_id, top_m=5, num_teams=3)
    except Exception as e:
        raise SystemExit(f"recommend_teams FAILED: {e!r}")
    print(f"{len(teams)} team(s), search_mode={teams[0]['search_mode']}, {time.time() - t0:.1f}s")
    for i, t in enumerate(teams, 1):
        print(f"\n#{i} team_score={t['team_score']} unusual_composition={t['unusual_composition']}")
        print("  breakdown:", t["score_breakdown"])
        print("  members  :", [a["employee_id"] for a in t["assignments"]])
        if t.get("composition_notes"):
            print("  notes    :", t["composition_notes"])

    print("\n=== check_composition on the best team's members ===")
    print(check_composition([a["employee_id"] for a in teams[0]["assignments"]]))