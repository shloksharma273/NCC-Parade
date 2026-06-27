from __future__ import annotations

from enum import Enum


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    RECORDING = "RECORDING"
    SAVING = "SAVING"
    PROCESSING = "PROCESSING"
    REPORT_READY = "REPORT_READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ProcessingStage(str, Enum):
    VIDEO_SAVED = "video_saved"
    POSE_EXTRACTION = "pose_extraction"
    PARAMETER_CALCULATION = "parameter_calculation"
    GROUND_TRUTH_COMPARISON = "ground_truth_comparison"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"
    FAILED = "failed"


VALID_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.CREATED: {SessionStatus.READY, SessionStatus.CANCELLED, SessionStatus.FAILED},
    SessionStatus.READY: {SessionStatus.RECORDING, SessionStatus.CANCELLED, SessionStatus.FAILED},
    SessionStatus.RECORDING: {SessionStatus.SAVING, SessionStatus.FAILED, SessionStatus.CANCELLED},
    SessionStatus.SAVING: {SessionStatus.PROCESSING, SessionStatus.FAILED},
    SessionStatus.PROCESSING: {SessionStatus.REPORT_READY, SessionStatus.FAILED},
    SessionStatus.REPORT_READY: set(),
    SessionStatus.FAILED: set(),
    SessionStatus.CANCELLED: set(),
}


def can_transition(current: SessionStatus, target: SessionStatus) -> bool:
    return target in VALID_TRANSITIONS.get(current, set())
