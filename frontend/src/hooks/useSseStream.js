import { parseSseBlock } from "../lib/sse.js";

export async function readSseStream(response, onEvent) {
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
        const parsed = parseSseBlock(block);
        if (parsed) {
          onEvent(parsed);
        }
      }

      boundary = buffer.indexOf("\n\n");
    }
  }
}

export function useSseStream() {
  return readSseStream;
}
