from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from ..config import settings
from ..models.api_models import ActionResponse
from ..video_pipeline.camera_service import camera_service
from ..video_pipeline.preview_service import preview_service
from ..services.session_service import session_service

router = APIRouter(tags=["camera"])


def _parse_usb_index(camera_id: str) -> int | None:
    return int(camera_id) if camera_id.isdigit() else None


@router.post("/sessions/{session_id}/camera/preview/start", response_model=ActionResponse)
async def start_camera_preview(session_id: str) -> ActionResponse:
    session = session_service.get_session(session_id)
    usb_index = _parse_usb_index(session["camera_id"])

    if camera_service.active_session_id and camera_service.active_session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "RECORDING_ALREADY_ACTIVE",
                "message": "Camera is in use by another session.",
            },
        )

    connection = camera_service.check_camera_connection(usb_index=usb_index)
    if not connection["camera_connected"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": connection.get("error", "CAMERA_NOT_FOUND"),
                "message": connection.get("message", "Camera is not available."),
            },
        )

    try:
        await preview_service.start(usb_index)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": str(exc).split(":")[0], "message": "Could not start camera preview."},
        ) from exc

    stream_label = "sub" if settings.is_ip_camera() and settings.preview_use_substream else "main"
    return ActionResponse(
        session_id=session_id,
        status="preview",
        message=f"Camera preview started ({stream_label} stream).",
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
