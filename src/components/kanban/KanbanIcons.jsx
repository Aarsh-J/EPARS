export function PriorityIcon({ priority = "Medium", size = 14, className = "" }) {
  switch (priority.toLowerCase()) {
    case "critical":
      return (
        <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} title="Critical Priority">
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
    default:
      return null;
  }
}
