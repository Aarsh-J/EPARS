import { Link } from "react-router-dom";

const MODULES = [
  {
    title: "Performance Evaluation",
    description:
      "Analyse employee performance scores, breakdown by competency clusters, and review history.",
    to: "/performance",
    active: true,
    iconBg: "#dbeafe",
    iconStroke: "#1d4ed8",
    path: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
  },
  {
    title: "Task Assignment",
    description:
      "Optimise employee-task matching using skill alignment, availability, and workload compatibility.",
    to: "/task-assignment",
    active: true,
    iconBg: "#dbeafe",
    iconStroke: "#1d4ed8",
    path: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z",
  },
  {
    title: "Workload & Risk",
    description:
      "Predict delay risk, overload probability, and burnout indicators from workload patterns.",
    to: "/burnout",
    active: true,
    iconBg: "#dbeafe",
    iconStroke: "#1d4ed8",
    path: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  },
  {
    title: "Team Formation",
    description:
      "Recommend optimal team compositions based on skills, experience balance, and collaboration history.",
    active: false,
    iconBg: "#f3f4f6",
    iconStroke: "#9ca3af",
    path: "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
  },
];

function ModuleIcon({ bg, stroke, path }) {
  return (
    <div className="module-icon" style={{ background: bg }}>
      <svg viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2">
        <path d={path} />
      </svg>
    </div>
  );
}

function ModuleCard({ mod }) {
  const inner = (
    <>
      <ModuleIcon bg={mod.iconBg} stroke={mod.iconStroke} path={mod.path} />
      <div className="module-info">
        <h3>{mod.title}</h3>
        <p>{mod.description}</p>
      </div>
      <span className={`module-status ${mod.active ? "active-badge" : "soon-badge"}`}>
        {mod.active ? "Active" : "Coming Soon"}
      </span>
    </>
  );

  if (mod.active) {
    return (
      <Link to={mod.to} className="module-card active">
        {inner}
      </Link>
    );
  }
  return <div className="module-card disabled">{inner}</div>;
}

export default function Dashboard() {
  return (
    <>
      <div className="dashboard-intro">
        <p>
          Welcome to EPARS — the Employee Performance Analyser &amp; Recommendation
          System. Select a module below to get started.
        </p>
      </div>
      <div className="module-grid">
        {MODULES.map((mod) => (
          <ModuleCard mod={mod} key={mod.title} />
        ))}
      </div>
    </>
  );
}
