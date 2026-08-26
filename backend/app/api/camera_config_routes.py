from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, status

from ..models.api_models import (
    CameraConfigListResponse,
    CameraConfigSaveRequest,
    CameraConfigSaveResponse,
    CameraConfigTestRequest,
    CameraConfigTestResponse,
    CameraConfigDeleteResponse,
)
from ..services.camera_config_service import CameraConfigError, camera_config_service

router = APIRouter(prefix="/camera/config", tags=["camera-config"])


def _fail(exc: CameraConfigError) -> HTTPException:
    unreachable = exc.code in {"NO_RESPONSE", "HOST_REQUIRED"}
    return HTTPException(
        status_code=(
            status.HTTP_503_SERVICE_UNAVAILABLE if unreachable else status.HTTP_400_BAD_REQUEST
        ),
        detail={"error": exc.code, "message": exc.message},
    )


@router.get("", response_model=CameraConfigListResponse)
async def list_camera_config() -> CameraConfigListResponse:
    data = await asyncio.to_thread(camera_config_service.list_cameras)
    return CameraConfigListResponse(**data)


@router.post("/test", response_model=CameraConfigTestResponse)
async def test_camera_config(request: CameraConfigTestRequest) -> CameraConfigTestResponse:
    """Check credentials without saving, and detect the camera's stream paths."""
    try:
        data = await asyncio.to_thread(
            camera_config_service.test_camera,
            request.host,
            request.port,
            request.username,
            request.password,
            request.main_path,
            request.slug,
        )
    except CameraConfigError as exc:
        raise _fail(exc) from exc
    return CameraConfigTestResponse(**data)


@router.put("", response_model=CameraConfigSaveResponse)
async def save_camera_config(request: CameraConfigSaveRequest) -> CameraConfigSaveResponse:
    try:
        data = await asyncio.to_thread(
            camera_config_service.save_camera,
            request.slug,
            request.label,
            request.host,
            request.port,
            request.username,
            request.password,
            request.main_path,
            request.sub_path,
            request.verify,
        )
    except CameraConfigError as exc:
        raise _fail(exc) from exc
    return CameraConfigSaveResponse(**data)


@router.delete("/{slug}", response_model=CameraConfigDeleteResponse)
async def delete_camera_config(slug: str) -> CameraConfigDeleteResponse:
    try:
        data = await asyncio.to_thread(camera_config_service.delete_camera, slug)
    except CameraConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    return CameraConfigDeleteResponse(**data)
