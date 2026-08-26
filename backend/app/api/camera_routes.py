from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse

from ..models.api_models import (
    ActionResponse,
    CameraDeviceListResponse,
    CameraDeviceResponse,
    CameraWarmupResponse,
)
from ..video_pipeline.camera_registry import camera_registry
from ..video_pipeline.camera_service import camera_service, resolve_device_id
from ..video_pipeline.device_pool import device_pool
from ..video_pipeline.preview_service import preview_service
from ..services.session_service import session_service

router = APIRouter(tags=["camera"])


def _device_payload() -> list[CameraDeviceResponse]:
    devices = camera_registry.discover()
    payload = []
    for device in devices:
        preview_state, preview_error = device_pool.describe(device.device_id)
        payload.append(
            CameraDeviceResponse(
                **device.to_dict(),
                warm=device_pool.is_warm(device.device_id),
                preview_state=preview_state,
                preview_error=preview_error,
            )
        )
    return payload


def _list_response() -> CameraDeviceListResponse:
    devices = _device_payload()
    available = [d for d in devices if d.available]
    return CameraDeviceListResponse(
        devices=devices,
        default_device_id=available[0].device_id if available else None,
        available_count=len(available),
        message=(
            f"{len(available)} of {len(devices)} camera(s) available."
            if devices
            else "No cameras were detected on this machine."
        ),
    )


# ---------------------------------------------------------------- device listing


@router.get("/camera/devices", response_model=CameraDeviceListResponse)
async def list_camera_devices(
    refresh: bool = Query(False, description="Force a fresh hardware scan."),
) -> CameraDeviceListResponse:
    if refresh:
        camera_registry.invalidate()
    # Discovery opens USB devices, so keep it off the event loop.
    return await asyncio.to_thread(_list_response)


@router.post("/camera/devices/refresh", response_model=CameraDeviceListResponse)
async def refresh_camera_devices() -> CameraDeviceListResponse:
    camera_registry.invalidate()
    return await asyncio.to_thread(_list_response)


# -------------------------------------------------------------------- warm-up


@router.post("/camera/warmup", response_model=CameraWarmupResponse)
async def warmup_cameras() -> CameraWarmupResponse:
    """Open every reachable camera ahead of time.

    Called from the landing page so the chooser screen has frames ready. Warming
    never blocks on a camera — each device opens on its own thread — and any
    camera nobody asks about is closed again by the idle reaper.
    """
    if camera_service.active_session_id is not None:
        return CameraWarmupResponse(
            warmed=[],
            skipped=True,
            message="A recording is in progress, so previews were not started.",
        )

    device_ids = await asyncio.to_thread(camera_service.warm_all_available)
    return CameraWarmupResponse(
        warmed=device_ids,
        skipped=False,
        message=(
            f"Warming {len(device_ids)} camera(s)."
            if device_ids
            else "No reachable cameras to warm up."
        ),
    )


@router.post("/camera/preview/stop-all", response_model=CameraWarmupResponse)
async def stop_all_previews() -> CameraWarmupResponse:
    if camera_service.active_session_id is not None:
        return CameraWarmupResponse(
            warmed=[],
            skipped=True,
            message="Recording is active; previews were left untouched.",
        )
    await preview_service.stop_all()
    return CameraWarmupResponse(warmed=[], skipped=False, message="All previews stopped.")


# ----------------------------------------------------------- per-device frames


def _require_device(device_id: str) -> str:
    resolved = resolve_device_id(device_id)
    device = camera_registry.get(resolved)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "DEVICE_NOT_FOUND",
                "message": f"Camera '{device_id}' was not found on this machine.",
            },
        )
    if not device.available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "CAMERA_UNAVAILABLE", "message": device.message},
        )
    return resolved


@router.get("/camera/devices/{device_id}/snapshot")
async def device_snapshot(device_id: str) -> Response:
    """One still frame from a device.

    The camera-chooser grid polls this once a second per tile rather than opening
    an MJPEG stream each: browsers cap concurrent connections per host, and a
    grid of never-ending streams would starve the page's other requests.
    """
    resolved = _require_device(device_id)
    frame = camera_service.get_device_jpeg(resolved)
    if frame is None:
        # First poll after a cold start: the reader thread is still opening.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": device_pool.error_for(resolved) or "PREVIEW_WARMING_UP",
                "message": "Camera preview is still starting. Retry shortly.",
            },
        )
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.get("/camera/devices/{device_id}/stream")
async def device_stream(device_id: str) -> StreamingResponse:
    resolved = _require_device(device_id)
    return StreamingResponse(
        camera_service.iter_device_mjpeg(resolved),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/camera/devices/{device_id}/preview/start", response_model=CameraWarmupResponse)
async def start_device_preview(device_id: str) -> CameraWarmupResponse:
    resolved = _require_device(device_id)
    try:
        await preview_service.start(device_id=resolved)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": str(exc).split(":")[0], "message": "Could not start camera preview."},
        ) from exc
    return CameraWarmupResponse(warmed=[resolved], skipped=False, message="Preview started.")


@router.post("/camera/devices/{device_id}/preview/stop", response_model=CameraWarmupResponse)
async def stop_device_preview(device_id: str) -> CameraWarmupResponse:
    resolved = resolve_device_id(device_id)
    await preview_service.stop(resolved)
    return CameraWarmupResponse(warmed=[], skipped=False, message="Preview stopped.")


# --------------------------------------------------------- session-scoped views


def _session_device_id(session_id: str) -> str:
    session = session_service.get_session(session_id)
    return resolve_device_id(session["camera_id"])


@router.post("/sessions/{session_id}/camera/preview/start", response_model=ActionResponse)
async def start_camera_preview(session_id: str) -> ActionResponse:
    device_id = _session_device_id(session_id)

    if camera_service.active_session_id and camera_service.active_session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "RECORDING_ALREADY_ACTIVE",
                "message": "Camera is in use by another session.",
            },
        )

    connection = camera_service.check_device_connection(device_id)
    if not connection["camera_connected"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": connection.get("error", "CAMERA_NOT_FOUND"),
                "message": connection.get("message", "Camera is not available."),
            },
        )

    try:
        await preview_service.start(device_id=device_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": str(exc).split(":")[0], "message": "Could not start camera preview."},
        ) from exc

    return ActionResponse(
        session_id=session_id,
        status="preview",
        message=f"Camera preview started ({device_id}).",
    )


@router.post("/sessions/{session_id}/camera/preview/stop", response_model=ActionResponse)
async def stop_camera_preview(session_id: str) -> ActionResponse:
    device_id = _session_device_id(session_id)

    if camera_service.active_session_id == session_id:
        return ActionResponse(
            session_id=session_id,
            status="recording",
            message="Preview left running for active recording.",
        )

    await preview_service.stop(device_id)

    return ActionResponse(
        session_id=session_id,
        status="ready",
        message="Camera preview stopped.",
    )


@router.get("/sessions/{session_id}/camera/stream")
async def camera_stream(session_id: str) -> StreamingResponse:
    device_id = _session_device_id(session_id)

    if camera_service.active_session_id and camera_service.active_session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "RECORDING_ALREADY_ACTIVE",
                "message": "Camera stream belongs to another active session.",
            },
        )

    if camera_service.active_session_id != session_id and not device_pool.is_warm(device_id):
        # Cold start is fine — warm it and let the stream begin as frames arrive.
        await preview_service.start(device_id=device_id)

    return StreamingResponse(
        camera_service.iter_device_mjpeg(device_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
