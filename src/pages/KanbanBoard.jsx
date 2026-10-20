import { useState, useEffect, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import KanbanColumn from "../components/kanban/KanbanColumn.jsx";
import CreateIssueModal from "../components/kanban/CreateIssueModal.jsx";
import IssueDetailModal from "../components/kanban/IssueDetailModal.jsx";
import { IssueTypeIcon, PriorityIcon } from "../components/kanban/KanbanIcons.jsx";
import {
  DEFAULT_COLUMNS,
  DEFAULT_TASKS,
  TEAM_MEMBERS,
  ISSUE_TYPES,
  PRIORITIES,
} from "../data/kanbanData.js";
import { getOpenTasks, updateTaskStatus } from "../api/client.js";

const STORAGE_KEY = "epars_kanban_tasks_v1";

export default function KanbanBoard() {
  // ── State ──────────────────────────────────────────────────────────────────
  const [tasks, setTasks] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (err) {
      console.warn("Could not load tasks from localStorage:", err);
    }
    return DEFAULT_TASKS;
  });

  // Filter & View State
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [filterPriority, setFilterPriority] = useState("all");
  const [filterAssignee, setFilterAssignee] = useState("all");
  const [quickFilters, setQuickFilters] = useState({
    myIssues: false,
    highPriority: false,
    bugsOnly: false,
    dueSoon: false,
  });
  const [groupBy, setGroupBy] = useState("none"); // 'none' | 'assignee' | 'priority' | 'type'
  const [density, setDensity] = useState("normal"); // 'normal' | 'compact'
  const [collapsedSwimlanes, setCollapsedSwimlanes] = useState({});

  // Drag and Drop State
  const [draggingTaskId, setDraggingTaskId] = useState(null);
  const [dragOverColumnId, setDragOverColumnId] = useState(null);
  const [dragOverCardId, setDragOverCardId] = useState(null);
  const [dropPosition, setDropPosition] = useState(null); // 'before' | 'after'

  // Modals
  const [selectedTask, setSelectedTask] = useState(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createInitialStatus, setCreateInitialStatus] = useState("todo");

  // Sync / Notice State
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncNotice, setSyncNotice] = useState(null);

  // ── Persistence ────────────────────────────────────────────────────────────
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
    } catch (err) {
      console.warn("Failed to persist tasks:", err);
    }
  }, [tasks]);

  // Keyboard shortcut: '/' focuses search input
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "/" && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
        e.preventDefault();
        const searchInput = document.getElementById("kanban-search-input");
        if (searchInput) searchInput.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // ── Drag & Drop Handlers ───────────────────────────────────────────────────
  const handleDragStartCard = useCallback((e, taskId) => {
    e.dataTransfer.setData("text/plain", taskId);
    e.dataTransfer.effectAllowed = "move";
    setDraggingTaskId(taskId);
  }, []);

  const handleDragEndCard = useCallback(() => {
    setDraggingTaskId(null);
    setDragOverColumnId(null);
    setDragOverCardId(null);
    setDropPosition(null);
  }, []);

  const handleDragOverColumn = useCallback((e, columnId) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverColumnId(columnId);
  }, []);

  const handleDragLeaveColumn = useCallback((e, columnId) => {
    if (e.currentTarget.contains(e.relatedTarget)) return;
    setDragOverColumnId((prev) => (prev === columnId ? null : prev));
  }, []);

  const handleDragOverCard = useCallback((e, targetCardId) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "move";

    const rect = e.currentTarget.getBoundingClientRect();
    const midPoint = rect.top + rect.height / 2;
    const pos = e.clientY < midPoint ? "before" : "after";

    setDragOverCardId(targetCardId);
    setDropPosition(pos);
  }, []);

  // Dropping directly onto another card (reorders or moves column)
  const handleDropOnCard = useCallback(
    (e, targetCardId) => {
      e.preventDefault();
      e.stopPropagation();

      const draggedId = e.dataTransfer.getData("text/plain") || draggingTaskId;
      if (!draggedId || draggedId === targetCardId) {
        handleDragEndCard();
        return;
      }

      setTasks((prevTasks) => {
        const draggedIndex = prevTasks.findIndex((t) => t.id === draggedId);
        const targetIndex = prevTasks.findIndex((t) => t.id === targetCardId);
        if (draggedIndex === -1 || targetIndex === -1) return prevTasks;

        const draggedTask = prevTasks[draggedIndex];
        const targetTask = prevTasks[targetIndex];
        const oldStatus = draggedTask.status;
        const newStatus = targetTask.status;

        const nextTasks = [...prevTasks];
        nextTasks.splice(draggedIndex, 1);

        const newTargetIndex = nextTasks.findIndex((t) => t.id === targetCardId);
        const insertIndex = dropPosition === "after" ? newTargetIndex + 1 : newTargetIndex;

        const historyEntry =
          oldStatus !== newStatus
            ? {
                timestamp: new Date().toISOString(),
                text: `Moved from ${DEFAULT_COLUMNS.find((c) => c.id === oldStatus)?.title || oldStatus} to ${DEFAULT_COLUMNS.find((c) => c.id === newStatus)?.title || newStatus}`,
              }
            : null;

        if (oldStatus !== newStatus) {
          updateTaskStatus(draggedId, newStatus).catch(() => {});
        }

        const updatedDraggedTask = {
          ...draggedTask,
          status: newStatus,
          updatedAt: new Date().toISOString(),
          history: historyEntry ? [historyEntry, ...(draggedTask.history || [])] : draggedTask.history,
        };

        nextTasks.splice(insertIndex, 0, updatedDraggedTask);
        return nextTasks;
      });

      handleDragEndCard();
    },
    [draggingTaskId, dropPosition, handleDragEndCard]
  );

  // Dropping into column body (empty area)
  const handleDropOnColumn = useCallback(
    (e, columnId) => {
      e.preventDefault();
      const draggedId = e.dataTransfer.getData("text/plain") || draggingTaskId;
      if (!draggedId) {
        handleDragEndCard();
        return;
      }

      setTasks((prevTasks) => {
        const draggedIndex = prevTasks.findIndex((t) => t.id === draggedId);
        if (draggedIndex === -1) return prevTasks;

        const draggedTask = prevTasks[draggedIndex];
        const oldStatus = draggedTask.status;

        if (oldStatus !== columnId) {
          updateTaskStatus(draggedId, columnId).catch(() => {});
        }

        // Move to the end of the target column
        const nextTasks = prevTasks.filter((t) => t.id !== draggedId);

        const historyEntry =
          oldStatus !== columnId
            ? {
                timestamp: new Date().toISOString(),
                text: `Moved from ${DEFAULT_COLUMNS.find((c) => c.id === oldStatus)?.title || oldStatus} to ${DEFAULT_COLUMNS.find((c) => c.id === columnId)?.title || columnId}`,
              }
            : null;

        const updatedTask = {
          ...draggedTask,
          status: columnId,
          updatedAt: new Date().toISOString(),
          history: historyEntry ? [historyEntry, ...(draggedTask.history || [])] : draggedTask.history,
        };

        return [...nextTasks, updatedTask];
      });

      handleDragEndCard();
    },
    [draggingTaskId, handleDragEndCard]
  );

  // Quick move button handler (advance / rewind status)
  const handleMoveColumn = useCallback((taskId, targetStatus) => {
    updateTaskStatus(taskId, targetStatus).catch(() => {});
    setTasks((prevTasks) =>
      prevTasks.map((t) => {
        if (t.id !== taskId) return t;
        const oldStatus = t.status;
        const historyEntry = {
          timestamp: new Date().toISOString(),
          text: `Moved from ${DEFAULT_COLUMNS.find((c) => c.id === oldStatus)?.title || oldStatus} to ${DEFAULT_COLUMNS.find((c) => c.id === targetStatus)?.title || targetStatus}`,
        };
        return {
          ...t,
          status: targetStatus,
          updatedAt: new Date().toISOString(),
          history: [historyEntry, ...(t.history || [])],
        };
      })
    );
  }, []);

  // ── Task Management Handlers ───────────────────────────────────────────────
  const handleCreateTask = (newTaskData) => {
    const nextNumber = Math.max(100, ...tasks.map((t) => parseInt(t.id.replace(/\D/g, ""), 10) || 0)) + 1;
    const newId = `EPARS-${nextNumber}`;

    const createdTask = {
      ...newTaskData,
      id: newId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      history: [
        {
          timestamp: new Date().toISOString(),
          text: `Created issue in ${DEFAULT_COLUMNS.find((c) => c.id === newTaskData.status)?.title || newTaskData.status}`,
        },
      ],
    };

    setTasks((prev) => [createdTask, ...prev]);
    showToastNotice(`Issue ${newId} created successfully`);
  };

  const handleUpdateTask = (updatedTask) => {
    if (updatedTask.status) {
      updateTaskStatus(updatedTask.id, updatedTask.status).catch(() => {});
    }
    setTasks((prev) => prev.map((t) => (t.id === updatedTask.id ? updatedTask : t)));
    setSelectedTask(updatedTask);
  };

  const handleDeleteTask = (taskId) => {
    setTasks((prev) => prev.filter((t) => t.id !== taskId));
    setSelectedTask(null);
    showToastNotice(`Issue ${taskId} deleted`);
  };

  const handleQuickAddTask = (columnId) => {
    setCreateInitialStatus(columnId);
    setIsCreateOpen(true);
  };

  const handleResetBoard = () => {
    if (window.confirm("Reset board to sample sprint tasks? Any manual edits will be overwritten.")) {
      setTasks(DEFAULT_TASKS);
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {}
      showToastNotice("Board reset to default sprint data");
    }
  };

  // Sync with real backend open tasks (if server is running)
  const handleSyncBackend = async () => {
    setIsSyncing(true);
    setSyncNotice(null);
    try {
      const backendTasks = await getOpenTasks();
      if (Array.isArray(backendTasks) && backendTasks.length > 0) {
        // Map backend tasks to Kanban format
        const mapped = backendTasks.map((bt) => {
          let status = "todo";
          const rawStatus = (bt.status || "").toLowerCase();
          if (rawStatus.includes("progress")) status = "in_progress";
          else if (rawStatus.includes("review") || rawStatus.includes("blocked")) status = "in_review";
          else if (rawStatus.includes("complete") || rawStatus.includes("done")) status = "done";

          let priority = "medium";
          const rawPri = (bt.priority || "").toLowerCase();
          if (rawPri.includes("crit") || rawPri.includes("highest")) priority = "highest";
          else if (rawPri.includes("high")) priority = "high";
          else if (rawPri.includes("low")) priority = "low";

          return {
            id: bt.task_id,
            title: bt.task_name,
            description: `Required role: ${bt.required_role || "Engineering"}. Task type: ${bt.task_type || "Task"}.`,
            status,
            type: "task",
            priority,
            assigneeId: bt.assigned_to || null,
            storyPoints: 3,
            dueDate: bt.due_date ? bt.due_date.split("T")[0] : null,
            tags: [bt.task_type, bt.required_role].filter(Boolean),
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            history: [{ timestamp: new Date().toISOString(), text: "Synced from EPARS backend tasks" }],
          };
        });

        // Merge with existing tasks avoiding duplicates
        const existingIds = new Set(tasks.map((t) => t.id));
        const newOnes = mapped.filter((m) => !existingIds.has(m.id));
        setTasks((prev) => [...prev, ...newOnes]);
        showToastNotice(`Synced ${newOnes.length} new tasks from backend`);
      } else {
        showToastNotice("Backend returned 0 open tasks. Keeping current sprint board.");
      }
    } catch (err) {
      showToastNotice(`Backend offline or unavailable (${err.message}). Using local board data.`);
    } finally {
      setIsSyncing(false);
    }
  };

  const showToastNotice = (msg) => {
    setSyncNotice(msg);
    setTimeout(() => setSyncNotice(null), 3500);
  };

  // ── Filters & Search ───────────────────────────────────────────────────────
  const toggleQuickFilter = (key) => {
    setQuickFilters((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const clearAllFilters = () => {
    setSearch("");
    setFilterType("all");
    setFilterPriority("all");
    setFilterAssignee("all");
    setQuickFilters({
      myIssues: false,
      highPriority: false,
      bugsOnly: false,
      dueSoon: false,
    });
  };

  const hasActiveFilters =
    search.trim() !== "" ||
    filterType !== "all" ||
    filterPriority !== "all" ||
    filterAssignee !== "all" ||
    Object.values(quickFilters).some(Boolean);

  const filteredTasks = useMemo(() => {
    const q = search.toLowerCase().trim();
    const now = new Date();

    return tasks.filter((task) => {
      // Text search
      if (q) {
        const matchesKey = task.id.toLowerCase().includes(q);
        const matchesTitle = task.title.toLowerCase().includes(q);
        const matchesDesc = (task.description || "").toLowerCase().includes(q);
        const matchesTags = (task.tags || []).some((tag) => tag.toLowerCase().includes(q));
        if (!matchesKey && !matchesTitle && !matchesDesc && !matchesTags) return false;
      }

      // Dropdowns
      if (filterType !== "all" && task.type !== filterType) return false;
      if (filterPriority !== "all" && task.priority !== filterPriority) return false;
      if (filterAssignee !== "all") {
        if (filterAssignee === "unassigned") {
          if (task.assigneeId != null && task.assigneeId !== "") return false;
        } else if (task.assigneeId !== filterAssignee) {
          return false;
        }
      }

      // Quick filter buttons
      if (quickFilters.myIssues && task.assigneeId !== "EMP001") return false;
      if (quickFilters.highPriority && task.priority !== "highest" && task.priority !== "high") return false;
      if (quickFilters.bugsOnly && task.type !== "bug") return false;
      if (quickFilters.dueSoon) {
        if (!task.dueDate || task.status === "done") return false;
        const diffDays = Math.ceil((new Date(task.dueDate) - now) / (1000 * 60 * 60 * 24));
        if (diffDays > 3) return false;
      }

      return true;
    });
  }, [tasks, search, filterType, filterPriority, filterAssignee, quickFilters]);

  // Sprint Metrics
  const sprintMetrics = useMemo(() => {
    const total = tasks.length;
    const done = tasks.filter((t) => t.status === "done").length;
    const inProg = tasks.filter((t) => t.status === "in_progress").length;
    const inRev = tasks.filter((t) => t.status === "in_review").length;
    const totalPoints = tasks.reduce((acc, t) => acc + (t.storyPoints || 0), 0);
    const donePoints = tasks
      .filter((t) => t.status === "done")
      .reduce((acc, t) => acc + (t.storyPoints || 0), 0);
    const progressPercent = totalPoints > 0 ? Math.round((donePoints / totalPoints) * 100) : 0;

    return { total, done, inProg, inRev, totalPoints, donePoints, progressPercent };
  }, [tasks]);

  // Swimlanes Grouping
  const swimlanes = useMemo(() => {
    if (groupBy === "none") return null;

    if (groupBy === "assignee") {
      const groups = TEAM_MEMBERS.map((member) => ({
        id: member.id,
        title: member.name,
        subtitle: member.role,
        avatar: member.avatar,
        color: member.color,
        tasks: filteredTasks.filter((t) => t.assigneeId === member.id),
      }));

      const unassigned = filteredTasks.filter((t) => !t.assigneeId);
      if (unassigned.length > 0) {
        groups.push({
          id: "unassigned",
          title: "Unassigned",
          subtitle: "No assignee yet",
          avatar: "—",
          color: "#94a3b8",
          tasks: unassigned,
        });
      }
      return groups;
    }

    if (groupBy === "priority") {
      return Object.values(PRIORITIES).map((pri) => ({
        id: pri.id,
        title: `${pri.label} Priority`,
        subtitle: `${pri.rank} of 5`,
        icon: <PriorityIcon priority={pri.id} size={15} />,
        color: pri.color,
        tasks: filteredTasks.filter((t) => t.priority === pri.id),
      }));
    }

    if (groupBy === "type") {
      return Object.values(ISSUE_TYPES).map((typ) => ({
        id: typ.id,
        title: typ.label,
        subtitle: `${typ.badge} Type`,
        icon: <IssueTypeIcon type={typ.id} size={16} />,
        color: typ.color,
        tasks: filteredTasks.filter((t) => t.type === typ.id),
      }));
    }

    return null;
  }, [groupBy, filteredTasks]);

  const toggleSwimlane = (laneId) => {
    setCollapsedSwimlanes((prev) => ({ ...prev, [laneId]: !prev[laneId] }));
  };

  return (
    <div className="kanban-page-wrap">
      {/* Toast Notice */}
      {syncNotice && (
        <div className="kanban-toast-notice">
          <span>{syncNotice}</span>
          <button type="button" onClick={() => setSyncNotice(null)}>✕</button>
        </div>
      )}

      {/* Top Breadcrumb & Project Header */}
      <div className="kanban-top-header">
        <div className="kanban-breadcrumbs">
          <Link to="/" className="crumb-link">Projects</Link>
          <span className="crumb-sep">/</span>
          <span className="crumb-text">EPARS Core</span>
          <span className="crumb-sep">/</span>
          <span className="crumb-text active">Sprint 14 Board</span>
        </div>

        <div className="kanban-header-main">
          <div className="kanban-title-group">
            <h1 className="kanban-board-title">Sprint 14 Kanban Board</h1>
            <span className="sprint-status-badge">Active Sprint</span>
            <span className="sprint-goal-text">Goal: Complete Q4 Performance &amp; Resource Allocation Release</span>
          </div>

          <div className="kanban-header-actions">
            <button
              type="button"
              className="btn-jira-primary"
              id="create-task-btn"
              onClick={() => handleQuickAddTask("todo")}
            >
              <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
                <path d="M8 2a.75.75 0 01.75.75v4.5h4.5a.75.75 0 010 1.5h-4.5v4.5a.75.75 0 01-1.5 0v-4.5h-4.5a.75.75 0 010-1.5h4.5v-4.5A.75.75 0 018 2z" />
              </svg>
              Create Issue
            </button>

            <button
              type="button"
              className="btn-jira-secondary"
              onClick={handleSyncBackend}
              disabled={isSyncing}
              title="Sync with backend tasks from /api/task_assignment/tasks"
            >
              <svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor">
                <path d="M8 3a5 5 0 104.546 2.914.5.5 0 01.908-.417A6 6 0 118 2v1z" />
                <path d="M8 4.466V.534a.25.25 0 01.41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 018 4.466z" />
              </svg>
              {isSyncing ? "Syncing…" : "Sync Backend"}
            </button>

            <button
              type="button"
              className="btn-jira-ghost"
              onClick={handleResetBoard}
              title="Reset to default sample sprint tasks"
            >
              Reset Board
            </button>
          </div>
        </div>

        {/* Sprint Summary Progress Bar */}
        <div className="sprint-summary-bar">
          <div className="sprint-stats-row">
            <div className="sprint-stat">
              <span className="stat-label">Total Issues:</span>
              <strong className="stat-value">{sprintMetrics.total}</strong>
            </div>
            <div className="sprint-stat">
              <span className="stat-label">In Progress:</span>
              <strong className="stat-value in-prog">{sprintMetrics.inProg}</strong>
            </div>
            <div className="sprint-stat">
              <span className="stat-label">In Review:</span>
              <strong className="stat-value in-rev">{sprintMetrics.inRev}</strong>
            </div>
            <div className="sprint-stat">
              <span className="stat-label">Done:</span>
              <strong className="stat-value done">{sprintMetrics.done}</strong>
            </div>
            <div className="sprint-stat">
              <span className="stat-label">Story Points:</span>
              <strong className="stat-value">{sprintMetrics.donePoints} / {sprintMetrics.totalPoints} pts</strong>
            </div>
            <div className="sprint-stat sprint-percent">
              <span className="stat-label">Progress:</span>
              <strong className="stat-value">{sprintMetrics.progressPercent}%</strong>
            </div>
          </div>

          <div className="sprint-progress-track">
            <div
              className="sprint-progress-fill"
              style={{ width: `${sprintMetrics.progressPercent}%` }}
              role="progressbar"
              aria-valuenow={sprintMetrics.progressPercent}
              aria-valuemin="0"
              aria-valuemax="100"
            />
          </div>
        </div>
      </div>

      {/* Toolbar: Search, Filters, Group By & Density */}
      <div className="kanban-toolbar">
        <div className="toolbar-left">
          {/* Search Bar with '/' hint */}
          <div className="kanban-search-box">
            <svg viewBox="0 0 16 16" width="14" height="14" fill="#94a3b8" className="search-icon">
              <path d="M11.742 10.344a6.5 6.5 0 10-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 001.415-1.414l-3.85-3.85a1.007 1.007 0 00-.115-.1zM12 6.5a5.5 5.5 0 11-11 0 5.5 5.5 0 0111 0z" />
            </svg>
            <input
              id="kanban-search-input"
              type="text"
              placeholder="Search by ID, title, or tag…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="kanban-search-input"
            />
            <span className="keyboard-shortcut-hint">/</span>
          </div>

          {/* Assignee Avatar Quick Filter Row */}
          <div className="assignee-filter-pills" title="Filter by team member">
            {TEAM_MEMBERS.map((m) => {
              const isSelected = filterAssignee === m.id;
              return (
                <button
                  type="button"
                  key={m.id}
                  className={`avatar-filter-btn ${isSelected ? "selected" : ""}`}
                  onClick={() => setFilterAssignee(isSelected ? "all" : m.id)}
                  title={`Filter to ${m.name} (${m.role})`}
                >
                  <div className="filter-avatar" style={{ backgroundColor: m.color }}>
                    {m.avatar}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Type Dropdown */}
          <select
            className="jira-select-filter"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="all">All Types</option>
            {Object.values(ISSUE_TYPES).map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>

          {/* Priority Dropdown */}
          <select
            className="jira-select-filter"
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value)}
          >
            <option value="all">All Priorities</option>
            {Object.values(PRIORITIES).map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>

          {/* Quick Filter Buttons */}
          <button
            type="button"
            className={`quick-filter-pill ${quickFilters.myIssues ? "active" : ""}`}
            onClick={() => toggleQuickFilter("myIssues")}
          >
            Only My Issues
          </button>

          <button
            type="button"
            className={`quick-filter-pill ${quickFilters.highPriority ? "active" : ""}`}
            onClick={() => toggleQuickFilter("highPriority")}
          >
            High Priority
          </button>

          <button
            type="button"
            className={`quick-filter-pill ${quickFilters.bugsOnly ? "active" : ""}`}
            onClick={() => toggleQuickFilter("bugsOnly")}
          >
            Bugs
          </button>

          <button
            type="button"
            className={`quick-filter-pill ${quickFilters.dueSoon ? "active" : ""}`}
            onClick={() => toggleQuickFilter("dueSoon")}
          >
            Due Soon
          </button>

          {hasActiveFilters && (
            <button type="button" className="clear-filters-link" onClick={clearAllFilters}>
              Clear filters
            </button>
          )}
        </div>

        {/* Toolbar Right: Swimlanes and Density */}
        <div className="toolbar-right">
          <div className="view-control-group">
            <label className="view-control-label" htmlFor="group-by-select">Group by:</label>
            <select
              id="group-by-select"
              className="jira-select-filter"
              value={groupBy}
              onChange={(e) => setGroupBy(e.target.value)}
            >
              <option value="none">None (Standard)</option>
              <option value="assignee">Assignee</option>
              <option value="priority">Priority</option>
              <option value="type">Issue Type</option>
            </select>
          </div>

          <div className="density-toggle" title="Card Density">
            <button
              type="button"
              className={`density-btn ${density === "normal" ? "active" : ""}`}
              onClick={() => setDensity("normal")}
              title="Normal density"
            >
              ☰
            </button>
            <button
              type="button"
              className={`density-btn ${density === "compact" ? "active" : ""}`}
              onClick={() => setDensity("compact")}
              title="Compact density"
            >
              ☷
            </button>
          </div>
        </div>
      </div>

      {/* Main Board Container */}
      <div className="kanban-board-canvas">
        {groupBy === "none" ? (
          /* Standard 4-Column View */
          <div className="kanban-columns-row">
            {DEFAULT_COLUMNS.map((col) => {
              const colTasks = filteredTasks.filter((t) => t.status === col.id);
              return (
                <KanbanColumn
                  key={col.id}
                  column={col}
                  tasks={colTasks}
                  isDragOver={dragOverColumnId === col.id}
                  draggingTaskId={draggingTaskId}
                  dragTargetCardId={dragOverCardId}
                  dragTargetPosition={dropPosition}
                  onDragOverColumn={handleDragOverColumn}
                  onDragLeaveColumn={handleDragLeaveColumn}
                  onDropOnColumn={handleDropOnColumn}
                  onDragStartCard={handleDragStartCard}
                  onDragEndCard={handleDragEndCard}
                  onDragOverCard={handleDragOverCard}
                  onDropOnCard={handleDropOnCard}
                  onOpenDetail={setSelectedTask}
                  onMoveColumn={handleMoveColumn}
                  onQuickAddTask={handleQuickAddTask}
                  density={density}
                />
              );
            })}
          </div>
        ) : (
          /* Swimlanes View (Grouped by Assignee, Priority, or Type) */
          <div className="kanban-swimlanes-container">
            {swimlanes &&
              swimlanes.map((lane) => {
                const isCollapsed = collapsedSwimlanes[lane.id];
                const laneTaskCount = lane.tasks.length;

                return (
                  <div key={lane.id} className="kanban-swimlane">
                    {/* Swimlane Accordion Header */}
                    <div
                      className="swimlane-header"
                      onClick={() => toggleSwimlane(lane.id)}
                    >
                      <button type="button" className="swimlane-toggle-icon">
                        {isCollapsed ? "▶" : "▼"}
                      </button>

                      {lane.avatar && (
                        <div
                          className="swimlane-avatar"
                          style={{ backgroundColor: lane.color }}
                        >
                          {lane.avatar}
                        </div>
                      )}
                      {lane.icon && <span className="swimlane-icon">{lane.icon}</span>}

                      <strong className="swimlane-title">{lane.title}</strong>
                      {lane.subtitle && (
                        <span className="swimlane-subtitle">({lane.subtitle})</span>
                      )}

                      <span className="swimlane-count-badge">
                        {laneTaskCount} {laneTaskCount === 1 ? "issue" : "issues"}
                      </span>
                    </div>

                    {/* Swimlane Columns Content */}
                    {!isCollapsed && (
                      <div className="swimlane-columns-row">
                        {DEFAULT_COLUMNS.map((col) => {
                          const laneColTasks = lane.tasks.filter((t) => t.status === col.id);
                          return (
                            <KanbanColumn
                              key={col.id}
                              column={col}
                              tasks={laneColTasks}
                              isDragOver={dragOverColumnId === col.id}
                              draggingTaskId={draggingTaskId}
                              dragTargetCardId={dragOverCardId}
                              dragTargetPosition={dropPosition}
                              onDragOverColumn={handleDragOverColumn}
                              onDragLeaveColumn={handleDragLeaveColumn}
                              onDropOnColumn={handleDropOnColumn}
                              onDragStartCard={handleDragStartCard}
                              onDragEndCard={handleDragEndCard}
                              onDragOverCard={handleDragOverCard}
                              onDropOnCard={handleDropOnCard}
                              onOpenDetail={setSelectedTask}
                              onMoveColumn={handleMoveColumn}
                              onQuickAddTask={handleQuickAddTask}
                              density={density}
                            />
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        )}
      </div>

      {/* Create Issue Modal */}
      <CreateIssueModal
        isOpen={isCreateOpen}
        initialStatus={createInitialStatus}
        onClose={() => setIsCreateOpen(false)}
        onCreate={handleCreateTask}
      />

      {/* Issue Detail & Edit Modal */}
      <IssueDetailModal
        task={selectedTask}
        isOpen={Boolean(selectedTask)}
        onClose={() => setSelectedTask(null)}
        onUpdateTask={handleUpdateTask}
        onDeleteTask={handleDeleteTask}
      />
    </div>
  );
}
