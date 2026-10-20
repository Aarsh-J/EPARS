"""
modules/ml/team_formation_features.py
=========================================
Live-DB data access + composition-feature assembly for Model4 (team formation).
Ported from preprocessor:code/Model4_TeamFormation/{composition_model.py,
team_recommender.py}, which read employees.csv / team_formations.csv / tasks;
here every value comes straight from Postgres, like task_assignment_features.py.

TRAIN/SERVE CONSISTENCY: `team_features()` below must stay identical (same 15
features, same formulas) to composition_model.team_features() on the
preprocessor branch, because the Isolation Forest in
ml_models/team_composition_bundle.pkl was trained on those exact features.
If you change one, change the other and retrain.
"""

import itertools
import time

import numpy as np

from db import get_connection

SENIORITY_RANK = {"Junior": 1, "Mid": 2, "Senior": 3, "Lead": 4, "Principal": 5}

# Feature order is read from the model bundle at predict time; this list is only
# used to build the dict. Kept in sync with the bundle's "feature_columns".
_EMPLOYEE_SQL_COLS = [
    "employee_id", "department", "seniority_level", "years_of_experience",
    "technical_proficiency_score", "collaboration_score", "burnout_risk_score",
    "primary_skills", "secondary_skills",
]

# Skill sets / burnout are cheap to reload per request (1 query, ~1500 rows) and
# burnout_risk_score changes over time, so employee records are NOT cached.
# Historical team pairs only ever grow and take a full table scan, so they get
# a short TTL cache.
_PAIRS_TTL_SECONDS = 600
_pairs_cache: dict = {"at": 0.0, "pairs": None}


def clear_caches() -> None:
    _pairs_cache.update({"at": 0.0, "pairs": None})


def _split_skills(*values) -> set:
    skills = set()
    for v in values:
        skills |= {s.strip().lower() for s in str(v or "").split(",") if s.strip()}
    return skills


def load_employee_records() -> dict:
    """employee_id -> plain dict. One query; plain dicts keep per-team feature
    computation cheap enough for exact-mode search (thousands of rosters)."""
    sql = f"SELECT {', '.join(_EMPLOYEE_SQL_COLS)} FROM employees"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    records = {}
    for r in rows:
        level = r.get("seniority_level")
        records[r["employee_id"]] = {
            "dept": r.get("department"),
            "level": level,
            "sr": SENIORITY_RANK.get(level, 2),
            "yoe": float(r.get("years_of_experience") or 0),
            "tech": float(r.get("technical_proficiency_score") or 50),
            "collab": float(r.get("collaboration_score") or 50),
            # 30.0 = same neutral fallback the training code used for missing burnout.
            "burn": float(r["burnout_risk_score"]) if r.get("burnout_risk_score") is not None else 30.0,
            "skills": _split_skills(r.get("primary_skills"), r.get("secondary_skills")),
        }
    return records


def load_historical_pairs() -> set:
    """Every member-pair that has ever co-occurred in a formed team
    (members + team lead) — a real synergy proxy, unlike the noisy
    collaborative_history_score column."""
    now = time.time()
    if _pairs_cache["pairs"] is not None and now - _pairs_cache["at"] < _PAIRS_TTL_SECONDS:
        return _pairs_cache["pairs"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT member_ids, team_lead_id FROM team_formations")
            rows = cur.fetchall()

    pairs = set()
    for r in rows:
        members = {m.strip() for m in str(r.get("member_ids") or "").split(",") if m.strip()}
        if r.get("team_lead_id"):
            members.add(r["team_lead_id"])
        pairs.update(itertools.combinations(sorted(members), 2))

    _pairs_cache.update({"at": now, "pairs": pairs})
    return pairs


def get_project_tasks(project_id: str, task_ids: list | None = None, include_closed: bool = False) -> list:
    """Tasks a team needs to be built for: [{"task_id", "required_skills"}, ...].

    By default only OPEN tasks (not Completed/Cancelled) — a team is formed for
    work still to be done. Pass task_ids to restrict to a specific subset."""
    sql = "SELECT task_id, required_skills FROM tasks WHERE project_id = %s"
    params: list = [project_id]
    if not include_closed:
        sql += " AND (status IS NULL OR status NOT IN ('Completed', 'Cancelled'))"
    if task_ids:
        sql += " AND task_id = ANY(%s)"
        params.append(list(task_ids))
    sql += " ORDER BY task_id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def list_projects_with_open_tasks(limit: int = 200) -> list:
    """Projects that have open tasks — candidate list for a selector UI."""
    sql = """
        SELECT p.project_id, p.project_name, p.current_status,
               COUNT(t.task_id) AS open_task_count
        FROM projects p
        JOIN tasks t ON t.project_id = p.project_id
        WHERE t.status IS NULL OR t.status NOT IN ('Completed', 'Cancelled')
        GROUP BY p.project_id, p.project_name, p.current_status
        ORDER BY open_task_count DESC, p.project_id
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            return [dict(r) for r in cur.fetchall()]


def team_features(employee_ids, records: dict) -> dict:
    """The 15 composition features the Isolation Forest was trained on.
    Unknown employee_ids are ignored; raises ValueError if none are known."""
    recs = [records[i] for i in dict.fromkeys(employee_ids) if i in records]
    n = len(recs)
    if n == 0:
        raise ValueError("No known employee_ids in team.")

    depts: dict = {}
    for r in recs:
        depts[r["dept"]] = depts.get(r["dept"], 0) + 1
    sr = np.array([r["sr"] for r in recs], dtype=float)
    yoe = np.array([r["yoe"] for r in recs])
    skills: set = set()
    for r in recs:
        skills |= r["skills"]

    f = {
        "dominant_dept_share": max(depts.values()) / n,
        "n_dept_ratio": len(depts) / n,
        "seniority_mean": float(sr.mean()),
        "seniority_std": float(sr.std()),
        "yoe_mean": float(yoe.mean()),
        "yoe_std": float(yoe.std()),
        "tech_mean": float(np.mean([r["tech"] for r in recs])),
        "collab_mean": float(np.mean([r["collab"] for r in recs])),
        "burnout_mean": float(np.mean([r["burn"] for r in recs])),
        "skill_breadth_per_member": len(skills) / n,
    }
    for level in SENIORITY_RANK:
        f[f"frac_{level}"] = sum(1 for r in recs if r["level"] == level) / n
    return f
