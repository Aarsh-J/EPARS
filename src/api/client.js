const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail || body.error;
    throw new Error(
      typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `Request failed: ${res.status}`
    );
  }
  return res.json();
}

export function getEmployees() {
  return request("/api/performance/employees");
}

export function getEmployeeDetail(employeeId) {
  return request(`/api/performance/employees/${encodeURIComponent(employeeId)}`);
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

export function getBurnoutEmployeeDetail(employeeId) {
  return request(`/api/burnout/employees/${encodeURIComponent(employeeId)}`);
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

export function updateTaskStatus(taskId, status) {
  return request(`/api/task_assignment/tasks/${encodeURIComponent(taskId)}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export function createKanbanTask(task) {
  return request("/api/task_assignment/tasks", {
    method: "POST",
    body: JSON.stringify(task),
  });
}

export function updateKanbanTask(taskId, changes) {
  return request(`/api/task_assignment/tasks/${encodeURIComponent(taskId)}`, {
    method: "PUT",
    body: JSON.stringify(changes),
  });
}

export function assignKanbanTask(taskId, employeeId) {
  return request(`/api/task_assignment/tasks/${encodeURIComponent(taskId)}/assign`, {
    method: "POST",
    body: JSON.stringify({ employee_id: employeeId }),
  });
}

export function deleteKanbanTask(taskId) {
  return request(`/api/task_assignment/tasks/${encodeURIComponent(taskId)}`, {
    method: "DELETE",
  });
}

export function getKanbanProjects() {
  return request("/api/task_assignment/board_projects");
}

export function getKanbanEmployees() {
  return request("/api/task_assignment/board_employees");
}

export function getKanbanBoard({
  projectIds = [],
  includeOtherTasks = false,
  projectView = "active",
  employeeId = "",
  unassignedOnly = false,
  dateFilter = "all",
  startDate = "",
  endDate = "",
  search = "",
  statusFilter = "",
  priorityFilter = "",
  highPriorityOnly = false,
  sortBy = "due_date",
  sortOrder = "asc",
  page = 1,
  pageSize = 50,
} = {}) {
  const params = new URLSearchParams({
    include_other_tasks: String(includeOtherTasks),
    project_view: projectView,
    date_filter: dateFilter,
    sort_by: sortBy,
    sort_order: sortOrder,
    page: String(page),
    page_size: String(pageSize),
  });
  projectIds.forEach((projectId) => params.append("project_ids", projectId));
  if (employeeId && employeeId !== "all" && employeeId !== "unassigned") {
    params.set("employee_id", employeeId);
  }
  if (unassignedOnly || employeeId === "unassigned") params.set("unassigned_only", "true");
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  if (search.trim()) params.set("search", search.trim());
  if (statusFilter) params.set("status_filter", statusFilter);
  if (priorityFilter) params.set("priority_filter", priorityFilter);
  if (highPriorityOnly) params.set("high_priority_only", "true");
  return request(`/api/task_assignment/board?${params.toString()}`);
}

export function getProjectsWithOpenTasks(limit = 200) {
  return request(`/api/team_formation/projects?limit=${limit}`);
}

export function recommendTeams(projectId, numTeams = 3, topM = 5, taskIds = null) {
  let url = `/api/team_formation/recommend/${encodeURIComponent(projectId)}?num_teams=${numTeams}&top_m=${topM}`;
  if (taskIds && taskIds.length > 0) {
    url += `&task_ids=${encodeURIComponent(taskIds.join(","))}`;
  }
  return request(url);
}

export function confirmTeamFormation(projectId, recommendation, teamLeadId) {
  return request(`/api/team_formation/confirm/${encodeURIComponent(projectId)}`, {
    method: "POST",
    body: JSON.stringify({
      recommendation,
      team_lead_id: teamLeadId,
    }),
  });
}

export function checkTeamComposition(employeeIds) {
  const idsStr = Array.isArray(employeeIds) ? employeeIds.join(",") : employeeIds;
  return request(`/api/team_formation/composition?employee_ids=${encodeURIComponent(idsStr)}`);
}
