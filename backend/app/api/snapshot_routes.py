from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from ..models.api_models import CameraDiagnosticsResponse
from ..services.camera_service import camera_service

router = APIRouter(tags=["camera"])


@router.get("/camera/diagnostics", response_model=CameraDiagnosticsResponse)
def camera_diagnostics() -> CameraDiagnosticsResponse:
    return CameraDiagnosticsResponse(**camera_service.get_diagnostics())


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
