"""
modules/performance/routes.py
Flask blueprint for the Performance Evaluation module.
"""

from flask import Blueprint, render_template, request, jsonify
from .model import get_employee_list, analyse_employee

performance_bp = Blueprint("performance", __name__)


@performance_bp.route("/")
def index():
    """Performance module home — employee selector."""
    employees = get_employee_list()
    return render_template("modules/performance.html", employees=employees)


@performance_bp.route("/api/analyse", methods=["POST"])
def api_analyse():
    """
    POST  { employee_id, review_id (optional) }
    Returns full performance analysis as JSON.
    """
    data        = request.get_json()
    employee_id = data.get("employee_id")
    review_id   = data.get("review_id")

    if not employee_id:
        return jsonify({"error": "employee_id is required"}), 400

    result = analyse_employee(employee_id, review_id)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result)


@performance_bp.route("/api/employees")
def api_employees():
    """Return full employee list as JSON (for search/filter)."""
    return jsonify(get_employee_list())