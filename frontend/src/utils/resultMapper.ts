import type { SessionStatus } from "../types/session";
import type { ParameterStatus, ReportResult } from "../types/report";

export const SESSION_STATUS_LABELS: Record<SessionStatus, string> = {
  CREATED: "Session Created",
  READY: "Ready",
  RECORDING: "Recording",
  SAVING: "Saving Video",
  PROCESSING: "Analysing",
  REPORT_READY: "Report Ready",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

export const RESULT_LABELS: Record<string, string> = {
  pass: "Pass",
  needs_correction: "Needs Correction",
  fail: "Fail",
  needs_human_review: "Needs Human Review",
};

export const STAGE_LABELS: Record<string, string> = {
  video_saved: "Video Saved",
  pose_extraction: "Pose Extracted",
  parameter_calculation: "Parameters Measured",
  ground_truth_comparison: "Compared with Ground Truth",
  report_generation: "Report Generated",
  completed: "Completed",
  failed: "Failed",
};

// viewSelectable: the cadet can choose Front/Side at session creation (drill supports both
// modes in the backend). baju_swing implements both (front = fist/thumb + arm spread,
// side = inter-arm swing angle); others use a fixed view.
export const DRILL_OPTIONS = [
  { value: "salute", label: "Salute", cameraView: "Front", backendSupported: true, viewSelectable: false },
  { value: "kadam_tal", label: "Kadam Tal", cameraView: "Side", backendSupported: true, viewSelectable: false },
  { value: "baju_swing", label: "Baju Swing", cameraView: "Front", backendSupported: true, viewSelectable: true },
  { value: "slow_march", label: "Slow March", cameraView: "Side", backendSupported: true, viewSelectable: false },
  { value: "slow_march_track", label: "Slow March Track", cameraView: "Side", backendSupported: false, viewSelectable: false },
  { value: "tez_march", label: "Tez March", cameraView: "Side", backendSupported: false, viewSelectable: false },
  { value: "hill_march", label: "Hill March", cameraView: "Side", backendSupported: false, viewSelectable: false },
] as const;

export const SUPPORTED_DRILL_TYPES = DRILL_OPTIONS.filter((d) => d.backendSupported);

export function sessionStatusLabel(status: SessionStatus | string): string {
  return SESSION_STATUS_LABELS[status as SessionStatus] ?? status;
}

export function resultLabel(result: ReportResult | string): string {
  return RESULT_LABELS[result] ?? result.replace(/_/g, " ");
}

export function parameterStatusLabel(status: ParameterStatus | string): string {
  const map: Record<string, string> = {
    pass: "Pass",
    correct: "Correct",
    needs_correction: "Needs Correction",
    fail: "Fail",
    incorrect: "Incorrect",
  };
  return map[status] ?? status;
}

export function drillTypeLabel(drillType: string): string {
  const found = DRILL_OPTIONS.find((d) => d.value === drillType);
  if (found) return found.label;
  return drillType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
