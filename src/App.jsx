import { Routes, Route, useLocation } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Performance from "./pages/Performance.jsx";
import Burnout from "./pages/Burnout.jsx";
import TaskAssignment from "./pages/TaskAssignment.jsx";
import KanbanBoard from "./pages/KanbanBoard.jsx";
import TeamFormation from "./pages/TeamFormation.jsx";

const PAGE_TITLES = {
  "/": "Dashboard",
  "/performance": "Performance Evaluation",
  "/burnout": "Workload & Risk",
  "/task-assignment": "Task Assignment",
  "/kanban": "Kanban Board",
  "/team-formation": "Team Formation",
};

export default function App() {
  const location = useLocation();
  const title = PAGE_TITLES[location.pathname] || "EPARS";

  return (
    <Layout title={title}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/performance" element={<Performance />} />
        <Route path="/burnout" element={<Burnout />} />
        <Route path="/task-assignment" element={<TaskAssignment />} />
        <Route path="/kanban" element={<KanbanBoard />} />
        <Route path="/team-formation" element={<TeamFormation />} />
      </Routes>
    </Layout>
  );
}
