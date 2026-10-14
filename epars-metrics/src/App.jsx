import { Routes, Route, useLocation } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import useResults from "./hooks/useResults.js";
import Overview from "./pages/Overview.jsx";
import Benchmark from "./pages/Benchmark.jsx";
import Routing from "./pages/Routing.jsx";
import Drift from "./pages/Drift.jsx";
import Why from "./pages/Why.jsx";

const TITLES = {
  "/": "Overview",
  "/benchmark": "Agent Benchmark",
  "/routing": "Cached vs Live Inference",
  "/drift": "Train/Serve Drift Guard",
  "/why": "Why ePARS",
};

export default function App() {
  const { pathname } = useLocation();
  const { data, error } = useResults();

  let body;
  if (error) {
    body = (
      <div className="card">
        <div className="card-title">No results yet</div>
        <p className="metric-label">Generate them first, then refresh this page:</p>
        <pre className="chat-bubble-text" style={{ background: "#0f172a", color: "#f1f5f9", padding: 12, borderRadius: 8, marginTop: 8 }}>npm run bench</pre>
      </div>
    );
  } else if (!data) {
    body = <div className="loading-wrap"><div className="spinner" /><span>Loading results…</span></div>;
  } else {
    body = (
      <Routes>
        <Route path="/" element={<Overview data={data} />} />
        <Route path="/benchmark" element={<Benchmark data={data} />} />
        <Route path="/routing" element={<Routing data={data} />} />
        <Route path="/drift" element={<Drift data={data} />} />
        <Route path="/why" element={<Why data={data} />} />
      </Routes>
    );
  }
  return <Layout title={TITLES[pathname] || "EPARS Metrics"}>{body}</Layout>;
}
