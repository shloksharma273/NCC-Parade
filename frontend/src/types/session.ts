export type SessionStatus =
  | "CREATED"
  | "READY"
  | "RECORDING"
  | "SAVING"
  | "PROCESSING"
  | "REPORT_READY"
  | "FAILED"
  | "CANCELLED";

export type CurrentSession = {
  session_id: string;
  cadet_id?: string;
  cadet_name: string;
  drill_type: string;
  attempt_number: number;
  camera_id: string;
  status: SessionStatus;
};

export type Session = {
  session_id: string;
  cadet_id?: string | null;
  cadet_name: string;
  drill_type: string;
  attempt_number: number;
  camera_id: string;
  status: SessionStatus;
  created_at: string;
  started_at?: string | null;
  stopped_at?: string | null;
  video_path?: string | null;
  report_path?: string | null;
  score?: number | null;
  result?: string | null;
  error_message?: string | null;
};

export type SessionListItem = {
  session_id: string;
  cadet_name: string;
  drill_type: string;
  attempt_number: number;
  status: SessionStatus;
  score?: number | null;
  result?: string | null;
  created_at: string;
};
