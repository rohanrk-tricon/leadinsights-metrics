import test from "node:test";
import assert from "node:assert/strict";

import { exportLeadMetrics, submitLeadQuestion } from "../src/features/lead-assistant/api.js";
import {
  exportTicketReport,
  ingestTickets,
  submitTicketQuestion,
} from "../src/features/ticket-intelligence/api.js";

test("submitLeadQuestion preserves the chat stream request contract", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return { ok: true };
  };

  await submitLeadQuestion("How many leads?", fetchImpl);

  assert.deepEqual(calls, [
    {
      url: "/api/chat/stream",
      options: {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: "How many leads?" }),
      },
    },
  ]);
});

test("exportLeadMetrics preserves the export request contract", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return { ok: true };
  };

  await exportLeadMetrics(fetchImpl);

  assert.deepEqual(calls, [
    {
      url: "/api/export-metrics",
      options: {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_case: "leadinsights" }),
      },
    },
  ]);
});

test("submitTicketQuestion preserves the ticket query contract", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return { ok: true };
  };

  await submitTicketQuestion("How many tickets?", fetchImpl);

  assert.deepEqual(calls, [
    {
      url: "/api/ticket-intelligence/query",
      options: {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: "How many tickets?" }),
      },
    },
  ]);
});

test("ingestTickets preserves the ticket ingest contract", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return { ok: true };
  };

  await ingestTickets(fetchImpl);

  assert.deepEqual(calls, [
    {
      url: "/api/ticket-intelligence/ingest",
      options: {
        method: "POST",
      },
    },
  ]);
});

test("exportTicketReport omits dateDuration when not selected", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return { ok: true };
  };

  await exportTicketReport("", fetchImpl);

  assert.deepEqual(calls, [
    {
      url: "/api/ticket-intelligence/export",
      options: {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_case: "leadinsights" }),
      },
    },
  ]);
});

test("exportTicketReport includes dateDuration when selected", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return { ok: true };
  };

  await exportTicketReport("Last Month", fetchImpl);

  assert.deepEqual(calls, [
    {
      url: "/api/ticket-intelligence/export",
      options: {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_case: "leadinsights", dateDuration: "Last Month" }),
      },
    },
  ]);
});
