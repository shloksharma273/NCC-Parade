import { getApiClient } from "./client";
import type { SessionActionResponse } from "../types/api";
import { getBackendUrl } from "../utils/backendUrl";

export type CameraDiagnostics = {
  camera_type: string;
  camera_host: string | null;
  rtsp_port: number | null;
  main_stream_configured: boolean;
  sub_stream_configured: boolean;
  main_stream_openable: boolean;
  sub_stream_openable: boolean;
  last_checked_at: string;
  message: string;
};

export async function startCameraPreview(sessionId: string): Promise<SessionActionResponse> {
  const client = getApiClient();
  const { data } = await client.post<SessionActionResponse>(
    `/sessions/${sessionId}/camera/preview/start`,
  );
  return data;
}

export async function stopCameraPreview(sessionId: string): Promise<SessionActionResponse> {
  const client = getApiClient();
  const { data } = await client.post<SessionActionResponse>(
    `/sessions/${sessionId}/camera/preview/stop`,
  );
  return data;
}

export async function fetchCameraDiagnostics(): Promise<CameraDiagnostics> {
  const client = getApiClient();
  const { data } = await client.get<CameraDiagnostics>("/camera/diagnostics");
  return data;
}

export type CameraDevice = {
  index: number | string; // USB: integer index; IP: "main" | "sub"
  label: string;
  available: boolean;
  thumbnail: string | null; // base64 data URI
};

export async function listCameraDevices(force = false): Promise<{ camera_type: string; devices: CameraDevice[] }> {
  const client = getApiClient();
  const { data } = await client.get<{ camera_type: string; devices: CameraDevice[] }>(
    `/camera/devices${force ? "?force=true" : ""}`,
  );
  return data;
}

/** Fire-and-forget camera warm-up (called from the first page to hide slow cold-start). */
export async function warmUpCamera(): Promise<void> {
  try {
    const client = getApiClient();
    await client.post("/camera/warmup");
  } catch {
    // best-effort; a failed warm-up must never block the UI
  }
}

/** Session-less preview of a chosen camera, for the picker on the New Session page. */
export async function startDevicePreview(cameraId: number | string): Promise<SessionActionResponse> {
  const client = getApiClient();
  const { data } = await client.post<SessionActionResponse>(
    `/camera/preview/start?camera_id=${encodeURIComponent(String(cameraId))}`,
  );
  return data;
}

export async function stopDevicePreview(): Promise<SessionActionResponse> {
  const client = getApiClient();
  const { data } = await client.post<SessionActionResponse>("/camera/preview/stop");
  return data;
}

export function getDeviceStreamUrl(): string | null {
  const backendUrl = getBackendUrl();
  if (!backendUrl) return null;
  return `${backendUrl}/camera/stream`;
}

export function getCameraStreamUrl(sessionId: string): string | null {
  const backendUrl = getBackendUrl();
  if (!backendUrl) return null;
  return `${backendUrl}/sessions/${sessionId}/camera/stream`;
}

export function getCameraSnapshotUrl(): string | null {
  const backend = getBackendUrl();
  if (!backend) return null;
  return `${backend}/camera/snapshot?t=${Date.now()}`;
}
