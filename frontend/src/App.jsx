import { useState } from "react";

import LeadAssistantWorkspace from "./features/lead-assistant/LeadAssistantWorkspace.jsx";
import { useLeadAssistant } from "./features/lead-assistant/useLeadAssistant.js";
import TicketIntelligenceWorkspace from "./features/ticket-intelligence/TicketIntelligenceWorkspace.jsx";
import { useTicketIntelligence } from "./features/ticket-intelligence/useTicketIntelligence.js";

export default function App() {
  const [activeWorkspace, setActiveWorkspace] = useState("lead");
  const leadAssistant = useLeadAssistant();
  const ticketIntelligence = useTicketIntelligence();

  return (
    <>
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <div className="logo-icon">✦</div>
            <span className="logo-text">Leadinsights Analytics</span>
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
        {activeWorkspace === "lead" && (
          <LeadAssistantWorkspace
            question={leadAssistant.question}
            setQuestion={leadAssistant.setQuestion}
            events={leadAssistant.events}
            answer={leadAssistant.answer}
            error={leadAssistant.error}
            loading={leadAssistant.loading}
            exporting={leadAssistant.exporting}
            appliedDateRange={leadAssistant.appliedDateRange}
            onSubmit={leadAssistant.handleSubmit}
            onExport={leadAssistant.handleMetricsExport}
          />
        )}

        {activeWorkspace === "ticket" && (
          <TicketIntelligenceWorkspace
            view={ticketIntelligence.view}
            setView={ticketIntelligence.setView}
            question={ticketIntelligence.question}
            setQuestion={ticketIntelligence.setQuestion}
            loading={ticketIntelligence.loading}
            ingesting={ticketIntelligence.ingesting}
            exporting={ticketIntelligence.exporting}
            error={ticketIntelligence.error}
            result={ticketIntelligence.result}
            dateDuration={ticketIntelligence.dateDuration}
            setDateDuration={ticketIntelligence.setDateDuration}
            appliedDateRange={ticketIntelligence.appliedDateRange}
            onSubmit={ticketIntelligence.handleSubmit}
            onIngest={ticketIntelligence.handleIngest}
            onExport={ticketIntelligence.handleExport}
          />
        )}
      </main>

      <div className="footer-line"></div>
    </>
  );
}
