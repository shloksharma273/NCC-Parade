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
