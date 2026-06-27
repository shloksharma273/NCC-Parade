import { getApiClient } from "./client";
import type { HealthResponse, SystemStatus } from "../types/api";

export async function checkHealth(): Promise<HealthResponse> {
  const client = getApiClient();
  const { data } = await client.get<HealthResponse>("/health");
  return data;
}

export async function getStatus(): Promise<SystemStatus> {
  const client = getApiClient();
  const { data } = await client.get<SystemStatus>("/status");
  return data;
}
