import { useState } from "react";

const LEAD_DEFAULT_QUESTION = "How many leads do we have by campaign?";
const TICKET_DEFAULT_QUESTION = "How many LeadInsights tickets were closed last month?";
const DATEDURATION_CHOICES = [
  "Yesterday", "Today", "This Week", "Last Week", "Next Week",
  "This Month", "Last Month", "Next Month", "This Quarter",
  "Last Quarter", "Next Quarter", "This Year", "Last Year", "Next Year"
];

export default function App() {
  const [activeWorkspace, setActiveWorkspace] = useState("lead");

  // Lead state
  const [leadQuestion, setLeadQuestion] = useState(LEAD_DEFAULT_QUESTION);
  const [leadEvents, setLeadEvents] = useState([]);
  const [leadAnswer, setLeadAnswer] = useState("");
  const [leadError, setLeadError] = useState("");
  const [leadLoading, setLeadLoading] = useState(false);
  const [leadExporting, setLeadExporting] = useState(false);
  const [leadAppliedDateRange, setLeadAppliedDateRange] = useState(null);

  // Ticket state
  const [ticketView, setTicketView] = useState("query"); // NEW
  const [ticketQuestion, setTicketQuestion] = useState(TICKET_DEFAULT_QUESTION);
  const [ticketLoading, setTicketLoading] = useState(false);
  const [ticketIngesting, setTicketIngesting] = useState(false);
  const [ticketExporting, setTicketExporting] = useState(false);
  const [ticketError, setTicketError] = useState("");
  const [ticketResult, setTicketResult] = useState(null);
  const [dateDuration, setDateDuration] = useState("");
  const [appliedDateRange, setAppliedDateRange] = useState(null);

  /* ================================
     API HELPERS
  ================================= */

  function getApiBaseUrl() {
    return import.meta.env.VITE_API_BASE_URL ?? "";
  }

  /* ================================
     LEAD HANDLER (UNCHANGED)
  ================================= */

  async function handleLeadSubmit(e) {
    e.preventDefault();
    setLeadEvents([]);
    setLeadAnswer("");
    setLeadError("");
    setLeadLoading(true);

    try {
      const res = await fetch(`${getApiBaseUrl()}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: leadQuestion }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const block = buffer.slice(0, boundary).trim();
          buffer = buffer.slice(boundary + 2);

          if (block) {
            const lines = block.split("\n");
            const eventLine = lines.find((line) => line.startsWith("event:"));
            const dataLines = lines.filter((line) => line.startsWith("data:"));
            const eventName = eventLine ? eventLine.replace(/^event:\s*/, "").trim() : "message";
            const dataText = dataLines.map((line) => line.replace(/^data:\s*/, "")).join("\n");

            if (dataText) {
              const payload = JSON.parse(dataText);
              const parsed = { event: eventName, data: payload };
              setLeadEvents((c) => [...c, parsed]);

              if (parsed.event === "complete") setLeadAnswer(parsed.data?.answer || "");
              if (parsed.event === "error") setLeadError(parsed.data?.message || "Error");
            }
          }

          boundary = buffer.indexOf("\n\n");
        }
      }
    } catch (err) {
      setLeadError(err.message);
    } finally {
      setLeadLoading(false);
    }
  }

  /* ================================
     TICKET HANDLERS
  ================================= */

  async function handleTicketSubmit(e) {
    e.preventDefault();
    setTicketLoading(true);
    setTicketError("");
    setTicketResult(null);

    try {
      const res = await fetch(`${getApiBaseUrl()}/api/ticket-intelligence/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: ticketQuestion }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);

      setTicketResult(data);
    } catch (err) {
      setTicketError(err.message);
    } finally {
      setTicketLoading(false);
    }
  }

  async function handleTicketIngest() {
    setTicketIngesting(true);
    setTicketError("");

    try {
      const res = await fetch(`${getApiBaseUrl()}/api/ticket-intelligence/ingest`, {
        method: "POST",
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);

      setTicketResult((prev) => ({
        ...(prev || {}),
        ingest_message: data.message,
      }));
    } catch (err) {
      setTicketError(err.message);
    } finally {
      setTicketIngesting(false);
    }
  }

  async function handleTicketExport() {
    setTicketExporting(true);
    setTicketError("");
    setAppliedDateRange(null);

    try {
      const body = { use_case: "leadinsights" };
      if (dateDuration) body.dateDuration = dateDuration;

      const res = await fetch(`${getApiBaseUrl()}/api/ticket-intelligence/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) throw new Error("Export failed");

      const start = res.headers.get("x-applied-start-date");
      const end = res.headers.get("x-applied-end-date");
      if (start && end) setAppliedDateRange({ start, end });

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = "report.xlsx";
      a.click();

      URL.revokeObjectURL(url);
    } catch (err) {
      setTicketError(err.message);
    } finally {
      setTicketExporting(false);
    }
  }

  async function handleLeadMetricsExport() {
    setLeadExporting(true);
    setLeadError("");
    setLeadAppliedDateRange(null);

    try {
      const res = await fetch(`${getApiBaseUrl()}/api/export-metrics`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_case: "leadinsights" }),
      });

      const start = res.headers.get("x-applied-start-date");
      const end = res.headers.get("x-applied-end-date");
      if (start && end) setLeadAppliedDateRange({ start, end });

      if (!res.ok) {
        const error = await res.text();
        throw new Error(error || "Lead metrics export failed");
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "leadinsights_metrics_export.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setLeadError(err.message);
    } finally {
      setLeadExporting(false);
    }
  }

  /* ================================
     RENDER
  ================================= */

  return (
    <>
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <div className="logo-icon">✦</div>
            <span className="logo-text">AI Command Center</span>
          </div>
          <div className="workspace-switcher">
            <button
              className={`workspace-tab ${activeWorkspace === "lead" ? "active" : ""}`}
              onClick={() => setActiveWorkspace("lead")}
            >
              <span>🤖 Lead Assistant</span>
            </button>
            <button
              className={`workspace-tab ${activeWorkspace === "ticket" ? "active" : ""}`}
              onClick={() => setActiveWorkspace("ticket")}
            >
              <span>🎫 Ticket Intelligence</span>
            </button>
          </div>
        </div>
      </header>

      <main className="main">
        {/* LEAD WORKSPACE */}
        {activeWorkspace === "lead" && (
          <div id="lead-workspace" className="workspace animate-in">
            <div className="workspace-header">
              <h2 className="workspace-title"><span className={`status-dot ${leadLoading ? "active" : ""}`}></span> Lead Assistant</h2>
              <p className="workspace-subtitle">Query your lead database with natural language</p>
            </div>

            <form id="lead-form" className="form-area" onSubmit={handleLeadSubmit}>
              <textarea
                className="input-area"
                placeholder="Describe what you want to know about your leads..."
                rows="3"
                value={leadQuestion}
                onChange={(e) => setLeadQuestion(e.target.value)}
              />
              <div className="btn-row">
                <button type="submit" className="btn-primary" disabled={leadLoading}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
                  {leadLoading ? "Processing..." : "Analyze"}
                </button>
                <button type="button" className="btn-secondary" onClick={handleLeadMetricsExport} disabled={leadExporting}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                  {leadExporting ? "Exporting..." : "Export Metrics"}
                </button>
              </div>
            </form>

            {leadAppliedDateRange && (
              <div className="glass-panel glow-border date-bounds">
                <span className="date-icon">📅</span>
                <span className="date-label">Applied date range:</span>
                <span className="date-value">{leadAppliedDateRange.start}</span>
                <span className="date-arrow">→</span>
                <span className="date-value">{leadAppliedDateRange.end}</span>
              </div>
            )}

            <div className="panels-grid">
              <div className="readout-panel">
                <div className="readout-label">AI Response</div>
                <div className="readout-content">
                  {leadAnswer ? leadAnswer : <span className="placeholder-text">Response will appear here…</span>}
                </div>
              </div>
              <div className="readout-panel">
                <div className="readout-label">Stream Trace</div>
                <div className="readout-content">
                  {leadEvents.length > 0 ? JSON.stringify(leadEvents, null, 2) : <span className="placeholder-text">Streaming chunks will appear here…</span>}
                </div>
              </div>
            </div>

            {leadError && <p style={{ color: '#dc2626', marginTop: '10px' }}>{leadError}</p>}
          </div>
        )}

        {/* TICKET WORKSPACE */}
        {activeWorkspace === "ticket" && (
          <div id="ticket-workspace" className="workspace animate-in">
            <div className="workspace-header-row">
              <div>
                <h2 className="workspace-title"><span className={`status-dot ${(ticketLoading || ticketIngesting) ? "active" : ""}`}></span> Ticket Intelligence</h2>
                <p className="workspace-subtitle">Query, analyze, and export ticket data</p>
              </div>
              <div className="sub-switcher">
                <button
                  className={`workspace-tab sub ${ticketView === "query" ? "active" : ""}`}
                  onClick={() => setTicketView("query")}
                >
                  <span>🔍 Query</span>
                </button>
                <button
                  className={`workspace-tab sub ${ticketView === "export" ? "active" : ""}`}
                  onClick={() => setTicketView("export")}
                >
                  <span>📥 Export</span>
                </button>
              </div>
            </div>

            {/* Query View */}
            {ticketView === "query" && (
              <div id="ticket-query-view" className="animate-in">
                <form id="ticket-form" className="form-area" onSubmit={handleTicketSubmit}>
                  <textarea
                    className="input-area"
                    placeholder="Ask about your tickets... e.g. 'Show me unresolved billing tickets from last week'"
                    rows="3"
                    value={ticketQuestion}
                    onChange={(e) => setTicketQuestion(e.target.value)}
                  />
                  <div className="btn-row">
                    <button type="submit" className="btn-primary" disabled={ticketLoading}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
                      {ticketLoading ? "Querying..." : "Query"}
                    </button>
                    <button type="button" className="btn-secondary" onClick={handleTicketIngest} disabled={ticketIngesting}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" /></svg>
                      {ticketIngesting ? "Running..." : "Ingest System"}
                    </button>
                  </div>
                </form>
                <div className="panels-grid">
                  <div className="readout-panel">
                    <div className="readout-label">AI Response</div>
                    <div className="readout-content">
                      {ticketResult?.response ? ticketResult.response : ticketResult?.ingest_message ? ticketResult.ingest_message : <span className="placeholder-text">Response will appear here…</span>}
                    </div>
                  </div>
                  <div className="readout-panel">
                    <div className="readout-label">Diagnostic SQL</div>
                    <div className="readout-content">
                      {ticketResult?.sql_query ? ticketResult.sql_query : <span className="placeholder-text">Generated SQL will appear here…</span>}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Export View */}
            {ticketView === "export" && (
              <div id="ticket-export-view" className="animate-in">
                <div className="glass-panel export-panel">
                  <label className="select-label">Select Date Range Filter</label>
                  <select
                    className="select-input"
                    value={dateDuration}
                    onChange={(e) => setDateDuration(e.target.value)}
                  >
                    <option value="">Default (Last Month)</option>
                    {DATEDURATION_CHOICES.map((dur) => (
                      <option key={dur} value={dur}>{dur}</option>
                    ))}
                  </select>
                  <button className="btn-primary" onClick={handleTicketExport} disabled={ticketExporting}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                    {ticketExporting ? "Exporting..." : "Export Report"}
                  </button>
                </div>
                {appliedDateRange && (
                  <div className="glass-panel glow-border date-bounds">
                    <span className="date-icon">📅</span>
                    <span className="date-label">Applied date range:</span>
                    <span className="date-value">{appliedDateRange.start}</span>
                    <span className="date-arrow">→</span>
                    <span className="date-value">{appliedDateRange.end}</span>
                  </div>
                )}
              </div>
            )}

            {ticketError && <p style={{ color: '#dc2626', marginTop: '10px' }}>{ticketError}</p>}
          </div>
        )}
      </main>

      <div className="footer-line"></div>
    </>
  );
}
