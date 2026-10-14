import Sidebar from "./Sidebar.jsx";

export default function Layout({ title = "Overview", children }) {
  return (
    <>
      <Sidebar />
      <main className="main">
        <header className="topbar">
          <h1 className="page-title">{title}</h1>
          <div className="topbar-right">
            <span className="topbar-label">
              Employee Performance Analyser &amp; Recommendation System — Performance Metrics
            </span>
          </div>
        </header>
        <div className="content">{children}</div>
      </main>
    </>
  );
}
