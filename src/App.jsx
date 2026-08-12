import { Routes, Route, useLocation } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Performance from "./pages/Performance.jsx";

const PAGE_TITLES = {
  "/": "Dashboard",
  "/performance": "Performance Evaluation",
};

export default function App() {
  const location = useLocation();
  const title = PAGE_TITLES[location.pathname] || "EPARS";

  return (
    <Layout title={title}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/performance" element={<Performance />} />
      </Routes>
    </Layout>
  );
}
