import { useState, useEffect } from "react";
import { IssueTypeIcon, PriorityIcon } from "./KanbanIcons.jsx";
import { ISSUE_TYPES, PRIORITIES, TEAM_MEMBERS, DEFAULT_COLUMNS } from "../../data/kanbanData.js";

export default function CreateIssueModal({
  isOpen,
  onClose,
  onCreate,
  initialStatus = "todo",
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState("task");
  const [status, setStatus] = useState(initialStatus);
  const [priority, setPriority] = useState("medium");
  const [assigneeId, setAssigneeId] = useState("");
  const [storyPoints, setStoryPoints] = useState(3);
  const [dueDate, setDueDate] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    setStatus(initialStatus);
  }, [initialStatus]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") handleClose();
    };
    if (isOpen) window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Please enter a summary / title for the issue.");
      return;
    }

    const tags = tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    const newTask = {
      title: title.trim(),
      description: description.trim(),
      type,
      status: status || initialStatus,
      priority,
      assigneeId: assigneeId || null,
      storyPoints: storyPoints !== "" ? Number(storyPoints) : null,
      dueDate: dueDate || null,
      tags,
    };

    onCreate(newTask);
    handleClose();
  };

  const handleClose = () => {
    setTitle("");
    setDescription("");
    setType("task");
    setStatus(initialStatus);
    setPriority("medium");
    setAssigneeId("");
    setStoryPoints(3);
    setDueDate("");
    setTagsInput("");
    setError(null);
    onClose();
  };

  return (
    <div className="jira-modal-backdrop" onClick={handleClose}>
      <div
        className="jira-modal-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-issue-title"
      >
        {/* Modal Header */}
        <div className="jira-modal-header">
          <div className="jira-modal-title-group">
            <span className="jira-badge-pill">Project: EPARS Core</span>
            <h2 id="create-issue-title">Create Issue</h2>
          </div>
          <button
            type="button"
            className="jira-modal-close"
            onClick={handleClose}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        {/* Modal Form */}
        <form onSubmit={handleSubmit} className="jira-modal-body">
          {error && <div className="jira-form-error">{error}</div>}

          {/* Row 1: Type & Status */}
          <div className="jira-form-grid-2">
            <div className="jira-form-group">
              <label htmlFor="issue-type-select">Issue Type *</label>
              <div className="jira-select-icon-wrap">
                <IssueTypeIcon type={type} size={16} />
                <select
                  id="issue-type-select"
                  className="jira-input jira-select-icon"
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                >
                  {Object.values(ISSUE_TYPES).map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="jira-form-group">
              <label htmlFor="issue-status-select">Status / Column</label>
              <select
                id="issue-status-select"
                className="jira-input"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                {DEFAULT_COLUMNS.map((col) => (
                  <option key={col.id} value={col.id}>
                    {col.title}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Row 2: Title / Summary */}
          <div className="jira-form-group">
            <label htmlFor="issue-summary-input">
              Summary * <span className="label-hint">(short title)</span>
            </label>
            <input
              id="issue-summary-input"
              type="text"
              className="jira-input"
              placeholder="e.g. Implement real-time task drag and drop"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                if (error) setError(null);
              }}
              autoFocus
            />
          </div>

          {/* Row 3: Description */}
          <div className="jira-form-group">
            <label htmlFor="issue-description-input">Description</label>
            <textarea
              id="issue-description-input"
              className="jira-input jira-textarea"
              rows={4}
              placeholder="Add details, acceptance criteria, or technical implementation notes…"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {/* Row 4: Priority & Story Points */}
          <div className="jira-form-grid-2">
            <div className="jira-form-group">
              <label htmlFor="issue-priority-select">Priority</label>
              <div className="jira-select-icon-wrap">
                <PriorityIcon priority={priority} size={15} />
                <select
                  id="issue-priority-select"
                  className="jira-input jira-select-icon"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                >
                  {Object.values(PRIORITIES).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="jira-form-group">
              <label htmlFor="issue-points-input">Story Points</label>
              <input
                id="issue-points-input"
                type="number"
                min="0"
                max="100"
                className="jira-input"
                value={storyPoints}
                onChange={(e) => setStoryPoints(e.target.value)}
              />
            </div>
          </div>

          {/* Row 5: Assignee & Due Date */}
          <div className="jira-form-grid-2">
            <div className="jira-form-group">
              <label htmlFor="issue-assignee-select">Assignee</label>
              <select
                id="issue-assignee-select"
                className="jira-input"
                value={assigneeId}
                onChange={(e) => setAssigneeId(e.target.value)}
              >
                <option value="">Unassigned</option>
                {TEAM_MEMBERS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.role})
                  </option>
                ))}
              </select>
            </div>

            <div className="jira-form-group">
              <label htmlFor="issue-due-input">Due Date</label>
              <input
                id="issue-due-input"
                type="date"
                className="jira-input"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </div>
          </div>

          {/* Row 6: Tags / Skills */}
          <div className="jira-form-group">
            <label htmlFor="issue-tags-input">
              Tags / Required Skills <span className="label-hint">(comma separated)</span>
            </label>
            <input
              id="issue-tags-input"
              type="text"
              className="jira-input"
              placeholder="e.g. React, Python, PostgreSQL, UI"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
            />
          </div>

          {/* Modal Footer */}
          <div className="jira-modal-footer">
            <button type="button" className="btn-jira-ghost" onClick={handleClose}>
              Cancel
            </button>
            <button type="submit" className="btn-jira-primary">
              Create Issue
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
