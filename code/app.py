"""
app.py — EPARS Flask entry point
Run:  python app.py
"""

from flask import Flask
from modules.performance.routes import performance_bp

app = Flask(__name__)
app.secret_key = "epars-secret-key"

# ── Register module blueprints ─────────────────────────────────────────────
app.register_blueprint(performance_bp, url_prefix="/performance")

# Future modules — uncomment as you add them:
# from modules.task_assignment.routes import task_bp
# app.register_blueprint(task_bp, url_prefix="/task_assignment")

# from modules.workload_risk.routes import workload_bp
# app.register_blueprint(workload_bp, url_prefix="/workload")

# from modules.team_formation.routes import team_bp
# app.register_blueprint(team_bp, url_prefix="/team_formation")

# ── Home route ─────────────────────────────────────────────────────────────
from flask import render_template

@app.route("/")
def home():
    return render_template("dashboard.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
