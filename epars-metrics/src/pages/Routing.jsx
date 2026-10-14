import { MetricBars, Pill, SimBanner, pct } from "../components/ui.jsx";

const COLORS = { always_cached: "#94a3b8", always_live: "#d97706", ttl_only: "#0d9488", hybrid: "#2563eb" };

// Latency (x) vs stale high-stakes decisions (y): bottom-left is best.
function Scatter({ rows }) {
  const W = 520, H = 280, P = 44;
  const maxX = Math.max(...rows.map((r) => r.avgInferenceMs)) * 1.5;
  const maxY = Math.max(0.05, ...rows.map((r) => r.staleHighStakesRate)) * 1.15;
  const x = (v) => P + (v / maxX) * (W - P - 16), y = (v) => H - P - (v / maxY) * (H - P - 16);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Latency versus stale high-stakes decisions">
      <line x1={P} y1={H - P} x2={W - 12} y2={H - P} stroke="#cbd5e1" />
      <line x1={P} y1={H - P} x2={P} y2={12} stroke="#cbd5e1" />
      <text x={W / 2} y={H - 8} textAnchor="middle" fontSize="11" fill="#64748b">Average inference latency (ms) →</text>
      <text x={12} y={H / 2} fontSize="11" fill="#64748b" transform={`rotate(-90 12 ${H / 2})`} textAnchor="middle">Stale high-stakes decisions</text>
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <text x={P - 6} y={y(maxY * t) + 4} textAnchor="end" fontSize="10" fill="#94a3b8">{pct(maxY * t, 0)}</text>
          <text x={x(maxX * t)} y={H - P + 14} textAnchor="middle" fontSize="10" fill="#94a3b8">{Math.round(maxX * t)}</text>
        </g>
      ))}
      {rows.map((r) => (
        <g key={r.id}>
          <circle cx={x(r.avgInferenceMs)} cy={y(r.staleHighStakesRate)} r={r.id === "hybrid" ? 9 : 7} fill={COLORS[r.id]} />
          <text x={x(r.avgInferenceMs) + (r.id === "always_live" ? -12 : 12)} textAnchor={r.id === "always_live" ? "end" : "start"} y={y(r.staleHighStakesRate) + (r.id === "hybrid" ? -10 : r.id === "ttl_only" ? 18 : 4)} fontSize="11" fill="#334155" fontWeight={r.id === "hybrid" ? 700 : 400}>{r.label}</text>
        </g>
      ))}
    </svg>
  );
}

export default function Routing({ data }) {
  if (!data.routing)
    return <div className="card"><div className="card-title">Not measured in live mode</div>
      <p className="metric-label">The cached/live comparison needs controllable data changes, so it only runs in simulation. Run <code>npm run bench</code>.</p></div>;
  const R = data.routing;
  return (
    <>
      <SimBanner data={data} />
      <div className="dashboard-intro"><p>
        Should the agent trust the stored score or recompute it? Each strategy handles {data.assumptions.routing.requests} requests over
        {" "}{Math.round(data.assumptions.routing.horizonHours / 24)} days while employee data keeps changing and stored scores refresh every
        {" "}{data.assumptions.routing.cacheRefreshHours} h.
      </p></div>
      <div className="card">
        <div className="card-header"><h2>Strategy comparison</h2></div>
        <div className="employee-table-wrap">
          <table className="employee-table">
            <thead><tr><th>Strategy</th><th>Live calls</th><th>Avg inference</th><th>Stale decisions</th><th>Stale (high-stakes)</th></tr></thead>
            <tbody>
              {R.map((r) => (
                <tr key={r.id}>
                  <td className="emp-name" style={{ fontWeight: r.id === "hybrid" ? 700 : 500 }}>
                    <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 3, background: COLORS[r.id], marginRight: 8 }} />{r.label}
                  </td>
                  <td>{pct(r.liveShare, 0)}</td>
                  <td>{r.avgInferenceMs.toFixed(0)} ms</td>
                  <td><Pill v={r.staleRate} low /></td>
                  <td><Pill v={r.staleHighStakesRate} low /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="result-grid">
        <div className="card"><div className="card-title">Cost vs staleness <span className="metric-label" style={{ fontWeight: 400 }}>· bottom-left is best</span></div><Scatter rows={R} /></div>
        <MetricBars title="Stale high-stakes decisions" lowerBetter max={Math.max(0.05, ...R.map((r) => r.staleHighStakesRate))}
          rows={R.map((r) => ({ label: r.label, value: r.staleHighStakesRate, color: COLORS[r.id], ours: r.id === "hybrid" }))} />
      </div>
    </>
  );
}
