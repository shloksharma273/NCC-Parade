import { getApiClient } from "./client";
import type { SessionActionResponse } from "../types/api";
import { getBackendUrl } from "../utils/backendUrl";

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

export function getCameraStreamUrl(sessionId: string): string | null {
  const backendUrl = getBackendUrl();
  if (!backendUrl) return null;
  return `${backendUrl}/sessions/${sessionId}/camera/stream`;
}
