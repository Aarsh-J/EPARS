const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed: ${res.status}`);
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
