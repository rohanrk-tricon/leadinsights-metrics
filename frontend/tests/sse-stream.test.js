import test from "node:test";
import assert from "node:assert/strict";

import { readSseStream } from "../src/hooks/useSseStream.js";

function makeResponse(chunks) {
  const encodedChunks = chunks.map((chunk) => new TextEncoder().encode(chunk));
  let index = 0;

  return {
    body: {
      getReader() {
        return {
          async read() {
            if (index >= encodedChunks.length) {
              return { done: true, value: undefined };
            }

            const value = encodedChunks[index];
            index += 1;
            return { done: false, value };
          },
        };
      },
    },
  };
}

test("readSseStream emits parsed events across chunk boundaries", async () => {
  const events = [];
  const response = makeResponse([
    'event: status\ndata: {"stage":"planning"}\n\n',
    'event: complete\ndata: {"answer":"done"}\n',
    "\n",
  ]);

  await readSseStream(response, (event) => {
    events.push(event);
  });

  assert.deepEqual(events, [
    { event: "status", data: { stage: "planning" } },
    { event: "complete", data: { answer: "done" } },
  ]);
});

test("readSseStream ignores empty blocks", async () => {
  const events = [];
  const response = makeResponse(["\n\n", 'data: {"answer":"ok"}\n\n']);

  await readSseStream(response, (event) => {
    events.push(event);
  });

  assert.deepEqual(events, [{ event: "message", data: { answer: "ok" } }]);
});
