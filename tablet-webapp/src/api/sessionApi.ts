import { getApiClient } from "./client";
import type {
  CreateSessionPayload,
  CreateSessionResponse,
  ProgressResponse,
  SessionActionResponse,
  SessionListResponse,
} from "../types/api";
import type { Session } from "../types/session";

export async function createSession(payload: CreateSessionPayload): Promise<CreateSessionResponse> {
  const client = getApiClient();
  const { data } = await client.post<CreateSessionResponse>("/sessions", payload);
  return data;
}

export async function getSession(sessionId: string): Promise<Session> {
  const client = getApiClient();
  const { data } = await client.get<Session>(`/sessions/${sessionId}`);
  return data;
}

export async function listSessions(limit = 20, drillType?: string, cadetId?: string): Promise<SessionListResponse> {
  const client = getApiClient();
  const params: Record<string, string | number> = { limit };
  if (drillType) params.drill_type = drillType;
  if (cadetId) params.cadet_id = cadetId;
  const { data } = await client.get<SessionListResponse>("/sessions", { params });
  return data;
}

export async function startRecording(sessionId: string): Promise<SessionActionResponse> {
  const client = getApiClient();
  const { data } = await client.post<SessionActionResponse>(`/sessions/${sessionId}/recording/start`);
  return data;
}

export async function stopRecording(sessionId: string): Promise<SessionActionResponse> {
  const client = getApiClient();
  const { data } = await client.post<SessionActionResponse>(`/sessions/${sessionId}/recording/stop`);
  return data;
}

export async function getProgress(sessionId: string): Promise<ProgressResponse> {
  const client = getApiClient();
  const { data } = await client.get<ProgressResponse>(`/sessions/${sessionId}/progress`);
  return data;
}
