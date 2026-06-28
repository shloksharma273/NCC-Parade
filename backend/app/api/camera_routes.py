from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from ..models.api_models import ActionResponse
from ..services.camera_service import camera_service
from ..services.preview_service import preview_service
from ..services.session_service import session_service

router = APIRouter(tags=["camera"])


@router.post("/sessions/{session_id}/camera/preview/start", response_model=ActionResponse)
async def start_camera_preview(session_id: str) -> ActionResponse:
    session = session_service.get_session(session_id)
    camera_id = int(session["camera_id"])

    if camera_service.active_session_id and camera_service.active_session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "RECORDING_ALREADY_ACTIVE",
                "message": "Camera is in use by another session.",
            },
        )

    if not camera_service.check_camera(camera_id):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "CAMERA_NOT_FOUND",
                "message": "No camera was detected. Please check camera connection.",
            },
        )

    try:
        await preview_service.start(camera_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": str(exc), "message": "Could not start camera preview."},
        ) from exc

    return ActionResponse(
        session_id=session_id,
        status="preview",
        message="Camera preview started.",
    )


@router.post("/sessions/{session_id}/camera/preview/stop", response_model=ActionResponse)
async def stop_camera_preview(session_id: str) -> ActionResponse:
    session_service.get_session(session_id)

    if camera_service.active_session_id == session_id:
        return ActionResponse(
            session_id=session_id,
            status="recording",
            message="Preview left running for active recording.",
        )

    await preview_service.stop()

    return ActionResponse(
        session_id=session_id,
        status="ready",
        message="Camera preview stopped.",
    )


@router.get("/sessions/{session_id}/camera/stream")
async def camera_stream(session_id: str) -> StreamingResponse:
    session_service.get_session(session_id)

    if camera_service.active_session_id and camera_service.active_session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "RECORDING_ALREADY_ACTIVE",
                "message": "Camera stream belongs to another active session.",
            },
        )

    if not camera_service.stream_available:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "STREAM_NOT_AVAILABLE",
                "message": "Camera preview is not active for this session.",
            },
        )

    return StreamingResponse(
        camera_service.iter_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
