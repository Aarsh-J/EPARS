import { useState, useEffect } from "react";
import { PriorityIcon } from "./KanbanIcons.jsx";
import SearchableDropdown from "./SearchableDropdown.jsx";

export default function CreateIssueModal({
  isOpen,
  onClose,
  onCreate,
  initialStatus = "Not Started",
  employees = [],
  statusOptions = [],
  priorityOptions = [],
  projectLabel = "",
  projects = [],
  selectedProjectIds = [],
  includeOtherTasks = false,
}) {
  const NO_PROJECT = "__other_tasks__";
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState(initialStatus);
  const [priority, setPriority] = useState("Medium");
  const [assigneeId, setAssigneeId] = useState("");
  const [storyPoints, setStoryPoints] = useState(3);
  const [dueDate, setDueDate] = useState("");
  const [requiredSkills, setRequiredSkills] = useState("");
  const [projectId, setProjectId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setStatus(initialStatus);
  }, [initialStatus]);

  useEffect(() => {
    if (selectedProjectIds.length === 1) {
      setProjectId(selectedProjectIds[0]);
    } else if (selectedProjectIds.length === 0 && includeOtherTasks) {
      setProjectId(NO_PROJECT);
    } else {
      setProjectId("");
    }
  }, [isOpen, selectedProjectIds, includeOtherTasks]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") handleClose();
    };
    if (isOpen) window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Please enter a summary / title for the issue.");
      return;
    }
    if (!projectId) {
      setError("Choose a project for this task.");
      return;
    }

    const newTask = {
      task_name: title.trim(),
      task_description: description.trim() || null,
      project_id: projectId === NO_PROJECT ? null : projectId,
      status: status || initialStatus,
      priority,
      assigned_to: assigneeId || null,
      story_points: storyPoints !== "" ? Number(storyPoints) : null,
      due_date: dueDate || null,
      required_skills: requiredSkills.trim() || null,
    };

    try {
      setIsSubmitting(true);
      setError(null);
      await onCreate(newTask);
      handleClose(true);
    } catch (submitError) {
      setError(submitError.message || "Unable to create task.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = (force = false) => {
    if (isSubmitting && !force) return;
    setTitle("");
    setDescription("");
    setStatus(initialStatus);
    setPriority("Medium");
    setAssigneeId("");
    setStoryPoints(3);
    setDueDate("");
    setRequiredSkills("");
    setProjectId("");
    setError(null);
    onClose();
  };

  return (
    <div className="jira-modal-backdrop" onClick={() => handleClose()}>
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
            <span className="jira-badge-pill">{projectLabel || "Select a project"}</span>
            <h2 id="create-issue-title">Create Issue</h2>
          </div>
          <button
            type="button"
            className="jira-modal-close"
            onClick={() => handleClose()}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        {/* Modal Form */}
        <form onSubmit={handleSubmit} className="jira-modal-body">
          {error && <div className="jira-form-error">{error}</div>}

          <div className="jira-form-grid-2">
            <div className="jira-form-group">
              <label htmlFor="issue-project-select">Project</label>
              <SearchableDropdown
                id="issue-project-select"
                className="kanban-form-dropdown"
                triggerClassName="jira-input"
                options={[
                  ...projects.map((project) => ({
                    value: project.project_id,
                    label: project.project_name
                      ? `${project.project_name} (${project.project_id})`
                      : project.project_id,
                  })),
                  { value: NO_PROJECT, label: "Other tasks (no project)" },
                ]}
                value={projectId}
                onChange={(value) => {
                  setProjectId(value);
                  if (error) setError(null);
                }}
                placeholder="Select a project"
                ariaLabel="Choose a project for this task"
              />
            </div>
          </div>

          {/* Status */}
          <div className="jira-form-grid-2">
            <div className="jira-form-group">
              <label htmlFor="issue-status-select">Status / Column</label>
              <SearchableDropdown
                id="issue-status-select"
                className="kanban-form-dropdown"
                triggerClassName="jira-input"
                options={statusOptions.map((option) => ({ value: option, label: option }))}
                value={status}
                onChange={setStatus}
                placeholder="Select status"
                ariaLabel="Choose task status"
              />
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
                <SearchableDropdown
                  id="issue-priority-select"
                  className="kanban-form-dropdown"
                  triggerClassName="jira-input jira-select-icon"
                  options={priorityOptions.map((option) => ({ value: option, label: option }))}
                  value={priority}
                  onChange={setPriority}
                  placeholder="Select priority"
                  ariaLabel="Choose task priority"
                />
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
              <SearchableDropdown
                id="issue-assignee-select"
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
                onChange={setAssigneeId}
                placeholder="Unassigned"
                ariaLabel="Choose task assignee"
              />
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

          {/* Required skills are stored in the tasks table. */}
          <div className="jira-form-group">
            <label htmlFor="issue-required-skills-input">
              Required Skills <span className="label-hint">(comma separated)</span>
            </label>
            <input
              id="issue-required-skills-input"
              type="text"
              className="jira-input"
              placeholder="e.g. React, Python, PostgreSQL, UI"
              value={requiredSkills}
              onChange={(e) => setRequiredSkills(e.target.value)}
            />
          </div>

          {/* Modal Footer */}
          <div className="jira-modal-footer">
            <button type="button" className="btn-jira-ghost" onClick={() => handleClose()} disabled={isSubmitting}>
              Cancel
            </button>
            <button type="submit" className="btn-jira-primary" disabled={isSubmitting}>
              {isSubmitting ? "Creating…" : "Create Issue"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
