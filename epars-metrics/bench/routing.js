// Cached-vs-live routing experiment (simulation, parameters in config.js ROUTING).
// Question: how stale are the scores behind decisions, and what does it cost in
// latency / live-inference calls, under four routing strategies?
import { ROUTING as R, LATENCY } from "./config.js";
import { rng } from "./sim.js";

export function runRouting(seed = 42) {
  const r = rng(seed + 999);
  // Poisson-ish data-change times per employee
  const changes = Array.from({ length: R.employees }, () => {
    const ts = []; let t = 0;
    while (true) { t += -Math.log(1 - r()) * (24 / R.dataChangePerDay); if (t > R.horizonHours) break; ts.push(t); }
    return ts;
  });
  const reqs = Array.from({ length: R.requests }, () => ({
    emp: Math.floor(r() * R.employees),
    t: r() * R.horizonHours,
    high: r() < R.highStakesShare,
    flip: r() < R.routerErrorRate, // the LLM router mis-judges this request
  }));

  const lastChange = (e, t) => { let l = -Infinity; for (const c of changes[e]) { if (c <= t) l = c; else break; } return l; };
  const cacheTime = (t) => Math.floor(t / R.cacheRefreshHours) * R.cacheRefreshHours;

  const strategies = {
    always_cached: () => false,
    always_live:   () => true,
    ttl_only:      (q, age) => age > R.ttlHours,
    hybrid:        (q, age) => { const need = q.high || age > R.ttlHours; return q.flip ? !need : need; },
  };
  const labels = {
    always_cached: "Always cached", always_live: "Always live",
    ttl_only: `TTL only (${R.ttlHours} h)`, hybrid: "Hybrid (stakes + freshness)",
  };

  return Object.entries(strategies).map(([id, decide]) => {
    let live = 0, stale = 0, staleHigh = 0, high = 0, ms = 0;
    for (const q of reqs) {
      const age = q.t - cacheTime(q.t);
      const useLive = decide(q, age);
      const stored = cacheTime(q.t);
      const isStale = !useLive && lastChange(q.emp, q.t) > stored;
      if (useLive) { live++; ms += LATENCY.inference_live; } else ms += LATENCY.inference_cached;
      if (isStale) stale++;
      if (q.high) { high++; if (isStale) staleHigh++; }
    }
    const n = reqs.length;
    return {
      id, label: labels[id],
      liveCalls: live, liveShare: live / n,
      avgInferenceMs: ms / n,
      staleRate: stale / n,
      staleHighStakesRate: high ? staleHigh / high : 0,
    };
  });
}
