import { useEffect, useMemo, useState } from "react";
import { getBurnoutEmployees, analyseBurnout, verifyBurnoutAssessment, decideReassignment } from "../api/client.js";

function categoryClass(category) {
  const c = (category || "").toLowerCase();
  if (c.includes("critical")) return "score-low";
  if (c.includes("high")) return "score-avg";
  if (c.includes("moderate")) return "score-good";
  return "score-exc";
}

export default function Burnout() {
  const [employees, setEmployees] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [search, setSearch] = useState("");

  const [selectedId, setSelectedId] = useState(null);
  const [result, setResult] = useState(null);
  const [analysing, setAnalysing] = useState(false);
  const [analyseError, setAnalyseError] = useState(null);

  useEffect(() => {
    getBurnoutEmployees()
      .then(setEmployees)
      .catch((err) => setLoadError(err.message));
  }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return employees;
    return employees.filter(
      (e) =>
        e.employee_id.toLowerCase().includes(q) ||
        e.department.toLowerCase().includes(q) ||
        e.role.toLowerCase().includes(q)
    );
  }, [employees, search]);

  function handleAnalyse(employeeId) {
    setSelectedId(employeeId);
    setAnalysing(true);
    setAnalyseError(null);
    setResult(null);
    analyseBurnout(employeeId)
      .then(setResult)
      .catch((err) => setAnalyseError(err.message))
      .finally(() => setAnalysing(false));
  }

  function resetView() {
    setSelectedId(null);
    setResult(null);
    setAnalyseError(null);
  }

  if (selectedId) {
    return (
      <div id="results-panel">
        {analysing && (
          <div className="loading-wrap">
            <div className="spinner" />
            <p>Running analysis…</p>
          </div>
        )}

        {!analysing && analyseError && (
          <div className="card">
            <p>{analyseError}</p>
            <button className="btn-secondary" onClick={resetView} style={{ marginTop: "1rem" }}>
              ← Back to employee list
            </button>
          </div>
        )}

        {!analysing && result && <ResultContent data={result} onBack={resetView} />}
      </div>
    );
  }

  return (
    <div className="card" id="selector-card">
      <div className="card-header">
        <h2>Select Employee</h2>
        <input
          type="text"
          id="emp-search"
          placeholder="Search by ID, department or role…"
          className="search-input"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {loadError && <p style={{ color: "#991b1b" }}>{loadError}</p>}

      <div className="employee-table-wrap">
        <table className="employee-table" id="emp-table">
          <thead>
            <tr>
              <th>Employee ID</th>
              <th>Department</th>
              <th>Role</th>
              <th>Seniority</th>
              <th>Stored Category</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((emp) => (
              <tr className="emp-row" key={emp.employee_id}>
                <td className="emp-name">{emp.employee_id}</td>
                <td>{emp.department}</td>
                <td>{emp.role}</td>
                <td>
                  <span className="seniority-badge">{emp.seniority}</span>
                </td>
                <td>
                  <span className={`score-pill ${categoryClass(emp.stored_category)}`}>
                    {emp.stored_category || "—"}
                  </span>
                </td>
                <td>
                  <button className="btn-analyse" onClick={() => handleAnalyse(emp.employee_id)}>
                    Analyse
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ResultContent({ data, onBack }) {
  const emp = data.employee;
  const initials = emp.employee_id.slice(-3);

  const [status, setStatus] = useState(data.status);
  const [verifying, setVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  function handleVerify() {
    setVerifying(true);
    setVerifyError(null);
    verifyBurnoutAssessment(data.assessment_id)
      .then(() => setStatus("verified"))
      .catch((err) => setVerifyError(err.message))
      .finally(() => setVerifying(false));
  }

  return (
    <div id="result-content">
      <div className="card result-header">
        <div className="emp-avatar">{initials}</div>
        <div className="emp-meta">
          <h2>{emp.employee_id}</h2>
          <p>
            {emp.role} &middot; {emp.department} &middot; {emp.seniority}
          </p>
        </div>
        <div className="score-hero">
          <div className="score-circle" style={{ borderColor: data.predicted_class_color }}>
            <span>{data.predicted_class}</span>
          </div>
          <p style={{ color: data.predicted_class_color }}>
            <span className={`confidence-badge confidence-${data.confidence}`}>
              {data.confidence} confidence
            </span>{" "}
            ({data.real_feature_count}/{data.total_feature_count} inputs real)
          </p>
          {data.stored_category && (
            <p className="live-score-note">
              Stored assessment: <strong>{data.stored_category}</strong> ({data.stored_score})
            </p>
          )}
        </div>
      </div>

      <div className="card" id="justification-card">
        <h3 className="card-title">AI Justification</h3>
        <p>{data.justification}</p>
        {data.policy_citation && (
          <p className="live-score-note">Policy reference: {data.policy_citation}</p>
        )}

        {status === "applied" && (
          <p style={{ marginTop: "1rem" }}>
            <strong>Auto-applied</strong> — high confidence, so this is now the employee's current
            recorded burnout status.
          </p>
        )}

        {status === "informational" && (
          <p style={{ marginTop: "1rem", color: "#64748b" }}>
            Low confidence — this prediction leans heavily on defaults rather than this
            employee's real data. No score has been applied and no reassignment was suggested;
            this is informational only, entirely your call.
          </p>
        )}

        {status === "verified" && (
          <p style={{ marginTop: "1rem" }}>
            <strong>Verified</strong> — you've confirmed this is now the employee's current
            recorded burnout status.
          </p>
        )}

        {status === "pending_review" && !dismissed && (
          <div style={{ marginTop: "1rem" }}>
            <p>
              <strong>Medium confidence</strong> — please check this score before it becomes the
              employee's current recorded status.
            </p>
            {verifyError && <p style={{ color: "#991b1b" }}>{verifyError}</p>}
            <button className="btn-analyse" disabled={verifying} onClick={handleVerify}>
              Verify Score
            </button>{" "}
            <button className="btn-secondary" disabled={verifying} onClick={() => setDismissed(true)}>
              Dismiss
            </button>
          </div>
        )}
        {status === "pending_review" && dismissed && (
          <p style={{ marginTop: "1rem", color: "#64748b" }}>
            Dismissed — left as pending, not applied as the current status.
          </p>
        )}
      </div>

      {data.recommendations.length > 0 && (
        <div className="card">
          <h3 className="card-title">Task Reassignment Recommendations</h3>
          <div className="review-list">
            {data.recommendations.map((rec) => (
              <RecommendationCard key={rec.recommendation_id} rec={rec} />
            ))}
          </div>
        </div>
      )}

      <button className="btn-secondary" onClick={onBack} style={{ marginTop: "1rem" }}>
        ← Back to employee list
      </button>
    </div>
  );
}

function RecommendationCard({ rec }) {
  const [decision, setDecision] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [executionResult, setExecutionResult] = useState(null);

  function submit(choice) {
    setSubmitting(true);
    setError(null);
    decideReassignment(rec.recommendation_id, choice)
      .then((saved) => {
        setExecutionResult(saved.execution_result);
        if (saved.manager_decision) {
          setDecision(saved.manager_decision);
        } else {
          setError(
            `Execution failed: ${saved.execution_result?.error || "unknown error"}. Not marked as decided — you can retry.`
          );
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setSubmitting(false));
  }

  return (
    <div className="card" style={{ marginBottom: "0.75rem" }}>
      <p>
        <strong>{rec.task_id}</strong> ({rec.task_type}, due {rec.due_date || "—"}) —{" "}
        <span style={{ textTransform: "uppercase", fontSize: "11px", fontWeight: 700 }}>{rec.action}</span>
        {rec.action === "reassign" && rec.target_employee_id && <> to {rec.target_employee_id}</>}
      </p>
      <p className="live-score-note">{rec.reasoning}</p>

      {rec.action === "none" ? (
        <p className="live-score-note">No action needed — informational only.</p>
      ) : decision ? (
        <p>
          <strong>{decision === "confirmed" ? "Confirmed and executed." : "Rejected."}</strong>
        </p>
      ) : (
        <div>
          {error && <p style={{ color: "#991b1b" }}>{error}</p>}
          <button className="btn-analyse" disabled={submitting} onClick={() => submit("confirmed")}>
            Confirm
          </button>{" "}
          <button className="btn-secondary" disabled={submitting} onClick={() => submit("rejected")}>
            Reject
          </button>
        </div>
      )}

      {executionResult && executionResult.details?.create?.success === false && (
        <p className="live-score-note">
          Note: reassigned in the system, but calendar sync failed ({executionResult.details.create.error}).
        </p>
      )}
    </div>
  );
}
