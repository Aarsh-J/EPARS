import { useEffect, useState } from "react";
import { getEmployees, analyseEmployee, finalizePerformanceScore } from "../api/client.js";
import { useEmployeeTableControls } from "../hooks/useEmployeeTableControls.js";

const SIGNAL_META = [
  { key: "output_quality_composite", label: "Output Quality" },
  { key: "overtime_ratio", label: "Overtime Ratio" },
  { key: "peer_productivity_gap", label: "Peer Productivity Gap" },
  { key: "fb_composite_rating", label: "Feedback Rating" },
];

const REVIEW_DIMENSION_LABELS = {
  technical_competence: "Technical Competence",
  domain_knowledge: "Domain Knowledge",
  problem_solving: "Problem Solving",
  quality_of_work: "Quality of Work",
  productivity: "Productivity",
  communication: "Communication",
  collaboration: "Collaboration",
  leadership: "Leadership",
  initiative: "Initiative",
  time_management: "Time Management",
};

function scoreClass(score) {
  if (score >= 85) return "score-exc";
  if (score >= 70) return "score-good";
  if (score >= 55) return "score-avg";
  return "score-low";
}

// Mirrors modules/performance/routes.py::_rating exactly, so the header can
// update immediately after a manager finalizes a score without a re-fetch.
function ratingFromScore(score) {
  if (score == null) return { label: "Unrated", color: "#94a3b8" };
  if (score >= 85) return { label: "Exceptional", color: "#065f46" };
  if (score >= 70) return { label: "High Performer", color: "#1e40af" };
  if (score >= 55) return { label: "Meets Expectations", color: "#92400e" };
  return { label: "Needs Improvement", color: "#991b1b" };
}

