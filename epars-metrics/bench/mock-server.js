// A tiny stand-in for POST /api/agent/query so you can test `npm run bench:live`
// without the real backend. It answers with keyword-based canned traces — its numbers
// mean NOTHING about ePARS. Run:  npm run mock   (port 8001)
import http from "node:http";

const T = (...tools) => tools.map((tool) => ({ tool, output: "{}" }));
function respond(q) {
  const s = q.toLowerCase();
  if (/terminate|delete|raise/.test(s)) return { output: "I'm not permitted to do that.", steps: [] };
  if (/fix the|usual person|do the thing/.test(s)) return { output: "Which employee or task do you mean?", steps: [] };
  if (/policy|allowed|approves|consecutive/.test(s)) return { output: "Per policy HR-12 …", steps: T("retrieve_hr_policy") };
  if (/exhausted|check-in|weekends|recovery|move emp|burnout review/.test(s))
    return { output: "I recommend this. Shall I go ahead? Please confirm.", steps: T("get_employee_profile", "compute_live_burnout_score", "retrieve_hr_policy") };
  if (/^assign|assign tsk|assign the/.test(s))
    return { output: "Assigned.", steps: T("get_task_details", "get_employee_ml_scores", "retrieve_hr_policy", "assign_task") };
  if (/performance|promotion/.test(s)) return { output: "Score is 78.", steps: T("get_employee_profile", "get_employee_ml_scores") };
  return { output: "Here is the info.", steps: T("get_employee_profile") };
}

http.createServer((req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.method === "POST" && req.url === "/api/agent/query") {
    let b = ""; req.on("data", (d) => (b += d));
    req.on("end", () => {
      const { query } = JSON.parse(b || "{}");
      setTimeout(() => { res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify({ input: query, ...respond(query) })); }, 80);
    });
  } else { res.statusCode = 404; res.end(); }
}).listen(8001, () => console.log("Mock agent on http://localhost:8001  (not real ePARS)"));
