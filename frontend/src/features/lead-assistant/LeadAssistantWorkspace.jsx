export default function LeadAssistantWorkspace({
  question,
  setQuestion,
  events,
  answer,
  error,
  loading,
  exporting,
  appliedDateRange,
  onSubmit,
  onExport,
}) {
  return (
    <div id="lead-workspace" className="workspace animate-in">
      <div className="workspace-header">
        <h2 className="workspace-title"><span className={`status-dot ${loading ? "active" : ""}`}></span> Lead Assistant</h2>
        <p className="workspace-subtitle">Query your lead database with natural language</p>
      </div>

      <form id="lead-form" className="form-area" onSubmit={onSubmit}>
        <textarea
          className="input-area"
          placeholder="Describe what you want to know about your leads..."
          rows="3"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div className="btn-row">
          <button type="submit" className="btn-primary" disabled={loading}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
            {loading ? "Processing..." : "Analyze"}
          </button>
          <button type="button" className="btn-secondary" onClick={onExport} disabled={exporting}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
            {exporting ? "Exporting..." : "Export Metrics"}
          </button>
        </div>
      </form>

      {appliedDateRange && (
        <div className="glass-panel glow-border date-bounds">
          <span className="date-icon">📅</span>
          <span className="date-label">Applied date range:</span>
          <span className="date-value">{appliedDateRange.start}</span>
          <span className="date-arrow">→</span>
          <span className="date-value">{appliedDateRange.end}</span>
        </div>
      )}

      <div className="panels-grid">
        <div className="readout-panel">
          <div className="readout-label">AI Response</div>
          <div className="readout-content">
            {answer ? answer : <span className="placeholder-text">Response will appear here…</span>}
          </div>
        </div>
        <div className="readout-panel">
          <div className="readout-label">Stream Trace</div>
          <div className="readout-content">
            {events.length > 0 ? JSON.stringify(events, null, 2) : <span className="placeholder-text">Streaming chunks will appear here…</span>}
          </div>
        </div>
      </div>

      {error && <p style={{ color: "#dc2626", marginTop: "10px" }}>{error}</p>}
    </div>
  );
}
