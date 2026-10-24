import { useEffect, useMemo, useState } from "react";
import { scanBurnout, executeTask, logAlert } from "../api/burnoutApi";
import "./BurnoutPanel.css";

const fmt = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "");

function describe(d) {
  if (d.action === "reassign") return `Reassign to ${d.new_employee_id}`;
  if (d.action === "reschedule") return `Reschedule to ${fmt(d.new_start_time)}`;
  return "No action suggested";
}

export default function BurnoutPanel({ onClose, onDone }) {
  const [employees, setEmployees] = useState([]);
  const [apply, setApply] = useState({});    // assignment_id -> true (apply suggestion) ; absent = leave as is
  const [alerts, setAlerts] = useState({});  // employee_id -> true
  const [phase, setPhase] = useState("loading"); // loading | review | confirm | applying | done | error
  const [error, setError] = useState("");
  const [results, setResults] = useState([]); // [{label, ok, msg}]

  useEffect(() => {
    scanBurnout()
      .then((d) => { setEmployees(d.employees || []); setPhase("review"); })
      .catch((e) => { setError(e.message); setPhase("error"); });
  }, []);

  const flat = useMemo(() => employees.flatMap((e) => e.tasks.map((t) => ({ ...t, emp: e }))), [employees]);
  const chosenTasks = flat.filter((t) => apply[t.assignment_id]);
  const chosenAlerts = employees.filter((e) => alerts[e.employee_id]);
  const total = chosenTasks.length + chosenAlerts.length;

  async function run() {
    setPhase("applying");
    const out = [];
    for (const e of chosenAlerts) {            // sequential, like the terminal
      try { const r = await logAlert(e.employee_id); out.push({ label: `Alert for ${e.name}`, ok: r.ok, msg: r.ok ? "logged" : "failed" }); }
      catch (x) { out.push({ label: `Alert for ${e.name}`, ok: false, msg: x.message }); }
    }
    for (const t of chosenTasks) {
      const label = `${t.task_id} (${t.emp.name}): ${t.decision.action}`;
      try { const r = await executeTask(t.assignment_id); out.push({ label, ok: r.ok, msg: r.ok ? "done" : JSON.stringify(r.result) }); }
      catch (x) { out.push({ label, ok: false, msg: x.message }); }
    }
    setResults(out);
    setPhase("done");
    onDone?.();
  }

  return (
    <div className="bp-overlay" onClick={onClose}>
      <div className="bp-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Employee burnout check">
        <header className="bp-head">
          <h2>Employee burnout check</h2>
          <button className="bp-x" onClick={onClose} aria-label="Close">×</button>
        </header>

        <div className="bp-body">
          {phase === "loading" && <p className="bp-muted">Scanning workloads and asking the model for suggestions. This can take a minute…</p>}
          {phase === "error" && <p className="bp-error">Couldn't run the scan: {error}</p>}

          {phase === "review" && (employees.length === 0
            ? <p className="bp-muted">No employees are currently at or above the burnout threshold.</p>
            : employees.map((emp) => (
              <section key={emp.employee_id} className="bp-emp">
                <div className="bp-emp-head">
                  <strong>{emp.name}</strong>
                  <span className="bp-id">{emp.employee_id}</span>
                  <label className="bp-alert">
                    <input type="checkbox" checked={!!alerts[emp.employee_id]}
                      onChange={(e) => setAlerts((a) => ({ ...a, [emp.employee_id]: e.target.checked }))} />
                    Log burnout alert
                  </label>
                  <span className="bp-pill bp-high">Burnout {emp.burnout_score.toFixed(2)}</span>
                </div>
                {emp.tasks.map((t) => {
                  const none = t.decision.action === "none";
                  const on = !!apply[t.assignment_id];
                  return (
                    <div key={t.assignment_id} className="bp-task">
                      <div className="bp-task-info">
                        <div className="bp-task-title">{t.task_id} · {t.task_type}</div>
                        <div className="bp-task-meta">
                          {t.priority && <>Priority {t.priority}</>}
                          {t.due_date && <> · Due {t.due_date}</>}
                          {t.estimated_hours != null && <> · {t.estimated_hours}h</>}
                        </div>
                        <div className="bp-suggest"><strong>{describe(t.decision)}.</strong> {t.decision.reasoning}</div>
                      </div>
                      <div className="bp-task-action">
                        <button className={`bp-seg ${!on ? "on" : ""}`}
                          onClick={() => setApply((a) => ({ ...a, [t.assignment_id]: false }))}>Leave as is</button>
                        <button className={`bp-seg ${on ? "on" : ""}`} disabled={none}
                          onClick={() => setApply((a) => ({ ...a, [t.assignment_id]: true }))}>
                          {t.decision.action === "reassign" ? "Reassign" : "Reschedule"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </section>
            )))}

          {phase === "confirm" && (
            <div>
              <p><strong>Confirm {total} change{total !== 1 && "s"}.</strong> Reassigning and rescheduling update the database and Google Calendar.</p>
              <ul className="bp-summary">
                {chosenAlerts.map((e) => <li key={e.employee_id}>Log burnout alert for {e.name}</li>)}
                {chosenTasks.map((t) => <li key={t.assignment_id}>{t.task_id} ({t.emp.name}): {describe(t.decision).toLowerCase()}</li>)}
              </ul>
            </div>
          )}

          {phase === "applying" && <p className="bp-muted">Applying…</p>}

          {phase === "done" && (
            <ul className="bp-summary">
              {results.map((r, i) => (
                <li key={i} className={r.ok ? "bp-okline" : "bp-error"}>{r.label}: {r.msg}</li>
              ))}
            </ul>
          )}
        </div>

        <footer className="bp-foot">
          {phase === "review" && employees.length > 0 && (<>
            <span className="bp-muted">{total} change{total !== 1 && "s"} selected</span>
            <button className="bp-btn" disabled={!total} onClick={() => setPhase("confirm")}>Review changes</button>
          </>)}
          {phase === "confirm" && (<>
            <button className="bp-btn bp-ghost" onClick={() => setPhase("review")}>Back</button>
            <button className="bp-btn" onClick={run}>Apply {total}</button>
          </>)}
          {(phase === "done" || phase === "error" || (phase === "review" && employees.length === 0)) &&
            <button className="bp-btn" onClick={onClose}>Close</button>}
        </footer>
      </div>
    </div>
  );
}
