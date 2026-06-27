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
};

export const STAGE_LABELS: Record<string, string> = {
  video_saved: "Video Saved",
  pose_extraction: "Pose Extraction",
  parameter_calculation: "Parameter Calculation",
  ground_truth_comparison: "Ground Truth Comparison",
  report_generation: "Report Generation",
  completed: "Completed",
  failed: "Failed",
};

export function sessionStatusLabel(status: SessionStatus | string): string {
  return SESSION_STATUS_LABELS[status as SessionStatus] ?? status;
}

export function resultLabel(result: ReportResult | string): string {
  return RESULT_LABELS[result] ?? result;
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
  const map: Record<string, string> = {
    kadam_tal: "Kadam Tal",
    salute: "Salute",
    attention: "Attention",
    march: "March",
  };
  return map[drillType] ?? drillType;
}

export const SUPPORTED_DRILL_TYPES = [
  { value: "kadam_tal", label: "Kadam Tal", backendSupported: true },
  { value: "salute", label: "Salute", backendSupported: true },
  { value: "attention", label: "Attention", backendSupported: false },
  { value: "march", label: "March", backendSupported: false },
];
