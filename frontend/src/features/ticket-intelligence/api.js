import { buildApiUrl } from "../../lib/api.js";

export function submitTicketQuestion(question, fetchImpl = fetch) {
  return fetchImpl(buildApiUrl("/api/ticket-intelligence/query"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export function ingestTickets(fetchImpl = fetch) {
  return fetchImpl(buildApiUrl("/api/ticket-intelligence/ingest"), {
    method: "POST",
  });
}

export function exportTicketReport(dateDuration, fetchImpl = fetch) {
  const body = { use_case: "leadinsights" };
  if (dateDuration) {
    body.dateDuration = dateDuration;
  }

  return fetchImpl(buildApiUrl("/api/ticket-intelligence/export"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
