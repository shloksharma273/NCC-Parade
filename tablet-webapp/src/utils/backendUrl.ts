const STORAGE_KEY = "drill_backend_url";

export function getBackendUrl(): string | null {
  const url = localStorage.getItem(STORAGE_KEY);
  return url?.trim() || null;
}

export function setBackendUrl(url: string): void {
  localStorage.setItem(STORAGE_KEY, url.replace(/\/$/, ""));
}

export function clearBackendUrl(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function normalizeBackendUrl(input: string): string {
  let url = input.trim();
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    url = `http://${url}`;
  }
  return url.replace(/\/$/, "");
}

export function toWebSocketUrl(backendUrl: string, path: string): string {
  const url = new URL(backendUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = path.startsWith("/") ? path : `/${path}`;
  url.search = "";
  url.hash = "";
  return url.toString();
}

export function mediaUrl(backendUrl: string, relativePath?: string | null): string | null {
  if (!relativePath) return null;
  if (relativePath.startsWith("http")) return relativePath;
  return `${backendUrl.replace(/\/$/, "")}${relativePath.startsWith("/") ? "" : "/"}${relativePath}`;
}
