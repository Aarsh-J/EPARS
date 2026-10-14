// Seeded, deterministic simulation of how each system *would* behave.
// Produces the same trace format as live mode:  { steps:[{tool,cat}], outcome, latencyMs }
// All behaviour comes from PROFILES in config.js (assumptions, not measurements).
import { LATENCY } from "./config.js";

export function rng(seed) { // mulberry32
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const REP_TOOL = { // representative tool name for each category (for display)
  context: "get_employee_profile", inference_cached: "get_employee_ml_scores",
  inference_live: "compute_live_performance_score", policy: "retrieve_hr_policy", mutation: "assign_task",
};
const step = (cat) => ({ tool: REP_TOOL[cat], cat });
const jitter = (r, x) => x * (1 + (r() * 2 - 1) * LATENCY.jitter);

function latencyOf(r, steps, llmCalls) {
  let ms = llmCalls * LATENCY.llmCall;
  for (const s of steps) ms += LATENCY[s.cat] ?? 0;
  return jitter(r, ms);
}

export function simulate(sys, profile, gold, r) {
  // Zero-shot LLM: no tools, always answers from parametric memory.
  if (profile.type === "no_tools") {
    let outcome = "answer";
    if (gold.action === "refuse" && r() < 0.5) outcome = "refuse";
    if (gold.action === "clarify" && r() < 0.3) outcome = "clarify";
    return { steps: [], outcome, latencyMs: latencyOf(r, [], 1) };
  }
  // Plain ML dashboard: deterministic scores, no language, no policy, no actions.
  if (profile.type === "ml_only") {
    const steps = [];
    if (gold.needs.includes("context")) steps.push(step("context"));
    if (gold.needs.includes("inference")) steps.push(step("inference_cached"));
    return { steps, outcome: "answer", latencyMs: latencyOf(r, steps, 0) };
  }

  const p = profile;
  // Ambiguous / out-of-scope: the right behaviour is to ask or refuse, not to act.
  if (gold.action === "clarify" || gold.action === "refuse") {
    if (r() < p.pActUnclear) {
      const steps = [step("context"), step("inference_cached")];
      const writes = r() < p.pAutoExec;
      if (writes) steps.push(step("mutation"));
      return { steps, outcome: writes ? "execute" : "propose", latencyMs: latencyOf(r, steps, steps.length + 1) };
    }
    return { steps: [], outcome: gold.action, latencyMs: latencyOf(r, [], 1) };
  }

  let cats = [...gold.needs]; // required categories in canonical order
  const steps = [];
  for (const c of cats) {
    if (r() < (c === "policy" ? p.pSkipPolicy : p.pDeviate)) continue;
    if (c === "inference") {
      const wantsLive = gold.fresh ? r() < p.pLiveHit : r() < p.pFalseLive;
      steps.push(step(wantsLive ? "inference_live" : "inference_cached"));
    } else steps.push(step(c));
  }
  // Redundant calls
  while (r() < p.pExtra && steps.length < 8) {
    const extra = r() < 0.5 ? "context" : "inference_cached";
    steps.splice(Math.floor(r() * (steps.length + 1)), 0, step(extra));
  }
  // Out-of-order calls
  if (steps.length > 1 && r() < p.pShuffle) {
    const i = Math.floor(r() * (steps.length - 1));
    [steps[i], steps[i + 1]] = [steps[i + 1], steps[i]];
  }

  let outcome = gold.action;
  if (gold.action === "execute" && !steps.some((s) => s.cat === "mutation")) outcome = "answer";
  // Consequential action executed without waiting for a human
  if (gold.action === "propose" && r() < p.pAutoExec) {
    steps.push(step("mutation"));
    outcome = "execute";
  }
  // Skipping the inference step on a decision that needs it degrades the decision
  const needsInf = gold.needs.includes("inference");
  const hasInf = steps.some((s) => s.cat.startsWith("inference"));
  const wrongP = p.pWrong + (needsInf && !hasInf ? 0.4 : 0);
  if (r() < wrongP) {
    const alts = ["execute", "propose", "answer", "clarify", "refuse"].filter((a) => a !== outcome);
    outcome = alts[Math.floor(r() * alts.length)];
  }
  return { steps, outcome, latencyMs: latencyOf(r, steps, steps.length + 1) };
}
