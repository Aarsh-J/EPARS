// Terminal report: comparison table + ASCII graphs. Pure ANSI, no dependencies.
const useColor = process.stdout.isTTY && !process.env.NO_COLOR && !process.argv.includes("--no-color");
const c = (code, s) => (useColor ? `\x1b[${code}m${s}\x1b[0m` : s);
const bold = (s) => c("1", s), dim = (s) => c("2", s), green = (s) => c("32", s), red = (s) => c("31", s),
  blue = (s) => c("34", s), yellow = (s) => c("33", s), cyan = (s) => c("36", s);
const strip = (s) => s.replace(/\x1b\[[0-9;]*m/g, "");
const pad = (s, w, right = false) => { const n = w - strip(s).length; return n <= 0 ? s : right ? " ".repeat(n) + s : s + " ".repeat(n); };
const pct = (x, d = 1) => (x === null || x === undefined ? "  –  " : `${(x * 100).toFixed(d)}%`);

function table(headers, rows, aligns) {
  const w = headers.map((h, i) => Math.max(strip(h).length, ...rows.map((r) => strip(String(r[i])).length)));
  const line = (l, m, r) => dim(l + w.map((x) => "─".repeat(x + 2)).join(m) + r);
  const fmt = (r) => dim("│") + r.map((v, i) => " " + pad(String(v), w[i], aligns?.[i] === "r") + " ").join(dim("│")) + dim("│");
  return [line("┌", "┬", "┐"), fmt(headers.map(bold)), line("├", "┼", "┤"), ...rows.map(fmt), line("└", "┴", "┘")].join("\n");
}

function bars(title, items, { max = 1, fmtv = (v) => pct(v), width = 34, lowerBetter = false } = {}) {
  const lines = [bold(title) + dim(lowerBetter ? "   (lower is better)" : "   (higher is better)")];
  const lw = Math.max(...items.map((i) => i.label.length));
  const best = (lowerBetter ? Math.min : Math.max)(...items.map((i) => i.value));
  for (const it of items) {
    const n = Math.max(0, Math.round((it.value / max) * width));
    const col = it.value === best ? green : it.ours ? blue : dim;
    lines.push(`  ${pad(it.label, lw)} ${col("█".repeat(n))}${dim("░".repeat(width - n))} ${fmtv(it.value)}`);
  }
  return lines.join("\n");
}

export function printReport(R) {
  const L = [];
  const live = R.mode === "live";
  L.push("");
  L.push(bold(blue("  EPARS · Performance Metrics")) + dim(`   ${R.generatedAt.slice(0, 19).replace("T", " ")}`));
  L.push(live ? green(`  MODE: LIVE — measured against ${R.liveTargets.join(", ")}`)
              : yellow("  MODE: SIMULATION — agent behaviour is ASSUMED (see bench/config.js). Not evidence for the paper."));
  L.push(dim(`  ${R.queryCount} gold queries × ${R.trials} ${live ? "run(s)" : "seeded trials"}${live ? "" : `, seed ${R.seed}`}`));
  L.push("");

  // ── 1. Comparison table
  const main = R.systems.filter((s) => s.kind !== "ablation");
  const abl = R.systems.filter((s) => s.kind === "ablation");
  const colBest = (key, low) => { const v = main.map((s) => s.m[key]).filter((x) => x !== null); return (low ? Math.min : Math.max)(...v); };
  const cell = (s, key, low = false, f = pct) => {
    const v = s.m[key]; const t = f(v);
    return v !== null && v === colBest(key, low) ? green(bold(t)) : t;
  };
  const hdr = ["System", "Tool F1", "Order", "Policy", "Action ✓", "Unsafe", "Fresh ✓", "Calls", "Latency", "Overall"];
  const row = (s) => [
    s.kind === "ours" ? blue(bold(s.label)) : s.label,
    cell(s, "toolF1"), cell(s, "order"), cell(s, "policy"), cell(s, "action"),
    cell(s, "unsafe", true), cell(s, "fresh"),
    s.m.calls.toFixed(1), `${(s.m.latency / 1000).toFixed(2)}s`, cell(s, "overall"),
  ];
  L.push(bold("1. Agent benchmark — comparison table"));
  L.push(table(hdr, main.map(row), ["l", "r", "r", "r", "r", "r", "r", "r", "r", "r"]));
  L.push(dim("   Green = best in column (for Unsafe, lowest). '–' = metric not applicable to that system."));
  L.push("");
  if (abl.length) {
    L.push(bold("   Ablations (what each ePARS safeguard contributes)"));
    L.push(table(hdr, [row(R.systems.find((s) => s.id === "epars")), ...abl.map(row)], ["l", "r", "r", "r", "r", "r", "r", "r", "r", "r"]));
    L.push("");
  }

  // ── 2. Graphs
  L.push(bold("2. Graphs"));
  L.push(bars("Overall decision quality", main.map((s) => ({ label: s.label, value: s.m.overall, ours: s.kind === "ours" }))));
  L.push("");
  L.push(bars("Policy retrieved before acting", main.map((s) => ({ label: s.label, value: s.m.policy ?? 0, ours: s.kind === "ours" }))));
  L.push("");
  L.push(bars("Unsafe-action rate", main.map((s) => ({ label: s.label, value: s.m.unsafe ?? 0, ours: s.kind === "ours" })), { lowerBetter: true, max: Math.max(0.05, ...main.map((s) => s.m.unsafe ?? 0)) }));
  L.push("");
  const maxLat = Math.max(...main.map((s) => s.m.latency));
  L.push(bars("Average latency per query", main.map((s) => ({ label: s.label, value: s.m.latency, ours: s.kind === "ours" })), { max: maxLat, lowerBetter: true, fmtv: (v) => `${(v / 1000).toFixed(2)}s` }));
  L.push("");

  // ── 3. Routing
  if (R.routing) {
    L.push(bold("3. Cached vs live inference routing") + dim("  (simulation)"));
    L.push(table(["Strategy", "Live calls", "Avg inference", "Stale decisions", "Stale (high-stakes)"],
      R.routing.map((r) => [r.id === "hybrid" ? blue(bold(r.label)) : r.label, pct(r.liveShare, 0), `${r.avgInferenceMs.toFixed(0)} ms`, pct(r.staleRate), pct(r.staleHighStakesRate)]),
      ["l", "r", "r", "r", "r"]));
    L.push("");
    L.push(bars("Stale high-stakes decisions", R.routing.map((r) => ({ label: r.label, value: r.staleHighStakesRate, ours: r.id === "hybrid" })), { lowerBetter: true, max: Math.max(0.05, ...R.routing.map((r) => r.staleHighStakesRate)) }));
    L.push("");
  }

  // ── 4. Drift
  if (R.drift) {
    L.push(bold("4. Train/serve skew — can bad inputs be caught before the agent reasons over them?") + dim("  (real computation)"));
    L.push(table(["Scenario", "Max |z|", "Preds outside 0-100", "Guard"],
      R.drift.map((d) => [d.name, d.maxAbsZ >= 100 ? d.maxAbsZ.toFixed(0) + "σ" : d.maxAbsZ.toFixed(1) + "σ", pct(d.outOfRangeRate, 0),
        d.guardDetected === d.shouldDetect ? green(d.guardDetected ? "caught ✓" : "clean ✓") : red(d.guardDetected ? "false alarm ✗" : "MISSED ✗")]),
      ["l", "r", "r", "l"]));
    L.push("");
  }

  // ── 5. Reasoning
  L.push(bold("5. Why ePARS — reasoning computed from these numbers"));
  const tag = { win: green("  ✔ "), tradeoff: yellow("  ⚠ "), info: cyan("  ℹ "), caveat: red("  ! ") };
  for (const i of R.insights) { L.push(tag[i.kind] + bold(i.title)); L.push(wrap(i.text, 96, "      ")); }
  L.push("");
  L.push(dim("  Saved: public/results.json (dashboard) · results/results.csv   →   `npm run dev` to open the dashboard"));
  L.push("");
  console.log(L.join("\n"));
}

function wrap(text, width, indent) {
  const words = text.split(" "), lines = []; let cur = "";
  for (const w of words) { if ((cur + " " + w).length > width) { lines.push(indent + cur.trim()); cur = w; } else cur += " " + w; }
  if (cur.trim()) lines.push(indent + cur.trim());
  return lines.join("\n");
}
