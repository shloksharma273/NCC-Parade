from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from ..models.api_models import CameraDiagnosticsResponse
from ..video_pipeline.camera_service import camera_service

router = APIRouter(tags=["camera"])


@router.get("/camera/diagnostics", response_model=CameraDiagnosticsResponse)
def camera_diagnostics() -> CameraDiagnosticsResponse:
    return CameraDiagnosticsResponse(**camera_service.get_diagnostics())


@router.get("/camera/devices")
def camera_devices(force: bool = False) -> dict:
    """List selectable cameras with a still thumbnail for each (for the picker grid).
    USB: probed indices; IP: configured RTSP streams. Cached — see CameraService TTL."""
    return {
        "camera_type": camera_service.get_diagnostics()["camera_type"],
        "devices": camera_service.enumerate_devices(force=force),
    }


@router.post("/camera/warmup")
def camera_warmup() -> dict:
    """Prime the camera subsystem early (called from the first page) so the slow cold-start
    happens up front rather than when the user hits Record. Returns the device list."""
    return camera_service.warm_up()


@router.get("/camera/snapshot")
def camera_snapshot() -> Response:
    frame = camera_service.get_latest_jpeg()
    if frame is None:
        frame = camera_service.capture_snapshot()
    if frame is None:
        detail = {
            "error": "SNAPSHOT_UNAVAILABLE",
            "message": (
                "Unable to fetch camera preview. Check LAN cable, PoE switch, and camera IP."
                if camera_service.get_diagnostics()["camera_type"] == "ip"
                else "Camera snapshot is not available."
            ),
        }
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
    return Response(content=frame, media_type="image/jpeg")