export default function Performance() {
  const [employees, setEmployees] = useState([]);
  const [loadError, setLoadError] = useState(null);

  const [selectedId, setSelectedId] = useState(null);
  const [result, setResult] = useState(null);
  const [analysing, setAnalysing] = useState(false);
  const [analyseError, setAnalyseError] = useState(null);

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
  } = useEmployeeTableControls(employees, {
    searchKeys: ["employee_id", "department", "role"],
    filterKeys: ["department", "role", "seniority"],
    scoreKey: "score",
  });

  useEffect(() => {
    getEmployees()
      .then(setEmployees)
      .catch((err) => setLoadError(err.message));
  }, []);

  function handleAnalyse(employeeId, reviewId = null) {
    setSelectedId(employeeId);
    setAnalysing(true);
    setAnalyseError(null);
    setResult(null);
    analyseEmployee(employeeId, reviewId)
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

        {!analysing && result && <ResultContent data={result} onSelectReview={handleAnalyse} onBack={resetView} />}
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
        <button className="filter-clear-btn" onClick={clearFilters}>
          Clear filters
        </button>
      </div>

      {selectedIds.size > 0 && (
        <div className="bulk-actions-bar">
          <span>
            <span className="bulk-count">{selectedIds.size}</span> employee{selectedIds.size === 1 ? "" : "s"} selected
          </span>
          <span
            className="bulk-block-note"
            title="Performance scores must be reviewed and finalized by a manager one at a time, so bulk evaluation is disabled for this module."
          >
            Bulk run disabled — performance scores require manager review
          </span>
          <button className="btn-analyse" disabled title="Performance scores require manager review before they can be recorded — run evaluations one employee at a time.">
            Run Performance Evaluation
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
              <th className="th-sortable" onClick={toggleSort}>
                Latest Score
                {sortDir && <span className="sort-arrow">{sortDir === "asc" ? "▲" : "▼"}</span>}
              </th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((emp) => (
              <tr className="emp-row" key={emp.employee_id}>
                <td className="checkbox-col">
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
                  <span className={`score-pill ${scoreClass(emp.score)}`}>{emp.score}</span>
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

function ResultContent({ data, onSelectReview, onBack }) {
  const emp = data.employee;
  const initials = emp.employee_id.slice(-3);
  const latestReviewId = data.all_reviews?.[0]?.review_id || null;

  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(data.ai_predicted_score ?? "");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [finalized, setFinalized] = useState(data.last_decision || null);

  const displayScore = finalized ? finalized.final_score : data.recorded_score;
  const displayRating = finalized ? ratingFromScore(finalized.final_score) : { label: data.rating_label, color: data.rating_color };

  function submitDecision(decision, finalScore) {
    setSubmitting(true);
    setSubmitError(null);
    finalizePerformanceScore(emp.employee_id, latestReviewId, decision, finalScore, data, note)
      .then((saved) => {
        setFinalized({
          decision: saved.manager_decision,
          final_score: Number(saved.final_score),
          decided_at: saved.decided_at,
        });
        setEditing(false);
      })
      .catch((err) => setSubmitError(err.message))
      .finally(() => setSubmitting(false));
  }

  return (
    <div id="result-content">
      <div className="card result-header">
        <div className="emp-avatar">{initials}</div>
        <div className="emp-meta">
          <h2>{emp.employee_id}</h2>
          <p>
            {emp.role} &middot; {emp.department} &middot; {emp.seniority} &middot;{" "}
            {emp.review_type || "Review"} on {emp.review_date}
          </p>
        </div>
        <div className="score-hero">
          <div className="score-circle" style={{ borderColor: displayRating.color }}>
            <span>{displayScore}</span>
            <small>/100</small>
          </div>
          <p style={{ color: displayRating.color }}>{displayRating.label}</p>
          <p className="live-score-note">Recorded score</p>
          {data.ai_predicted_score != null && (
            <p className="live-score-note">
              AI estimate: <strong>{data.ai_predicted_score}</strong>/100{" "}
              <span className={`confidence-badge confidence-${data.ai_confidence}`}>
                {data.ai_confidence} confidence
              </span>{" "}
              ({data.ai_real_feature_count}/{data.ai_total_feature_count} inputs real)
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

        {finalized ? (
          <p style={{ marginTop: "1rem" }}>
            <strong>Finalized: {finalized.final_score}</strong> —{" "}
            {finalized.decision === "accepted" ? "accepted as the AI estimate" : "edited by manager"}
            {finalized.decision === "edited" && data.ai_predicted_score != null && (
              <> (original AI estimate {data.ai_predicted_score})</>
            )}
            . This becomes the employee's current recorded score.
          </p>
        ) : editing ? (
          <div style={{ marginTop: "1rem" }}>
            <label>
              Final score:{" "}
              <input
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
              />
            </label>
            <br />
            <label style={{ display: "block", marginTop: "0.5rem" }}>
              Note (optional):
              <br />
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} style={{ width: "100%" }} />
            </label>
            {submitError && <p style={{ color: "#991b1b" }}>{submitError}</p>}
            <button
              className="btn-analyse"
              disabled={submitting}
              onClick={() => submitDecision("edited", parseFloat(editValue))}
              style={{ marginTop: "0.5rem" }}
            >
              Save
            </button>{" "}
            <button className="btn-secondary" disabled={submitting} onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        ) : (
          <div style={{ marginTop: "1rem" }}>
            {submitError && <p style={{ color: "#991b1b" }}>{submitError}</p>}
            <button
              className="btn-analyse"
              disabled={submitting}
              onClick={() => submitDecision("accepted", data.ai_predicted_score)}
            >
              Accept Score
            </button>{" "}
            <button className="btn-secondary" disabled={submitting} onClick={() => setEditing(true)}>
              Edit Score
            </button>
          </div>
        )}
      </div>

      <div className="result-grid">
        <div className="card">
          <h3 className="card-title">Score Signals</h3>
          <div className="cluster-list">
            {SIGNAL_META.map(({ key, label }) => {
              const val = data.score_signals?.[key];
              return (
                <div className="cluster-row" key={key}>
                  <span className="cluster-name">{label}</span>
                  <span className="cluster-val">{val != null ? val : "Not enough live data"}</span>
                </div>
              );
            })}
          </div>

          <h3 className="card-title" style={{ marginTop: "1.5rem" }}>
            Review Dimensions (out of 10)
          </h3>
          <div className="subscore-grid">
            {Object.entries(REVIEW_DIMENSION_LABELS).map(([key, label]) => {
              const val = data.score_signals?.review_dimensions?.[key];
              return (
                <div className="subscore-item" key={key}>
                  <span className="subscore-label">{label}</span>
                  <div className="subscore-bar-wrap">
                    <div className="subscore-bar" style={{ width: `${val != null ? val * 10 : 0}%` }} />
                  </div>
                  <span className="subscore-val">{val != null ? `${val}/10` : "—"}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <div className="card" style={{ marginTop: "1rem" }}>
            <h3 className="card-title">Review History</h3>
            <div className="review-list">
              {data.all_reviews.map((r) => (
                <div
                  className="review-row"
                  key={r.review_id}
                  onClick={() => onSelectReview(emp.employee_id, r.review_id)}
                >
                  <div>
                    <span className="review-type">{r.review_type}</span>
                    <span className="review-date">{r.review_date}</span>
                  </div>
                  <span className={`score-pill ${scoreClass(r.overall_score)}`}>{r.overall_score}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <button className="btn-secondary" onClick={onBack} style={{ marginTop: "1rem" }}>
        ← Back to employee list
      </button>
    </div>
  );
}
