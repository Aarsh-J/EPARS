import { Routes, Route, useLocation } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Performance from "./pages/Performance.jsx";
import Burnout from "./pages/Burnout.jsx";
import TaskAssignment from "./pages/TaskAssignment.jsx";

const PAGE_TITLES = {
  "/": "Dashboard",
  "/performance": "Performance Evaluation",
  "/burnout": "Workload & Risk",
  "/task-assignment": "Task Assignment",
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
      </Routes>
    </Layout>
  );
}
