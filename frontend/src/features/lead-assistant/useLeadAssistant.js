import { useState } from "react";

import { downloadBlob } from "../../lib/download.js";
import { useSseStream } from "../../hooks/useSseStream.js";
import { exportLeadMetrics, submitLeadQuestion } from "./api.js";

export const LEAD_DEFAULT_QUESTION = "How many leads do we have by campaign?";

export function useLeadAssistant() {
  const [question, setQuestion] = useState(LEAD_DEFAULT_QUESTION);
  const [events, setEvents] = useState([]);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [appliedDateRange, setAppliedDateRange] = useState(null);
  const consumeSseStream = useSseStream();

  async function handleSubmit(e) {
    e.preventDefault();
    setEvents([]);
    setAnswer("");
    setError("");
    setLoading(true);

    try {
      const response = await submitLeadQuestion(question);
      await consumeSseStream(response, (parsed) => {
        setEvents((current) => [...current, parsed]);

        if (parsed.event === "complete") {
          setAnswer(parsed.data?.answer || "");
        }

        if (parsed.event === "error") {
          setError(parsed.data?.message || "Error");
        }
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleMetricsExport() {
    setExporting(true);
    setError("");
    setAppliedDateRange(null);

    try {
      const response = await exportLeadMetrics();
      const start = response.headers.get("x-applied-start-date");
      const end = response.headers.get("x-applied-end-date");

      if (start && end) {
        setAppliedDateRange({ start, end });
      }

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Lead metrics export failed");
      }

      const blob = await response.blob();
      downloadBlob(blob, "leadinsights_metrics_export.xlsx");
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  }

  return {
    question,
    setQuestion,
    events,
    answer,
    error,
    loading,
    exporting,
    appliedDateRange,
    handleSubmit,
    handleMetricsExport,
  };
}
