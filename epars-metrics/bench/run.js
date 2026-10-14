#!/usr/bin/env node
// Usage:
//   node bench/run.js                      simulation mode (no backend needed)
//   node bench/run.js --live               live mode against http://localhost:8000
//   node bench/run.js --live --system epars=http://localhost:8000 --system zero_shot=http://localhost:8001
//   options: --trials N  --seed N  --no-color
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { DEFAULTS, PROFILES, SYSTEMS, LATENCY, ROUTING, DRIFT, TOOL_MAP } from "./config.js";
import { QUERIES, INTENTS } from "./queries.js";
import { rng, simulate } from "./sim.js";
import { scoreTrace, aggregate, stats } from "./score.js";
import { runRouting } from "./routing.js";
import { runDrift } from "./drift.js";
import { runQueryLive } from "./live.js";
import { buildInsights } from "./insights.js";
import { printReport } from "./report.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const flag = (n) => args.includes(n);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const live = flag("--live");
const trials = Number(opt("--trials", live ? 1 : DEFAULTS.trials));
const seed = Number(opt("--seed", DEFAULTS.seed));

const METRIC_KEYS = ["toolF1", "order", "policy", "action", "unsafe", "fresh", "calls", "latency", "overall"];

function summarise(id, runs) {
  // runs: array (one per trial) of { scores:[...] } aligned with QUERIES
  const per = runs.map((scores) => aggregate(QUERIES, scores));
  const m = { byIntent: {} }, ci = {};
  for (const k of METRIC_KEYS) {
    const vals = per.map((p) => p[k]).filter((v) => v !== null);
    if (!vals.length) { m[k] = null; continue; }
    const s = stats(vals); m[k] = s.mean; ci[k] = s.ci;
  }
  for (const it of INTENTS) m.byIntent[it] = stats(per.map((p) => p.byIntent[it])).mean;
  // per-query pass rates (+ one sample trace) for the dashboard drill-down
  const queries = QUERIES.map((g, qi) => {
    const col = (k) => { const v = runs.map((r) => r[qi][k]).filter((x) => x !== null); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
    return { id: g.id, action: col("action"), policy: col("policy"), order: col("order"), unsafe: col("unsafe"), fresh: col("fresh"), sel: col("sel") };
  });
  const meta = SYSTEMS[id] ?? { label: id, kind: "baseline", color: "#64748b" };
  return { id, ...meta, m, ci, queries };
}

async function main() {
  let systems = [], liveTargets = [], unknownTools = new Set(), samples = {};

  if (!live) {
    for (const id of Object.keys(PROFILES)) {
      const runs = [];
      for (let t = 0; t < trials; t++) {
        const r = rng(seed * 100003 + t * 7919 + id.length);
        const traces = QUERIES.map((g) => simulate(id, PROFILES[id], g, r));
        if (t === 0) samples[id] = traces.map((x) => ({ steps: x.steps.map((s) => s.cat), outcome: x.outcome }));
        runs.push(traces.map((tr, i) => scoreTrace(QUERIES[i], tr)));
      }
      systems.push(summarise(id, runs));
    }
  } else {
    const given = args.flatMap((a, i) => (a === "--system" ? [args[i + 1]] : []));
    const targets = given.length ? given.map((s) => s.split(/=(.*)/s).slice(0, 2)) : [["epars", opt("--url", "http://localhost:8000")]];
    for (const [id, url] of targets) {
      liveTargets.push(`${id}@${url}`);
      const runs = [];
      for (let t = 0; t < trials; t++) {
        const scores = [], sm = [];
        for (const g of QUERIES) {
          process.stdout.write(`\r  ${id} run ${t + 1}/${trials}  ${g.id}/${QUERIES.at(-1).id}   `);
          try {
            const tr = await runQueryLive(url, g.text, unknownTools);
            scores.push(scoreTrace(g, tr)); sm.push({ steps: tr.steps.map((s) => s.cat ?? `?${s.tool}`), outcome: tr.outcome });
          } catch (e) {
            console.error(`\n  ✗ ${g.id}: ${e.message}`);
            scores.push(scoreTrace(g, { steps: [], outcome: "error", latencyMs: 0 })); sm.push({ steps: [], outcome: "error" });
          }
        }
        if (t === 0) samples[id] = sm;
        runs.push(scores);
      }
      systems.push(summarise(id, runs));
    }
    process.stdout.write("\n");
    if (unknownTools.size) console.warn(`  ⚠ Unmapped tools (add to TOOL_MAP in bench/config.js): ${[...unknownTools].join(", ")}`);
  }

  // Attach sample traces
  for (const s of systems) s.queries.forEach((q, i) => (q.sample = samples[s.id]?.[i]));

  const routing = live ? null : runRouting(seed);
  const drift = runDrift(seed);
  const mode = live ? "live" : "simulation";
  const insights = buildInsights({ mode, systems, routing, drift, queryCount: QUERIES.length, trials });

  const R = {
    mode, generatedAt: new Date().toISOString(), trials, seed, queryCount: QUERIES.length, liveTargets,
    systems, routing, drift, insights, intents: INTENTS,
    gold: QUERIES.map(({ id, text, intent, needs, action, fresh, stakes }) => ({ id, text, intent, needs, action, fresh, stakes })),
    assumptions: live ? { toolMap: TOOL_MAP } : { profiles: PROFILES, latencyMs: LATENCY, routing: ROUTING, drift: DRIFT },
  };

  fs.mkdirSync(path.join(root, "public"), { recursive: true });
  fs.mkdirSync(path.join(root, "results"), { recursive: true });
  fs.writeFileSync(path.join(root, "public", "results.json"), JSON.stringify(R, null, 2));
  const csv = ["system,kind," + METRIC_KEYS.join(",")]
    .concat(systems.map((s) => [s.id, s.kind, ...METRIC_KEYS.map((k) => (s.m[k] === null ? "" : s.m[k].toFixed(4)))].join(",")));
  fs.writeFileSync(path.join(root, "results", "results.csv"), csv.join("\n") + "\n");

  printReport(R);
}

main().catch((e) => { console.error(e); process.exit(1); });
