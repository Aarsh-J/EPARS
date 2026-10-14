// ─────────────────────────────────────────────────────────────────────────────
// Central configuration. Everything you may need to edit lives in this file.
// ─────────────────────────────────────────────────────────────────────────────

// Canonical order of the four tool categories used in the paper's "action spaces".
export const ORDER = ["context", "inference", "policy", "mutation"];

// Map backend tool names → category. Used by LIVE mode to read `steps[].tool`.
// ⚠ VERIFY against src/epars_agent/agent/tools.py on dev-backend and add every
//   one of the 15 tools. Unknown tools are ignored (and listed in the live report).
export const TOOL_MAP = {
  get_task_details:               "context",
  get_employee_profile:           "context",
  get_employee_workload:          "context",
  find_candidates:                "context",
  get_employee_ml_scores:         "inference_cached", // stored (cached) score
  compute_live_performance_score: "inference_live",   // fresh model inference
  compute_live_burnout_score:     "inference_live",
  score_task_assignment:          "inference_live",
  retrieve_hr_policy:             "policy",           // pgvector RAG
  assign_task:                    "mutation",
  reassign_task:                  "mutation",
  create_calendar_event:          "mutation",
  record_burnout_assessment:      "mutation",
};

export const category = (tool) => TOOL_MAP[tool] ?? null;
export const collapse = (c) => (c && c.startsWith("inference") ? "inference" : c);

// Latency model used in SIMULATION mode only (milliseconds). ← ASSUMPTIONS
export const LATENCY = {
  llmCall: 900, // one ReAct iteration / one LLM completion
  context: 25,
  inference_cached: 15,
  inference_live: 350,
  policy: 120,
  mutation: 60,
  jitter: 0.15, // ±15 %
};

export const DEFAULTS = { trials: 200, seed: 42 };

// Display metadata for every system. kind: ours | baseline | ablation
export const SYSTEMS = {
  epars:         { label: "ePARS (bounded workflow)",   kind: "ours",     color: "#2563eb" },
  open_react:    { label: "Open-ended ReAct agent",     kind: "baseline", color: "#d97706" },
  zero_shot:     { label: "Zero-shot LLM (no tools)",   kind: "baseline", color: "#94a3b8" },
  ml_only:       { label: "ML dashboard only",          kind: "baseline", color: "#0d9488" },
  epars_no_rag:  { label: "ePARS − RAG policy gate",    kind: "ablation", color: "#93c5fd" },
  epars_no_hitl: { label: "ePARS − human confirmation", kind: "ablation", color: "#a5b4fc" },
};

// ─────────────────────────────────────────────────────────────────────────────
// SIMULATION PROFILES — these are ASSUMPTIONS, not measurements.
// They describe how each system is *expected* to behave and are printed in every
// report. Change them to test sensitivity; replace with real data via `--live`.
//   pDeviate     chance an agent skips a required tool step
//   pSkipPolicy  chance the policy (RAG) step is skipped
//   pExtra       chance of redundant tool calls
//   pShuffle     chance of out-of-order calls
//   pAutoExec    chance a "propose-only" action is executed without confirmation
//   pLiveHit     chance of choosing live inference when freshness matters
//   pFalseLive   chance of choosing live inference when it is not needed
//   pActUnclear  chance of acting on an ambiguous / out-of-scope request
//   pWrong       chance the final decision class is wrong for other reasons
// ─────────────────────────────────────────────────────────────────────────────
export const PROFILES = {
  epars:         { type: "agent", pDeviate: 0.04, pSkipPolicy: 0.06, pExtra: 0.05, pShuffle: 0.03, pAutoExec: 0.0,  pLiveHit: 0.85, pFalseLive: 0.10, pActUnclear: 0.10, pWrong: 0.04 },
  open_react:    { type: "agent", pDeviate: 0.18, pSkipPolicy: 0.45, pExtra: 0.35, pShuffle: 0.15, pAutoExec: 0.80, pLiveHit: 0.50, pFalseLive: 0.35, pActUnclear: 0.55, pWrong: 0.14 },
  epars_no_rag:  { type: "agent", pDeviate: 0.04, pSkipPolicy: 1.0,  pExtra: 0.05, pShuffle: 0.03, pAutoExec: 0.0,  pLiveHit: 0.85, pFalseLive: 0.10, pActUnclear: 0.10, pWrong: 0.10 },
  epars_no_hitl: { type: "agent", pDeviate: 0.04, pSkipPolicy: 0.06, pExtra: 0.05, pShuffle: 0.03, pAutoExec: 0.85, pLiveHit: 0.85, pFalseLive: 0.10, pActUnclear: 0.10, pWrong: 0.04 },
  zero_shot:     { type: "no_tools" },
  ml_only:       { type: "ml_only" },
};

// Cached-vs-live routing simulation parameters. ← ASSUMPTIONS
export const ROUTING = {
  employees: 100,
  requests: 2000,
  horizonHours: 24 * 14,
  dataChangePerDay: 0.6,   // how often an employee's inputs change
  cacheRefreshHours: 24,   // nightly batch refresh of stored scores
  ttlHours: 6,             // hybrid: tolerate cache up to this age
  highStakesShare: 0.25,
  routerErrorRate: 0.10,   // LLM mis-judges whether live is needed
};

// Train/serve skew experiment parameters (this one is a REAL computation).
export const DRIFT = { trainRows: 5000, serveRows: 200, rowThresholdSigma: 6, batchK: 4 };
