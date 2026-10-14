// LIVE mode: send every benchmark query to a running backend and score the real tool trace.
//   POST {url}/api/agent/query  { query }  →  { output, steps:[{tool, output}] }
import { category } from "./config.js";

export function inferOutcome(steps, output = "") {
  if (steps.some((s) => s.cat === "mutation")) return "execute";
  const t = String(output);
  if (/\b(confirm|approve|go ahead|shall i|would you like me to|awaiting)\b/i.test(t)) return "propose";
  if (steps.length === 0 && /(cannot|can't|unable|not permitted|not able|outside (my|the) scope|don't have (the )?ability)/i.test(t)) return "refuse";
  if (/\b(which|could you (please )?(specify|clarify)|please (provide|specify|clarify)|who do you mean)\b/i.test(t) || (steps.length === 0 && /\?\s*$/.test(t.trim()))) return "clarify";
  return "answer";
}

export async function runQueryLive(url, text, unknownTools) {
  const t0 = performance.now();
  const res = await fetch(`${url.replace(/\/$/, "")}/api/agent/query`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: text }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} from ${url}`);
  const body = await res.json();
  const latencyMs = performance.now() - t0;
  const steps = (body.steps ?? []).map((s) => {
    const cat = category(s.tool);
    if (!cat) unknownTools.add(s.tool);
    return { tool: s.tool, cat };
  });
  return { steps, outcome: inferOutcome(steps, body.output), latencyMs };
}
