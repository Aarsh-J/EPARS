import { useEffect, useMemo, useState } from "react";
import {
  getProjectsWithOpenTasks,
  recommendTeams,
  checkTeamComposition,
} from "../api/client.js";
import {
  SAMPLE_PROJECTS,
  SAMPLE_RECOMMENDATIONS,
} from "../data/teamFormationData.js";

function scoreClass(score) {
  if (score == null) return "score-avg";
  if (score >= 85) return "score-exc";
  if (score >= 70) return "score-good";
  if (score >= 50) return "score-avg";
  return "score-low";
}

const DIMENSION_META = [
  { key: "task_fit", label: "Task Fit", weight: "45%", desc: "Individual suitability for assigned tasks (from Model 3)" },
  { key: "experience_balance", label: "Experience Balance", weight: "10%", desc: "Mix of junior, mid, and senior expertise" },
  { key: "workload_balance", label: "Workload & Health", weight: "10%", desc: "Healthy overtime & low burnout risk score" },
  { key: "past_overlap", label: "Historical Synergy", weight: "5%", desc: "Co-occurrence in past successful team projects" },
  { key: "composition_typicality", label: "Composition Typicality", weight: "10%", desc: "Isolation Forest typicality score vs company history" },
];

export default function TeamFormation() {
  // ── Project List State ─────────────────────────────────────────────────────
  const [projects, setProjects] = useState([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [projectError, setProjectError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  // Recommendation Parameters
  const [numTeams, setNumTeams] = useState(3);
  const [topM, setTopM] = useState(5);

  // Selected Project & Results
  const [selectedProject, setSelectedProject] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [activeTeamIndex, setActiveTeamIndex] = useState(0);
  const [loadingTeams, setLoadingTeams] = useState(false);
  const [recommendError, setRecommendError] = useState(null);

  // Ad-Hoc Custom Roster Checker
  const [adHocIdsInput, setAdHocIdsInput] = useState("");
  const [adHocResult, setAdHocResult] = useState(null);
  const [adHocLoading, setAdHocLoading] = useState(false);
  const [adHocError, setAdHocError] = useState(null);

  // ── Load Projects ──────────────────────────────────────────────────────────
  useEffect(() => {
    setLoadingProjects(true);
    getProjectsWithOpenTasks()
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setProjects(data);
        } else {
          setProjects(SAMPLE_PROJECTS);
        }
      })
      .catch((err) => {
        console.warn("Backend unavailable, using sample projects:", err.message);
        setProjects(SAMPLE_PROJECTS);
      })
      .finally(() => setLoadingProjects(false));
  }, []);

  // Filtered Projects
  const filteredProjects = useMemo(() => {
    const q = search.toLowerCase().trim();
    return projects.filter((p) => {
      const matchesSearch =
        !q ||
        (p.project_id && p.project_id.toLowerCase().includes(q)) ||
        (p.project_name && p.project_name.toLowerCase().includes(q)) ||
        (p.department && p.department.toLowerCase().includes(q));

      const matchesStatus =
        statusFilter === "all" ||
        (p.current_status && p.current_status.toLowerCase() === statusFilter.toLowerCase());

      return matchesSearch && matchesStatus;
    });
  }, [projects, search, statusFilter]);

  // ── Form Team Handler ──────────────────────────────────────────────────────
  const handleSelectProject = (project) => {
    setSelectedProject(project);
    setRecommendations(null);
    setActiveTeamIndex(0);
    setRecommendError(null);
    setLoadingTeams(true);

    recommendTeams(project.project_id, numTeams, topM)
      .then((res) => {
        if (Array.isArray(res) && res.length > 0) {
          setRecommendations(res);
        } else {
          // Fallback to sample recommendations if DB has no candidates
          setRecommendations(SAMPLE_RECOMMENDATIONS[project.project_id] || SAMPLE_RECOMMENDATIONS.PRJ026);
        }
      })
      .catch((err) => {
        console.warn("Backend recommendation call failed, fallback to sample data:", err.message);
        const fallback = SAMPLE_RECOMMENDATIONS[project.project_id] || SAMPLE_RECOMMENDATIONS.PRJ026;
        if (fallback) {
          setRecommendations(fallback);
        } else {
          setRecommendError(err.message || "Failed to generate team recommendations.");
        }
      })
      .finally(() => setLoadingTeams(false));
  };

  // ── Ad-Hoc Roster Composition Checker ──────────────────────────────────────
  const handleCheckAdHoc = (e) => {
    e.preventDefault();
    const ids = adHocIdsInput
      .split(/[\s,]+/)
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    if (ids.length < 2) {
      setAdHocError("Please enter at least 2 distinct Employee IDs (e.g., EMP001, EMP003).");
      return;
    }

    setAdHocLoading(true);
    setAdHocError(null);
    setAdHocResult(null);

    checkTeamComposition(ids)
      .then(setAdHocResult)
      .catch((err) => {
        setAdHocError(err.message || "Error checking team composition.");
      })
      .finally(() => setAdHocLoading(false));
  };

  const handleReset = () => {
    setSelectedProject(null);
    setRecommendations(null);
    setActiveTeamIndex(0);
    setRecommendError(null);
  };

  // ── Render: Team Results View ──────────────────────────────────────────────
  if (selectedProject) {
    const activeTeam = recommendations ? recommendations[activeTeamIndex] : null;

    return (
      <div id="team-formation-results">
        {/* Project Header Card */}
        <div className="card result-header">
          <div className="emp-meta">
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className="badge-project-id">{selectedProject.project_id}</span>
              <h2>{selectedProject.project_name}</h2>
            </div>
            <p style={{ marginTop: "4px" }}>
              Status: <strong>{selectedProject.current_status || "Active"}</strong> &middot;{" "}
              Open Tasks to Fill: <strong>{selectedProject.open_task_count || "Multiple"}</strong>{" "}
              {activeTeam?.search_mode && (
                <span>&middot; Search Engine: <em>{activeTeam.search_mode}</em></span>
              )}
            </p>
          </div>
          <button className="btn-secondary" onClick={handleReset}>
            ← Back to projects
          </button>
        </div>

        {/* Loading Spinner */}
        {loadingTeams && (
          <div className="loading-wrap">
            <div className="spinner" />
            <p>Evaluating candidate team combinations (Hungarian assignment &amp; Isolation Forest typicality)…</p>
          </div>
        )}

        {/* Error Callout */}
        {!loadingTeams && recommendError && (
          <div className="card" style={{ borderColor: "#fca5a5", background: "#fef2f2" }}>
            <p style={{ color: "#991b1b" }}>{recommendError}</p>
          </div>
        )}

        {/* Recommendations Multi-Option View */}
        {!loadingTeams && recommendations && recommendations.length > 0 && activeTeam && (
          <>
            {/* Team Option Selector Tabs */}
            <div className="team-options-bar">
              <span className="team-options-label">Recommended Team Rosters:</span>
              <div className="team-tabs-list">
                {recommendations.map((team, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className={`team-tab-btn ${activeTeamIndex === idx ? "active" : ""}`}
                    onClick={() => setActiveTeamIndex(idx)}
                  >
                    <span className="tab-title">Option {idx + 1}</span>
                    <span className={`tab-score-pill ${scoreClass(team.team_score)}`}>
                      {team.team_score}
                    </span>
                    {idx === 0 && <span className="tab-badge-best">Best Fit</span>}
                  </button>
                ))}
              </div>
            </div>

            {/* Active Team Overview Card */}
            <div className="card">
              <div className="team-overview-header">
                <div>
                  <h3 className="card-title" style={{ fontSize: "16px", marginBottom: "4px" }}>
                    Team Option {activeTeamIndex + 1} Overview
                  </h3>
                  <p style={{ color: "#64748b", fontSize: "13px" }}>
                    Roster of {activeTeam.assignments?.length || activeTeam.n_tasks} members tailored for {selectedProject.project_name}
                  </p>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{ textAlign: "right" }}>
                    <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", display: "block" }}>
                      Composite Team Score
                    </span>
                    <span className={`score-pill ${scoreClass(activeTeam.team_score)}`} style={{ fontSize: "16px", padding: "4px 12px" }}>
                      {activeTeam.team_score} / 100
                    </span>
                  </div>
                </div>
              </div>

              {/* Anomaly Advisory Callout Banner */}
              {activeTeam.unusual_composition ? (
                <div className="composition-alert warning">
                  <div className="alert-icon">⚠️</div>
                  <div className="alert-content">
                    <strong>Advisory Flag: Unusual Team Composition Profile</strong>
                    <p>
                      This team's cross-departmental or seniority distribution deviates significantly from historical team patterns.
                    </p>
                    {activeTeam.composition_notes && (
                      <ul className="alert-notes-list">
                        {activeTeam.composition_notes.map((note, i) => (
                          <li key={i}>{note}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              ) : (
                <div className="composition-alert success">
                  <div className="alert-icon">✓</div>
                  <div className="alert-content">
                    <strong>Standard Composition Profile</strong>
                    <p>
                      The Isolation Forest model verified this roster matches established historical team formation patterns (Typicality score: {activeTeam.score_breakdown?.composition_typicality ?? 85}).
                    </p>
                  </div>
                </div>
              )}

              {/* 5-Dimension Score Breakdown */}
              <div style={{ marginTop: "1.25rem" }}>
                <h4 className="detail-section-title">Team Performance Factors</h4>
                <div className="dimension-grid">
                  {DIMENSION_META.map(({ key, label, weight, desc }) => {
                    const val = activeTeam.score_breakdown ? activeTeam.score_breakdown[key] : null;
                    return (
                      <div className="dimension-card" key={key}>
                        <div className="dimension-header">
                          <span className="dimension-name">{label}</span>
                          <span className="dimension-weight">wt. {weight}</span>
                        </div>
                        <div className="dimension-score-row">
                          <span className={`dimension-val ${scoreClass(val)}`}>
                            {val != null ? val : "—"}
                          </span>
                        </div>
                        <div className="dimension-bar-track">
                          <div
                            className="dimension-bar-fill"
                            style={{
                              width: `${Math.min(100, Math.max(0, val || 0))}%`,
                              backgroundColor: val >= 85 ? "#10b981" : val >= 70 ? "#3b82f6" : val >= 50 ? "#f59e0b" : "#ef4444",
                            }}
                          />
                        </div>
                        <p className="dimension-desc">{desc}</p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Task-to-Employee Assignment Roster */}
              <div style={{ marginTop: "1.5rem" }}>
                <h4 className="detail-section-title">Assigned Member Roster (1 Employee per Task)</h4>
                <div className="employee-table-wrap">
                  <table className="employee-table">
                    <thead>
                      <tr>
                        <th>Task</th>
                        <th>Assigned Member</th>
                        <th>Role &amp; Seniority</th>
                        <th>Department</th>
                        <th>Task Fit Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeTeam.assignments?.map((item) => (
                        <tr key={item.task_id}>
                          <td>
                            <strong>{item.task_id}</strong>
                            {item.task_name && (
                              <div style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>
                                {item.task_name}
                              </div>
                            )}
                          </td>
                          <td>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <div className="member-avatar">
                                {(item.employee_name || item.employee_id).substring(0, 2).toUpperCase()}
                              </div>
                              <div>
                                <strong>{item.employee_name || item.employee_id}</strong>
                                <div style={{ fontSize: "11px", color: "#64748b" }}>{item.employee_id}</div>
                              </div>
                            </div>
                          </td>
                          <td>
                            <span>{item.role || "Developer"}</span> &middot;{" "}
                            <span className="seniority-tag">{item.seniority || "Mid"}</span>
                          </td>
                          <td>{item.department || "Engineering"}</td>
                          <td>
                            <span className={`score-pill ${scoreClass(item.task_composite_score)}`}>
                              {item.task_composite_score ?? "—"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Ad-Hoc Roster Composition Evaluator */}
        <div className="card" style={{ marginTop: "1.5rem" }}>
          <h3 className="card-title">Test a Custom Team Roster</h3>
          <p style={{ color: "#64748b", fontSize: "13px", marginBottom: "1rem" }}>
            Check any custom set of employees against the Isolation Forest composition model to evaluate typicality and identify friction risks.
          </p>

          <form onSubmit={handleCheckAdHoc} style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <input
              type="text"
              className="search-input"
              style={{ minWidth: "320px", flex: 1 }}
              placeholder="Enter Employee IDs separated by comma (e.g. EMP001, EMP003, EMP007)"
              value={adHocIdsInput}
              onChange={(e) => setAdHocIdsInput(e.target.value)}
            />
            <button type="submit" className="btn-analyse" disabled={adHocLoading}>
              {adHocLoading ? "Evaluating…" : "Check Composition"}
            </button>
          </form>

          {adHocError && (
            <p style={{ color: "#991b1b", marginTop: "0.75rem", fontSize: "13px" }}>{adHocError}</p>
          )}

          {adHocResult && (
            <div style={{ marginTop: "1rem", padding: "1rem", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <strong>Custom Roster:</strong> {adHocResult.employee_ids?.join(", ")}
                </div>
                <div>
                  <span style={{ fontSize: "12px", color: "#64748b", marginRight: "8px" }}>Typicality Score:</span>
                  <span className={`score-pill ${scoreClass(adHocResult.composition_typicality)}`}>
                    {adHocResult.composition_typicality}
                  </span>
                </div>
              </div>

              {adHocResult.unusual_composition ? (
                <div className="composition-alert warning" style={{ marginTop: "0.75rem" }}>
                  <strong>⚠️ Advisory Flag:</strong> This custom roster has an unusual department or seniority distribution.
                  {adHocResult.composition_notes && (
                    <ul className="alert-notes-list" style={{ marginTop: "6px" }}>
                      {adHocResult.composition_notes.map((n, i) => (
                        <li key={i}>{n}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                <p style={{ color: "#065f46", fontSize: "13px", marginTop: "0.5rem" }}>
                  ✓ This team composition matches historical project norms.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Render: Project Selector Table View ────────────────────────────────────
  return (
    <div className="card" id="team-formation-selector">
      <div className="card-header">
        <div>
          <h2>Team Formation</h2>
          <p style={{ color: "#64748b", fontSize: "13px", marginTop: "4px" }}>
            Select a project with open tasks to generate optimal multi-candidate teams using Model 4.
          </p>
        </div>

        <input
          type="text"
          placeholder="Search by project name or ID…"
          className="search-input"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {projectError && <p style={{ color: "#991b1b" }}>{projectError}</p>}

      {/* Filter and Config Bar */}
      <div className="filter-bar" style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "10px" }}>
        <div style={{ display: "flex", gap: "8px" }}>
          <select
            className="filter-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Project Statuses</option>
            <option value="active">Active</option>
            <option value="planning">Planning</option>
          </select>

          <button className="filter-clear-btn" onClick={() => { setSearch(""); setStatusFilter("all"); }}>
            Reset filters
          </button>
        </div>

        {/* Algorithm Settings */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px", fontSize: "12.5px", color: "#475569" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span>Teams to form:</span>
            <select
              className="filter-select"
              value={numTeams}
              onChange={(e) => setNumTeams(Number(e.target.value))}
              style={{ padding: "4px 8px" }}
            >
              <option value={1}>1 Team</option>
              <option value={2}>2 Teams</option>
              <option value={3}>3 Teams</option>
              <option value={5}>5 Teams</option>
            </select>
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span>Candidates/task:</span>
            <select
              className="filter-select"
              value={topM}
              onChange={(e) => setTopM(Number(e.target.value))}
              style={{ padding: "4px 8px" }}
            >
              <option value={3}>Top 3</option>
              <option value={5}>Top 5</option>
              <option value={8}>Top 8</option>
            </select>
          </label>
        </div>
      </div>

      {/* Projects Table */}
      {loadingProjects ? (
        <div className="loading-wrap">
          <div className="spinner" />
          <p>Loading projects with open tasks…</p>
        </div>
      ) : (
        <div className="employee-table-wrap">
          <table className="employee-table">
            <thead>
              <tr>
                <th>Project ID</th>
                <th>Project Name</th>
                <th>Department</th>
                <th>Status</th>
                <th>Open Tasks</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filteredProjects.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}>
                    No projects found matching current filters.
                  </td>
                </tr>
              ) : (
                filteredProjects.map((p) => (
                  <tr
                    className="emp-row"
                    key={p.project_id}
                    onClick={() => handleSelectProject(p)}
                    style={{ cursor: "pointer" }}
                  >
                    <td className="emp-name">{p.project_id}</td>
                    <td>
                      <strong>{p.project_name}</strong>
                      {p.description && (
                        <div style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>
                          {p.description}
                        </div>
                      )}
                    </td>
                    <td>{p.department || "Engineering"}</td>
                    <td>
                      <span className={`status-pill status-${(p.current_status || "active").toLowerCase()}`}>
                        {p.current_status || "Active"}
                      </span>
                    </td>
                    <td>
                      <span className="open-tasks-count">{p.open_task_count || "—"} open tasks</span>
                    </td>
                    <td>
                      <button className="btn-analyse" onClick={() => handleSelectProject(p)}>
                        Form Team →
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
