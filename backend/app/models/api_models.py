from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    cadet_id: str | None = None
    cadet_name: str = "Unknown Cadet"
    squad: str | None = None
    unit: str | None = None
    drill_type: str = "kadam_tal"
    camera_id: str = "0"
    camera_view: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    cadet_id: str | None = None
    cadet_name: str
    squad: str | None = None
    unit: str | None = None
    drill_type: str
    attempt_number: int
    camera_id: str
    camera_view: str | None = None
    status: str
    created_at: str
    started_at: str | None = None
    stopped_at: str | None = None
    video_path: str | None = None
    report_path: str | None = None
    score: int | None = None
    result: str | None = None
    ai_result: str | None = None
    instructor_decision: str | None = None
    instructor_remarks: str | None = None
    decision_at: str | None = None
    final_result: str | None = None
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
    cadet_id: str | None = None
    drill_type: str
    attempt_number: int
    status: str
    score: int | None = None
    result: str | None = None
    final_result: str | None = None
    created_at: str


class SessionListResponse(BaseModel):
    sessions: list[SessionListItem]


class HealthResponse(BaseModel):
    status: str = "ok"
    server: str = "running"
    version: str


class SystemStatusResponse(BaseModel):
    backend_status: str
    camera_type: str = "usb"
    camera_connected: bool
    camera_id: str
    camera_host: str | None = None
    camera_stream: str | None = None
    model_ready: bool
    active_session_id: str | None
    storage_available: bool
    error: str | None = None


class CameraDeviceResponse(BaseModel):
    device_id: str
    kind: str
    label: str
    status: str
    available: bool
    message: str
    index: int | None = None
    host: str | None = None
    port: int | None = None
    has_sub_stream: bool = False
    capabilities: dict = Field(default_factory=dict)
    warm: bool = False
    preview_state: str | None = None
    preview_error: str | None = None


class CameraDeviceListResponse(BaseModel):
    devices: list[CameraDeviceResponse] = Field(default_factory=list)
    default_device_id: str | None = None
    available_count: int = 0
    message: str = ""


class CameraWarmupResponse(BaseModel):
    warmed: list[str] = Field(default_factory=list)
    skipped: bool = False
    message: str = ""


class CameraConfigEntry(BaseModel):
    slug: str
    device_id: str
    label: str
    host: str
    port: int
    username: str = ""
    password_set: bool = False
    # Always masked — the real password never leaves the server.
    password: str = ""
    main_url: str = ""
    sub_url: str = ""
    status: str = "unknown"
    message: str = ""
    available: bool = False


class CameraConfigListResponse(BaseModel):
    cameras: list[CameraConfigEntry] = Field(default_factory=list)
    config_path: str
    config_exists: bool
    message: str = ""


class CameraConfigTestRequest(BaseModel):
    host: str
    port: int = 554
    username: str = "admin"
    password: str = ""
    # Optional: skip path detection and test this exact path.
    main_path: str | None = None
    # Supplied when editing an existing camera, so a masked password resolves.
    slug: str | None = None


class CameraConfigTestResponse(BaseModel):
    success: bool
    outcome: str
    message: str
    main_path: str | None = None
    sub_path: str | None = None
    detected_family: str | None = None


class CameraConfigSaveRequest(BaseModel):
    slug: str = ""
    label: str = ""
    host: str
    port: int = 554
    username: str = "admin"
    password: str = ""
    main_path: str | None = None
    sub_path: str | None = None
    # Refuse to save credentials the camera rejects, unless explicitly told to.
    verify: bool = True


class CameraConfigSaveResponse(BaseModel):
    slug: str
    device_id: str
    saved: bool
    detected_family: str | None = None
    status: str = "unknown"
    message: str = ""


class CameraConfigDeleteResponse(BaseModel):
    slug: str
    deleted: bool
    message: str = ""


class CameraDiagnosticsResponse(BaseModel):
    camera_type: str
    camera_host: str | None = None
    rtsp_port: int | None = None
    main_stream_configured: bool
    sub_stream_configured: bool
    main_stream_openable: bool
    sub_stream_openable: bool
    last_checked_at: str
    message: str
    device_count: int = 0
    available_device_count: int = 0


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
    report_pdf_url: str | None = None
    report_pdf_filename: str | None = None


class DrillReport(BaseModel):
    session_id: str
    cadet_id: str | None = None
    cadet_name: str
    squad: str | None = None
    unit: str | None = None
    drill_type: str
    attempt_number: int
    score: int
    result: str
    ai_result: str | None = None
    instructor_decision: str | None = None
    instructor_remarks: str | None = None
    final_result: str | None = None
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


class InstructorDecisionRequest(BaseModel):
    decision: str
    remarks: str | None = None


class InstructorDecisionResponse(BaseModel):
    session_id: str
    ai_result: str | None = None
    instructor_decision: str
    final_result: str
    remarks: str | None = None
    message: str
