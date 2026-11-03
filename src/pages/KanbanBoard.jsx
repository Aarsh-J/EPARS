import { useState, useEffect, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import KanbanColumn from "../components/kanban/KanbanColumn.jsx";
import CreateIssueModal from "../components/kanban/CreateIssueModal.jsx";
import IssueDetailModal from "../components/kanban/IssueDetailModal.jsx";
import SearchableDropdown from "../components/kanban/SearchableDropdown.jsx";
import { PriorityIcon } from "../components/kanban/KanbanIcons.jsx";
import {
  assignKanbanTask,
  createKanbanTask,
  deleteKanbanTask,
  getKanbanBoard,
  getKanbanEmployees,
  getKanbanProjects,
  updateKanbanTask,
  updateTaskStatus,
} from "../api/client.js";

const KANBAN_COLUMNS = [
  { id: "Not Started", title: "Not Started", color: "#64748b" },
  { id: "In Progress", title: "In Progress", color: "#3b82f6" },
  { id: "In Review", title: "In Review", color: "#8b5cf6" },
  { id: "Blocked", title: "Blocked", color: "#ef4444" },
  { id: "Completed", title: "Completed", color: "#10b981" },
];

const PRIORITY_OPTIONS = ["Critical", "High", "Medium", "Low"];
const STATUS_OPTIONS = KANBAN_COLUMNS.map((column) => column.id);
const BOARD_PAGE_SIZE = 50;

function initials(name) {
  return (name || "")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0] || "")
    .join("")
    .toUpperCase();
}

function mapBoardTask(task, employees) {
  const assignee = employees.find((employee) => employee.employee_id === task.assigned_to);
  const status = KANBAN_COLUMNS.find((column) => column.id === task.status)?.id;
  if (!status) {
    throw new Error(`Task ${task.task_id} has unsupported status "${task.status}".`);
  }

  return {
    id: task.task_id,
    title: task.task_name || "",
    description: task.task_description || "",
    projectId: task.project_id,
    projectName: task.project_name || "",
    status,
    priority: task.priority,
    assigneeId: task.assigned_to || null,
    assignee: assignee
      ? {
          name: assignee.full_name,
          role: assignee.role,
          avatar: initials(assignee.full_name),
        }
      : task.assigned_to
        ? {
            name: task.assignee_name || task.assigned_to,
            role: "",
            avatar: initials(task.assignee_name || task.assigned_to),
          }
        : null,
    storyPoints: task.story_points,
    dueDate: task.due_date,
    requiredSkills: (task.required_skills || "")
      .split(",")
      .map((skill) => skill.trim())
      .filter(Boolean),
    createdAt: task.created_at,
    updatedAt: task.last_updated,
  };
}

