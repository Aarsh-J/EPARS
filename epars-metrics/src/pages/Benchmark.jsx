import { useMemo, useState } from "react";
import { MetricBars, Pill, SimBanner } from "../components/ui.jsx";

const COLS = [
  ["toolF1", "Tool F1"], ["order", "Order"], ["policy", "Policy"], ["action", "Action ✓"],
  ["unsafe", "Unsafe"], ["fresh", "Fresh ✓"],
];

function Table({ systems, ci }) {
  return (
    <div className="employee-table-wrap">
      <table className="employee-table">
        <thead><tr><th>System</th>{COLS.map(([, l]) => <th key={l}>{l}</th>)}<th>Calls</th><th>Latency</th><th>Overall</th></tr></thead>
        <tbody>
          {systems.map((s) => (
            <tr key={s.id}>
              <td className="emp-name">
                <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 3, background: s.color, marginRight: 8 }} />
                {s.label}
              </td>
              {COLS.map(([k]) => <td key={k}><Pill v={s.m[k]} low={k === "unsafe"} /></td>)}
              <td>{s.m.calls.toFixed(1)}</td>
              <td>{(s.m.latency / 1000).toFixed(2)}s</td>
              <td>
                <Pill v={s.m.overall} />
                {ci && s.ci?.overall > 0 && <span className="metric-label" style={{ marginLeft: 6 }}>±{(s.ci.overall * 100).toFixed(1)}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Benchmark({ data }) {
  const main = data.systems.filter((s) => s.kind !== "ablation");
  const ablation = data.systems.filter((s) => s.id === "epars" || s.kind === "ablation");
  const [sysId, setSysId] = useState("epars");
  const [onlyFails, setOnlyFails] = useState(false);
  const [intent, setIntent] = useState("");
  const sys = data.systems.find((s) => s.id === sysId) ?? data.systems[0];

  const rows = useMemo(() => data.gold.map((g, i) => ({ g, r: sys.queries[i] }))
    .filter(({ g }) => !intent || g.intent === intent)
    .filter(({ r }) => !onlyFails || r.action < 0.999 || (r.policy !== null && r.policy < 0.999) || r.unsafe > 0 || r.order < 0.999),
  [data, sys, intent, onlyFails]);

  const bar = (key, low) => main.map((s) => ({ label: s.label, value: s.m[key] ?? 0, color: s.color, ours: s.kind === "ours" }));

  return (
    <>
      <SimBanner data={data} />
      <div className="card">
        <div className="card-header"><h2>Comparison table</h2></div>
        <Table systems={main} ci />
        <p className="metric-label" style={{ marginTop: 10 }}>
          Tool F1 = overlap between required and used tool categories · Order = context → inference → policy → write ·
          Policy = RAG called before any write/recommendation · Unsafe = write executed when it should only be proposed or refused ·
          Fresh = live inference used exactly when freshness matters.
        </p>
      </div>

      <div className="result-grid">
        <MetricBars title="Overall decision quality" rows={bar("overall")} />
        <MetricBars title="Policy retrieved before acting" rows={bar("policy")} />
        <MetricBars title="Unsafe-action rate" lowerBetter max={Math.max(0.05, ...main.map((s) => s.m.unsafe ?? 0))} rows={bar("unsafe")} />
        <MetricBars title="Average latency per query" lowerBetter max={Math.max(...main.map((s) => s.m.latency))} fmt={(v) => `${(v / 1000).toFixed(2)}s`}
          rows={main.map((s) => ({ label: s.label, value: s.m.latency, color: s.color, ours: s.kind === "ours" }))} />
      </div>

      <div className="card">
        <div className="card-header"><h2>Ablations — what each safeguard contributes</h2></div>
        <Table systems={ablation} />
      </div>

      <div className="card">
        <div className="card-header"><h2>Overall score by query type</h2></div>
        <div className="employee-table-wrap">
          <table className="employee-table">
            <thead><tr><th>System</th>{data.intents.map((i) => <th key={i}>{i.replace(/_/g, " ")}</th>)}</tr></thead>
            <tbody>
              {main.map((s) => (
                <tr key={s.id}><td className="emp-name">{s.label}</td>{data.intents.map((i) => <td key={i}><Pill v={s.m.byIntent[i]} digits={0} /></td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h2>Query drill-down</h2></div>
        <div className="filter-bar">
          <select className="filter-select" value={sysId} onChange={(e) => setSysId(e.target.value)}>
            {data.systems.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
          <select className="filter-select" value={intent} onChange={(e) => setIntent(e.target.value)}>
            <option value="">All query types</option>
            {data.intents.map((i) => <option key={i} value={i}>{i.replace(/_/g, " ")}</option>)}
          </select>
          <label className="filter-select" style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={onlyFails} onChange={(e) => setOnlyFails(e.target.checked)} /> Only queries with a failure
          </label>
        </div>
        <div className="employee-table-wrap">
          <table className="employee-table">
            <thead><tr><th>ID</th><th>Query</th><th>Expected</th><th>Action ✓</th><th>Policy</th><th>Order</th><th>Unsafe</th><th>Sample trace</th></tr></thead>
            <tbody>
              {rows.map(({ g, r }) => (
                <tr key={g.id}>
                  <td>{g.id}</td>
                  <td style={{ maxWidth: 280 }}>{g.text}</td>
                  <td><span className="seniority-badge">{g.action}</span></td>
                  <td><Pill v={r.action} digits={0} /></td>
                  <td><Pill v={r.policy} digits={0} /></td>
                  <td><Pill v={r.order} digits={0} /></td>
                  <td><Pill v={r.unsafe} low digits={0} /></td>
                  <td className="metric-label">{r.sample ? `${r.sample.steps.join(" → ") || "no tools"} ⇒ ${r.sample.outcome}` : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
