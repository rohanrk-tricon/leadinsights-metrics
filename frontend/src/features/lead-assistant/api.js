import { buildApiUrl } from "../../lib/api.js";

export function submitLeadQuestion(question, fetchImpl = fetch) {
  return fetchImpl(buildApiUrl("/api/chat/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export function exportLeadMetrics(fetchImpl = fetch) {
  return fetchImpl(buildApiUrl("/api/export-metrics"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ use_case: "leadinsights" }),
  });
}
