"""
composition_model.py  —  Model 4 (trained component): team-composition anomaly detector
────────────────────────────────────────────────────────────────────────────
Question answered: "Does this candidate team's composition look like how teams
are actually staffed in team_formations.csv, or is it an outlier?"

No outcome label is needed (team_formations.csv outcome columns are noise), so
this is UNSUPERVISED: an Isolation Forest fit on the composition of the ~1000
real historical teams.

Train/serve consistency: the SAME function (team_features) computes features
for historical teams (training) and for candidate teams (inference), straight
from employees.csv. Nothing is read from the pre-computed team_formations
score columns, so there is no scale mismatch between training and serving.

Public API
    team_features(employee_ids)            -> dict of composition features
    CompositionModel.load()                -> loads artifacts/composition_model.joblib
    model.typicality(employee_ids)         -> 0-100 (100 = very typical, 0 = outlier)
    model.is_anomalous(employee_ids)       -> bool (below the training-set 5th percentile)
"""
import os
import numpy as np
import pandas as pd
import joblib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "../../dataset")
ARTIFACT_PATH = os.path.join(BASE_DIR, "artifacts", "composition_model.joblib")

SENIORITY_RANK = {"Junior": 1, "Mid": 2, "Senior": 3, "Lead": 4, "Principal": 5}

# n (team size) is deliberately NOT a feature: candidate teams have one person
# per task and can be larger/smaller than historical 3-10. Every feature below
# is a ratio/mean so it stays comparable across sizes.
FEATURE_COLUMNS = [
    "dominant_dept_share", "n_dept_ratio",
    "seniority_mean", "seniority_std",
    "frac_Junior", "frac_Mid", "frac_Senior", "frac_Lead", "frac_Principal",
    "yoe_mean", "yoe_std", "tech_mean", "collab_mean", "burnout_mean",
    "skill_breadth_per_member",
]

_emp = None


def _employees() -> dict:
    """employee_id -> plain-dict record. Built once per process; plain dict
    lookups keep per-team feature computation cheap enough for exact-mode
    search (thousands of candidate teams)."""
    global _emp
    if _emp is None:
        df = pd.read_csv(os.path.join(DATASET_DIR, "employees.csv"))
        _emp = {}
        for r in df.itertuples(index=False):
            skills = (str(r.primary_skills) if pd.notna(r.primary_skills) else "") + "," + \
                     (str(r.secondary_skills) if pd.notna(r.secondary_skills) else "")
            _emp[r.employee_id] = {
                "dept": r.department, "level": r.seniority_level,
                "sr": SENIORITY_RANK.get(r.seniority_level, 2),
                "yoe": float(r.years_of_experience), "tech": float(r.technical_proficiency_score),
                "collab": float(r.collaboration_score),
                "burn": float(r.burnout_risk_score) if pd.notna(r.burnout_risk_score) else 30.0,
                "skills": set(x.strip().lower() for x in skills.split(",") if x.strip()),
            }
    return _emp


def employee_ids_known() -> set:
    return set(_employees().keys())


def team_features(employee_ids) -> dict:
    emp = _employees()
    recs = [emp[i] for i in dict.fromkeys(employee_ids) if i in emp]
    n = len(recs)
    if n == 0:
        raise ValueError("No known employee_ids in team.")
    depts = {}
    for r in recs:
        depts[r["dept"]] = depts.get(r["dept"], 0) + 1
    sr = np.array([r["sr"] for r in recs], dtype=float)
    yoe = np.array([r["yoe"] for r in recs])
    skills = set()
    for r in recs:
        skills |= r["skills"]
    f = {
        "dominant_dept_share": max(depts.values()) / n,
        "n_dept_ratio": len(depts) / n,
        "seniority_mean": sr.mean(),
        "seniority_std": sr.std(),
        "yoe_mean": yoe.mean(),
        "yoe_std": yoe.std(),
        "tech_mean": float(np.mean([r["tech"] for r in recs])),
        "collab_mean": float(np.mean([r["collab"] for r in recs])),
        "burnout_mean": float(np.mean([r["burn"] for r in recs])),
        "skill_breadth_per_member": len(skills) / n,
    }
    for k in SENIORITY_RANK:
        f[f"frac_{k}"] = sum(1 for r in recs if r["level"] == k) / n
    return f


def historical_team_members(row) -> list:
    members = [m.strip() for m in str(row["member_ids"]).split(",") if m.strip()]
    lead = row.get("team_lead_id")
    if pd.notna(lead):
        members.append(lead)
    return list(dict.fromkeys(members))


class CompositionModel:
    def __init__(self, scaler, forest, score_lo, score_hi, anomaly_threshold):
        self.scaler, self.forest = scaler, forest
        self.score_lo, self.score_hi = score_lo, score_hi      # training-set score range for 0-100 mapping
        self.anomaly_threshold = anomaly_threshold             # 5th percentile of training scores (0-100)

    @classmethod
    def load(cls, path: str = ARTIFACT_PATH) -> "CompositionModel":
        return joblib.load(path)

    def typicality_many(self, teams) -> np.ndarray:
        """teams: list of employee-id lists. One vectorised forest call."""
        X = pd.DataFrame([team_features(t) for t in teams])[FEATURE_COLUMNS]
        raw = self.forest.score_samples(self.scaler.transform(X))
        return np.clip((raw - self.score_lo) / (self.score_hi - self.score_lo) * 100.0, 0.0, 100.0)

    def typicality(self, employee_ids) -> float:
        return float(self.typicality_many([employee_ids])[0])

    def is_anomalous(self, employee_ids) -> bool:
        return self.typicality(employee_ids) < self.anomaly_threshold