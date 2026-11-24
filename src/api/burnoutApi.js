const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const PREFIX = `${BASE}/api/burnout`;

async function handle(res) {
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}
const post = (path, body) =>
  fetch(`${PREFIX}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(handle);

export const scanBurnout = () => fetch(`${PREFIX}/scan`).then(handle);
export const executeTask = (assignment_id) => post("execute", { assignment_id });
export const logAlert = (employee_id) => post("alert", { employee_id });