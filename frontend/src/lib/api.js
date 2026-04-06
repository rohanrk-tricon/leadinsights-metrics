export function getApiBaseUrl() {
  return import.meta.env?.VITE_API_BASE_URL ?? "";
}

export function buildApiUrl(path) {
  return `${getApiBaseUrl()}${path}`;
}
