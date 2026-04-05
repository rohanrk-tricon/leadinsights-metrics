export function parseSseBlock(block) {
  const lines = block.split("\n");
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines.filter((line) => line.startsWith("data:"));
  const eventName = eventLine ? eventLine.replace(/^event:\s*/, "").trim() : "message";
  const dataText = dataLines.map((line) => line.replace(/^data:\s*/, "")).join("\n");

  if (!dataText) {
    return null;
  }

  return {
    event: eventName,
    data: JSON.parse(dataText),
  };
}
