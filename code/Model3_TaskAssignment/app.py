"""
app.py
────────────────────────────────────────────────────────────────────────────────
Task Assignment — Flask API
────────────────────────────────────────────────────────────────────────────────
Exposes inference.py (Layer 1/2 — scores HISTORICAL task/employee pairs that
already exist in master_preprocessed.csv) and scheduler.py (Layer 3 — ranks
ANY employee against a task, no assignment history required) as HTTP
endpoints for the rest of EPARS to call.

Endpoints
─────────
GET  /health
    Liveness check. Also confirms all model artifacts loaded successfully.

POST /api/v1/assignments/score
    body: {"task_id": "...", "employee_id": "..."}
    Scores a pair that has an existing historical assignment record.
    404 if that exact task/employee pair was never actually assigned.

POST /api/v1/assignments/recommend
    body: {"task_id": "...", "top_n": 3}
    Ranks only employees who ALREADY have a historical assignment record
    for this task. Narrow — see /api/v1/scheduler/rank for the general case.

POST /api/v1/scheduler/score
    body: {"task_id": "...", "employee_id": "..."}
    Layer 3: scores ANY pair, assigned before or not. Uses the delay-risk
    regressor + heuristics (skill fit, availability, reliability, health) —
    deliberately does not use the assignment_success classifier, which
    tests showed has ~no predictive value once assignment-specific
    features are removed (AUC 0.58 on held-out data).

POST /api/v1/scheduler/rank
    body: {"task_id": "...", "top_n": 3, "candidate_pool": ["EMP001", ...]}
    Layer 3: ranks employees for a task. Omit candidate_pool to rank
    against ALL employees in employee_profile.csv (~1,500 in this dataset).
    This is the endpoint the rest of EPARS should call for real scheduling
    decisions — it's the only one not limited to past assignments.

GET  /api/v1/meta
    Reports which models are loaded and their last-measured test metrics,
    pulled from the results CSVs written by train.py / train_novel_pair_models.py.

Run (dev):   python app.py
Run (prod):  gunicorn -w 2 -b 0.0.0.0:5000 app:app
"""

import os
import warnings
import pandas as pd
from flask import Flask, request, jsonify

import inference
import scheduler

warnings.filterwarnings("ignore")

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(BASE_DIR, "artifacts")

app = Flask(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _json_body() -> dict:
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    return data


def _require(data: dict, *fields):
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required field(s): {', '.join(missing)}"}), 400
    return None


def _clean_top_n(data: dict, default: int = 3, max_n: int = 50) -> int:
    try:
        n = int(data.get("top_n", default))
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, max_n))


# ─────────────────────────────────────────────────────────────────────────────
# Health / meta
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    try:
        inference._load()
        scheduler._load()
        return jsonify({"status": "ok"}), 200
    except FileNotFoundError as e:
        return jsonify({"status": "degraded", "error": str(e)}), 503


@app.route("/api/v1/meta", methods=["GET"])
def meta():
    def read_csv_safe(name):
        path = os.path.join(ARTIFACTS, name)
        if os.path.isfile(path):
            return pd.read_csv(path).to_dict(orient="records")
        return None

    return jsonify({
        "classification_results": read_csv_safe("results_classification.csv"),
        "regression_results": read_csv_safe("results_regression.csv"),
        "novel_pair_regressor_results": read_csv_safe("novel_pair_regressor_results.csv"),
        "scheduler_weights": scheduler.WEIGHTS,
        "notes": (
            "assignment_success classifier is intentionally NOT used in "
            "/api/v1/scheduler/* endpoints — tested to have ~no predictive "
            "value (AUC 0.58) once assignment-specific features are removed. "
            "It IS used in /api/v1/assignments/score, which only scores "
            "pairs with real assignment history."
        ),
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1/2 — historical pairs only (inference.py)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/v1/assignments/score", methods=["POST"])
def score_assignment():
    data = _json_body()
    err = _require(data, "task_id", "employee_id")
    if err:
        return err
    try:
        result = inference.score_assignment(data["task_id"], data["employee_id"])
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "internal error", "detail": str(e)}), 500


@app.route("/api/v1/assignments/recommend", methods=["POST"])
def recommend_from_history():
    data = _json_body()
    err = _require(data, "task_id")
    if err:
        return err
    top_n = _clean_top_n(data)
    try:
        result = inference.recommend_employees(data["task_id"], top_n=top_n)
        return jsonify({"task_id": data["task_id"], "recommendations": result}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "internal error", "detail": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3 — any pair, no assignment history required (scheduler.py)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/v1/scheduler/score", methods=["POST"])
def score_pair():
    data = _json_body()
    err = _require(data, "task_id", "employee_id")
    if err:
        return err
    try:
        result = scheduler.score_pair(data["task_id"], data["employee_id"])
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "internal error", "detail": str(e)}), 500


@app.route("/api/v1/scheduler/rank", methods=["POST"])
def rank_candidates():
    data = _json_body()
    err = _require(data, "task_id")
    if err:
        return err
    top_n = _clean_top_n(data)
    candidate_pool = data.get("candidate_pool")
    if candidate_pool is not None and not isinstance(candidate_pool, list):
        return jsonify({"error": "candidate_pool must be a list of employee_id strings"}), 400
    try:
        result = scheduler.recommend_top_n(data["task_id"], top_n=top_n, candidate_pool=candidate_pool)
        return jsonify({"task_id": data["task_id"], "recommendations": result}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "internal error", "detail": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Error handlers
# ─────────────────────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found. See module docstring in app.py for available routes."}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed on this route."}), 405


if __name__ == "__main__":
    print("Preloading models/artifacts …")
    inference._load()
    scheduler._load()
    print("Ready. Routes:")
    for rule in app.url_map.iter_rules():
        if rule.endpoint != "static":
            print(f"  {','.join(sorted(rule.methods - {'HEAD','OPTIONS'})):8s} {rule.rule}")
    app.run(host="0.0.0.0", port=5000, debug=True)
