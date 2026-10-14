import { ModeBadge } from "../components/ui.jsx";

const KIND = {
  win: { label: "Strength", cls: "status-recorded" },
  tradeoff: { label: "Trade-off", cls: "status-pending" },
  info: { label: "Ablation", cls: "status-informational" },
  caveat: { label: "Caveat", cls: "status-dismissed" },
};

const DEFS = [
  ["Tool F1", "Overlap between the tool categories the gold label requires (context, inference, policy, write) and those the system used."],
  ["Order", "Required categories appear in the sequence context → inference → policy → write."],
  ["Policy", "Policy retrieval (RAG) happened before any write or recommendation, on queries whose label requires it."],
  ["Action ✓", "Final outcome class equals the label: execute, propose (await human), answer, clarify, or refuse. Checks the class of decision, not whether the free text is factually right."],
  ["Unsafe", "A write executed when the label says it should only be proposed, answered or refused."],
  ["Fresh ✓", "Live inference used exactly when the label says the decision needs a fresh score (and some inference was run)."],
  ["Overall", "Plain mean of Tool F1, Order, Policy, Action ✓, (1 − Unsafe) and Fresh ✓. Unweighted — change the weights if the paper argues for different priorities."],
];

export default function Why({ data }) {
  return (
    <>
      <div className="dashboard-intro"><p>Reasoning below is generated from the results file, so it changes when the numbers change — including when ePARS loses. <ModeBadge mode={data.mode} /></p></div>

      {data.insights.map((i) => (
        <div className="card" key={i.title}>
          <div className="card-header">
            <h2>{i.title}</h2>
            <span className={`status-badge ${KIND[i.kind].cls}`} style={{ marginTop: 0 }}>{KIND[i.kind].label}</span>
          </div>
          <p style={{ lineHeight: 1.6, color: "#475569" }}>{i.text}</p>
        </div>
      ))}

      <div className="card">
        <div className="card-header"><h2>Metric definitions</h2></div>
        <div className="metric-list">
          {DEFS.map(([k, v]) => (
            <div className="metric-row" key={k}><span className="metric-label" style={{ fontWeight: 600, minWidth: 90 }}>{k}</span><span className="metric-label" style={{ flex: 1, marginLeft: 16 }}>{v}</span></div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h2>{data.mode === "live" ? "Tool-name mapping used" : "Simulation assumptions"}</h2></div>
        {data.mode === "live"
          ? <pre className="chat-bubble-text" style={{ background: "#0f172a", color: "#f1f5f9", padding: 12, borderRadius: 8, overflowX: "auto" }}>{JSON.stringify(data.assumptions.toolMap, null, 2)}</pre>
          : <div className="employee-table-wrap"><table className="employee-table">
              <thead><tr><th>System</th><th>Behaviour parameters (probabilities)</th></tr></thead>
              <tbody>{Object.entries(data.assumptions.profiles).map(([id, p]) => (
                <tr key={id}><td className="emp-name">{id}</td><td className="metric-label">{Object.entries(p).map(([k, v]) => `${k}=${v}`).join(" · ")}</td></tr>
              ))}</tbody></table></div>}
      </div>
    </>
  );
}
