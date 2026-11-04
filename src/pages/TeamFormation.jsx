import { useEffect, useMemo, useRef, useState } from "react";
import {
  getProjectsWithOpenTasks,
  recommendTeams,
  confirmTeamFormation,
  checkTeamComposition,
} from "../api/client.js";

function scoreClass(score) {
  if (score == null) return "score-avg";
  if (score >= 85) return "score-exc";
  if (score >= 70) return "score-good";
  if (score >= 50) return "score-avg";
  return "score-low";
}

const DIMENSION_META = [
  { key: "task_fit", label: "Task Fit", desc: "Model 3 fit for the recommended task assignments" },
  { key: "skill_coverage", label: "Skill Coverage", desc: "Coverage of required skills across assigned tasks" },
  { key: "experience_balance", label: "Experience Balance", desc: "Experience distribution across the roster" },
  { key: "workload_balance", label: "Workload Balance", desc: "Fairness of projected workload" },
  { key: "historical_cooccurrence", label: "Historical Co-occurrence", desc: "Recorded roster co-occurrence; not evidence of successful collaboration" },
  { key: "composition_typicality", label: "Composition Typicality", desc: "Advisory: resemblance to historical team compositions" },
];

export default function TeamFormation() {
  const recommendationRequestId = useRef(0);
  const confirmationInFlight = useRef(false);
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
  const [selectedTeamLeadId, setSelectedTeamLeadId] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [confirmationError, setConfirmationError] = useState(null);
  const [confirmedTeam, setConfirmedTeam] = useState(null);

  // Ad-Hoc Custom Roster Checker
  const [adHocIdsInput, setAdHocIdsInput] = useState("");
  const [adHocResult, setAdHocResult] = useState(null);
  const [adHocLoading, setAdHocLoading] = useState(false);
  const [adHocError, setAdHocError] = useState(null);

  // ── Load Projects ──────────────────────────────────────────────────────────
  useEffect(() => {
    let active = true;
    setLoadingProjects(true);
    setProjectError(null);
    getProjectsWithOpenTasks()
      .then((data) => {
        if (active) setProjects(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        if (active) {
          setProjects([]);
          setProjectError(err.message || "Unable to load projects.");
        }
      })
      .finally(() => {
        if (active) setLoadingProjects(false);
      });
    return () => {
      active = false;
    };
  }, []);

  // Filtered Projects
  const filteredProjects = useMemo(() => {
    const q = search.toLowerCase().trim();
    return projects.filter((p) => {
      const matchesSearch =
        !q ||
        (p.project_id && p.project_id.toLowerCase().includes(q)) ||
        (p.project_name && p.project_name.toLowerCase().includes(q));

      const matchesStatus =
        statusFilter === "all" ||
        (p.current_status && p.current_status.toLowerCase() === statusFilter.toLowerCase());

      return matchesSearch && matchesStatus;
    });
  }, [projects, search, statusFilter]);

  // ── Form Team Handler ──────────────────────────────────────────────────────
  const handleSelectProject = (project) => {
    const requestId = ++recommendationRequestId.current;
    setSelectedProject(project);
    setRecommendations(null);
    setActiveTeamIndex(0);
    setRecommendError(null);
    setSelectedTeamLeadId("");
    setConfirmationError(null);
    setConfirmedTeam(null);
    setLoadingTeams(true);

    recommendTeams(project.project_id, numTeams, topM)
      .then((res) => {
        if (requestId !== recommendationRequestId.current) return;
        if (Array.isArray(res)) {
          setRecommendations(res);
        } else {
          setRecommendations([]);
        }
      })
      .catch((err) => {
        if (requestId === recommendationRequestId.current) {
          setRecommendations(null);
          setRecommendError(err.message || "Failed to generate team recommendations.");
        }
      })
      .finally(() => {
        if (requestId === recommendationRequestId.current) setLoadingTeams(false);
      });
  };

  const handleConfirmTeam = async () => {
    const activeTeam = recommendations?.[activeTeamIndex];
    if (confirmationInFlight.current || !selectedTeamLeadId || !activeTeam) return;
    confirmationInFlight.current = true;
    setConfirming(true);
    setConfirmationError(null);
    setConfirmedTeam(null);
    try {
      const result = await confirmTeamFormation(
        selectedProject.project_id,
        activeTeam,
        selectedTeamLeadId
      );
      setConfirmedTeam(result);
    } catch (err) {
      const message = err.message || "Team confirmation failed.";
      setConfirmationError(
        /\b409\b|conflict|changed|stale|active AI formation/i.test(message)
          ? `${message} Refresh the recommendation before trying again.`
          : message
      );
    } finally {
      confirmationInFlight.current = false;
      setConfirming(false);
    }
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
    recommendationRequestId.current += 1;
    setSelectedProject(null);
    setRecommendations(null);
    setActiveTeamIndex(0);
    setRecommendError(null);
    setSelectedTeamLeadId("");
    setConfirmationError(null);
    setConfirmedTeam(null);
    setLoadingTeams(false);
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
              Status: <strong>{selectedProject.current_status || "—"}</strong> &middot;{" "}
              Team size: <strong>{selectedProject.team_size ?? "Unavailable"}</strong> &middot;{" "}
              Open tasks: <strong>{selectedProject.open_task_count ?? "—"}</strong>{" "}
              {activeTeam?.search_mode && (
                <span>&middot; Search Engine: <em>{activeTeam.search_mode}</em></span>
              )}
            </p>
          </div>
          <button className="btn-secondary" onClick={handleReset} disabled={confirming}>
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
            <button className="btn-analyse" style={{ marginTop: "0.75rem" }} onClick={() => handleSelectProject(selectedProject)}>
              Refresh recommendation
            </button>
          </div>
        )}

        {!loadingTeams && !recommendError && Array.isArray(recommendations) && recommendations.length === 0 && (
          <div className="card">
            <p>No recommendations are available for this project.</p>
            <button className="btn-analyse" style={{ marginTop: "0.75rem" }} onClick={() => handleSelectProject(selectedProject)}>
              Try again
            </button>
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
                    disabled={confirming || Boolean(confirmedTeam)}
                    onClick={() => {
                      setActiveTeamIndex(idx);
                      setSelectedTeamLeadId("");
                      setConfirmationError(null);
                    }}
                  >
                    <span className="tab-title">Option {idx + 1}</span>
                    <span className={`tab-score-pill ${scoreClass(team.team_score)}`}>
                      {team.team_score ?? "—"}
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
                    Recommended roster: {activeTeam.team_member_ids?.length ?? "—"} of {activeTeam.team_size ?? selectedProject.team_size ?? "—"} members.
                    {" "}Assignments cover {activeTeam.assignments?.length ?? 0} tasks.
                  </p>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{ textAlign: "right" }}>
                    <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", display: "block" }}>
                      Composite Team Score
                    </span>
                    <span className={`score-pill ${scoreClass(activeTeam.team_score)}`} style={{ fontSize: "16px", padding: "4px 12px" }}>
                      {activeTeam.team_score != null ? `${activeTeam.team_score} / 100` : "Unavailable"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Anomaly Advisory Callout Banner */}
              {activeTeam.unusual_composition ? (
                <div className="composition-alert warning">
                  <div className="alert-icon">⚠️</div>
                  <div className="alert-content">
                    <strong>Composition typicality advisory: unusual profile</strong>
                    <p>
                      The Isolation Forest indicates this composition differs from the historical team compositions it was trained on. This is not a team-quality or compatibility prediction.
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
              ) : activeTeam.score_breakdown?.composition_typicality != null ? (
                <div className="composition-alert success">
                  <div className="alert-icon">✓</div>
                  <div className="alert-content">
                    <strong>Composition typicality advisory</strong>
                    <p>
                      The composition was not flagged as unusual relative to historical team compositions (score: {activeTeam.score_breakdown.composition_typicality}).
                    </p>
                  </div>
                </div>
              ) : (
                <div className="composition-alert">
                  Composition typicality is unavailable; this advisory does not predict team quality or compatibility.
                </div>
              )}

              {/* Six-dimension score breakdown */}
              <div style={{ marginTop: "1.25rem" }}>
                <h4 className="detail-section-title">Score Breakdown</h4>
                <div className="dimension-grid">
                  {DIMENSION_META.map(({ key, label, desc }) => {
                    const val = activeTeam.score_breakdown ? activeTeam.score_breakdown[key] : null;
                    const weight = activeTeam.score_weights?.[key];
                    return (
                      <div className="dimension-card" key={key}>
                        <div className="dimension-header">
                          <span className="dimension-name">{label}</span>
                          <span className="dimension-weight">
                            {typeof weight === "number" ? `wt. ${(weight * 100).toFixed(0)}%` : "Weight unavailable"}
                          </span>
                        </div>
                        <div className="dimension-score-row">
                          <span className={`dimension-val ${scoreClass(val)}`}>
                            {val != null ? val : "—"}
                          </span>
                        </div>
                        {val != null && <div className="dimension-bar-track">
                          <div className="dimension-bar-fill" style={{
                            width: `${Math.min(100, Math.max(0, val))}%`,
                            backgroundColor: val >= 85 ? "#10b981" : val >= 70 ? "#3b82f6" : val >= 50 ? "#f59e0b" : "#ef4444",
                          }} />
                        </div>}
                        <p className="dimension-desc">{desc}</p>
                      </div>
                    );
                  })}
                </div>
                {activeTeam.score_unavailable_components?.length > 0 && (
                  <p role="status" style={{ color: "#64748b", fontSize: "13px", marginTop: "0.75rem" }}>
                    Scores unavailable: {activeTeam.score_unavailable_components.join(", ")}. The final score is not calculated when a component is unavailable.
                  </p>
                )}
              </div>

              <div style={{ marginTop: "1.5rem" }}>
                <h4 className="detail-section-title">Recommended Roster</h4>
                {Array.isArray(activeTeam.team_member_ids) && activeTeam.team_member_ids.length > 0 ? (
                  <ul>
                    {activeTeam.team_member_ids.map((employeeId) => (
                      <li key={employeeId}>{employeeId}</li>
                    ))}
                  </ul>
                ) : <p>Roster IDs are unavailable in this recommendation.</p>}
              </div>

              {/* Task-to-Employee Assignment Roster */}
              <div style={{ marginTop: "1.5rem" }}>
                <h4 className="detail-section-title">Task Assignments</h4>
                <div className="employee-table-wrap">
                  <table className="employee-table">
                    <thead>
                      <tr>
                        <th>Task ID</th>
                        <th>Assigned Employee ID</th>
                        <th>Estimated Hours</th>
                        <th>Required Skills</th>
                        <th>Task Fit Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeTeam.assignments?.map((item) => (
                        <tr key={item.task_id}>
                          <td><strong>{item.task_id}</strong></td>
                          <td>{item.employee_id || "Unavailable"}</td>
                          <td>{item.task_estimated_hours ?? "Unavailable"}</td>
                          <td>{item.task_required_skills ?? "Unavailable"}</td>
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

              <div className="card" style={{ marginTop: "1.5rem" }}>
                <h4 className="detail-section-title">Manager Confirmation</h4>
                {confirmedTeam ? (
                  <p role="status" style={{ color: "#166534" }}>
                    Team formation {confirmedTeam.team_id} confirmed for project {confirmedTeam.project_id}.
                  </p>
                ) : (
                  <>
                    <label htmlFor="team-lead-select">Select team lead from the recommended roster</label>
                    <select
                      id="team-lead-select"
                      className="filter-select"
                      value={selectedTeamLeadId}
                      disabled={confirming}
                      onChange={(event) => setSelectedTeamLeadId(event.target.value)}
                    >
                      <option value="">Select a team lead</option>
                      {(activeTeam.team_member_ids || []).map((employeeId) => (
                        <option key={employeeId} value={employeeId}>{employeeId}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="btn-analyse"
                      style={{ marginLeft: "0.75rem" }}
                      disabled={confirming || !selectedTeamLeadId}
                      onClick={handleConfirmTeam}
                    >
                      {confirming ? "Confirming…" : "Confirm team formation"}
                    </button>
                  </>
                )}
                {confirmationError && (
                  <p role="alert" style={{ color: "#991b1b", marginTop: "0.75rem" }}>
                    {confirmationError}
                    {/\b409\b|conflict|changed|stale|active AI formation/i.test(confirmationError) && (
                      <button
                        type="button"
                        className="btn-secondary"
                        style={{ marginLeft: "0.75rem" }}
                        disabled={confirming}
                        onClick={() => handleSelectProject(selectedProject)}
                      >
                        Refresh recommendation
                      </button>
                    )}
                  </p>
                )}
              </div>
            </div>
          </>
        )}

        {/* Ad-Hoc Roster Composition Evaluator */}
        <div className="card" style={{ marginTop: "1.5rem" }}>
          <h3 className="card-title">Test a Custom Team Roster</h3>
          <p style={{ color: "#64748b", fontSize: "13px", marginBottom: "1rem" }}>
            Check a roster's resemblance to historical team compositions. This is an advisory, not a prediction of team quality or compatibility.
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
                <th>Status</th>
                <th>Team Size</th>
                <th>Open Tasks</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filteredProjects.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}>
                    {projects.length === 0
                      ? "No projects with open tasks are available."
                      : "No projects found matching current filters."}
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
                    </td>
                    <td>
                      {p.current_status
                        ? <span className={`status-pill status-${p.current_status.toLowerCase()}`}>{p.current_status}</span>
                        : "Unavailable"}
                    </td>
                    <td>{p.team_size ?? "Unavailable"}</td>
                    <td>
                      <span className="open-tasks-count">{p.open_task_count ?? "—"} open tasks</span>
                    </td>
                    <td>
                      <button className="btn-analyse" onClick={(event) => {
                        event.stopPropagation();
                        handleSelectProject(p);
                      }}>
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
