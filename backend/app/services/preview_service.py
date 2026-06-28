from __future__ import annotations

import asyncio
import threading

from .camera_service import camera_service


class PreviewService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop_task: asyncio.Task | None = None
        self._running = False

    async def start(self, camera_id: int) -> None:
        with self._lock:
            if self._running:
                return
            camera_service.start_preview(camera_id)
            self._running = True

        self._loop_task = asyncio.create_task(self._capture_loop())

    async def _capture_loop(self) -> None:
        while self._running:
            ok = await asyncio.to_thread(camera_service.read_frame)
            if not ok:
                await asyncio.sleep(0.05)
                continue
            await asyncio.sleep(1 / 15)

    async def stop_loop(self) -> None:
        self._running = False
        if self._loop_task is not None:
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

    async def stop(self) -> None:
        await self.stop_loop()
        with self._lock:
            camera_service.stop_preview()


preview_service = PreviewService()
