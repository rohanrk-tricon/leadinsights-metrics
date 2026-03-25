import { useState } from "react";

const LEAD_DEFAULT_QUESTION = "How many leads do we have by campaign?";
const TICKET_DEFAULT_QUESTION = "How many LeadInsights tickets were closed last month?";

const WORKSPACES = [
  {
    id: "lead",
    eyebrow: "Streaming SQL assistant",
    title: "LeadDB Assistant",
    description:
      "Use the MCP-backed workflow to generate SQL, stream each execution step, and validate the final answer.",
  },
  {
    id: "ticket",
    eyebrow: "Freshdesk analytics",
    title: "Ticket Intelligence",
    description:
      "Query the ticket warehouse directly, inspect SQL when analytics is used, and trigger background ingestion.",
  },
];

function parseEventBlock(block) {
  const lines = block.split("\n");
  const event = lines.find((line) => line.startsWith("event:"))?.replace("event:", "").trim();
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace("data:", "").trim())
    .join("\n");

  return {
    event,
    data: data ? JSON.parse(data) : {},
  };
}

function getApiBaseUrl() {
  return import.meta.env.VITE_API_BASE_URL ?? "";
}

export default function App() {
  const [activeWorkspace, setActiveWorkspace] = useState("lead");
  const [leadQuestion, setLeadQuestion] = useState(LEAD_DEFAULT_QUESTION);
  const [leadEvents, setLeadEvents] = useState([]);
  const [leadAnswer, setLeadAnswer] = useState("");
  const [leadError, setLeadError] = useState("");
  const [leadLoading, setLeadLoading] = useState(false);

  const [ticketQuestion, setTicketQuestion] = useState(TICKET_DEFAULT_QUESTION);
  const [ticketLoading, setTicketLoading] = useState(false);
  const [ticketIngesting, setTicketIngesting] = useState(false);
  const [ticketExporting, setTicketExporting] = useState(false);
  const [ticketError, setTicketError] = useState("");
  const [ticketResult, setTicketResult] = useState(null);

  async function handleLeadSubmit(event) {
    event.preventDefault();
    setLeadEvents([]);
    setLeadAnswer("");
    setLeadError("");
    setLeadLoading(true);

    try {
      const response = await fetch(`${getApiBaseUrl()}/api/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: leadQuestion }),
      });

      if (!response.ok || !response.body) {
        throw new Error("Streaming request failed.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const block = buffer.slice(0, boundary).trim();
          buffer = buffer.slice(boundary + 2);

          if (block) {
            const parsed = parseEventBlock(block);
            setLeadEvents((current) => [...current, parsed]);
            if (parsed.event === "complete") {
              setLeadAnswer(parsed.data.answer ?? "");
            }
            if (parsed.event === "error") {
              setLeadError(parsed.data.message ?? "Unknown backend error.");
            }
          }

          boundary = buffer.indexOf("\n\n");
        }
      }
    } catch (submissionError) {
      setLeadError(submissionError.message);
    } finally {
      setLeadLoading(false);
    }
  }

  async function handleTicketSubmit(event) {
    event.preventDefault();
    setTicketError("");
    setTicketResult(null);
    setTicketLoading(true);

    try {
      const response = await fetch(`${getApiBaseUrl()}/api/ticket-intelligence/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: ticketQuestion }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Ticket Intelligence request failed.");
      }

      setTicketResult(payload);
    } catch (submissionError) {
      setTicketError(submissionError.message);
    } finally {
      setTicketLoading(false);
    }
  }

  async function handleTicketIngest() {
    setTicketError("");
    setTicketIngesting(true);

    try {
      const response = await fetch(`${getApiBaseUrl()}/api/ticket-intelligence/ingest`, {
        method: "POST",
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Ticket ingestion trigger failed.");
      }

      setTicketResult((current) => ({
        ...(current ?? {}),
        ingest_message: payload.message,
      }));
    } catch (submissionError) {
      setTicketError(submissionError.message);
    } finally {
      setTicketIngesting(false);
    }
  }

  async function handleTicketExport() {
    setTicketError("");
    setTicketExporting(true);

    try {
      const response = await fetch(`${getApiBaseUrl()}/api/ticket-intelligence/export`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ use_case: "leadinsights" }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail ?? "Ticket export failed.");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "leadinsights_metrics_export.xlsx";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

    } catch (submissionError) {
      setTicketError(submissionError.message);
    } finally {
      setTicketExporting(false);
    }
  }

  const currentWorkspace = WORKSPACES.find((workspace) => workspace.id === activeWorkspace);

  return (
    <main className="app-shell">
      <section className="hero-card">
        <div className="hero-meta">
          <p className="eyebrow">Merged branch workspace</p>
          <p className="hero-chip">FastAPI backend + React frontend</p>
        </div>
        <h1>LeadDB + Ticket Intelligence</h1>
        <p className="hero-copy">
          One frontend now drives both the streaming LeadDB assistant and the cloned ticket-intelligence flow.
        </p>

        <div className="workspace-switcher" role="tablist" aria-label="Workspace switcher">
          {WORKSPACES.map((workspace) => (
            <button
              key={workspace.id}
              className={workspace.id === activeWorkspace ? "switch-pill active" : "switch-pill"}
              onClick={() => setActiveWorkspace(workspace.id)}
              type="button"
            >
              <span>{workspace.title}</span>
              <small>{workspace.eyebrow}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="workspace-card">
        <div className="workspace-header">
          <div>
            <p className="eyebrow">{currentWorkspace.eyebrow}</p>
            <h2>{currentWorkspace.title}</h2>
          </div>
          <p className="workspace-copy">{currentWorkspace.description}</p>
        </div>

        {activeWorkspace === "lead" ? (
          <>
            <form className="question-form" onSubmit={handleLeadSubmit}>
              <label htmlFor="lead-question">Question</label>
              <textarea
                id="lead-question"
                value={leadQuestion}
                onChange={(nextEvent) => setLeadQuestion(nextEvent.target.value)}
                rows={4}
                placeholder="Ask about campaigns, sponsors, leads, or transactions"
              />
              <div className="action-row">
                <button disabled={leadLoading} type="submit">
                  {leadLoading ? "Streaming..." : "Ask LeadDB"}
                </button>
              </div>
            </form>

            <section className="panel-grid">
              <article className="panel">
                <div className="panel-header">
                  <h3>Final Answer</h3>
                </div>
                {leadAnswer ? <p className="answer-text">{leadAnswer}</p> : <p className="muted">No answer yet.</p>}
                {leadError ? <p className="error-text">{leadError}</p> : null}
              </article>

              <article className="panel">
                <div className="panel-header">
                  <h3>Stream Trace</h3>
                </div>
                <div className="event-list">
                  {leadEvents.length === 0 ? <p className="muted">Streaming events will appear here.</p> : null}
                  {leadEvents.map((entry, index) => (
                    <div className="event-card" key={`${entry.event}-${index}`}>
                      <p className="event-name">{entry.event}</p>
                      <pre>{JSON.stringify(entry.data, null, 2)}</pre>
                    </div>
                  ))}
                </div>
              </article>
            </section>
          </>
        ) : (
          <>
            <form className="question-form" onSubmit={handleTicketSubmit}>
              <label htmlFor="ticket-question">Question</label>
              <textarea
                id="ticket-question"
                value={ticketQuestion}
                onChange={(nextEvent) => setTicketQuestion(nextEvent.target.value)}
                rows={4}
                placeholder="Ask about ticket counts, resolution time, or common support themes"
              />
              <div className="action-row">
                <button disabled={ticketLoading} type="submit">
                  {ticketLoading ? "Analyzing..." : "Ask Ticket Intelligence"}
                </button>
                <button
                  className="secondary-button"
                  disabled={ticketIngesting}
                  onClick={handleTicketIngest}
                  type="button"
                >
                  {ticketIngesting ? "Triggering..." : "Run Ingestion"}
                </button>
                <button
                  className="secondary-button"
                  disabled={ticketExporting}
                  onClick={handleTicketExport}
                  type="button"
                >
                  {ticketExporting ? "Exporting..." : "Export Report"}
                </button>
              </div>
            </form>

            <section className="panel-grid">
              <article className="panel">
                <div className="panel-header">
                  <h3>Ticket Response</h3>
                  {ticketResult?.query_type ? <span className="status-pill">{ticketResult.query_type}</span> : null}
                </div>
                {ticketResult?.response ? (
                  <pre className="response-block">{ticketResult.response}</pre>
                ) : (
                  <p className="muted">Ticket answers will appear here.</p>
                )}
                {ticketResult?.ingest_message ? (
                  <p className="info-text">{ticketResult.ingest_message}</p>
                ) : null}
                {ticketError ? <p className="error-text">{ticketError}</p> : null}
              </article>

              <article className="panel">
                <div className="panel-header">
                  <h3>Diagnostics</h3>
                </div>
                {ticketResult?.sql_query ? (
                  <>
                    <p className="detail-label">SQL</p>
                    <pre>{ticketResult.sql_query}</pre>
                  </>
                ) : (
                  <p className="muted">SQL appears here for analytics queries.</p>
                )}
                {ticketResult?.raw_data ? (
                  <>
                    <p className="detail-label">Raw Data</p>
                    <pre>{JSON.stringify(ticketResult.raw_data, null, 2)}</pre>
                  </>
                ) : null}
              </article>
            </section>
          </>
        )}
      </section>
    </main>
  );
}
