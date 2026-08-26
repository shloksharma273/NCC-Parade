"""Preview lifecycle.

Frame reading now happens on the pool's own per-device threads, so this layer is
a thin async-friendly facade over :mod:`device_pool` rather than a capture loop
of its own.
"""

from __future__ import annotations

from .camera_service import camera_service, resolve_device_id
from .device_pool import device_pool


class PreviewService:
    async def start(self, camera_id: int | str | None = None, device_id: str | None = None) -> str:
        """Warm one device for preview. Returns the resolved device id."""
        target = device_id if device_id is not None else camera_id
        camera_service.start_preview(target)
        return resolve_device_id(target)

    async def start_all(self) -> list[str]:
        """Warm every reachable camera — used to prefetch from the landing page."""
        return camera_service.warm_all_available()

    async def stop(self, device_id: str | None = None) -> None:
        camera_service.stop_preview(device_id)

    async def stop_all(self) -> None:
        device_pool.release_all()

    async def stop_loop(self) -> None:
        """Kept for backward compatibility with earlier callers."""
        await self.stop_all()


preview_service = PreviewService()
