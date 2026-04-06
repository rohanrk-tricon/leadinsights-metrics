import { useState } from "react";

import { downloadBlob } from "../../lib/download.js";
import { exportTicketReport, ingestTickets, submitTicketQuestion } from "./api.js";

export const TICKET_DEFAULT_QUESTION = "How many LeadInsights tickets were closed last month?";
export const DATEDURATION_CHOICES = [
  "Yesterday", "Today", "This Week", "Last Week", "Next Week",
  "This Month", "Last Month", "Next Month", "This Quarter",
  "Last Quarter", "Next Quarter", "This Year", "Last Year", "Next Year",
];

export function useTicketIntelligence() {
  const [view, setView] = useState("query");
  const [question, setQuestion] = useState(TICKET_DEFAULT_QUESTION);
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [dateDuration, setDateDuration] = useState("");
  const [appliedDateRange, setAppliedDateRange] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await submitTicketQuestion(question);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail);
      }

      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleIngest() {
    setIngesting(true);
    setError("");

    try {
      const response = await ingestTickets();
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail);
      }

      setResult((current) => ({
        ...(current || {}),
        ingest_message: data.message,
      }));
    } catch (err) {
      setError(err.message);
    } finally {
      setIngesting(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    setError("");
    setAppliedDateRange(null);

    try {
      const response = await exportTicketReport(dateDuration);
      if (!response.ok) {
        throw new Error("Export failed");
      }

      const start = response.headers.get("x-applied-start-date");
      const end = response.headers.get("x-applied-end-date");
      if (start && end) {
        setAppliedDateRange({ start, end });
      }

      const blob = await response.blob();
      downloadBlob(blob, "report.xlsx");
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  }

  return {
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
    handleSubmit,
    handleIngest,
    handleExport,
  };
}
