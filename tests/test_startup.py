import subprocess
import sys
import unittest
from pathlib import Path


class StartupTests(unittest.TestCase):
    def test_health_and_routes_load_without_ml_or_agent_libraries(self):
        backend_root = Path(__file__).resolve().parents[1]
        script = """
import sys
import modules.main as main

heavy_modules = {
    "numpy", "pandas", "sklearn", "torch", "sentence_transformers",
    "langchain_groq", "langgraph", "googleapiclient.discovery",
}
assert not (heavy_modules & sys.modules.keys())

from fastapi.testclient import TestClient
with TestClient(main.app) as client:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

paths = main.app.openapi()["paths"]
required = {
    "/api/auth/login",
    "/api/performance/analyse",
    "/api/burnout/analyse",
    "/api/agent/query",
    "/api/task_assignment/recommend/{task_id}",
    "/api/team_formation/recommend/{project_id}",
    "/health",
}
assert required <= paths.keys(), required - paths.keys()
assert not (heavy_modules & sys.modules.keys())
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=backend_root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
