import { DATEDURATION_CHOICES } from "./useTicketIntelligence.js";

export default function TicketIntelligenceWorkspace({
  view,
  setView,
  question,
  setQuestion,
  loading,
  ingesting,
  exporting,
  error,
  result,
  dateDuration,
  setDateDuration,
  appliedDateRange,
  onSubmit,
  onIngest,
  onExport,
}) {
  return (
    <div id="ticket-workspace" className="workspace animate-in">
      <div className="workspace-header-row">
        <div>
          <h2 className="workspace-title"><span className={`status-dot ${(loading || ingesting) ? "active" : ""}`}></span> Ticket Intelligence</h2>
          <p className="workspace-subtitle">Query, analyze, and export ticket data</p>
        </div>
        <div className="sub-switcher">
          <button
            className={`workspace-tab sub ${view === "query" ? "active" : ""}`}
            onClick={() => setView("query")}
          >
            <span>🔍 Query</span>
          </button>
          <button
            className={`workspace-tab sub ${view === "export" ? "active" : ""}`}
            onClick={() => setView("export")}
          >
            <span>📥 Export</span>
          </button>
        </div>
      </div>

      {view === "query" && (
        <div id="ticket-query-view" className="animate-in">
          <form id="ticket-form" className="form-area" onSubmit={onSubmit}>
            <textarea
              className="input-area"
              placeholder="Ask about your tickets... e.g. 'Show me unresolved billing tickets from last week'"
              rows="3"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <div className="btn-row">
              <button type="submit" className="btn-primary" disabled={loading}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
                {loading ? "Querying..." : "Query"}
              </button>
              <button type="button" className="btn-secondary" onClick={onIngest} disabled={ingesting}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" /></svg>
                {ingesting ? "Running..." : "Ingest System"}
              </button>
            </div>
          </form>
          <div className="panels-grid">
            <div className="readout-panel">
              <div className="readout-label">AI Response</div>
              <div className="readout-content">
                {result?.response ? result.response : result?.ingest_message ? result.ingest_message : <span className="placeholder-text">Response will appear here…</span>}
              </div>
            </div>
            <div className="readout-panel">
              <div className="readout-label">Diagnostic SQL</div>
              <div className="readout-content">
                {result?.sql_query ? result.sql_query : <span className="placeholder-text">Generated SQL will appear here…</span>}
              </div>
            </div>
          </div>
        </div>
      )}

      {view === "export" && (
        <div id="ticket-export-view" className="animate-in">
          <div className="glass-panel export-panel">
            <label className="select-label">Select Date Range Filter</label>
            <select
              className="select-input"
              value={dateDuration}
              onChange={(e) => setDateDuration(e.target.value)}
            >
              <option value="">Default (Last Month)</option>
              {DATEDURATION_CHOICES.map((duration) => (
                <option key={duration} value={duration}>{duration}</option>
              ))}
            </select>
            <button className="btn-primary" onClick={onExport} disabled={exporting}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
              {exporting ? "Exporting..." : "Export Report"}
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

      {error && <p style={{ color: "#dc2626", marginTop: "10px" }}>{error}</p>}
    </div>
  );
}
