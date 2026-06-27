export type ReportResult = "pass" | "needs_correction" | "fail";

export type ParameterStatus = "pass" | "needs_correction" | "fail" | "correct" | "incorrect";

export type DrillParameter = {
  name: string;
  expected: string;
  actual: string;
  score: number;
  status: ParameterStatus;
  feedback?: string;
};

export type DrillReport = {
  session_id: string;
  cadet_id?: string | null;
  cadet_name: string;
  drill_type: string;
  attempt_number: number;
  score: number;
  result: ReportResult | string;
  summary: string[];
  parameters: DrillParameter[];
  media?: {
    raw_video_url?: string | null;
    annotated_video_url?: string | null;
    key_frame_url?: string | null;
  };
  created_at: string;
  kadam_tal_count?: number | null;
  average_score_per_kadam_tal?: number | null;
};

export type ReportNotReady = {
  session_id: string;
  status: string;
  message: string;
};

export function isDrillReport(data: unknown): data is DrillReport {
  return (
    typeof data === "object" &&
    data !== null &&
    "parameters" in data &&
    "summary" in data &&
    "score" in data
  );
}