export default function KanbanBoard() {
  const [tasks, setTasks] = useState([]);
  const [projects, setProjects] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [selectedProjectIds, setSelectedProjectIds] = useState([]);
  const [includeOtherTasks, setIncludeOtherTasks] = useState(false);
  const [isLoadingOptions, setIsLoadingOptions] = useState(true);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [loadingError, setLoadingError] = useState("");
  const [boardRefreshVersion, setBoardRefreshVersion] = useState(0);

  const [search, setSearch] = useState("");
  const [filterPriority, setFilterPriority] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterAssignee, setFilterAssignee] = useState("all");
  const [highPriorityOnly, setHighPriorityOnly] = useState(false);
  const [dateFilter, setDateFilter] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sortBy, setSortBy] = useState("due_date");
  const [sortOrder, setSortOrder] = useState("asc");
  const [projectView, setProjectView] = useState("active");
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: BOARD_PAGE_SIZE,
    total: 0,
    total_pages: 0,
  });
  const [statusCounts, setStatusCounts] = useState(
    Object.fromEntries(STATUS_OPTIONS.map((status) => [status, 0])),
  );
  const [page, setPage] = useState(1);
  const [groupBy, setGroupBy] = useState("none");
  const [density, setDensity] = useState("normal");
  const [collapsedSwimlanes, setCollapsedSwimlanes] = useState({});

  const [draggingTaskId, setDraggingTaskId] = useState(null);
  const [dragOverColumnId, setDragOverColumnId] = useState(null);
  const [dragOverCardId, setDragOverCardId] = useState(null);
  const [dropPosition, setDropPosition] = useState(null);
  const [pendingStatusTaskIds, setPendingStatusTaskIds] = useState([]);

  const [selectedTask, setSelectedTask] = useState(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createInitialStatus, setCreateInitialStatus] = useState("Not Started");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([getKanbanProjects(), getKanbanEmployees()])
      .then(([projectRows, employeeRows]) => {
        if (!active) return;
        setProjects(projectRows);
        setEmployees(employeeRows);
      })
      .catch((error) => {
        if (active) setLoadingError(`Unable to load projects and employees: ${error.message}`);
      })
      .finally(() => {
        if (active) setIsLoadingOptions(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    if (selectedProjectIds.length === 0 && !includeOtherTasks) {
      setTasks([]);
      setIsLoadingTasks(false);
      setLoadingError("");
      setPagination({ page: 1, page_size: BOARD_PAGE_SIZE, total: 0, total_pages: 0 });
      setStatusCounts(Object.fromEntries(STATUS_OPTIONS.map((status) => [status, 0])));
      return () => {
        active = false;
      };
    }

    if (dateFilter === "custom" && (!startDate || !endDate)) {
      setTasks([]);
      setIsLoadingTasks(false);
      setLoadingError("Choose both a start date and an end date for the custom date filter.");
      setPagination({ page: 1, page_size: BOARD_PAGE_SIZE, total: 0, total_pages: 0 });
      setStatusCounts(Object.fromEntries(STATUS_OPTIONS.map((status) => [status, 0])));
      return () => {
        active = false;
      };
    }

    const loadTasks = async () => {
      setIsLoadingTasks(true);
      setLoadingError("");
      try {
        const firstPage = await getKanbanBoard({
          projectIds: selectedProjectIds,
          includeOtherTasks,
          projectView,
          employeeId: filterAssignee,
          dateFilter,
          startDate,
          endDate,
          search,
          statusFilter: filterStatus === "all" ? "" : filterStatus,
          priorityFilter: filterPriority === "all" ? "" : filterPriority,
          highPriorityOnly,
          sortBy,
          sortOrder,
          page,
          pageSize: BOARD_PAGE_SIZE,
        });
        if (active) {
          setTasks(firstPage.tasks.map((task) => mapBoardTask(task, employees)));
          setPagination(firstPage.pagination);
          setStatusCounts(firstPage.status_counts);
          setSelectedTask((current) => {
            if (!current) return null;
            const refreshedTask = firstPage.tasks.find((task) => task.task_id === current.id);
            return refreshedTask ? mapBoardTask(refreshedTask, employees) : current;
          });
        }
      } catch (error) {
        if (active) {
          setTasks([]);
          setPagination({ page, page_size: BOARD_PAGE_SIZE, total: 0, total_pages: 0 });
          setStatusCounts(Object.fromEntries(STATUS_OPTIONS.map((status) => [status, 0])));
          setLoadingError(`Unable to load board tasks: ${error.message}`);
        }
      } finally {
        if (active) setIsLoadingTasks(false);
      }
    };

    const timer = window.setTimeout(loadTasks, search.trim() ? 250 : 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [
    selectedProjectIds,
    includeOtherTasks,
    employees,
    projectView,
    filterAssignee,
    dateFilter,
    startDate,
    endDate,
    search,
    filterStatus,
    filterPriority,
    highPriorityOnly,
    sortBy,
    sortOrder,
    page,
    boardRefreshVersion,
  ]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (
        event.key === "/" &&
        document.activeElement.tagName !== "INPUT" &&
        document.activeElement.tagName !== "TEXTAREA" &&
        document.activeElement.tagName !== "SELECT"
      ) {
        event.preventDefault();
        document.getElementById("kanban-search-input")?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const showNotice = (message) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 5000);
  };

  const changeTaskStatus = useCallback(async (taskId, newStatus) => {
    const task = tasks.find((item) => item.id === taskId);
    if (!task || task.status === newStatus || pendingStatusTaskIds.includes(taskId)) {
      return { ok: true };
    }

    const oldStatus = task.status;
    setPendingStatusTaskIds((current) => [...current, taskId]);
    setTasks((current) =>
      current.map((item) => item.id === taskId ? { ...item, status: newStatus } : item)
    );
    setSelectedTask((current) =>
      current?.id === taskId ? { ...current, status: newStatus } : current
    );

    try {
      const response = await updateTaskStatus(taskId, newStatus);
      if (response.task) {
        const updatedTask = mapBoardTask(response.task, employees);
        setTasks((current) =>
          current.map((item) => item.id === taskId ? updatedTask : item)
        );
        setSelectedTask((current) => current?.id === taskId ? updatedTask : current);
        setBoardRefreshVersion((current) => current + 1);
      }
      return { ok: true };
    } catch (error) {
      setTasks((current) =>
        current.map((item) =>
          item.id === taskId && item.status === newStatus
            ? { ...item, status: oldStatus }
            : item
        )
      );
      setSelectedTask((current) =>
        current?.id === taskId && current.status === newStatus
          ? { ...current, status: oldStatus }
          : current
      );
      showNotice(`Unable to update task status: ${error.message}`);
      return { ok: false, error };
    } finally {
      setPendingStatusTaskIds((current) => current.filter((id) => id !== taskId));
    }
  }, [tasks, pendingStatusTaskIds, employees]);

  const handleDragStartCard = useCallback((event, taskId) => {
    event.dataTransfer.setData("text/plain", taskId);
    event.dataTransfer.effectAllowed = "move";
    setDraggingTaskId(taskId);
  }, []);

  const handleDragEndCard = useCallback(() => {
    setDraggingTaskId(null);
    setDragOverColumnId(null);
    setDragOverCardId(null);
    setDropPosition(null);
  }, []);

  const handleDragOverColumn = useCallback((event, columnId) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDragOverColumnId(columnId);
  }, []);

  const handleDragLeaveColumn = useCallback((event, columnId) => {
    if (event.currentTarget.contains(event.relatedTarget)) return;
    setDragOverColumnId((current) => current === columnId ? null : current);
  }, []);

  const handleDragOverCard = useCallback((event, targetCardId) => {
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = "move";
    const rect = event.currentTarget.getBoundingClientRect();
    setDragOverCardId(targetCardId);
    setDropPosition(event.clientY < rect.top + rect.height / 2 ? "before" : "after");
  }, []);

  const handleDropOnCard = useCallback((event, targetCardId) => {
    event.preventDefault();
    event.stopPropagation();
    const draggedId = event.dataTransfer.getData("text/plain") || draggingTaskId;
    const target = tasks.find((task) => task.id === targetCardId);
    if (draggedId && draggedId !== targetCardId && target) {
      changeTaskStatus(draggedId, target.status);
    }
    handleDragEndCard();
  }, [changeTaskStatus, draggingTaskId, handleDragEndCard, tasks]);

  const handleDropOnColumn = useCallback((event, columnId) => {
    event.preventDefault();
    const draggedId = event.dataTransfer.getData("text/plain") || draggingTaskId;
    if (draggedId) changeTaskStatus(draggedId, columnId);
    handleDragEndCard();
  }, [changeTaskStatus, draggingTaskId, handleDragEndCard]);

  const handleMoveColumn = useCallback((taskId, targetStatus) => {
    changeTaskStatus(taskId, targetStatus);
  }, [changeTaskStatus]);

  const handleCreateTask = async (taskInput) => {
    const response = await createKanbanTask(taskInput);
    if (!response.task) throw new Error("The server did not return the created task.");
    setBoardRefreshVersion((current) => current + 1);
  };

  const handleUpdateTask = async (changes) => {
    const currentTask = tasks.find((task) => task.id === changes.id);
    if (!currentTask) throw new Error("This task is no longer on the selected board.");

    let response;
    if (Object.prototype.hasOwnProperty.call(changes, "status")) {
      const result = await changeTaskStatus(changes.id, changes.status);
      if (!result.ok) throw result.error;
      return;
    }

    if (Object.prototype.hasOwnProperty.call(changes, "assigneeId") && Object.keys(changes).length === 2) {
      response = await assignKanbanTask(changes.id, changes.assigneeId);
    } else {
      const fieldMap = {
        title: "task_name",
        description: "task_description",
        priority: "priority",
        storyPoints: "story_points",
        dueDate: "due_date",
        requiredSkills: "required_skills",
        assigneeId: "assigned_to",
      };
      const update = {};
      for (const [field, value] of Object.entries(changes)) {
        if (field === "id") continue;
        if (!fieldMap[field]) throw new Error(`Unsupported task field: ${field}`);
        update[fieldMap[field]] = value;
      }
      response = await updateKanbanTask(changes.id, update);
    }

    if (!response.task) throw new Error("The server did not return the updated task.");
    const updatedTask = mapBoardTask(response.task, employees);
    setTasks((current) =>
      current.map((task) => task.id === updatedTask.id ? updatedTask : task)
    );
    setSelectedTask((current) => current?.id === updatedTask.id ? updatedTask : current);
    setBoardRefreshVersion((current) => current + 1);
  };

  const handleDeleteTask = async (taskId) => {
    await deleteKanbanTask(taskId);
    setTasks((current) => current.filter((task) => task.id !== taskId));
    setSelectedTask((current) => current?.id === taskId ? null : current);
    setBoardRefreshVersion((current) => current + 1);
  };

  const handleQuickAddTask = (status) => {
    setCreateInitialStatus(status);
    setIsCreateOpen(true);
  };

  const clearAllFilters = () => {
    setSearch("");
    setFilterPriority("all");
    setFilterStatus("all");
    setFilterAssignee("all");
    setHighPriorityOnly(false);
    setDateFilter("all");
    setStartDate("");
    setEndDate("");
    setSortBy("due_date");
    setSortOrder("asc");
    setPage(1);
  };

  const filteredTasks = tasks;

  const sprintMetrics = useMemo(() => {
    const total = pagination.total;
    const done = statusCounts.Completed || 0;
    const inProgress = statusCounts["In Progress"] || 0;
    const inReview = statusCounts["In Review"] || 0;
    const totalPoints = tasks.reduce((sum, task) => sum + (Number(task.storyPoints) || 0), 0);
    const donePoints = tasks
      .filter((task) => task.status === "Completed")
      .reduce((sum, task) => sum + (Number(task.storyPoints) || 0), 0);
    return {
      total,
      done,
      inProgress,
      inReview,
      totalPoints,
      donePoints,
      progressPercent: totalPoints ? Math.round((donePoints / totalPoints) * 100) : 0,
    };
  }, [tasks, pagination.total, statusCounts]);

  const swimlanes = useMemo(() => {
    if (groupBy === "assignee") {
      const lanes = employees.map((employee) => ({
        id: employee.employee_id,
        title: employee.full_name,
        subtitle: employee.role,
        avatar: initials(employee.full_name),
        color: "#64748b",
        tasks: filteredTasks.filter((task) => task.assigneeId === employee.employee_id),
      }));
      const unassigned = filteredTasks.filter((task) => !task.assigneeId);
      if (unassigned.length) {
        lanes.push({
          id: "unassigned",
          title: "Unassigned",
          subtitle: "No assignee yet",
          avatar: "—",
          color: "#94a3b8",
          tasks: unassigned,
        });
      }
      return lanes;
    }
    if (groupBy === "priority") {
      return PRIORITY_OPTIONS.map((priority) => ({
        id: priority,
        title: `${priority} Priority`,
        icon: <PriorityIcon priority={priority} size={15} />,
        color: "#64748b",
        tasks: filteredTasks.filter((task) => task.priority === priority),
      }));
    }
    if (groupBy === "status") {
      return STATUS_OPTIONS.map((status) => ({
        id: status,
        title: status,
        color: KANBAN_COLUMNS.find((column) => column.id === status)?.color || "#64748b",
        tasks: filteredTasks.filter((task) => task.status === status),
      }));
    }
    return null;
  }, [groupBy, employees, filteredTasks]);

  const hasActiveFilters = search.trim() !== "" ||
    filterPriority !== "all" ||
    filterStatus !== "all" ||
    filterAssignee !== "all" ||
    highPriorityOnly ||
    dateFilter !== "all" ||
    sortBy !== "due_date" ||
    sortOrder !== "asc";
  const selectedProjectLabel = [
    ...projects
      .filter((project) => selectedProjectIds.includes(project.project_id))
      .map((project) => project.project_name || project.project_id),
    ...(includeOtherTasks ? ["Other tasks"] : []),
  ].join(", ");
  const projectOptions = projects.map((project) => ({
    value: project.project_id,
    label: project.project_name || project.project_id,
  }));
  const employeeOptions = [
    { value: "all", label: "All Employees" },
    { value: "unassigned", label: "Unassigned" },
    ...employees.map((employee) => ({
      value: employee.employee_id,
      label: employee.full_name || employee.employee_id,
    })),
  ];

  const renderColumns = (columnTasks) => (
    <div className="kanban-columns-row">
      {KANBAN_COLUMNS.map((column) => (
        <KanbanColumn
          key={column.id}
          column={column}
          columns={KANBAN_COLUMNS}
          tasks={columnTasks.filter((task) => task.status === column.id)}
          isDragOver={dragOverColumnId === column.id}
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
      ))}
    </div>
  );

  return (
    <div className="kanban-page-wrap">
      {(notice || loadingError) && (
        <div className="kanban-toast-notice" role="status">
          <span>{loadingError || notice}</span>
          <button type="button" onClick={() => { setNotice(""); setLoadingError(""); }}>✕</button>
        </div>
      )}

      <div className="kanban-top-header">
        <div className="kanban-breadcrumbs">
          <Link to="/" className="crumb-link">Projects</Link>
          <span className="crumb-sep">/</span>
          <span className="crumb-text active">{selectedProjectLabel || "Select board scope"}</span>
        </div>

        <div className="kanban-header-main">
          <div className="kanban-title-group">
            <h1 className="kanban-board-title">Kanban Board</h1>
            <span className="sprint-status-badge">{isLoadingTasks ? "Loading" : `${pagination.total} tasks`}</span>
          </div>
          <div className="kanban-header-actions">
            <button
              type="button"
              className="btn-jira-primary"
              id="create-task-btn"
              onClick={() => handleQuickAddTask("Not Started")}
            >
              <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
                <path d="M8 2a.75.75 0 01.75.75v4.5h4.5a.75.75 0 010 1.5h-4.5v4.5a.75.75 0 01-1.5 0v-4.5h-4.5a.75.75 0 010-1.5h4.5v-4.5A.75.75 0 018 2z" />
              </svg>
              Create Issue
            </button>
          </div>
        </div>

        <div className="kanban-view-switch" role="tablist" aria-label="Task project view">
          <button
            type="button"
            role="tab"
            aria-selected={projectView === "active"}
            className={`quick-filter-pill ${projectView === "active" ? "active" : ""}`}
            onClick={() => { setProjectView("active"); setPage(1); }}
          >
            Active Tasks
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={projectView === "previous"}
            className={`quick-filter-pill ${projectView === "previous" ? "active" : ""}`}
            onClick={() => { setProjectView("previous"); setPage(1); }}
            title="Tasks from projects completed successfully"
          >
            Previous Tasks
          </button>
        </div>

        <div className="sprint-summary-bar">
          <div className="sprint-stats-row">
            <div className="sprint-stat"><span className="stat-label">Total Issues:</span><strong className="stat-value">{sprintMetrics.total}</strong></div>
            <div className="sprint-stat"><span className="stat-label">In Progress:</span><strong className="stat-value in-prog">{sprintMetrics.inProgress}</strong></div>
            <div className="sprint-stat"><span className="stat-label">In Review:</span><strong className="stat-value in-rev">{sprintMetrics.inReview}</strong></div>
            <div className="sprint-stat"><span className="stat-label">Done:</span><strong className="stat-value done">{sprintMetrics.done}</strong></div>
            <div className="sprint-stat"><span className="stat-label">Story Points (page):</span><strong className="stat-value">{sprintMetrics.donePoints} / {sprintMetrics.totalPoints} pts</strong></div>
            <div className="sprint-stat sprint-percent"><span className="stat-label">Progress:</span><strong className="stat-value">{sprintMetrics.progressPercent}%</strong></div>
          </div>
          <div className="sprint-progress-track">
            <div className="sprint-progress-fill" style={{ width: `${sprintMetrics.progressPercent}%` }} role="progressbar" aria-valuenow={sprintMetrics.progressPercent} aria-valuemin="0" aria-valuemax="100" />
          </div>
        </div>
      </div>

      <div className="kanban-toolbar">
        <div className="toolbar-left">
          <SearchableDropdown
            className="kanban-project-dropdown"
            options={projectOptions}
            value={selectedProjectIds}
            onChange={(value) => { setSelectedProjectIds(value); setPage(1); }}
            placeholder="Projects"
            ariaLabel="Filter by projects"
            multiple
            showSelectionActions
            disabled={isLoadingOptions}
          />
          <label className="view-control-label">
            <input
              type="checkbox"
              checked={includeOtherTasks}
              onChange={(event) => { setIncludeOtherTasks(event.target.checked); setPage(1); }}
            />
            Other tasks
          </label>

          <div className="kanban-search-box">
            <svg viewBox="0 0 16 16" width="14" height="14" fill="#94a3b8" className="search-icon">
              <path d="M11.742 10.344a6.5 6.5 0 10-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 001.415-1.414l-3.85-3.85a1.007 1.007 0 00-.115-.1zM12 6.5a5.5 5.5 0 11-11 0 5.5 5.5 0 0111 0z" />
            </svg>
            <input id="kanban-search-input" type="text" placeholder="Search by ID or task name…" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} className="kanban-search-input" />
            <span className="keyboard-shortcut-hint">/</span>
          </div>

          <SearchableDropdown
            className="kanban-employee-dropdown"
            options={employeeOptions}
            value={filterAssignee}
            onChange={(value) => { setFilterAssignee(value); setPage(1); }}
            placeholder="All Employees"
            ariaLabel="Filter by employee"
            disabled={isLoadingOptions}
          />

          <SearchableDropdown
            className="kanban-priority-dropdown"
            options={[
              { value: "all", label: "All Priorities" },
              ...PRIORITY_OPTIONS.map((priority) => ({ value: priority, label: priority })),
            ]}
            value={filterPriority}
            onChange={(value) => { setFilterPriority(value); setPage(1); }}
            placeholder="All Priorities"
            ariaLabel="Filter by priority"
          />

          <SearchableDropdown
            className="kanban-status-dropdown"
            options={[
              { value: "all", label: "All Statuses" },
              ...STATUS_OPTIONS.map((status) => ({ value: status, label: status })),
            ]}
            value={filterStatus}
            onChange={(value) => { setFilterStatus(value); setPage(1); }}
            placeholder="All Statuses"
            ariaLabel="Filter by status"
          />

          <SearchableDropdown
            className="kanban-date-dropdown"
            options={[
              { value: "all", label: "All Dates" },
              { value: "today", label: "Due Today" },
              { value: "this_week", label: "Due This Week" },
              { value: "due_soon", label: "Due Soon (3 days)" },
              { value: "upcoming", label: "Upcoming (7 days)" },
              { value: "overdue", label: "Overdue" },
              { value: "custom", label: "Custom Range" },
            ]}
            value={dateFilter}
            onChange={(value) => { setDateFilter(value); setPage(1); }}
            placeholder="All Dates"
            ariaLabel="Filter by due date"
          />

          {dateFilter === "custom" && (
            <div className="kanban-custom-date-filter">
              <input
                type="date"
                className="jira-select-filter"
                aria-label="Start date"
                value={startDate}
                onChange={(event) => { setStartDate(event.target.value); setPage(1); }}
              />
              <input
                type="date"
                className="jira-select-filter"
                aria-label="End date"
                value={endDate}
                onChange={(event) => { setEndDate(event.target.value); setPage(1); }}
              />
            </div>
          )}

          <button
            type="button"
            className={`quick-filter-pill ${highPriorityOnly ? "active" : ""}`}
            onClick={() => { setHighPriorityOnly((value) => !value); setPage(1); }}
          >
            High Priority
          </button>
          {hasActiveFilters && <button type="button" className="clear-filters-link" onClick={clearAllFilters}>Clear filters</button>}
        </div>

        <div className="toolbar-right">
          <div className="view-control-group">
            <label className="view-control-label" htmlFor="group-by-select">Group by:</label>
            <SearchableDropdown
              id="group-by-select"
              className="kanban-group-dropdown"
              options={[
                { value: "none", label: "None (Standard)" },
                { value: "assignee", label: "Assignee" },
                { value: "priority", label: "Priority" },
                { value: "status", label: "Status" },
              ]}
              value={groupBy}
              onChange={setGroupBy}
              placeholder="None (Standard)"
              ariaLabel="Group by"
            />
          </div>
          <div className="view-control-group">
            <label className="view-control-label" htmlFor="sort-by-select">Sort:</label>
            <SearchableDropdown
              id="sort-by-select"
              className="kanban-sort-dropdown"
              options={[
                { value: "due_date", label: "Due date" },
                { value: "priority", label: "Priority" },
                { value: "task_name", label: "Task name" },
                { value: "created_at", label: "Created" },
                { value: "last_updated", label: "Last updated" },
                { value: "status", label: "Status" },
              ]}
              value={sortBy}
              onChange={(value) => { setSortBy(value); setPage(1); }}
              placeholder="Due date"
              ariaLabel="Sort tasks by"
            />
            <button
              type="button"
              className="density-btn"
              onClick={() => { setSortOrder((value) => value === "asc" ? "desc" : "asc"); setPage(1); }}
              aria-label={`Sort ${sortOrder === "asc" ? "descending" : "ascending"}`}
              title={`Sort ${sortOrder === "asc" ? "descending" : "ascending"}`}
            >
              {sortOrder === "asc" ? "↑" : "↓"}
            </button>
          </div>
          <div className="density-toggle" title="Card Density">
            <button type="button" className={`density-btn ${density === "normal" ? "active" : ""}`} onClick={() => setDensity("normal")} title="Normal density">☰</button>
            <button type="button" className={`density-btn ${density === "compact" ? "active" : ""}`} onClick={() => setDensity("compact")} title="Compact density">☷</button>
          </div>
        </div>
      </div>

      <div className="kanban-board-canvas">
        {groupBy === "none" ? renderColumns(filteredTasks) : (
          <div className="kanban-swimlanes-container">
            {swimlanes?.map((lane) => (
              <div key={lane.id} className="kanban-swimlane">
                <div className="swimlane-header" onClick={() => setCollapsedSwimlanes((current) => ({ ...current, [lane.id]: !current[lane.id] }))}>
                  <button type="button" className="swimlane-toggle-icon">{collapsedSwimlanes[lane.id] ? "▶" : "▼"}</button>
                  {lane.avatar && <div className="swimlane-avatar" style={{ backgroundColor: lane.color }}>{lane.avatar}</div>}
                  {lane.icon && <span className="swimlane-icon">{lane.icon}</span>}
                  <strong className="swimlane-title">{lane.title}</strong>
                  {lane.subtitle && <span className="swimlane-subtitle">({lane.subtitle})</span>}
                  <span className="swimlane-count-badge">{lane.tasks.length} {lane.tasks.length === 1 ? "issue" : "issues"}</span>
                </div>
                {!collapsedSwimlanes[lane.id] && renderColumns(lane.tasks)}
              </div>
            ))}
          </div>
        )}
        {!selectedProjectIds.length && !includeOtherTasks && (
          <p className="activity-empty">Select one or more projects or choose Other tasks to load board tasks.</p>
        )}
        {selectedProjectIds.length + Number(includeOtherTasks) > 0 && pagination.total > 0 && (
          <div className="kanban-pagination" aria-label="Board pagination">
            <span>
              Showing {(page - 1) * BOARD_PAGE_SIZE + 1}–{Math.min(page * BOARD_PAGE_SIZE, pagination.total)} of {pagination.total}
            </span>
            <button
              type="button"
              className="btn-jira-secondary"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={page <= 1 || isLoadingTasks}
            >
              Previous
            </button>
            <span>Page {page} of {Math.max(1, pagination.total_pages)}</span>
            <button
              type="button"
              className="btn-jira-secondary"
              onClick={() => setPage((current) => Math.min(pagination.total_pages, current + 1))}
              disabled={page >= pagination.total_pages || isLoadingTasks}
            >
              Next
            </button>
          </div>
        )}
      </div>

      <CreateIssueModal
        isOpen={isCreateOpen}
        initialStatus={createInitialStatus}
        employees={employees}
        projects={projects}
        selectedProjectIds={selectedProjectIds}
        includeOtherTasks={includeOtherTasks}
        statusOptions={KANBAN_COLUMNS.map((column) => column.id)}
        priorityOptions={PRIORITY_OPTIONS}
        projectLabel={selectedProjectLabel}
        onClose={() => setIsCreateOpen(false)}
        onCreate={handleCreateTask}
      />

      <IssueDetailModal
        task={selectedTask}
        isOpen={Boolean(selectedTask)}
        employees={employees}
        statusOptions={KANBAN_COLUMNS.map((column) => column.id)}
        priorityOptions={PRIORITY_OPTIONS}
        onClose={() => setSelectedTask(null)}
        onUpdateTask={handleUpdateTask}
        onDeleteTask={handleDeleteTask}
      />
    </div>
  );
}
