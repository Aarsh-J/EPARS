import { request } from "./client.js";

const PREFIX = "/api/burnout";
const post = (path, body) =>
  request(`${PREFIX}/${path}`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const scanBurnout = () => request(`${PREFIX}/scan`);
export const executeTask = (assignment_id) => post("execute", { assignment_id });
export const logAlert = (employee_id) => post("alert", { employee_id });