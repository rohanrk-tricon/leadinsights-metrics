export function downloadBlob(blob, filename, documentRef = document, urlRef = URL) {
  const url = urlRef.createObjectURL(blob);
  const link = documentRef.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  urlRef.revokeObjectURL(url);
}
