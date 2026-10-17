import KanbanCard from "./KanbanCard.jsx";

export default function KanbanColumn({
  column,
  tasks = [],
  isDragOver = false,
  draggingTaskId = null,
  dragTargetCardId = null,
  dragTargetPosition = null,
  onDragOverColumn,
  onDragLeaveColumn,
  onDropOnColumn,
  onDragStartCard,
  onDragEndCard,
  onDragOverCard,
  onDropOnCard,
  onOpenDetail,
  onMoveColumn,
  onQuickAddTask,
  density = "normal",
}) {
  const isOverWip = column.wipLimit && tasks.length > column.wipLimit;
  const isAtWip = column.wipLimit && tasks.length === column.wipLimit;

  return (
    <div
      className={`kanban-column ${isDragOver ? "column-drag-over" : ""}`}
      id={`kanban-col-${column.id}`}
      onDragOver={(e) => onDragOverColumn(e, column.id)}
      onDragLeave={(e) => onDragLeaveColumn(e, column.id)}
      onDrop={(e) => onDropOnColumn(e, column.id)}
    >
      {/* Column Header */}
      <div className="column-header">
        <div className="column-title-wrap">
          <span className="column-status-indicator" style={{ backgroundColor: column.color }} />
          <h3 className="column-title">{column.title}</h3>
          <span className="column-count-badge">{tasks.length}</span>

          {column.wipLimit && (
            <span
              className={`column-wip-badge ${isOverWip ? "wip-exceeded" : isAtWip ? "wip-reached" : ""}`}
              title={
                isOverWip
                  ? `WIP limit exceeded: ${tasks.length} of max ${column.wipLimit}`
                  : `WIP limit: max ${column.wipLimit}`
              }
            >
              max {column.wipLimit}
            </span>
          )}
        </div>

        <button
          type="button"
          className="column-add-btn"
          title={`Add task to ${column.title}`}
          onClick={() => onQuickAddTask(column.id)}
          aria-label={`Add task to ${column.title}`}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
            <path d="M8 2a.75.75 0 01.75.75v4.5h4.5a.75.75 0 010 1.5h-4.5v4.5a.75.75 0 01-1.5 0v-4.5h-4.5a.75.75 0 010-1.5h4.5v-4.5A.75.75 0 018 2z" />
          </svg>
        </button>
      </div>

      {/* Column Body / Drop Zone */}
      <div className="column-cards-container">
        {tasks.length === 0 ? (
          <div
            className={`column-empty-state ${isDragOver ? "empty-drag-over" : ""}`}
            onClick={() => onQuickAddTask(column.id)}
          >
            <div className="empty-state-icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="4" y="4" width="16" height="16" rx="3" strokeDasharray="3 3" />
                <path d="M12 8v8M8 12h8" strokeLinecap="round" />
              </svg>
            </div>
            <p className="empty-state-text">No issues in {column.title}</p>
            <span className="empty-state-action">+ Create issue</span>
          </div>
        ) : (
          tasks.map((task) => (
            <KanbanCard
              key={task.id}
              task={task}
              isDragging={draggingTaskId === task.id}
              dragTargetPosition={dragTargetCardId === task.id ? dragTargetPosition : null}
              onDragStart={onDragStartCard}
              onDragEnd={onDragEndCard}
              onDragOverCard={onDragOverCard}
              onDropOnCard={onDropOnCard}
              onOpenDetail={onOpenDetail}
              onMoveColumn={onMoveColumn}
              density={density}
            />
          ))
        )}

        {/* If dragging over column and no card is directly targeted */}
        {isDragOver && !dragTargetCardId && tasks.length > 0 && (
          <div className="column-drop-placeholder-bottom">
            <span>Drop here to add to {column.title}</span>
          </div>
        )}
      </div>
    </div>
  );
}
