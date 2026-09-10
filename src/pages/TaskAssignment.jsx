import { useEffect, useMemo, useState } from "react";
import { getOpenTasks, recommendForTask, scoreTaskAssignment } from "../api/client.js";

function scoreClass(score) {
  if (score == null) return "score-avg";
  if (score >= 70) return "score-exc";
  if (score >= 50) return "score-good";
  if (score >= 30) return "score-avg";
  return "score-low";
}

const COMPONENT_META = [
  { key: "delay_component", label: "Low Delay Risk" },
  { key: "skill_component", label: "Skill Fit" },
  { key: "availability_component", label: "Availability" },
  { key: "reliability_component", label: "Historical Reliability" },
  { key: "health_component", label: "Health / Burnout" },
];

export default function TaskAssignment() {
  const [tasks, setTasks] = useState([]);
  const [loadError, setLoadError] = useState(null);

  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({});

  const [selectedTask, setSelectedTask] = useState(null);
  const [candidates, setCandidates] = useState(null);
  const [ranking, setRanking] = useState(false);
  const [rankError, setRankError] = useState(null);

  const [adHocEmployeeId, setAdHocEmployeeId] = useState("");
  const [adHocResult, setAdHocResult] = useState(null);
  const [adHocError, setAdHocError] = useState(null);
  const [adHocLoading, setAdHocLoading] = useState(false);

  useEffect(() => {
    getOpenTasks()
      .then(setTasks)
      .catch((err) => setLoadError(err.message));
  }, []);

  const filterOptions = useMemo(() => {
    const options = {};
    for (const key of ["task_type", "priority", "required_role"]) {
      options[key] = [...new Set(tasks.map((t) => t[key]).filter((v) => v != null && v !== ""))].sort();
    }
    return options;
  }, [tasks]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    let rows = tasks;
    if (q) {
      rows = rows.filter((t) =>
        ["task_id", "task_name", "task_type"].some((k) => String(t[k] ?? "").toLowerCase().includes(q))
      );
    }
    for (const key of ["task_type", "priority", "required_role"]) {
      const val = filters[key];
      if (val) rows = rows.filter((t) => String(t[key] ?? "") === val);
    }
    return rows;
  }, [tasks, search, filters]);

  function setFilter(key, value) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  function clearFilters() {
    setSearch("");
    setFilters({});
  }

  function openTaskDetail(task) {
    setSelectedTask(task);
    setCandidates(null);
    setRankError(null);
    setAdHocResult(null);
    setAdHocError(null);
    setAdHocEmployeeId("");
  }

  function handleRunRanking(taskId = selectedTask?.task_id) {
    if (!taskId) return;
    setRankError(null);
    setRanking(true);
    recommendForTask(taskId, 5)
      .then(setCandidates)
      .catch((err) => setRankError(err.message))
      .finally(() => setRanking(false));
  }

  // "Find Candidates" button — runs the model immediately instead of opening
  // the no-model detail view first (that's what the row click does).
  function handleFindCandidatesNow(task) {
    setSelectedTask(task);
    setCandidates(null);
    setRankError(null);
    setAdHocResult(null);
    setAdHocError(null);
    setAdHocEmployeeId("");
    handleRunRanking(task.task_id);
  }

  function handleAdHocScore() {
    if (!adHocEmployeeId.trim() || !selectedTask) return;
    setAdHocLoading(true);
    setAdHocError(null);
    setAdHocResult(null);
    scoreTaskAssignment(selectedTask.task_id, adHocEmployeeId.trim())
      .then(setAdHocResult)
      .catch((err) => setAdHocError(err.message))
      .finally(() => setAdHocLoading(false));
  }

  function resetView() {
    setSelectedTask(null);
    setCandidates(null);
    setRankError(null);
  }

  if (selectedTask) {
    return (
      <div id="results-panel">
        <div className="card result-header">
          <div className="emp-meta">
            <h2>{selectedTask.task_id}</h2>
            <p>
              {selectedTask.task_name} &middot; {selectedTask.task_type} &middot; {selectedTask.priority} priority
              &middot; needs {selectedTask.required_role}
            </p>
          </div>
        </div>

        {!ranking && !candidates && (
          <div className="card">
            <h3 className="card-title">Candidate Ranking</h3>
            <p className="live-score-note">
              No candidate ranking has been run yet for this task. Run the model to rank employees
              by fit.
            </p>
            {rankError && <p style={{ color: "#991b1b", marginTop: "0.5rem" }}>{rankError}</p>}
            <button className="btn-analyse" style={{ marginTop: "0.75rem" }} onClick={handleRunRanking}>
              Run Candidate Ranking
            </button>
          </div>
        )}

        {ranking && (
          <div className="loading-wrap">
            <div className="spinner" />
            <p>Ranking candidates…</p>
          </div>
        )}

        {!ranking && candidates && (
          <div className="card">
            <h3 className="card-title">Top Candidates</h3>
            {candidates.length === 0 ? (
              <p className="live-score-note">No candidates found.</p>
            ) : (
              candidates.map((c) => <CandidateCard key={c.employee_id} data={c} />)
            )}
          </div>
        )}

        <div className="card">
          <h3 className="card-title">Score a Specific Employee</h3>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <input
              type="text"
              className="search-input"
              placeholder="Employee ID (e.g. EMP0123)"
              value={adHocEmployeeId}
              onChange={(e) => setAdHocEmployeeId(e.target.value)}
            />
            <button className="btn-analyse" disabled={adHocLoading} onClick={handleAdHocScore}>
              {adHocLoading ? "Scoring…" : "Score"}
            </button>
          </div>
          {adHocError && <p style={{ color: "#991b1b", marginTop: "0.5rem" }}>{adHocError}</p>}
          {adHocResult && (
            <div style={{ marginTop: "1rem" }}>
              <CandidateCard data={adHocResult} />
            </div>
          )}
        </div>

        <button className="btn-secondary" onClick={resetView} style={{ marginTop: "1rem" }}>
          ← Back to task list
        </button>
      </div>
    );
  }

  return (
    <div className="card" id="selector-card">
      <div className="card-header">
        <h2>Select Task</h2>
        <input
          type="text"
          id="task-search"
          placeholder="Search by ID, name or type…"
          className="search-input"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {loadError && <p style={{ color: "#991b1b" }}>{loadError}</p>}

      <div className="filter-bar">
        <select className="filter-select" value={filters.task_type || ""} onChange={(e) => setFilter("task_type", e.target.value)}>
          <option value="">All Task Types</option>
          {filterOptions.task_type?.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
        <select className="filter-select" value={filters.priority || ""} onChange={(e) => setFilter("priority", e.target.value)}>
          <option value="">All Priorities</option>
          {filterOptions.priority?.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
        <select className="filter-select" value={filters.required_role || ""} onChange={(e) => setFilter("required_role", e.target.value)}>
          <option value="">All Required Roles</option>
          {filterOptions.required_role?.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
        <button className="filter-clear-btn" onClick={clearFilters}>
          Clear filters
        </button>
      </div>

      <div className="employee-table-wrap">
        <table className="employee-table" id="task-table">
          <thead>
            <tr>
              <th>Task ID</th>
              <th>Name</th>
              <th>Type</th>
              <th>Priority</th>
              <th>Required Role</th>
              <th>Due Date</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr className="emp-row" key={t.task_id} onClick={() => openTaskDetail(t)} style={{ cursor: "pointer" }}>
                <td className="emp-name">{t.task_id}</td>
                <td>{t.task_name}</td>
                <td>{t.task_type}</td>
                <td>{t.priority}</td>
                <td>{t.required_role}</td>
                <td>{t.due_date ?? "—"}</td>
                <td>{t.status}</td>
                <td>
                  <button
                    className="btn-analyse"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleFindCandidatesNow(t);
                    }}
                  >
                    Find Candidates
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

function CandidateCard({ data }) {
  return (
    <div className="card" style={{ marginBottom: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong>{data.employee_id}</strong>
        <span className={`score-pill ${scoreClass(data.composite_score)}`}>{data.composite_score}</span>
      </div>
      <div className="cluster-list" style={{ marginTop: "0.5rem" }}>
        {COMPONENT_META.map(({ key, label }) => (
          <div className="cluster-row" key={key}>
            <span className="cluster-name">{label}</span>
            <span className="cluster-val">{data[key]}</span>
          </div>
        ))}
      </div>
      <p className="live-score-note" style={{ marginTop: "0.5rem" }}>
        Predicted delay risk: {data.predicted_delay_risk} &middot; Real skill match: {data.real_skill_match}%
      </p>
    </div>
  );
}
