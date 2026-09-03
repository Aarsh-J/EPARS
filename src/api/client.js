const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.error || `Request failed: ${res.status}`);
  }
  return res.json();
}

export function getEmployees() {
  return request("/api/performance/employees");
}

export function analyseEmployee(employeeId, reviewId = null) {
  return request("/api/performance/analyse", {
    method: "POST",
    body: JSON.stringify({ employee_id: employeeId, review_id: reviewId }),
  });
}

export function finalizePerformanceScore(employeeId, reviewId, decision, finalScore, aiData, note) {
  return request("/api/performance/finalize", {
    method: "POST",
    body: JSON.stringify({
      employee_id: employeeId,
      review_id: reviewId,
      decision,
      final_score: finalScore,
      ai_predicted_score: aiData.ai_predicted_score,
      ai_confidence: aiData.ai_confidence,
      ai_justification: aiData.justification,
      policy_citation: aiData.policy_citation,
      manager_note: note || null,
    }),
  });
}

export function getPastEvaluations(employeeId) {
  return request(`/api/performance/evaluations/${employeeId}`);
}

export function getBurnoutEmployees() {
  return request("/api/burnout/employees");
}

export function analyseBurnout(employeeId) {
  return request("/api/burnout/analyse", {
    method: "POST",
    body: JSON.stringify({ employee_id: employeeId }),
  });
}

export function queryAgent(query) {
  return request("/api/agent/query", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export function verifyBurnoutAssessment(assessmentId) {
  return request(`/api/burnout/assessments/${assessmentId}/verify`, {
    method: "POST",
  });
}

export function decideReassignment(recommendationId, decision) {
  return request(`/api/burnout/recommendations/${recommendationId}/decide`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}

export function getOpenTasks() {
  return request("/api/task_assignment/tasks");
}

export function scoreTaskAssignment(taskId, employeeId) {
  return request(`/api/task_assignment/score?task_id=${encodeURIComponent(taskId)}&employee_id=${encodeURIComponent(employeeId)}`);
}

export function recommendForTask(taskId, topN = 5) {
  return request(`/api/task_assignment/recommend/${encodeURIComponent(taskId)}?top_n=${topN}`);
}
