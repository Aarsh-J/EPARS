import { useState, useEffect } from "react";
import { PriorityIcon } from "./KanbanIcons.jsx";
import SearchableDropdown from "./SearchableDropdown.jsx";

function formatRequiredSkills(value) {
  return Array.isArray(value) ? value.join(", ") : value || "";
}

export default function IssueDetailModal({
  task,
  isOpen,
  onClose,
  onUpdateTask,
  onDeleteTask,
  employees = [],
  statusOptions = [],
  priorityOptions = [],
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("Not Started");
  const [priority, setPriority] = useState("Medium");
  const [assigneeId, setAssigneeId] = useState("");
  const [storyPoints, setStoryPoints] = useState(3);
  const [dueDate, setDueDate] = useState("");
  const [requiredSkills, setRequiredSkills] = useState("");
  const [isSavedNotice, setIsSavedNotice] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (task) {
      setTitle(task.title || "");
      setDescription(task.description || "");
      setStatus(task.status || "Not Started");
      setPriority(task.priority || "Medium");
      setAssigneeId(task.assigneeId || "");
      setStoryPoints(task.storyPoints != null ? task.storyPoints : "");
      setDueDate(task.dueDate || "");
      setRequiredSkills(formatRequiredSkills(task.requiredSkills));
      setSaveError("");
    }
  }, [task]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !task) return null;

  const handleStatusChange = (newStatus) => {
    setStatus(newStatus);
    saveChanges({ status: newStatus });
  };

  const handlePriorityChange = (newPriority) => {
    setPriority(newPriority);
    saveChanges({ priority: newPriority });
  };

  const handleAssigneeChange = (newAssignee) => {
    setAssigneeId(newAssignee);
    saveChanges({ assigneeId: newAssignee || null });
  };

  const saveChanges = async (changes) => {
    if (isSaving || Object.keys(changes).length === 0) return;
    setSaveError("");
    setIsSaving(true);
    try {
      await onUpdateTask({ id: task.id, ...changes });
      setIsSavedNotice(true);
      setTimeout(() => setIsSavedNotice(false), 2000);
    } catch (error) {
      setTitle(task.title || "");
      setDescription(task.description || "");
      setStatus(task.status || "Not Started");
      setPriority(task.priority || "Medium");
      setAssigneeId(task.assigneeId || "");
      setStoryPoints(task.storyPoints != null ? task.storyPoints : "");
      setDueDate(task.dueDate || "");
      setRequiredSkills(formatRequiredSkills(task.requiredSkills));
      setSaveError(error.message || "Unable to save task changes.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (window.confirm(`Are you sure you want to delete task ${task.id}?`)) {
      try {
        setIsDeleting(true);
        await onDeleteTask(task.id);
        onClose();
      } catch (error) {
        setSaveError(error.message || "Unable to delete task.");
      } finally {
        setIsDeleting(false);
      }
    }
  };

  const formatTimestamp = (iso) => {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  const assignee = employees.find((employee) => employee.employee_id === assigneeId);
  const assigneeInitials = assignee
    ? (assignee.full_name || assignee.employee_id).split(/\s+/).slice(0, 2).map((part) => part[0]).join("")
    : "";

  return (
    <div className="jira-modal-backdrop" onClick={onClose}>
      <div
        className="jira-modal-dialog jira-detail-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="issue-detail-key"
      >
        {/* Modal Top Bar */}
        <div className="jira-modal-header detail-header">
          <div className="jira-breadcrumbs">
            <span className="crumb">{task.projectName || "Tasks"}</span>
            <span className="crumb-sep">/</span>
            <span className="crumb">Kanban</span>
            <span className="crumb-sep">/</span>
            <div className="crumb-key-group">
              <strong id="issue-detail-key">{task.id}</strong>
            </div>
          </div>

          <div className="detail-header-actions">
            {isSavedNotice && <span className="saved-indicator">✓ Saved</span>}
            <button
              type="button"
              className="btn-jira-danger-ghost"
              onClick={handleDelete}
              disabled={isDeleting}
              title="Delete Issue"
            >
              <svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor">
                <path d="M5.5 5.5A.5.5 0 016 6v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm2.5 0a.5.5 0 01.5.5v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm3 .5a.5.5 0 00-1 0v6a.5.5 0 001 0V6z" />
                <path
                  fillRule="evenodd"
                  d="M14.5 3a1 1 0 01-1 1H13v9a2 2 0 01-2 2H5a2 2 0 01-2-2V4h-.5a1 1 0 01-1-1V2a1 1 0 011-1H6a1 1 0 011-1h2a1 1 0 011 1h3.5a1 1 0 011 1v1zM4.118 4L4 4.059V13a1 1 0 001 1h6a1 1 0 001-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"
                />
              </svg>
              {isDeleting ? "Deleting…" : "Delete"}
            </button>
            <button
              type="button"
              className="jira-modal-close"
              onClick={onClose}
              aria-label="Close dialog"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Modal Main Layout (Jira 2-column) */}
        <div className="jira-detail-columns">
          {/* Left Column: Title, Description, History/Comments */}
          <div className="detail-col-main">
            {saveError && <div className="jira-form-error">{saveError}</div>}
            <div className="detail-title-edit">
              <input
                type="text"
                className="detail-title-input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                onBlur={() => title.trim() !== task.title && saveChanges({ title: title.trim() })}
                placeholder="Issue Title"
                disabled={isSaving}
              />
            </div>

            <div className="detail-section">
              <h4 className="detail-section-title">Description</h4>
              <textarea
                className="jira-input jira-textarea detail-description-input"
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                onBlur={() => description !== (task.description || "") && saveChanges({ description: description.trim() || null })}
                placeholder="Add a detailed description or acceptance criteria…"
                disabled={isSaving}
              />
            </div>

            <div className="detail-activity-section">
              <div className="activity-tabs-header">
                <h4 className="detail-section-title">Timeline</h4>
              </div>
              <div className="activity-history-list">
                {[
                  { label: "Created", timestamp: task.createdAt },
                  { label: "Last updated", timestamp: task.updatedAt },
                ]
                  .filter((entry) => entry.timestamp)
                  .sort((left, right) => new Date(left.timestamp) - new Date(right.timestamp))
                  .map((entry) => (
                    <div key={entry.label} className="activity-history-item">
                      <span className="history-bullet" />
                      <div className="history-content">
                        <span className="history-text">{entry.label}</span>
                        <span className="history-time">{formatTimestamp(entry.timestamp)}</span>
                      </div>
                    </div>
                  ))}
                {!task.createdAt && !task.updatedAt && (
                  <p className="activity-empty">No timestamps are available for this task.</p>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: Meta & Attributes */}
          <div className="detail-col-sidebar">
            {/* Status Dropdown */}
            <div className="sidebar-field">
              <label className="sidebar-label" htmlFor="detail-status-select">Status</label>
              <SearchableDropdown
                id="detail-status-select"
                className="kanban-form-dropdown"
                triggerClassName="jira-input jira-status-select"
                options={statusOptions.map((option) => ({ value: option, label: option }))}
                value={status}
                onChange={handleStatusChange}
                placeholder="Select status"
                ariaLabel="Change task status"
                disabled={isSaving}
              />
            </div>

            {/* Assignee Field */}
            <div className="sidebar-field">
              <label className="sidebar-label">Assignee</label>
              <div className="sidebar-assignee-row">
                {assignee ? (
                  <div
                    className="card-assignee-avatar"
                    style={{ backgroundColor: "#64748b" }}
                  >
                    {assigneeInitials}
                  </div>
                ) : (
                  <div className="card-assignee-unassigned">
                    <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor">
                      <path d="M8 8a3 3 0 100-6 3 3 0 000 6zm-5 7a5 5 0 0110 0H3z" />
                    </svg>
                  </div>
                )}
                <SearchableDropdown
                  className="kanban-form-dropdown"
                  triggerClassName="jira-input"
                  options={[
                    { value: "", label: "Unassigned" },
                    ...employees.map((employee) => ({
                      value: employee.employee_id,
                      label: `${employee.full_name}${employee.role ? ` (${employee.role})` : ""}`,
                    })),
                  ]}
                  value={assigneeId}
                  onChange={handleAssigneeChange}
                  placeholder="Unassigned"
                  ariaLabel="Change task assignee"
                  disabled={isSaving}
                />
              </div>
            </div>

            {/* Priority Field */}
            <div className="sidebar-field">
              <label className="sidebar-label">Priority</label>
              <div className="jira-select-icon-wrap">
                <PriorityIcon priority={priority} size={15} />
                <SearchableDropdown
                  className="kanban-form-dropdown"
                  triggerClassName="jira-input jira-select-icon"
                  options={priorityOptions.map((option) => ({ value: option, label: option }))}
                  value={priority}
                  onChange={handlePriorityChange}
                  placeholder="Select priority"
                  ariaLabel="Change task priority"
                  disabled={isSaving}
                />
              </div>
            </div>

            {/* Story Points */}
            <div className="sidebar-field">
              <label className="sidebar-label">Story Points</label>
              <input
                type="number"
                min="0"
                max="100"
                className="jira-input"
                value={storyPoints}
                onChange={(e) => setStoryPoints(e.target.value)}
                onBlur={() => {
                  const value = storyPoints !== "" ? Number(storyPoints) : null;
                  if (value !== task.storyPoints) saveChanges({ storyPoints: value });
                }}
                disabled={isSaving}
              />
            </div>

            {/* Due Date */}
            <div className="sidebar-field">
              <label className="sidebar-label">Due Date</label>
              <input
                type="date"
                className="jira-input"
                value={dueDate}
                onChange={(e) => {
                  setDueDate(e.target.value);
                }}
                onBlur={() => {
                  const value = dueDate || null;
                  if (value !== task.dueDate) saveChanges({ dueDate: value });
                }}
                disabled={isSaving}
              />
            </div>

            <div className="sidebar-field">
              <label className="sidebar-label">Required Skills</label>
              <input
                type="text"
                className="jira-input"
                value={requiredSkills}
                onChange={(e) => setRequiredSkills(e.target.value)}
                onBlur={() => {
                  const value = requiredSkills.trim() || null;
                  if (value !== formatRequiredSkills(task.requiredSkills)) saveChanges({ requiredSkills: value });
                }}
                placeholder="Comma separated skills"
                disabled={isSaving}
              />
            </div>

          </div>
        </div>

        {/* Modal Footer */}
        <div className="jira-modal-footer">
          <button type="button" className="btn-jira-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
