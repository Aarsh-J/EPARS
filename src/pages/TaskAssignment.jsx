import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  getOpenTasks,
  recommendForTask,
  scoreTaskAssignment,
  assignKanbanTask,
} from "../api/client.js";

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

  const [assigningId, setAssigningId] = useState(null);
  const [assignNotice, setAssignNotice] = useState(null);
  const [assignError, setAssignError] = useState(null);

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
        ["task_id", "task_name", "task_type", "assigned_to"].some((k) =>
          String(t[k] ?? "").toLowerCase().includes(q)
        )
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
    setAssignNotice(null);
    setAssignError(null);
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

  function handleFindCandidatesNow(task) {
    setSelectedTask(task);
    setCandidates(null);
    setRankError(null);
    setAdHocResult(null);
    setAdHocError(null);
    setAdHocEmployeeId("");
    setAssignNotice(null);
    setAssignError(null);
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

  function handleAssign(employeeId) {
    if (!selectedTask || !employeeId) return;
    setAssigningId(employeeId);
    setAssignNotice(null);
    setAssignError(null);

    assignKanbanTask(selectedTask.task_id, employeeId)
      .then(() => {
        setAssignNotice(`Successfully assigned ${selectedTask.task_id} to ${employeeId}.`);
        setSelectedTask((prev) => ({
          ...prev,
          assigned_to: employeeId,
          status: prev.status === "Not Started" ? "In Progress" : prev.status,
        }));
        setTasks((prev) =>
          prev.map((t) =>
            t.task_id === selectedTask.task_id
              ? {
                  ...t,
                  assigned_to: employeeId,
                  status: t.status === "Not Started" ? "In Progress" : t.status,
                }
              : t
          )
        );
      })
      .catch((err) => {
        setAssignError(err.message || "Failed to assign task.");
      })
      .finally(() => {
        setAssigningId(null);
      });
  }

  function resetView() {
    setSelectedTask(null);
    setCandidates(null);
    setRankError(null);
    setAssignNotice(null);
    setAssignError(null);
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
            <p style={{ marginTop: "0.35rem", fontSize: "0.88rem", color: "#64748b" }}>
              Current Assignee:{" "}
              {selectedTask.assigned_to ? (
                <span
                  style={{
                    backgroundColor: "#e0f2fe",
                    color: "#0369a1",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    fontWeight: 600,
                  }}
                >
                  {selectedTask.assigned_to}
                </span>
              ) : (
                <em style={{ color: "#94a3b8" }}>Unassigned</em>
              )}
            </p>
          </div>
        </div>

        {assignNotice && (
          <div
            style={{
              padding: "0.75rem 1rem",
              borderRadius: "8px",
              backgroundColor: "#dcfce7",
              color: "#166534",
              fontWeight: 500,
              marginBottom: "1rem",
              border: "1px solid #bbf7d0",
            }}
          >
            ✓ {assignNotice}
          </div>
        )}

        {assignError && (
          <div
            style={{
              padding: "0.75rem 1rem",
              borderRadius: "8px",
              backgroundColor: "#fee2e2",
              color: "#991b1b",
              fontWeight: 500,
              marginBottom: "1rem",
              border: "1px solid #fecaca",
            }}
          >
            ✕ {assignError}
          </div>
        )}

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
              candidates.map((c) => (
                <CandidateCard
                  key={c.employee_id}
                  data={c}
                  isAssigned={selectedTask.assigned_to === c.employee_id}
                  onAssign={handleAssign}
                  assigning={assigningId === c.employee_id}
                />
              ))
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
              <CandidateCard
                data={adHocResult}
                isAssigned={selectedTask.assigned_to === adHocResult.employee_id}
                onAssign={handleAssign}
                assigning={assigningId === adHocResult.employee_id}
              />
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
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <h2>Select Task</h2>
          <Link to="/kanban" className="btn-jira-primary btn-sm" style={{ textDecoration: "none" }}>
            View in Kanban Board →
          </Link>
        </div>
        <input
          type="text"
          id="task-search"
          placeholder="Search by ID, name, role or assignee…"
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
              <th>Assigned To</th>
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
                <td>
                  {t.assigned_to ? (
                    <span
                      style={{
                        backgroundColor: "#f1f5f9",
                        color: "#334155",
                        padding: "2px 6px",
                        borderRadius: "4px",
                        fontSize: "0.8rem",
                        fontWeight: 600,
                      }}
                    >
                      {t.assigned_to}
                    </span>
                  ) : (
                    <span style={{ color: "#94a3b8" }}>—</span>
                  )}
                </td>
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

function CandidateCard({ data, isAssigned = false, onAssign, assigning = false }) {
  return (
    <div className="card" style={{ marginBottom: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <strong style={{ fontSize: "1.05rem" }}>{data.employee_id}</strong>
          {isAssigned && (
            <span
              style={{
                padding: "2px 8px",
                borderRadius: "999px",
                fontSize: "0.75rem",
                fontWeight: 600,
                backgroundColor: "#dcfce7",
                color: "#15803d",
              }}
            >
              ✓ Currently Assigned
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <span className={`score-pill ${scoreClass(data.composite_score)}`}>{data.composite_score}</span>
          {!isAssigned && onAssign && (
            <button
              className="btn-analyse btn-sm"
              disabled={assigning}
              onClick={() => onAssign(data.employee_id)}
              style={{
                padding: "4px 12px",
                fontSize: "0.82rem",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              {assigning ? "Assigning…" : "Assign Task →"}
            </button>
          )}
        </div>
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
