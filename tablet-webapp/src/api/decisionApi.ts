import { getApiClient } from "./client";

export type DecisionPayload = {
  decision: "accept_ai" | "pass" | "needs_correction" | "fail" | "needs_human_review";
  remarks?: string;
};

export type DecisionResponse = {
  session_id: string;
  ai_result?: string | null;
  instructor_decision: string;
  final_result: string;
  remarks?: string | null;
  message: string;
};

export async function saveDecision(sessionId: string, payload: DecisionPayload): Promise<DecisionResponse> {
  const client = getApiClient();
  const { data } = await client.post<DecisionResponse>(`/sessions/${sessionId}/decision`, payload);
  return data;
}

export async function getAttempts(sessionId: string): Promise<{ attempts: Record<string, unknown>[] }> {
  const client = getApiClient();
  const { data } = await client.get(`/sessions/${sessionId}/attempts`);
  return data;
}
