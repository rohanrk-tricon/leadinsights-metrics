import test from "node:test";
import assert from "node:assert/strict";

import { parseSseBlock } from "../src/lib/sse.js";

test("parseSseBlock parses event and JSON payload", () => {
  const parsed = parseSseBlock('event: status\ndata: {"stage":"accepted","message":"ok"}');

  assert.deepEqual(parsed, {
    event: "status",
    data: {
      stage: "accepted",
      message: "ok",
    },
  });
});

test("parseSseBlock supports blocks with only data lines", () => {
  const parsed = parseSseBlock('data: {"answer":"done"}');

  assert.deepEqual(parsed, {
    event: "message",
    data: {
      answer: "done",
    },
  });
});

test("parseSseBlock returns null when no data payload exists", () => {
  assert.equal(parseSseBlock("event: status"), null);
});
