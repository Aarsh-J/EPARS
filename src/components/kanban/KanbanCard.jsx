import { IssueTypeIcon, PriorityIcon } from "./KanbanIcons.jsx";
import { TEAM_MEMBERS, DEFAULT_COLUMNS } from "../../data/kanbanData.js";

export default function KanbanCard({
  task,
  isDragging,
  dragTargetPosition, // 'before' | 'after' | null
  onDragStart,
  onDragEnd,
  onDragOverCard,
  onDropOnCard,
  onOpenDetail,
  onMoveColumn,
  density = "normal",
}) {
  const assignee = TEAM_MEMBERS.find((m) => m.id === task.assigneeId);
  const currentColIndex = DEFAULT_COLUMNS.findIndex((c) => c.id === task.status);
  const prevCol = currentColIndex > 0 ? DEFAULT_COLUMNS[currentColIndex - 1] : null;
  const nextCol = currentColIndex < DEFAULT_COLUMNS.length - 1 ? DEFAULT_COLUMNS[currentColIndex + 1] : null;

  // Due date status
  let dueDateClass = "";
  if (task.dueDate && task.status !== "done") {
    const due = new Date(task.dueDate);
    const now = new Date();
    const diffDays = Math.ceil((due - now) / (1000 * 60 * 60 * 24));
    if (diffDays < 0) {
      dueDateClass = "due-overdue";
    } else if (diffDays <= 3) {
      dueDateClass = "due-soon";
    }
  }

  const formatDueDate = (dateStr) => {
    if (!dateStr) return null;
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  return (
    <div
      className={`kanban-card-wrapper ${dragTargetPosition ? `drop-${dragTargetPosition}` : ""}`}
      onDragOver={(e) => onDragOverCard(e, task.id)}
      onDrop={(e) => onDropOnCard(e, task.id)}
    >
      <div
        id={`task-card-${task.id}`}
        className={`kanban-card ${isDragging ? "is-dragging" : ""} ${density === "compact" ? "compact" : ""}`}
        draggable
        onDragStart={(e) => onDragStart(e, task.id)}
        onDragEnd={onDragEnd}
        onClick={() => onOpenDetail(task)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onOpenDetail(task);
          }
        }}
        tabIndex={0}
        role="button"
        aria-label={`Task ${task.id}: ${task.title}`}
      >
        {/* Card Header: Type, Key, Priority, Quick Move Actions */}
        <div className="card-top-row">
          <div className="card-key-group">
            <IssueTypeIcon type={task.type} size={14} />
            <span className="card-issue-key">{task.id}</span>
          </div>

          <div className="card-actions-group" onClick={(e) => e.stopPropagation()}>
            <span className="card-priority-icon" title={`Priority: ${task.priority}`}>
              <PriorityIcon priority={task.priority} size={13} />
            </span>

            {/* Quick advance shortcut buttons */}
            <div className="card-quick-nav">
              {prevCol && (
                <button
                  type="button"
                  className="quick-move-btn"
                  title={`Move to ${prevCol.title}`}
                  onClick={() => onMoveColumn(task.id, prevCol.id)}
                >
                  ←
                </button>
              )}
              {nextCol && (
                <button
                  type="button"
                  className="quick-move-btn"
                  title={`Move to ${nextCol.title}`}
                  onClick={() => onMoveColumn(task.id, nextCol.id)}
                >
                  →
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Card Title */}
        <div className="card-title-text">{task.title}</div>

        {/* Tags / Skills */}
        {density !== "compact" && task.tags && task.tags.length > 0 && (
          <div className="card-tags-row">
            {task.tags.slice(0, 3).map((tag) => (
              <span key={tag} className="card-tag-pill">
                {tag}
              </span>
            ))}
            {task.tags.length > 3 && (
              <span className="card-tag-pill more">+{task.tags.length - 3}</span>
            )}
          </div>
        )}

        {/* Card Footer: Due Date, Story Points, Assignee Avatar */}
        <div className="card-bottom-row">
          <div className="card-meta-left">
            {task.dueDate && (
              <span className={`card-due-date ${dueDateClass}`} title={`Due: ${task.dueDate}`}>
                <svg viewBox="0 0 16 16" width="11" height="11" fill="currentColor">
                  <path d="M4 1v2H2a1 1 0 00-1 1v10a1 1 0 001 1h12a1 1 0 001-1V4a1 1 0 00-1-1h-2V1h-2v2H6V1H4zm10 5H2v8h12V6z" />
                </svg>
                {formatDueDate(task.dueDate)}
              </span>
            )}

            {task.storyPoints != null && (
              <span className="card-story-points" title={`${task.storyPoints} Story Points`}>
                {task.storyPoints}
              </span>
            )}
          </div>

          <div className="card-assignee-wrap" title={assignee ? `${assignee.name} (${assignee.role})` : "Unassigned"}>
            {assignee ? (
              <div
                className="card-assignee-avatar"
                style={{ backgroundColor: assignee.color }}
              >
                {assignee.avatar}
              </div>
            ) : (
              <div className="card-assignee-unassigned" title="Unassigned">
                <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor">
                  <path d="M8 8a3 3 0 100-6 3 3 0 000 6zm-5 7a5 5 0 0110 0H3z" />
                </svg>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
