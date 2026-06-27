import { getApiClient } from "./client";
import type { DrillReport, ReportNotReady } from "../types/report";
import { isDrillReport } from "../types/report";

export async function getReport(sessionId: string): Promise<DrillReport | ReportNotReady> {
  const client = getApiClient();
  const { data } = await client.get<DrillReport | ReportNotReady>(`/sessions/${sessionId}/report`);
  return data;
}

export async function fetchReadyReport(sessionId: string): Promise<DrillReport> {
  const data = await getReport(sessionId);
  if (!isDrillReport(data)) {
    throw new Error(data.message || "Report is still being generated. Please wait.");
  }
  return data;
}
