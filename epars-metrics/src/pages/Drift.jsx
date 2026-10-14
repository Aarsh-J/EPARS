import { SimBanner, pct } from "../components/ui.jsx";

export default function Drift({ data }) {
  const D = data.drift;
  const caught = D.filter((d) => d.shouldDetect && d.guardDetected).length, bad = D.filter((d) => d.shouldDetect).length;
  const falseAlarm = D.some((d) => !d.shouldDetect && d.guardDetected);
  return (
    <>
      <SimBanner data={{ mode: "live" }} />
      <div className="dashboard-intro"><p>
        A traditional ML service may crash or alert on garbage inputs; an LLM agent will explain them fluently. This experiment feeds
        corrupted serving batches to a toy linear scorer and checks whether a simple pre-agent guard (row z-score &gt; {data.assumptions.drift?.rowThresholdSigma ?? 6}σ or batch mean-shift test) catches them.
        This is a <strong>real computation</strong> on synthetic data; the guard is a <strong>proposal</strong>, not yet part of ePARS.
      </p></div>
      <div className="module-grid" style={{ marginBottom: "1rem" }}>
        <div className="card" style={{ marginBottom: 0 }}><div className="metric-label">Corrupted scenarios caught</div><div style={{ fontSize: 28, fontWeight: 700 }}>{caught}/{bad}</div></div>
        <div className="card" style={{ marginBottom: 0 }}><div className="metric-label">False alarms on clean data</div><div style={{ fontSize: 28, fontWeight: 700, color: falseAlarm ? "#991b1b" : "#065f46" }}>{falseAlarm ? "Yes" : "None"}</div></div>
      </div>
      <div className="card">
        <div className="card-header"><h2>Scenarios</h2></div>
        <div className="employee-table-wrap">
          <table className="employee-table">
            <thead><tr><th>Scenario</th><th>What changed</th><th>Max |z|</th><th>Mean prediction (0–100 scale)</th><th>Outside 0–100</th><th>Guard</th></tr></thead>
            <tbody>
              {D.map((d) => {
                const ok = d.guardDetected === d.shouldDetect;
                return (
                  <tr key={d.name}>
                    <td className="emp-name">{d.name}</td>
                    <td className="metric-label">{d.desc}</td>
                    <td>{d.maxAbsZ.toFixed(d.maxAbsZ >= 100 ? 0 : 1)}σ</td>
                    <td>{d.meanPrediction.toFixed(1)}</td>
                    <td>{pct(d.outOfRangeRate, 0)}</td>
                    <td><span className={`score-pill ${ok ? "score-exc" : "score-low"}`}>{ok ? (d.guardDetected ? "caught" : "clean") : d.guardDetected ? "false alarm" : "missed"}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card">
        <div className="card-title">What this means for the paper</div>
        <p className="metric-label" style={{ lineHeight: 1.6 }}>
          The 800σ case produces predictions far outside any valid score range, yet nothing in an agent loop rejects them. Validating
          inputs and outputs <em>between the ML tool and the LLM</em> turns this from an anecdote into a testable safeguard.
          To claim it for ePARS, implement the check inside the tools layer (e.g. in <code>get_employee_ml_scores</code> /
          <code> compute_live_performance_score</code>) and re-run this experiment against the real feature pipeline and a canonical dataset.
        </p>
      </div>
    </>
  );
}
