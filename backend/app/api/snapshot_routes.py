from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from ..config import FRAMES_MEDIA_DIR
from ..services.camera_service import camera_service

router = APIRouter(tags=["camera"])


@router.get("/camera/snapshot")
def camera_snapshot() -> Response:
    frame = camera_service.get_latest_jpeg()
    if frame is None:
        frame = camera_service.capture_snapshot()
    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "SNAPSHOT_UNAVAILABLE", "message": "Camera snapshot is not available."},
        )
    return Response(content=frame, media_type="image/jpeg")
