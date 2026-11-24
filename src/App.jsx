import { useState } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import { useAuth } from "./auth/AuthContext.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Performance from "./pages/Performance.jsx";
import Burnout from "./pages/Burnout.jsx";
import TaskAssignment from "./pages/TaskAssignment.jsx";
import KanbanBoard from "./pages/KanbanBoard.jsx";
import TeamFormation from "./pages/TeamFormation.jsx";
import Forms from "./pages/Forms.jsx";
import Login from "./pages/Login.jsx";

const PAGE_TITLES = {
  "/": "Dashboard",
  "/performance": "Performance Evaluation",
  "/burnout": "Workload & Risk",
  "/task-assignment": "Task Assignment",
  "/kanban": "Kanban Board",
  "/team-formation": "Team Formation",
  "/forms": "Forms",
};

function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="auth-loading">Checking your session...</div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <Outlet />;
}

function AuthenticatedLayout() {
  const location = useLocation();
  const { logout } = useAuth();
  const [logoutError, setLogoutError] = useState("");
  const title = PAGE_TITLES[location.pathname] || "EPARS";

  async function handleLogout() {
    setLogoutError("");
    try {
      await logout();
    } catch (error) {
      console.error("Unable to sign out:", error);
      setLogoutError("Sign out failed. Please try again.");
    }
  }

  return (
    <Layout title={title} onLogout={handleLogout} logoutError={logoutError}>
      <Outlet />
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route element={<AuthenticatedLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/performance" element={<Performance />} />
          <Route path="/burnout" element={<Burnout />} />
          <Route path="/task-assignment" element={<TaskAssignment />} />
          <Route path="/kanban" element={<KanbanBoard />} />
          <Route path="/team-formation" element={<TeamFormation />} />
          <Route path="/forms" element={<Forms />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
