import { useState, useEffect } from "react";
import { IssueTypeIcon, PriorityIcon } from "./KanbanIcons.jsx";
import { ISSUE_TYPES, PRIORITIES, TEAM_MEMBERS, DEFAULT_COLUMNS } from "../../data/kanbanData.js";

export default function IssueDetailModal({
  task,
  isOpen,
  onClose,
  onUpdateTask,
  onDeleteTask,
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState("task");
  const [status, setStatus] = useState("todo");
  const [priority, setPriority] = useState("medium");
  const [assigneeId, setAssigneeId] = useState("");
  const [storyPoints, setStoryPoints] = useState(3);
  const [dueDate, setDueDate] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [commentText, setCommentText] = useState("");
  const [isSavedNotice, setIsSavedNotice] = useState(false);
  const [activeTab, setActiveTab] = useState("history"); // 'history' | 'comments'
  const [comments, setComments] = useState([]);

  useEffect(() => {
    if (task) {
      setTitle(task.title || "");
      setDescription(task.description || "");
      setType(task.type || "task");
      setStatus(task.status || "todo");
      setPriority(task.priority || "medium");
      setAssigneeId(task.assigneeId || "");
      setStoryPoints(task.storyPoints != null ? task.storyPoints : "");
      setDueDate(task.dueDate || "");
      setTagsInput(task.tags ? task.tags.join(", ") : "");
      setComments(task.comments || []);
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
    saveChanges({ status: newStatus }, `Moved to ${DEFAULT_COLUMNS.find((c) => c.id === newStatus)?.title || newStatus}`);
  };

  const handlePriorityChange = (newPriority) => {
    setPriority(newPriority);
    saveChanges({ priority: newPriority }, `Priority changed to ${newPriority}`);
  };

  const handleAssigneeChange = (newAssignee) => {
    setAssigneeId(newAssignee);
    const member = TEAM_MEMBERS.find((m) => m.id === newAssignee);
    saveChanges({ assigneeId: newAssignee || null }, member ? `Assigned to ${member.name}` : "Unassigned issue");
  };

  const saveChanges = (overrides = {}, historyNote = null) => {
    const tags = tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    const updated = {
      ...task,
      title: overrides.title !== undefined ? overrides.title : title.trim(),
      description: overrides.description !== undefined ? overrides.description : description.trim(),
      type: overrides.type !== undefined ? overrides.type : type,
      status: overrides.status !== undefined ? overrides.status : status,
      priority: overrides.priority !== undefined ? overrides.priority : priority,
      assigneeId: overrides.assigneeId !== undefined ? overrides.assigneeId : (assigneeId || null),
      storyPoints: overrides.storyPoints !== undefined ? overrides.storyPoints : (storyPoints !== "" ? Number(storyPoints) : null),
      dueDate: overrides.dueDate !== undefined ? overrides.dueDate : (dueDate || null),
      tags: overrides.tags !== undefined ? overrides.tags : tags,
      comments: overrides.comments !== undefined ? overrides.comments : comments,
      updatedAt: new Date().toISOString(),
    };

    if (historyNote) {
      const historyEntry = {
        timestamp: new Date().toISOString(),
        text: historyNote,
      };
      updated.history = [historyEntry, ...(updated.history || [])];
    }

    onUpdateTask(updated);
    setIsSavedNotice(true);
    setTimeout(() => setIsSavedNotice(false), 2000);
  };

  const handleAddComment = (e) => {
    e.preventDefault();
    if (!commentText.trim()) return;

    const newComment = {
      id: "c-" + Date.now(),
      author: "Manager / Current User",
      avatar: "CU",
      color: "#3b82f6",
      text: commentText.trim(),
      timestamp: new Date().toISOString(),
    };

    const newComments = [newComment, ...comments];
    setComments(newComments);
    setCommentText("");
    saveChanges({ comments: newComments }, "Added a comment");
  };

  const handleDelete = () => {
    if (window.confirm(`Are you sure you want to delete task ${task.id}?`)) {
      onDeleteTask(task.id);
      onClose();
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

  const assignee = TEAM_MEMBERS.find((m) => m.id === assigneeId);

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
            <span className="crumb">EPARS Core</span>
            <span className="crumb-sep">/</span>
            <span className="crumb">Sprint 14</span>
            <span className="crumb-sep">/</span>
            <div className="crumb-key-group">
              <IssueTypeIcon type={type} size={15} />
              <strong id="issue-detail-key">{task.id}</strong>
            </div>
          </div>

          <div className="detail-header-actions">
            {isSavedNotice && <span className="saved-indicator">✓ Saved</span>}
            <button
              type="button"
              className="btn-jira-danger-ghost"
              onClick={handleDelete}
              title="Delete Issue"
            >
              <svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor">
                <path d="M5.5 5.5A.5.5 0 016 6v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm2.5 0a.5.5 0 01.5.5v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm3 .5a.5.5 0 00-1 0v6a.5.5 0 001 0V6z" />
                <path
                  fillRule="evenodd"
                  d="M14.5 3a1 1 0 01-1 1H13v9a2 2 0 01-2 2H5a2 2 0 01-2-2V4h-.5a1 1 0 01-1-1V2a1 1 0 011-1H6a1 1 0 011-1h2a1 1 0 011 1h3.5a1 1 0 011 1v1zM4.118 4L4 4.059V13a1 1 0 001 1h6a1 1 0 001-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"
                />
              </svg>
              Delete
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
            <div className="detail-title-edit">
              <input
                type="text"
                className="detail-title-input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                onBlur={() => saveChanges({ title })}
                placeholder="Issue Title"
              />
            </div>

            <div className="detail-section">
              <h4 className="detail-section-title">Description</h4>
              <textarea
                className="jira-input jira-textarea detail-description-input"
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                onBlur={() => saveChanges({ description })}
                placeholder="Add a detailed description or acceptance criteria…"
              />
            </div>

            {/* Activity Tabs */}
            <div className="detail-activity-section">
              <div className="activity-tabs-header">
                <h4 className="detail-section-title">Activity</h4>
                <div className="activity-tab-buttons">
                  <button
                    type="button"
                    className={`activity-tab-btn ${activeTab === "history" ? "active" : ""}`}
                    onClick={() => setActiveTab("history")}
                  >
                    History ({task.history?.length || 0})
                  </button>
                  <button
                    type="button"
                    className={`activity-tab-btn ${activeTab === "comments" ? "active" : ""}`}
                    onClick={() => setActiveTab("comments")}
                  >
                    Comments ({comments.length})
                  </button>
                </div>
              </div>

              {activeTab === "history" ? (
                <div className="activity-history-list">
                  {(!task.history || task.history.length === 0) ? (
                    <p className="activity-empty">No transitions recorded yet.</p>
                  ) : (
                    task.history.map((h, i) => (
                      <div key={i} className="activity-history-item">
                        <span className="history-bullet" />
                        <div className="history-content">
                          <span className="history-text">{h.text}</span>
                          <span className="history-time">{formatTimestamp(h.timestamp)}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              ) : (
                <div className="activity-comments-wrap">
                  <form onSubmit={handleAddComment} className="comment-input-box">
                    <textarea
                      className="jira-input jira-textarea"
                      rows={2}
                      placeholder="Add a comment on this task…"
                      value={commentText}
                      onChange={(e) => setCommentText(e.target.value)}
                    />
                    <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "6px" }}>
                      <button
                        type="submit"
                        className="btn-jira-primary btn-sm"
                        disabled={!commentText.trim()}
                      >
                        Save Comment
                      </button>
                    </div>
                  </form>

                  <div className="comments-list">
                    {comments.map((c) => (
                      <div key={c.id} className="comment-item">
                        <div
                          className="comment-avatar"
                          style={{ backgroundColor: c.color || "#3b82f6" }}
                        >
                          {c.avatar}
                        </div>
                        <div className="comment-body">
                          <div className="comment-meta">
                            <strong>{c.author}</strong>
                            <span>{formatTimestamp(c.timestamp)}</span>
                          </div>
                          <p className="comment-text">{c.text}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Meta & Attributes */}
          <div className="detail-col-sidebar">
            {/* Status Dropdown */}
            <div className="sidebar-field">
              <label className="sidebar-label">Status</label>
              <select
                className="jira-input jira-status-select"
                value={status}
                onChange={(e) => handleStatusChange(e.target.value)}
              >
                {DEFAULT_COLUMNS.map((col) => (
                  <option key={col.id} value={col.id}>
                    {col.title}
                  </option>
                ))}
              </select>
            </div>

            {/* Assignee Field */}
            <div className="sidebar-field">
              <label className="sidebar-label">Assignee</label>
              <div className="sidebar-assignee-row">
                {assignee ? (
                  <div
                    className="card-assignee-avatar"
                    style={{ backgroundColor: assignee.color }}
                  >
                    {assignee.avatar}
                  </div>
                ) : (
                  <div className="card-assignee-unassigned">
                    <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor">
                      <path d="M8 8a3 3 0 100-6 3 3 0 000 6zm-5 7a5 5 0 0110 0H3z" />
                    </svg>
                  </div>
                )}
                <select
                  className="jira-input"
                  value={assigneeId}
                  onChange={(e) => handleAssigneeChange(e.target.value)}
                >
                  <option value="">Unassigned</option>
                  {TEAM_MEMBERS.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.role})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Priority Field */}
            <div className="sidebar-field">
              <label className="sidebar-label">Priority</label>
              <div className="jira-select-icon-wrap">
                <PriorityIcon priority={priority} size={15} />
                <select
                  className="jira-input jira-select-icon"
                  value={priority}
                  onChange={(e) => handlePriorityChange(e.target.value)}
                >
                  {Object.values(PRIORITIES).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Issue Type */}
            <div className="sidebar-field">
              <label className="sidebar-label">Issue Type</label>
              <div className="jira-select-icon-wrap">
                <IssueTypeIcon type={type} size={15} />
                <select
                  className="jira-input jira-select-icon"
                  value={type}
                  onChange={(e) => {
                    setType(e.target.value);
                    saveChanges({ type: e.target.value });
                  }}
                >
                  {Object.values(ISSUE_TYPES).map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
                </select>
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
                onBlur={() => saveChanges({ storyPoints: storyPoints !== "" ? Number(storyPoints) : null })}
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
                  saveChanges({ dueDate: e.target.value });
                }}
              />
            </div>

            {/* Tags / Required Skills */}
            <div className="sidebar-field">
              <label className="sidebar-label">Tags / Skills</label>
              <input
                type="text"
                className="jira-input"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                onBlur={() => saveChanges()}
                placeholder="Comma separated tags"
              />
            </div>

            {/* Meta Info */}
            <div className="sidebar-meta-box">
              <div className="meta-line">
                <span>Created</span>
                <strong>{formatTimestamp(task.createdAt)}</strong>
              </div>
              <div className="meta-line">
                <span>Updated</span>
                <strong>{formatTimestamp(task.updatedAt)}</strong>
              </div>
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
