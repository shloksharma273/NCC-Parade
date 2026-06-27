from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from ..models.api_models import ActionResponse, ProgressResponse
from ..models.session_models import SessionStatus
from ..services.camera_service import camera_service
from ..services.processing_service import processing_service
from ..services.recording_service import recording_service
from ..services.session_service import session_service
from ..services.websocket_manager import ws_manager
from ..utils.time_utils import utc_now_iso

router = APIRouter(prefix="/sessions", tags=["recording"])


@router.post("/{session_id}/recording/start", response_model=ActionResponse)
async def start_recording(session_id: str) -> ActionResponse:
    session = session_service.get_session(session_id)
    current = SessionStatus(session["status"])

    if current in {SessionStatus.RECORDING, SessionStatus.SAVING, SessionStatus.PROCESSING}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "INVALID_SESSION_STATE",
                "message": f"Cannot start recording because the session is already {current.value.lower()}.",
            },
        )

    if camera_service.active_session_id and camera_service.active_session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "RECORDING_ALREADY_ACTIVE",
                "message": "Another recording is already in progress.",
            },
        )

    camera_id = int(session["camera_id"])
    if not camera_service.check_camera(camera_id):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "CAMERA_NOT_FOUND",
                "message": "No camera was detected. Please check camera connection.",
            },
        )

    if current == SessionStatus.CREATED:
        session_service.transition(session_id, SessionStatus.READY)

    try:
        await recording_service.start(session_id, camera_id)
    except RuntimeError as exc:
        code = str(exc)
        if code == "RECORDING_ALREADY_ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": code, "message": "Another recording is already in progress."},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "CAMERA_NOT_FOUND", "message": "Could not start camera recording."},
        ) from exc

    session_service.transition(session_id, SessionStatus.RECORDING, started_at=utc_now_iso())
    await ws_manager.broadcast(
        session_id,
        {
            "type": "status_update",
            "session_id": session_id,
            "status": SessionStatus.RECORDING.value,
            "message": "Recording in progress.",
            "timestamp": utc_now_iso(),
        },
    )

    return ActionResponse(
        session_id=session_id,
        status=SessionStatus.RECORDING.value,
        message="Recording started.",
    )


@router.post("/{session_id}/recording/stop", response_model=ActionResponse)
async def stop_recording(session_id: str, background_tasks: BackgroundTasks) -> ActionResponse:
    session = session_service.get_session(session_id)
    current = SessionStatus(session["status"])

    if current != SessionStatus.RECORDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "INVALID_SESSION_STATE",
                "message": "Cannot stop recording because recording has not started.",
            },
        )

    session_service.transition(session_id, SessionStatus.SAVING)
    await ws_manager.broadcast(
        session_id,
        {
            "type": "status_update",
            "session_id": session_id,
            "status": SessionStatus.SAVING.value,
            "message": "Saving recorded video.",
            "timestamp": utc_now_iso(),
        },
    )

    try:
        video_path = await recording_service.stop()
    except RuntimeError as exc:
        session_service.mark_failed(session_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "PROCESSING_FAILED", "message": str(exc)},
        ) from exc

    session_service.transition(
        session_id,
        SessionStatus.PROCESSING,
        stopped_at=utc_now_iso(),
        video_path=str(video_path),
    )
    processing_service._record_progress(
        session_id,
        SessionStatus.PROCESSING.value,
        "video_saved",
        10,
        "Video saved successfully.",
    )

    background_tasks.add_task(processing_service.run_analysis, session_id, str(video_path))

    await ws_manager.broadcast(
        session_id,
        {
            "type": "status_update",
            "session_id": session_id,
            "status": SessionStatus.PROCESSING.value,
            "message": "Recording stopped. Processing started.",
            "timestamp": utc_now_iso(),
        },
    )

    return ActionResponse(
        session_id=session_id,
        status=SessionStatus.PROCESSING.value,
        message="Recording stopped. Processing started.",
    )


@router.get("/{session_id}/progress", response_model=ProgressResponse)
def get_progress(session_id: str) -> ProgressResponse:
    session_service.get_session(session_id)
    progress = processing_service.get_progress(session_id)
    return ProgressResponse(**progress)
