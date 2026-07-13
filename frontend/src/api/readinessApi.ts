import { getApiClient } from "./client";

export type ReadinessCheck = {
  key: string;
  name: string;
  status: "pass" | "warning" | "fail";
  message: string;
};

export type ReadinessResponse = {
  session_id?: string;
  can_record: boolean;
  checks: ReadinessCheck[];
  message: string;
  cadet_name?: string;
  drill_type?: string;
};

export async function getSessionReadiness(sessionId: string): Promise<ReadinessResponse> {
  const client = getApiClient();
  const { data } = await client.get<ReadinessResponse>(`/sessions/${sessionId}/readiness`);
  return data;
}

export async function getGlobalReadiness(): Promise<ReadinessResponse> {
  const client = getApiClient();
  const { data } = await client.get<ReadinessResponse>("/readiness");
  return data;
}
