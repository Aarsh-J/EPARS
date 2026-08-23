"""
inference.py
────────────────────────────────────────────────────────────────────────────────
Task Assignment — Inference
────────────────────────────────────────────────────────────────────────────────
Scores an (task_id, employee_id) pair using the trained Layer 1 (classifier)
and Layer 2 (regressor) models.

IMPORTANT LIMITATION — read before wiring this into an API:
This module looks up a row from artifacts/master_preprocessed.csv, it does
NOT compute features from scratch for an arbitrary task/employee pair. That
csv is built from *historical* task_assignments.csv records, so features
like skill_match_score, availability_match_score, workload_compatibility_score
and experience_match_score are values that were already computed for a
specific past assignment — they are not derivable for a task/employee pair
that has never been assigned together.

Practically this means:
  - score_assignment(task_id, employee_id) only works for pairs that already
    exist as a row in master_preprocessed.csv (i.e. "what would the model
    have said about this real historical assignment").
  - recommend_employees(task_id, top_n) only ranks employees who already
    have a historical assignment record for that task_id — it cannot
    consider an employee who was never assigned to that task.
  - A true "assign anyone to anything" scorer needs a feature-computation
    step (match scores between a task's required_skills/required_role and
    an arbitrary employee's profile) that doesn't exist yet. That's exactly
    the job of the Layer 3 heuristic scheduler — build match-score
    computation there, or split it out before this module can score novel
    pairs.

Run standalone for a demo:  python inference.py
"""

import os
import json
import pandas as pd
import joblib

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS   = os.path.join(BASE_DIR, "artifacts")
MASTER_PATH = os.path.join(ARTIFACTS, "master_preprocessed.csv")
CLF_PATH    = os.path.join(ARTIFACTS, "best_classifier.pkl")
REG_PATH    = os.path.join(ARTIFACTS, "best_regressor.pkl")

ID_COLS    = ["assignment_id", "task_id", "employee_id", "project_id"]
TARGET_CLF = "assignment_success"
TARGET_REG = "delay_risk_score"

_master = None
_clf = None
_reg = None


def _load():
    global _master, _clf, _reg
    if _master is None:
        if not os.path.isfile(MASTER_PATH):
            raise FileNotFoundError(f"{MASTER_PATH} not found — run preprocessing.py first.")
        _master = pd.read_csv(MASTER_PATH)
    if _clf is None:
        if not os.path.isfile(CLF_PATH):
            raise FileNotFoundError(f"{CLF_PATH} not found — run train.py then save_models.py first.")
        _clf = joblib.load(CLF_PATH)
    if _reg is None:
        if not os.path.isfile(REG_PATH):
            raise FileNotFoundError(f"{REG_PATH} not found — run train.py then save_models.py first.")
        _reg = joblib.load(REG_PATH)
    return _master, _clf, _reg


def _delay_risk_label(score: float) -> str:
    if score < 25:
        return "Low"
    elif score < 50:
        return "Moderate"
    elif score < 75:
        return "High"
    return "Critical"


def _recommendation(success_prob: float, delay_score: float) -> str:
    if success_prob >= 70 and delay_score < 35:
        return "Strong match — recommend assigning."
    if success_prob >= 50 and delay_score < 60:
        return "Reasonable match — assign with normal monitoring."
    if success_prob < 50 and delay_score >= 60:
        return "Poor match — high risk of both failure and delay. Consider alternatives."
    return "Mixed signals — review manually before assigning."


def _feature_row(row: pd.Series, model) -> pd.DataFrame:
    """Align a master_preprocessed.csv row to the exact feature order the model was trained on."""
    if hasattr(model, "feature_names_in_"):
        cols = list(model.feature_names_in_)
    else:
        cols = [c for c in row.index if c not in ID_COLS + [TARGET_CLF, TARGET_REG]]
    return pd.DataFrame([row[cols].values], columns=cols)


def score_assignment(task_id: str, employee_id: str) -> dict:
    """
    Score a single historical (task_id, employee_id) pair.
    Returns a JSON-serializable dict with both model outputs and a
    human-readable verdict. Raises ValueError if no such assignment
    record exists in master_preprocessed.csv.
    """
    master, clf, reg = _load()

    match = master[(master["task_id"] == task_id) & (master["employee_id"] == employee_id)]
    if match.empty:
        raise ValueError(
            f"No assignment record found for task_id={task_id!r}, employee_id={employee_id!r}. "
            "This inference module only scores pairs that exist in master_preprocessed.csv — "
            "see the module docstring."
        )
    row = match.iloc[0]

    clf_X = _feature_row(row, clf)
    reg_X = _feature_row(row, reg)

    pred_success = int(clf.predict(clf_X)[0])
    proba = clf.predict_proba(clf_X)[0]
    success_prob = round(float(proba[1]) * 100, 1)  # P(class==1) as a %

    delay_score = round(float(reg.predict(reg_X)[0]), 1)
    delay_label = _delay_risk_label(delay_score)

    return {
        "task_id": task_id,
        "employee_id": employee_id,
        "assignment_success": pred_success,
        "success_probability": success_prob,
        "delay_risk_score": delay_score,
        "delay_risk_label": delay_label,
        "recommendation": _recommendation(success_prob, delay_score),
    }


def recommend_employees(task_id: str, top_n: int = 3) -> list:
    """
    Rank employees who have a historical assignment record for this task
    by predicted success probability (ties broken by lower delay risk).
    Only considers employees already present in master_preprocessed.csv
    for this task — see module docstring for why.
    """
    master, clf, reg = _load()

    candidates = master[master["task_id"] == task_id]
    if candidates.empty:
        raise ValueError(f"No assignment records found for task_id={task_id!r}.")

    scored = []
    for _, row in candidates.iterrows():
        result = score_assignment(task_id, row["employee_id"])
        scored.append(result)

    scored.sort(key=lambda r: (-r["success_probability"], r["delay_risk_score"]))
    return scored[:top_n]


if __name__ == "__main__":
    master, clf, reg = _load()
    print(f"Loaded {len(master):,} historical assignment records.")

    demo_row = master.iloc[0]
    task_id, employee_id = demo_row["task_id"], demo_row["employee_id"]

    print(f"\nDemo: scoring task_id={task_id}, employee_id={employee_id}")
    result = score_assignment(task_id, employee_id)
    print(json.dumps(result, indent=2))

    print(f"\nDemo: top employees on record for task_id={task_id}")
    top = recommend_employees(task_id, top_n=3)
    print(json.dumps(top, indent=2))
