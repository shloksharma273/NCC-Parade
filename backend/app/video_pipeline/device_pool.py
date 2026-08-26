"""A pool of cameras held open simultaneously for preview.

The original pipeline could only hold one capture at a time, which is fine once
a camera has been chosen but makes a "pick your camera" screen impossible. This
pool keeps several devices open at once, each with its own reader thread that
retains only the most recent frame as a JPEG.

Two deliberate choices:

* **Previews open at low resolution.** Several USB cameras sharing one
  controller can genuinely run out of bandwidth at full resolution. The chooser
  only needs to answer "where is this camera pointing", so it opens small.
* **Idle cameras are closed automatically.** A tablet left on the chooser screen
  (or abandoned mid-flow) would otherwise hold every camera open forever, so an
  entry nobody has asked about for ``PREVIEW_IDLE_TIMEOUT_SECONDS`` is released.

Opening is always done on the entry's own thread — an unreachable RTSP stream
can block the FFmpeg backend for many seconds, and that must never stall an HTTP
request.
"""

from __future__ import annotations

import os
import platform
import threading
import time
from dataclasses import dataclass
from typing import Literal

# pyrefly: ignore [missing-import]
import cv2

from ..config import parse_device_id, settings

_USB_BACKEND = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY

# Prefer TCP for LAN RTSP and cap the connect/read wait, so a dead camera fails
# in seconds instead of hanging a reader thread indefinitely.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;5000000",
)

EntryState = Literal["opening", "streaming", "failed"]

_REAPER_INTERVAL_SECONDS = 5.0

# How long to leave a failed camera alone before trying to open it again.
_FAILED_RETRY_SECONDS = 15.0


@dataclass
class PoolStatus:
    device_id: str
    state: EntryState
    has_frame: bool
    error: str | None
    idle_seconds: float


class _PoolEntry:
    """One camera held open, with a thread reading frames into a JPEG slot."""

    def __init__(self, device_id: str, stream_type: str) -> None:
        self.device_id = device_id
        self.stream_type = stream_type
        self.state: EntryState = "opening"
        self.error: str | None = None
        self.latest_jpeg: bytes | None = None
        self.last_requested = time.monotonic()
        self.failed_at: float | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name=f"preview-{device_id}",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def touch(self) -> None:
        self.last_requested = time.monotonic()

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_requested

    @property
    def idle_since_failure(self) -> float:
        return 0.0 if self.failed_at is None else time.monotonic() - self.failed_at

    def mark_failed(self, error: str) -> None:
        self.error = error
        self.state = "failed"
        self.failed_at = time.monotonic()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float = 3.0) -> None:
        if self._thread.is_alive():
            self._thread.join(timeout=timeout)

    # ------------------------------------------------------------------ thread

    def _open(self) -> "cv2.VideoCapture | None":
        try:
            source = settings.resolve_device_source(self.device_id, self.stream_type)
        except ValueError as exc:
            self.error = str(exc)
            return None

        if isinstance(source, str):
            cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        else:
            cap = cv2.VideoCapture(int(source), _USB_BACKEND)

        if not cap.isOpened():
            cap.release()
            kind, _ = parse_device_id(self.device_id)
            self.error = "IP_CAMERA_NOT_REACHABLE" if kind == "ip" else "CAMERA_NOT_FOUND"
            return None

        if not isinstance(source, str):
            # Only meaningful for USB; RTSP resolution is fixed by the camera.
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.preview_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.preview_height)
        return cap

    def _run(self) -> None:
        cap = self._open()
        if cap is None:
            self.mark_failed(self.error or "PREVIEW_OPEN_FAILED")
            return

        self.state = "streaming"
        interval = 1.0 / max(settings.preview_fps, 1)
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), settings.preview_jpeg_quality]
        failures = 0

        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= settings.max_frame_read_failures:
                        self.mark_failed("PREVIEW_STREAM_FAILED")
                        break
                    time.sleep(0.05)
                    continue

                failures = 0
                ok, encoded = cv2.imencode(".jpg", frame, encode_params)
                if ok:
                    self.latest_jpeg = encoded.tobytes()
                time.sleep(interval)
        finally:
            cap.release()


