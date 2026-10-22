export function StoryIcon({ className = "icon", size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} title="Story">
      <rect width="16" height="16" rx="3" fill="#10b981" />
      <path
        d="M5 4.5H11C11.5523 4.5 12 4.94772 12 5.5V11.5L8.5 9.5L5 11.5V4.5Z"
        fill="white"
      />
    </svg>
  );
}

export function TaskIcon({ className = "icon", size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} title="Task">
      <rect width="16" height="16" rx="3" fill="#3b82f6" />
      <path
        d="M4.5 8.2L7 10.7L11.5 5.5"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function BugIcon({ className = "icon", size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} title="Bug">
      <rect width="16" height="16" rx="3" fill="#ef4444" />
      <circle cx="8" cy="8" r="3.2" fill="white" />
      <path
        d="M8 2.5V4.5M8 11.5V13.5M3 6L4.5 7M13 6L11.5 7M3 10L4.5 9M13 10L11.5 9"
        stroke="white"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function EpicIcon({ className = "icon", size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} title="Epic">
      <rect width="16" height="16" rx="3" fill="#8b5cf6" />
      <path
        d="M8.5 3L4.5 9H8L7.5 13L11.5 7H8L8.5 3Z"
        fill="white"
        stroke="white"
        strokeWidth="0.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IssueTypeIcon({ type = "task", size = 16, className = "" }) {
  switch (type.toLowerCase()) {
    case "story":
      return <StoryIcon size={size} className={className} />;
    case "bug":
      return <BugIcon size={size} className={className} />;
    case "epic":
      return <EpicIcon size={size} className={className} />;
    case "task":
    default:
      return <TaskIcon size={size} className={className} />;
  }
}

export function PriorityIcon({ priority = "medium", size = 14, className = "" }) {
  switch (priority.toLowerCase()) {
    case "highest":
      return (
        <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} title="Highest Priority">
          <path d="M4 7.5L8 3.5L12 7.5" stroke="#dc2626" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 12.5L8 8.5L12 12.5" stroke="#dc2626" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "high":
      return (
        <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} title="High Priority">
          <path d="M4 10L8 6L12 10" stroke="#ea580c" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "medium":
      return (
        <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} title="Medium Priority">
          <path d="M3.5 6.5H12.5" stroke="#eab308" strokeWidth="2.2" strokeLinecap="round" />
          <path d="M3.5 10H12.5" stroke="#eab308" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      );
    case "low":
      return (
        <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} title="Low Priority">
          <path d="M4 6L8 10L12 6" stroke="#16a34a" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "lowest":
    default:
      return (
        <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} title="Lowest Priority">
          <path d="M4 4L8 8L12 4" stroke="#64748b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 9L8 13L12 9" stroke="#64748b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
  }
}
