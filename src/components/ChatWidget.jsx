import { useEffect, useRef, useState } from "react";
import { queryAgent } from "../api/client.js";

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, open]);

  async function handleSend(e) {
    e.preventDefault();
    const query = input.trim();
    if (!query || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: query }]);
    setInput("");
    setLoading(true);

    try {
      const res = await queryAgent(query);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: res.output, steps: res.steps },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: err.message || "Something went wrong.", error: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {!open && (
        <button
          className="chat-bubble"
          onClick={() => setOpen(true)}
          aria-label="Open assistant"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </button>
      )}

      {open && (
        <div className="chat-panel">
          <div className="chat-panel-header">
            <span>ePARS Assistant</span>
            <button className="chat-panel-close" onClick={() => setOpen(false)} aria-label="Close">
              &times;
            </button>
          </div>

          <div className="chat-messages">
            {messages.length === 0 && (
              <div className="chat-empty">
                Ask about employee performance, workload, burnout risk, task
                assignment, or HR policy.
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`chat-message ${m.role}${m.error ? " error" : ""}`}>
                <div className="chat-bubble-text">{m.text}</div>
                {m.steps && m.steps.length > 0 && (
                  <details className="chat-steps">
                    <summary>What I did ({m.steps.length} step{m.steps.length > 1 ? "s" : ""})</summary>
                    {m.steps.map((s, j) => (
                      <div key={j} className="chat-step">
                        <strong>{s.tool}</strong>
                        <span>{s.output}</span>
                      </div>
                    ))}
                  </details>
                )}
              </div>
            ))}
            {loading && (
              <div className="chat-message assistant">
                <div className="chat-bubble-text chat-typing">Thinking…</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="chat-input-bar" onSubmit={handleSend}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask the assistant..."
              disabled={loading}
            />
            <button type="submit" disabled={loading || !input.trim()}>
              Send
            </button>
          </form>
        </div>
      )}
    </>
  );
}
