import { useEffect, useMemo, useState } from "react";
import { getEmployees, analyseEmployee } from "../api/client.js";

const CLUSTER_META = [
  { key: "technical", name: "Technical", weight: "30%", color: "#1d4ed8" },
  { key: "behavioral", name: "Behavioral", weight: "25%", color: "#0891b2" },
  { key: "quality", name: "Quality", weight: "20%", color: "#059669" },
  { key: "productivity", name: "Productivity", weight: "25%", color: "#d97706" },
];

const SUBSCORE_LABELS = {
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

export default function Performance() {
  const [employees, setEmployees] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [search, setSearch] = useState("");

  const [selectedId, setSelectedId] = useState(null);
  const [result, setResult] = useState(null);
  const [analysing, setAnalysing] = useState(false);
  const [analyseError, setAnalyseError] = useState(null);

  useEffect(() => {
    getEmployees()
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

      <div className="employee-table-wrap">
        <table className="employee-table" id="emp-table">
          <thead>
            <tr>
              <th>Employee ID</th>
              <th>Department</th>
              <th>Role</th>
              <th>Seniority</th>
              <th>Latest Score</th>
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
          <div className="score-circle" style={{ borderColor: data.rating_color }}>
            <span>{data.predicted_score}</span>
            <small>/100</small>
          </div>
          <p style={{ color: data.rating_color }}>{data.rating_label}</p>
        </div>
      </div>

      <div className="result-grid">
        <div className="card">
          <h3 className="card-title">Score Breakdown</h3>
          <div className="cluster-list">
            {CLUSTER_META.map((c) => {
              const val = data.breakdown[c.key];
              return (
                <div className="cluster-row" key={c.key}>
                  <span className="cluster-name">
                    {c.name} <small>({c.weight})</small>
                  </span>
                  <div className="bar-wrap">
                    <div
                      className="bar"
                      style={{ width: `${Math.min(val, 100)}%`, background: c.color }}
                    />
                  </div>
                  <span className="cluster-val">{val}</span>
                </div>
              );
            })}
          </div>

          <h3 className="card-title" style={{ marginTop: "1.5rem" }}>
            Sub-scores (out of 10)
          </h3>
          <div className="subscore-grid">
            {Object.entries(SUBSCORE_LABELS).map(([key, label]) => (
              <div className="subscore-item" key={key}>
                <span className="subscore-label">{label}</span>
                <div className="subscore-bar-wrap">
                  <div className="subscore-bar" style={{ width: `${data.sub_scores[key] * 10}%` }} />
                </div>
                <span className="subscore-val">{data.sub_scores[key]}/10</span>
              </div>
            ))}
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
