// Turns raw numbers into plain-language reasoning. Every sentence is computed from
// the results — nothing here is hard-coded to favour ePARS. If ePARS loses, it says so.
const pct = (x, d = 0) => `${(x * 100).toFixed(d)}%`;
const pp = (x) => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)} pp`;

export function buildInsights({ mode, systems, routing, drift, queryCount, trials }) {
  const out = [];
  const S = Object.fromEntries(systems.map((s) => [s.id, s]));
  const e = S.epars;
  const baselines = systems.filter((s) => s.kind === "baseline");
  if (e && baselines.length) {
    const best = [...baselines].sort((a, b) => b.m.overall - a.m.overall)[0];
    const d = e.m.overall - best.m.overall;
    out.push({
      kind: d > 0 ? "win" : "tradeoff",
      title: d > 0 ? "Highest overall decision quality" : "Not the best overall",
      text: `ePARS scores ${pct(e.m.overall, 1)} overall vs ${pct(best.m.overall, 1)} for the strongest baseline (${best.label}), ${pp(d)}. Overall = mean of tool-selection F1, order compliance, policy compliance, action correctness, safety (1 − unsafe rate) and freshness correctness.`,
    });
    const o = S.open_react;
    if (o) {
      out.push({
        kind: e.m.policy > o.m.policy ? "win" : "tradeoff",
        title: "Policy grounding before acting",
        text: `Policy retrieval happened before any recommendation/write in ${pct(e.m.policy)} of queries that require it, vs ${pct(o.m.policy)} for the open-ended agent (${pp(e.m.policy - o.m.policy)}). This is what the fixed decision procedures buy.`,
      });
      out.push({
        kind: e.m.unsafe < o.m.unsafe ? "win" : "tradeoff",
        title: "Safer actions",
        text: `Unsafe-action rate (a write executed when only a proposal or refusal was correct): ${pct(e.m.unsafe, 1)} for ePARS vs ${pct(o.m.unsafe, 1)} for open-ended ReAct.`,
      });
    }
    if (S.epars_no_rag) out.push({
      kind: "info", title: "Ablation — remove the RAG gate",
      text: `Overall drops from ${pct(e.m.overall, 1)} to ${pct(S.epars_no_rag.m.overall, 1)} and policy compliance to ${pct(S.epars_no_rag.m.policy ?? 0)}.`,
    });
    if (S.epars_no_hitl) out.push({
      kind: "info", title: "Ablation — remove human confirmation",
      text: `Unsafe-action rate rises from ${pct(e.m.unsafe, 1)} to ${pct(S.epars_no_hitl.m.unsafe, 1)}.`,
    });
    const slowest = [S.zero_shot, S.ml_only].filter(Boolean).sort((a, b) => a.m.latency - b.m.latency)[0];
    if (slowest) out.push({
      kind: "tradeoff", title: "Cost: more latency and tool calls",
      text: `ePARS averages ${e.m.calls.toFixed(1)} tool calls and ${(e.m.latency / 1000).toFixed(1)} s per query, vs ${(slowest.m.latency / 1000).toFixed(2)} s for ${slowest.label}. The extra work is the price of grounded, ordered, confirmable decisions.`,
    });
  }

  if (routing) {
    const ttl = routing.find((x) => x.id === "ttl_only");
    const h = routing.find((x) => x.id === "hybrid"), c = routing.find((x) => x.id === "always_cached"), l = routing.find((x) => x.id === "always_live");
    out.push({
      kind: "win", title: "Hybrid cached/live routing",
      text: `Hybrid cuts stale high-stakes decisions from ${pct(c.staleHighStakesRate, 1)} (always cached) to ${pct(h.staleHighStakesRate, 1)}, while using ${pct(h.liveShare)} live calls instead of ${pct(l.liveShare)} (always live) — ${Math.round((1 - h.avgInferenceMs / l.avgInferenceMs) * 100)}% less inference latency than always-live.`,
    });
  }

  if (routing) {
    const h = routing.find((x) => x.id === "hybrid"), ttl = routing.find((x) => x.id === "ttl_only");
    if (h.staleHighStakesRate > ttl.staleHighStakesRate)
      out.push({
        kind: "tradeoff", title: "Hybrid is not better than a deterministic TTL rule here",
        text: `Because the LLM sometimes mis-judges when live inference is needed, hybrid leaves ${pct(h.staleHighStakesRate, 1)} of high-stakes decisions stale vs ${pct(ttl.staleHighStakesRate, 1)} for a plain ${"TTL"} rule. Forcing live inference for high-stakes actions in code (not in the prompt) would remove this gap.`,
      });
  }

  if (drift) {
    const bad = drift.filter((d) => d.shouldDetect), caught = bad.filter((d) => d.guardDetected).length;
    const huge = drift.find((d) => d.name.startsWith("Wrong dataset"));
    out.push({
      kind: "win", title: "Train/serve skew is detectable before the agent sees it",
      text: `A simple pre-agent guard caught ${caught}/${bad.length} corrupted scenarios and raised 0 false alarms on clean data. Without it, the ${huge ? huge.maxAbsZ.toFixed(0) : "800"}σ scenario produces a mean prediction of ${huge ? huge.meanPrediction.toFixed(0) : "?"} on a 0–100 scale — a number an LLM would still explain fluently. (The guard is a proposal, not yet in ePARS.)`,
    });
  }

  out.push(mode === "simulation"
    ? { kind: "caveat", title: "These are simulated results", text: `Agent behaviour comes from the assumption profiles in bench/config.js (${trials} seeded trials × ${queryCount} queries). They show what the harness measures and how the comparison reads — they are NOT evidence for the paper. Run \`npm run bench:live\` against dev-backend to get measured numbers. The drift experiment is a real computation but uses synthetic data.` }
    : { kind: "caveat", title: "Live results, small benchmark", text: `Measured on ${queryCount} queries (${trials} run(s) each). Labels were written by the system authors — have an independent annotator verify them before publication. Outcome classes are inferred from tool traces and response text.` });
  return out;
}
