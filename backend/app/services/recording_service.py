from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from ..config import settings
from .camera_service import camera_service


class RecordingService:
    MAX_LOOP_FAILURES = camera_service.MAX_FRAME_READ_FAILURES

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop_task: asyncio.Task | None = None
        self._running = False
        self._stream_failed = False

    @property
    def stream_failed(self) -> bool:
        return self._stream_failed

    async def start(self, session_id: str, camera_id: int | None = None) -> Path:
        with self._lock:
            if camera_service.active_session_id is not None:
                raise RuntimeError("RECORDING_ALREADY_ACTIVE")
            output_path = camera_service.start_recording(session_id, camera_id)
            self._running = True
            self._stream_failed = False

        self._loop_task = asyncio.create_task(self._capture_loop())
        return output_path

    async def _capture_loop(self) -> None:
        consecutive_failures = 0
        fps = max(settings.camera_fps, 1)
        while self._running:
            ok = await asyncio.to_thread(camera_service.write_frame)
            if not ok:
                consecutive_failures += 1
                if camera_service.recording_stream_failed or consecutive_failures >= self.MAX_LOOP_FAILURES:
                    self._stream_failed = True
                    self._running = False
                    break
                await asyncio.sleep(0.05)
                continue
            consecutive_failures = 0
            await asyncio.sleep(1 / fps)

    async def stop(self) -> Path:
        self._running = False
        if self._loop_task is not None:
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

        with self._lock:
            try:
                return camera_service.stop_recording()
            except RuntimeError as exc:
                if self._stream_failed:
                    raise RuntimeError(
                        "RECORDING_STREAM_FAILED: Recording stopped because the camera stream was interrupted."
                    ) from exc
                raise


recording_service = RecordingService()