class DevicePool:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, _PoolEntry] = {}
        self._reaper: threading.Thread | None = None
        self._reaper_stop = threading.Event()
        self._suspended = False
        self._exclusive_device_id: str | None = None

    # -------------------------------------------------------------------- warm

    def _preferred_stream(self, device_id: str) -> str:
        kind, _ = parse_device_id(device_id)
        if kind == "ip" and settings.preview_use_substream:
            return "sub"
        return "main"

    def warm(self, device_id: str) -> None:
        """Ensure *device_id* is open and being read. Never blocks on the camera."""
        with self._lock:
            if self._suspended:
                return
            entry = self._entries.get(device_id)
            if entry is not None:
                entry.touch()
                if entry.state != "failed":
                    return
                # A failed camera is retried, but not on every poll — a wrong
                # RTSP URL or bad credentials would otherwise be re-attempted
                # once a second forever.
                if entry.idle_since_failure < _FAILED_RETRY_SECONDS:
                    return
                entry.stop()
                del self._entries[device_id]

            entry = _PoolEntry(device_id, self._preferred_stream(device_id))
            self._entries[device_id] = entry
            entry.start()
            self._ensure_reaper()

    def warm_many(self, device_ids: list[str]) -> None:
        for device_id in device_ids:
            self.warm(device_id)

    # ------------------------------------------------------------------ frames

    def latest_jpeg(self, device_id: str, warm_if_cold: bool = True) -> bytes | None:
        with self._lock:
            entry = self._entries.get(device_id)
        if entry is None:
            if warm_if_cold:
                self.warm(device_id)
            return None
        entry.touch()
        return entry.latest_jpeg

    def iter_mjpeg(self, device_id: str):
        """Yield a multipart JPEG stream for one device.

        Used for the single full-size preview; the chooser grid polls snapshots
        instead, because browsers cap concurrent connections per host and a grid
        of never-ending MJPEG streams would starve the page's other requests.
        """
        boundary = b"frame"
        interval = 1.0 / max(settings.preview_fps, 1)
        while True:
            with self._lock:
                entry = self._entries.get(device_id)
            if entry is None or entry.state == "failed":
                break
            entry.touch()
            frame = entry.latest_jpeg
            if frame is not None:
                yield (
                    b"--"
                    + boundary
                    + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(frame)).encode()
                    + b"\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
            time.sleep(interval)

    # ----------------------------------------------------------------- release

    def release(self, device_id: str) -> None:
        with self._lock:
            entry = self._entries.pop(device_id, None)
        if entry is not None:
            entry.stop()
            entry.join()

    def release_all(self, except_id: str | None = None) -> None:
        with self._lock:
            entries = [e for did, e in self._entries.items() if did != except_id]
            self._entries = (
                {except_id: self._entries[except_id]}
                if except_id and except_id in self._entries
                else {}
            )
        for entry in entries:
            entry.stop()
        for entry in entries:
            entry.join()

    def suspend(self, exclusive_device_id: str | None = None) -> None:
        """Close every preview and refuse new ones — used while recording.

        *exclusive_device_id* marks a device as solely owned by the recorder, so
        discovery skips probing it and cannot disturb the take in progress.
        """
        with self._lock:
            self._suspended = True
            self._exclusive_device_id = exclusive_device_id
        self.release_all()

    def resume(self) -> None:
        with self._lock:
            self._suspended = False
            self._exclusive_device_id = None

    @property
    def exclusive_device_id(self) -> str | None:
        with self._lock:
            return self._exclusive_device_id

    # ------------------------------------------------------------------ status

    def is_warm(self, device_id: str) -> bool:
        with self._lock:
            entry = self._entries.get(device_id)
        return entry is not None and entry.state == "streaming"

    def status(self) -> list[PoolStatus]:
        with self._lock:
            entries = list(self._entries.values())
        return [
            PoolStatus(
                device_id=entry.device_id,
                state=entry.state,
                has_frame=entry.latest_jpeg is not None,
                error=entry.error,
                idle_seconds=round(entry.idle_seconds, 1),
            )
            for entry in entries
        ]

    def error_for(self, device_id: str) -> str | None:
        with self._lock:
            entry = self._entries.get(device_id)
        return entry.error if entry else None

    def describe(self, device_id: str) -> tuple[str | None, str | None]:
        """Return (preview_state, preview_error) for one device."""
        with self._lock:
            entry = self._entries.get(device_id)
        if entry is None:
            return None, None
        return entry.state, entry.error

    # ------------------------------------------------------------------ reaper

    def _ensure_reaper(self) -> None:
        # Callers already hold the re-entrant lock, so the liveness check and the
        # start cannot interleave with a reaper retiring itself.
        with self._lock:
            if self._reaper is not None and self._reaper.is_alive():
                return
            self._reaper_stop.clear()
            self._reaper = threading.Thread(
                target=self._reap_loop, name="preview-reaper", daemon=True
            )
            self._reaper.start()

    def _reap_loop(self) -> None:
        while not self._reaper_stop.wait(_REAPER_INTERVAL_SECONDS):
            try:
                timeout = settings.preview_idle_timeout_seconds
                with self._lock:
                    stale = [
                        device_id
                        for device_id, entry in self._entries.items()
                        if entry.idle_seconds > timeout
                    ]
                    reaped = [self._entries.pop(device_id) for device_id in stale]
                    empty = not self._entries
                    if empty:
                        # Retire while holding the lock so _ensure_reaper cannot
                        # observe a half-cleared reaper and start a second one.
                        self._reaper_stop.set()
                        self._reaper = None
                for entry in reaped:
                    entry.stop()
                if empty:
                    return
            except Exception:
                # A dead reaper would leak every open camera, so never let one
                # unexpected error end the loop.
                continue

    def shutdown(self) -> None:
        self._reaper_stop.set()
        self.release_all()


device_pool = DevicePool()
