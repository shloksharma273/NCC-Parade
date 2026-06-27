from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from ..utils.time_utils import utc_now_iso
from .camera_service import camera_service


class RecordingService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop_task: asyncio.Task | None = None
        self._running = False

    async def start(self, session_id: str, camera_id: int) -> Path:
        with self._lock:
            if camera_service.active_session_id is not None:
                raise RuntimeError("RECORDING_ALREADY_ACTIVE")
            output_path = camera_service.start_recording(session_id, camera_id)
            self._running = True

        self._loop_task = asyncio.create_task(self._capture_loop())
        return output_path

    async def _capture_loop(self) -> None:
        while self._running:
            ok = await asyncio.to_thread(camera_service.write_frame)
            if not ok:
                await asyncio.sleep(0.01)
                continue
            await asyncio.sleep(1 / 30)

    async def stop(self) -> Path:
        self._running = False
        if self._loop_task is not None:
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

        with self._lock:
            return camera_service.stop_recording()


recording_service = RecordingService()
