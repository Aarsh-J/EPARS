// Small presentational helpers that reuse the main EPARS classes (card, score-pill, bar-wrap…).
export const pct = (x, d = 1) => (x === null || x === undefined ? "–" : `${(x * 100).toFixed(d)}%`);

export const pillClass = (v) => (v >= 0.9 ? "score-exc" : v >= 0.75 ? "score-good" : v >= 0.5 ? "score-avg" : "score-low");
export const pillClassLow = (v) => (v <= 0.02 ? "score-exc" : v <= 0.1 ? "score-good" : v <= 0.2 ? "score-avg" : "score-low");

export function Pill({ v, low = false, digits = 1 }) {
  if (v === null || v === undefined) return <span className="metric-label">–</span>;
  return <span className={`score-pill ${low ? pillClassLow(v) : pillClass(v)}`}>{pct(v, digits)}</span>;
}

export function ModeBadge({ mode }) {
  return mode === "live"
    ? <span className="status-badge status-recorded">Live · measured</span>
    : <span className="status-badge status-pending">Simulation · assumed behaviour</span>;
}

export function SimBanner({ data }) {
  if (data.mode === "live") return null;
  return (
    <div className="bulk-block-note" style={{ marginBottom: "1rem" }}>
      Agent behaviour on this page is <strong>simulated</strong> from the assumption profiles in
      <code> bench/config.js</code>. Use it to see how the metrics read; run{" "}
      <code>npm run bench:live</code> against <code>dev-backend</code> for numbers you can cite.
    </div>
  );
}

// Horizontal bar list — same visual language as the cluster bars on the Performance page.
export function MetricBars({ title, rows, max = 1, fmt = (v) => pct(v), lowerBetter = false }) {
  const best = (lowerBetter ? Math.min : Math.max)(...rows.map((r) => r.value));
  return (
    <div className="card">
      <div className="card-title">
        {title} <span className="metric-label" style={{ fontWeight: 400 }}>· {lowerBetter ? "lower" : "higher"} is better</span>
      </div>
      {rows.map((r) => (
        <div className="cluster-row" key={r.label}>
          <span className="cluster-name" style={{ width: 190, fontWeight: r.ours ? 600 : 400 }}>{r.label}</span>
          <div className="bar-wrap" style={{ height: 10 }}>
            <div className="bar" style={{ width: `${Math.min(100, (r.value / max) * 100)}%`, background: r.color, opacity: r.value === best ? 1 : 0.75 }} />
          </div>
          <span className="cluster-val" style={{ width: 64, color: r.value === best ? "#065f46" : undefined }}>{fmt(r.value)}</span>
        </div>
      ))}
    </div>
  );
}

export function Stat({ label, value, sub, tone }) {
  return (
    <div className="card" style={{ marginBottom: 0 }}>
      <div className="metric-label">{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, margin: "4px 0", color: tone || "#0f172a" }}>{value}</div>
      <div className="metric-label" style={{ fontSize: 12 }}>{sub}</div>
    </div>
  );
}
