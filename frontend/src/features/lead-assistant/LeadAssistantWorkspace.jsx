function buildTimeline(events) {
  const timeline = [];
  let refiningCount = 0;

  for (const event of events) {
    if (event.event === "status") {
      const stage = event.data?.stage;
      const message = event.data?.message;
      if (!message) {
        continue;
      }

      if (stage === "refining_sql") {
        refiningCount += 1;
        continue;
      }

      timeline.push({ label: stage || "status", message });
      continue;
    }

    if (event.event === "complete") {
      timeline.push({ label: "complete", message: "Answer ready." });
      continue;
    }

    if (event.event === "error") {
      timeline.push({ label: "error", message: event.data?.message || "Request failed." });
    }
  }

  if (refiningCount > 0) {
    timeline.splice(2, 0, {
      label: "refining",
      message: `SQL was refined ${refiningCount} time${refiningCount === 1 ? "" : "s"} to match policy rules.`,
    });
  }

  return timeline;
}

function formatAnswer(answer) {
  return answer
    .split(/\n{2,}/)
    .map((section) => section.trim())
    .filter(Boolean);
}

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
  const timeline = buildTimeline(events);
  const answerSections = formatAnswer(answer);

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
          <div className="readout-content answer-content">
            {answerSections.length > 0 ? (
              answerSections.map((section, index) => (
                <p key={`${index}-${section.slice(0, 24)}`} className="answer-paragraph">
                  {section}
                </p>
              ))
            ) : (
              <span className="placeholder-text">Response will appear here…</span>
            )}
          </div>
        </div>
        <div className="readout-panel">
          <div className="readout-label">Request Activity</div>
          <div className="readout-content activity-content">
            {timeline.length > 0 ? (
              <div className="activity-list">
                {timeline.map((item, index) => (
                  <div key={`${item.label}-${index}`} className="activity-item">
                    <span className={`activity-badge ${item.label}`}>{item.label.replaceAll("_", " ")}</span>
                    <span className="activity-message">{item.message}</span>
                  </div>
                ))}
              </div>
            ) : (
              <span className="placeholder-text">Processing steps will appear here…</span>
            )}
          </div>
        </div>
      </div>

      {error && <p style={{ color: "#dc2626", marginTop: "10px" }}>{error}</p>}
    </div>
  );
}
