import { useEffect, useState } from "react";
import {
  getBurnoutEmployees,
  getBurnoutEmployeeDetail,
  analyseBurnout,
  verifyBurnoutAssessment,
  decideReassignment,
} from "../api/client.js";
import { useEmployeeTableControls } from "../hooks/useEmployeeTableControls.js";

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

  const [selectedId, setSelectedId] = useState(null);
  const [result, setResult] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);
  const [analysing, setAnalysing] = useState(false);
  const [analyseError, setAnalyseError] = useState(null);

  const [bulkRunning, setBulkRunning] = useState(false);
  const [bulkResults, setBulkResults] = useState(null);
  const [bulkProgress, setBulkProgress] = useState(0);

  const {
    search,
    setSearch,
    filters,
    setFilter,
    filterOptions,
    clearFilters,
    sortDir,
    toggleSort,
    rows: filtered,
    selectedIds,
    toggleSelect,
    toggleSelectAll,
    allFilteredSelected,
    clearSelection,
  } = useEmployeeTableControls(employees, {
    searchKeys: ["employee_id", "department", "role"],
    filterKeys: ["department", "role", "seniority", "stored_category"],
    scoreKey: "stored_score",
  });

  useEffect(() => {
    getBurnoutEmployees()
      .then(setEmployees)
      .catch((err) => setLoadError(err.message));
  }, []);

  function patchEmployeeCategory(employeeId, category) {
    setEmployees((prev) =>
      prev.map((e) => (e.employee_id === employeeId ? { ...e, stored_category: category } : e))
    );
  }

  function openDetail(employeeId) {
    setSelectedId(employeeId);
    setDetailLoading(true);
    setDetailError(null);
    setAnalyseError(null);
    setResult(null);
    getBurnoutEmployeeDetail(employeeId)
      .then(setResult)
      .catch((err) => setDetailError(err.message))
      .finally(() => setDetailLoading(false));
  }

  function handleRunAnalysis(employeeId) {
    setAnalysing(true);
    setAnalyseError(null);
    analyseBurnout(employeeId)
      .then((data) => {
        setResult(data);
        if (data.status === "applied") {
          patchEmployeeCategory(employeeId, data.predicted_class);
        }
      })
      .catch((err) => setAnalyseError(err.message))
      .finally(() => setAnalysing(false));
  }

  // "Analyse" button — runs the model immediately instead of opening the
  // no-model detail view first (that's what the row click does).
  function handleAnalyseNow(employeeId) {
    setSelectedId(employeeId);
    setDetailLoading(false);
    setDetailError(null);
    setResult(null);
    handleRunAnalysis(employeeId);
  }

  const BULK_CONCURRENCY = 8;

  async function handleBulkRun() {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    setBulkRunning(true);
    setBulkResults(null);
    setBulkProgress(0);

    const outcomes = new Array(ids.length);
    let next = 0;
    let done = 0;
    async function worker() {
      while (next < ids.length) {
        const i = next++;
        try {
          outcomes[i] = { employee_id: ids[i], success: true, data: await analyseBurnout(ids[i]), error: null };
        } catch (err) {
          outcomes[i] = { employee_id: ids[i], success: false, data: null, error: err.message };
        }
        done++;
        setBulkProgress(done);
      }
    }
    await Promise.all(Array.from({ length: Math.min(BULK_CONCURRENCY, ids.length) }, worker));

    for (const o of outcomes) {
      if (o.success && o.data.status === "applied") {
        patchEmployeeCategory(o.employee_id, o.data.predicted_class);
      }
    }

    setBulkResults(outcomes);
    setBulkRunning(false);
    clearSelection();
  }

  function resetView() {
    setSelectedId(null);
    setResult(null);
    setDetailError(null);
    setAnalyseError(null);
  }

  if (bulkResults) {
    return (
      <div className="card" id="bulk-results-panel">
        <div className="card-header">
          <h2>Bulk Burnout Evaluation Results</h2>
          <button className="btn-secondary" onClick={() => setBulkResults(null)}>
            ← Back to employee list
          </button>
        </div>
        {bulkResults.map((r) => (
          <div className="bulk-result-row" key={r.employee_id}>
            <span className="emp-name">{r.employee_id}</span>
            {r.success ? (
              <span className={`score-pill ${categoryClass(r.data.predicted_class)}`}>
                {r.data.predicted_class} ({r.data.confidence} confidence)
              </span>
            ) : (
              <span className="bulk-result-error">Failed: {r.error}</span>
            )}
          </div>
        ))}
      </div>
    );
  }

  if (selectedId) {
    return (
      <div id="results-panel">
        {detailLoading && (
          <div className="loading-wrap">
            <div className="spinner" />
            <p>Loading employee details…</p>
          </div>
        )}

        {analysing && !result && (
          <div className="loading-wrap">
            <div className="spinner" />
            <p>Running analysis…</p>
          </div>
        )}

        {!detailLoading && detailError && (
          <div className="card">
            <p>{detailError}</p>
            <button className="btn-secondary" onClick={resetView} style={{ marginTop: "1rem" }}>
              ← Back to employee list
            </button>
          </div>
        )}

        {!analysing && analyseError && !result && (
          <div className="card">
            <p>{analyseError}</p>
            <button className="btn-secondary" onClick={resetView} style={{ marginTop: "1rem" }}>
              ← Back to employee list
            </button>
          </div>
        )}

        {!detailLoading && result && (
          <ResultContent
            data={result}
            onRunAnalysis={handleRunAnalysis}
            analysing={analysing}
            analyseError={analyseError}
            onVerified={patchEmployeeCategory}
            onBack={resetView}
          />
        )}
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

      <div className="filter-bar">
        <select className="filter-select" value={filters.department || ""} onChange={(e) => setFilter("department", e.target.value)}>
          <option value="">All Departments</option>
          {filterOptions.department.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
        <select className="filter-select" value={filters.role || ""} onChange={(e) => setFilter("role", e.target.value)}>
          <option value="">All Roles</option>
          {filterOptions.role.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
        <select className="filter-select" value={filters.seniority || ""} onChange={(e) => setFilter("seniority", e.target.value)}>
          <option value="">All Seniorities</option>
          {filterOptions.seniority.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
        <select
          className="filter-select"
          value={filters.stored_category || ""}
          onChange={(e) => setFilter("stored_category", e.target.value)}
        >
          <option value="">All Categories</option>
          {filterOptions.stored_category.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
        <button className="filter-clear-btn" onClick={clearFilters}>
          Clear filters
        </button>
      </div>

      {selectedIds.size > 0 && (
        <div className="bulk-actions-bar">
          <span>
            <span className="bulk-count">{selectedIds.size}</span> employee{selectedIds.size === 1 ? "" : "s"} selected
          </span>
          <button className="btn-analyse" disabled={bulkRunning} onClick={handleBulkRun}>
            {bulkRunning ? `Running… (${bulkProgress}/${selectedIds.size})` : "Run Burnout Evaluation"}
          </button>
        </div>
      )}

      <div className="employee-table-wrap">
        <table className="employee-table" id="emp-table">
          <thead>
            <tr>
              <th className="checkbox-col">
                <input
                  type="checkbox"
                  className="emp-table-checkbox"
                  checked={allFilteredSelected}
                  onChange={toggleSelectAll}
                  aria-label="Select all filtered employees"
                />
              </th>
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
              <tr className="emp-row" key={emp.employee_id} onClick={() => openDetail(emp.employee_id)} style={{ cursor: "pointer" }}>
                <td className="checkbox-col" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    className="emp-table-checkbox"
                    checked={selectedIds.has(emp.employee_id)}
                    onChange={() => toggleSelect(emp.employee_id)}
                    aria-label={`Select ${emp.employee_id}`}
                  />
                </td>
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
                  <button
                    className="btn-analyse"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleAnalyseNow(emp.employee_id);
                    }}
                  >
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

function ResultContent({ data, onRunAnalysis, analysing, analyseError, onVerified, onBack }) {
  const emp = data.employee;
  const initials = emp.employee_id.slice(-3);

  const [verifiedOverride, setVerifiedOverride] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState(null);

  // A fresh analysis run (new assessment_id) starts a new session — clear any
  // verify/dismiss decision made on a previous assessment.
  useEffect(() => {
    setVerifiedOverride(false);
    setDismissed(false);
  }, [data.assessment_id]);

  const hasPrediction = data.predicted_class != null;
  const status = verifiedOverride ? "verified" : data.status;

  function handleVerify() {
    setVerifying(true);
    setVerifyError(null);
    verifyBurnoutAssessment(data.assessment_id)
      .then(() => {
        setVerifiedOverride(true);
        onVerified?.(emp.employee_id, data.predicted_class);
      })
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
          <div className="score-circle" style={{ borderColor: hasPrediction ? data.predicted_class_color : "#94a3b8" }}>
            <span>{hasPrediction ? data.predicted_class : data.stored_category || "Unrated"}</span>
          </div>
          {hasPrediction ? (
            <p style={{ color: data.predicted_class_color }}>
              <span className={`confidence-badge confidence-${data.confidence}`}>
                {data.confidence} confidence
              </span>{" "}
              ({data.real_feature_count}/{data.total_feature_count} inputs real)
            </p>
          ) : (
            <p style={{ color: "#64748b" }}>Recorded status — no AI analysis run yet</p>
          )}
          {!hasPrediction && <span className="status-badge status-recorded">Recorded status</span>}
          {hasPrediction && status === "applied" && <span className="status-badge status-recorded">Auto-applied · recorded</span>}
          {hasPrediction && status === "verified" && <span className="status-badge status-recorded">Verified · recorded</span>}
          {hasPrediction && status === "pending_review" && !dismissed && (
            <span className="status-badge status-pending">Pending manager review</span>
          )}
          {hasPrediction && status === "pending_review" && dismissed && (
            <span className="status-badge status-dismissed">Dismissed · not recorded</span>
          )}
          {hasPrediction && status === "informational" && (
            <span className="status-badge status-informational">Informational only</span>
          )}

          {hasPrediction && data.stored_category && (
            <div className="score-compare">
              <div className="score-compare-row">
                <span className="score-compare-label">Old stored assessment</span>
                <span className="score-compare-val">
                  {data.stored_category} {data.stored_score != null && `(${data.stored_score})`}
                </span>
              </div>
              <div className="score-compare-row">
                <span className="score-compare-label">New AI prediction</span>
                <span className="score-compare-val score-compare-new">
                  {data.predicted_class}
                  {data.stored_category && data.stored_category !== data.predicted_class && (
                    <span className="score-delta-up"> (changed)</span>
                  )}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card" id="justification-card">
        <h3 className="card-title">AI Justification</h3>
        {hasPrediction ? (
          <>
            <p>{data.justification}</p>
            {data.policy_citation && (
              <p className="live-score-note">Policy reference: {data.policy_citation}</p>
            )}
          </>
        ) : (
          <p className="live-score-note">
            No AI analysis has been run yet. Run the burnout model to get an AI-predicted risk
            category and justification.
          </p>
        )}

        {!hasPrediction ? (
          <div style={{ marginTop: "1rem" }}>
            {analyseError && <p style={{ color: "#991b1b" }}>{analyseError}</p>}
            <button className="btn-analyse" disabled={analysing} onClick={() => onRunAnalysis(emp.employee_id)}>
              {analysing ? "Running…" : "Run Burnout Analysis"}
            </button>
          </div>
        ) : (
          <>
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
          </>
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
