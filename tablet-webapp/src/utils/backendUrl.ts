const BACKEND_KEY = "drill_backend_url";
const TOKEN_KEY = "drill_pairing_token";

export function getBackendUrl(): string | null {
  const url = localStorage.getItem(BACKEND_KEY);
  return url?.trim() || null;
}

export function setBackendUrl(url: string): void {
  localStorage.setItem(BACKEND_KEY, url.replace(/\/$/, ""));
}

export function getPairingToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setPairingToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function clearBackendUrl(): void {
  localStorage.removeItem(BACKEND_KEY);
  localStorage.removeItem(TOKEN_KEY);
}

export function normalizeBackendUrl(input: string): string {
  let url = input.trim();
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    url = `http://${url}`;
  }
  return url.replace(/\/$/, "");
}

export function applyPairingFromSearch(search: string): boolean {
  const params = new URLSearchParams(search);
  const backend = params.get("backend");
  if (!backend) return false;
  setBackendUrl(normalizeBackendUrl(backend));
  const token = params.get("pairing_token") || params.get("token");
  if (token) setPairingToken(token);
  return true;
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

export function snapshotUrl(backendUrl: string): string {
  return `${backendUrl.replace(/\/$/, "")}/camera/snapshot?t=${Date.now()}`;
}
