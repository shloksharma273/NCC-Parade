from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    cadet_id: str | None = None
    cadet_name: str = "Unknown Cadet"
    drill_type: str = "kadam_tal"
    camera_id: str = "0"


class SessionResponse(BaseModel):
    session_id: str
    cadet_id: str | None = None
    cadet_name: str
    drill_type: str
    attempt_number: int
    camera_id: str
    status: str
    created_at: str
    started_at: str | None = None
    stopped_at: str | None = None
    video_path: str | None = None
    report_path: str | None = None
    score: int | None = None
    result: str | None = None
    error_message: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str
    message: str


class ActionResponse(BaseModel):
    session_id: str
    status: str
    message: str


class ProgressResponse(BaseModel):
    session_id: str
    status: str
    stage: str
    progress: int
    message: str


class SessionListItem(BaseModel):
    session_id: str
    cadet_name: str
    drill_type: str
    attempt_number: int
    status: str
    score: int | None = None
    result: str | None = None
    created_at: str


class SessionListResponse(BaseModel):
    sessions: list[SessionListItem]


class HealthResponse(BaseModel):
    status: str = "ok"
    server: str = "running"
    version: str


class SystemStatusResponse(BaseModel):
    backend_status: str
    camera_connected: bool
    camera_id: str
    model_ready: bool
    active_session_id: str | None
    storage_available: bool


class ErrorResponse(BaseModel):
    error: str
    message: str


class ReportParameter(BaseModel):
    name: str
    expected: str
    actual: str
    score: float
    status: str
    feedback: str


class ReportMedia(BaseModel):
    raw_video_url: str | None = None
    annotated_video_url: str | None = None
    key_frame_url: str | None = None


class DrillReport(BaseModel):
    session_id: str
    cadet_id: str | None = None
    cadet_name: str
    drill_type: str
    attempt_number: int
    score: int
    result: str
    summary: list[str]
    parameters: list[ReportParameter]
    media: ReportMedia
    created_at: str
    kadam_tal_count: int | None = None
    average_score_per_kadam_tal: float | None = None
    peak_frames: list[dict] = Field(default_factory=list)


class ReportNotReadyResponse(BaseModel):
    session_id: str
    status: str
    message: str
