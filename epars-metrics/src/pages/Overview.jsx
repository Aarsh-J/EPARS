import { Link } from "react-router-dom";
import { MetricBars, ModeBadge, Pill, SimBanner, Stat, pct } from "../components/ui.jsx";

const LINKS = [
  { to: "/benchmark", title: "Agent Benchmark", text: "Tool selection, ordering, policy compliance, unsafe actions, latency — ePARS vs baselines and ablations.", path: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
  { to: "/routing", title: "Cached vs Live", text: "Freshness, cost and staleness under four inference-routing strategies.", path: "M13 10V3L4 14h7v7l9-11h-7z" },
  { to: "/drift", title: "Drift Guard", text: "Can a pre-agent check catch the 800σ-style train/serve skew before the LLM reasons over it?", path: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" },
  { to: "/why", title: "Why ePARS", text: "Plain-language reasoning computed from the numbers, plus method and assumptions.", path: "M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" },
];

export default function Overview({ data }) {
  const e = data.systems.find((s) => s.id === "epars");
  const main = data.systems.filter((s) => s.kind !== "ablation");
  const ranked = [...main].sort((a, b) => b.m.overall - a.m.overall);

  return (
    <>
      <div className="dashboard-intro">
        <p>
          How well does the bounded agentic workflow decide, compared with alternatives? {data.queryCount} gold-labelled
          queries, {data.trials} {data.mode === "live" ? "run(s)" : "seeded trials"}. <ModeBadge mode={data.mode} />
        </p>
      </div>
      <SimBanner data={data} />

      {e && (
        <div className="module-grid" style={{ marginBottom: "1rem" }}>
          <Stat label="Overall decision quality" value={pct(e.m.overall)} sub={`rank ${ranked.findIndex((s) => s.id === "epars") + 1} of ${main.length} systems`} tone="#1e40af" />
          <Stat label="Policy retrieved before acting" value={pct(e.m.policy)} sub="queries that require policy grounding" />
          <Stat label="Unsafe-action rate" value={pct(e.m.unsafe)} sub="write executed when only a proposal was right" tone={e.m.unsafe <= 0.02 ? "#065f46" : "#991b1b"} />
          <Stat label="Avg latency / query" value={`${(e.m.latency / 1000).toFixed(2)}s`} sub={`${e.m.calls.toFixed(1)} tool calls on average`} />
        </div>
      )}

      <div className="card">
        <div className="card-header"><h2>Leaderboard</h2></div>
        <div className="employee-table-wrap">
          <table className="employee-table">
            <thead><tr><th>#</th><th>System</th><th>Overall</th><th>Policy</th><th>Unsafe</th><th>Action ✓</th><th>Latency</th></tr></thead>
            <tbody>
              {ranked.map((s, i) => (
                <tr key={s.id}>
                  <td>{i + 1}</td>
                  <td className="emp-name">
                    <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 3, background: s.color, marginRight: 8 }} />
                    {s.label}{s.kind === "ours" && <span className="seniority-badge" style={{ marginLeft: 8 }}>ours</span>}
                  </td>
                  <td><Pill v={s.m.overall} /></td>
                  <td><Pill v={s.m.policy} /></td>
                  <td><Pill v={s.m.unsafe} low /></td>
                  <td><Pill v={s.m.action} /></td>
                  <td>{(s.m.latency / 1000).toFixed(2)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <MetricBars title="Overall decision quality" rows={ranked.map((s) => ({ label: s.label, value: s.m.overall, color: s.color, ours: s.kind === "ours" }))} />

      <div className="module-grid">
        {LINKS.map((l) => (
          <Link to={l.to} className="module-card active" key={l.to}>
            <div className="module-icon" style={{ background: "#dbeafe" }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="#1d4ed8" strokeWidth="2"><path d={l.path} /></svg>
            </div>
            <div className="module-info"><h3>{l.title}</h3><p>{l.text}</p></div>
          </Link>
        ))}
      </div>
    </>
  );
}
