import type { DrillReport } from "./report";
import type { Session, SessionListItem } from "./session";

export type HealthResponse = {
  status: string;
  server: string;
  version: string;
};

export type SystemStatus = {
  backend_status: string;
  camera_connected: boolean;
  camera_id: string;
  model_ready: boolean;
  active_session_id: string | null;
  storage_available: boolean;
};

export type CreateSessionPayload = {
  cadet_id?: string;
  cadet_name: string;
  squad?: string;
  unit?: string;
  drill_type: string;
  camera_id: string;
  camera_view?: string;
};

export type CreateSessionResponse = {
  session_id: string;
  status: string;
  message: string;
};

export type SessionActionResponse = {
  session_id: string;
  status: string;
  message: string;
};

export type ProgressResponse = {
  session_id: string;
  status: string;
  stage: string;
  progress: number;
  message: string;
};

export type SessionListResponse = {
  sessions: SessionListItem[];
};

export type WebSocketMessage = {
  type: "status_update" | "processing_update" | "report_ready";
  session_id: string;
  status: string;
  stage?: string;
  progress?: number;
  message?: string;
  report_url?: string;
  timestamp?: string;
};

export type ApiError = {
  error: string;
  message: string;
};

export type { DrillReport, Session, SessionListItem };
