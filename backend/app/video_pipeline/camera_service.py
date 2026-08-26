from __future__ import annotations

import os
import platform
import threading
import time
from pathlib import Path
from typing import Literal

# pyrefly: ignore [missing-import]
import cv2

# On Windows, DirectShow (CAP_DSHOW) opens USB cameras faster than the default
# MSMF backend, which enumerates all devices and can block for 15-20 s.
_USB_BACKEND = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY

from ..config import (
    RAW_MEDIA_DIR,
    SNAPSHOTS_MEDIA_DIR,
    make_device_id,
    parse_device_id,
    settings,
)
from .camera_registry import camera_registry
from .device_pool import device_pool

StreamType = Literal["main", "sub"]

# Prefer TCP transport for LAN RTSP streams (OpenCV FFmpeg backend) and bound
# the connect wait so an absent camera fails instead of hanging.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;5000000")


def resolve_device_id(raw: str | int | None) -> str:
    """Normalise anything a caller might hand us into a device id.

    Accepts a device id (``usb:1``, ``ip:front``), a bare USB index as int or
    string (``0`` — how sessions stored the camera before device ids existed),
    or ``None`` for the configured default.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return settings.default_device_id()
    kind, key = parse_device_id(str(raw))
    return make_device_id(kind, key)


class CameraService:
    """Owns the recording capture; preview lives in :mod:`device_pool`.

    Recording deliberately does *not* share a handle with preview: when a take
    starts, every preview is closed and the chosen camera is reopened at full
    resolution so nothing competes with the footage being analysed.
    """

    MAX_FRAME_READ_FAILURES = settings.max_frame_read_failures

    def __init__(self) -> None:
        self._capture: cv2.VideoCapture | None = None
        self._video_writer: cv2.VideoWriter | None = None
        self._active_session_id: str | None = None
        self._active_device_id: str | None = None
        self._preview_device_id: str | None = None
        self._output_path: Path | None = None
        self._latest_jpeg: bytes | None = None
        self._frames_written = 0
        self._consecutive_read_failures = 0
        self._open_stream_type: StreamType | None = None
        self._last_error: str | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ sources

    def get_camera_source(self, stream_type: StreamType = "main", usb_index: int | None = None) -> str | int:
        return settings.get_camera_source(stream_type, usb_index=usb_index)

    def _open_device_capture(self, device_id: str, stream_type: StreamType = "main") -> cv2.VideoCapture:
        """Open one device for recording, at full configured resolution."""
        try:
            source = settings.resolve_device_source(device_id, stream_type)
        except ValueError as exc:
            code = str(exc)
            if code == "RTSP_URL_MISSING":
                raise RuntimeError(
                    "RTSP_URL_MISSING: This IP camera has no RTSP URL configured."
                ) from exc
            raise RuntimeError(f"{code}: Camera '{device_id}' is not configured.") from exc

        kind, _ = parse_device_id(device_id)

        if isinstance(source, str):
            cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        else:
            cap = cv2.VideoCapture(int(source), _USB_BACKEND)

        if not cap.isOpened():
            cap.release()
            if kind == "ip":
                raise RuntimeError(
                    "IP_CAMERA_NOT_REACHABLE: Unable to reach IP camera. "
                    "Check camera power, PoE switch, LAN cable, and IP address."
                )
            raise RuntimeError("CAMERA_NOT_FOUND")

        if kind == "usb":
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.camera_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.camera_height)
            cap.set(cv2.CAP_PROP_FPS, settings.camera_fps)

        self._open_stream_type = stream_type
        return cap

    def _open_capture(self, stream_type: StreamType = "main", usb_index: int | None = None) -> cv2.VideoCapture:
        """Legacy entry point kept for callers that still think in USB indices."""
        if settings.is_ip_camera() and usb_index is None:
            device_id = settings.default_device_id()
        else:
            device_id = resolve_device_id(usb_index if usb_index is not None else None)
        return self._open_device_capture(device_id, stream_type)

    def _fourcc(self) -> int:
        for codec in ("avc1", "mp4v", "XVID"):
            fourcc = cv2.VideoWriter_fourcc(*codec)
            test_path = RAW_MEDIA_DIR / "_codec_test.mp4"
            writer = cv2.VideoWriter(str(test_path), fourcc, settings.camera_fps, (640, 480))
            if writer.isOpened():
                writer.release()
                if test_path.exists():
                    test_path.unlink()
                return fourcc
        return cv2.VideoWriter_fourcc(*"mp4v")

    def _cache_frame(self, frame) -> None:
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ok:
            self._latest_jpeg = encoded.tobytes()

    def _read_with_retries(self, cap: cv2.VideoCapture, attempts: int = 5) -> tuple[bool, object | None]:
        for _ in range(attempts):
            ok, frame = cap.read()
            if ok and frame is not None:
                return True, frame
            time.sleep(0.05)
        return False, None

    # ------------------------------------------------------------------- checks

    def check_device_connection(self, device_id: str | int | None = None) -> dict:
        """Availability of one device, answered from discovery (never blocks on RTSP)."""
        resolved = resolve_device_id(device_id)

        if self._active_session_id is not None and resolved == self._active_device_id:
            # Being recorded right now: answer from what we already hold rather
            # than reopening the device to ask.
            return {
                "camera_connected": True,
                "device_id": resolved,
                "message": "Camera is recording.",
            }

        if device_pool.is_warm(resolved):
            return {
                "camera_connected": True,
                "device_id": resolved,
                "message": "Camera is reachable.",
            }

        device = camera_registry.get(resolved)
        if device is None:
            return {
                "camera_connected": False,
                "device_id": resolved,
                "error": "DEVICE_NOT_FOUND",
                "message": f"Camera '{resolved}' was not found on this machine.",
            }
        if not device.available:
            error = {
                "unreachable": "IP_CAMERA_NOT_REACHABLE",
                "unconfigured": "RTSP_URL_MISSING",
                "detected": "CAMERA_NOT_CONFIGURED",
            }.get(device.status, "CAMERA_NOT_FOUND")
            return {
                "camera_connected": False,
                "device_id": resolved,
                "error": error,
                "message": device.message,
            }
        return {
            "camera_connected": True,
            "device_id": resolved,
            "message": device.message,
        }

    def check_camera_connection(self, usb_index: int | None = None, device_id: str | None = None) -> dict:
        if device_id is not None:
            return self.check_device_connection(device_id)
        if usb_index is not None:
            return self.check_device_connection(make_device_id("usb", usb_index))
        return self.check_device_connection(None)

    def check_camera(self, camera_id: int | str | None = None) -> bool:
        return self.check_device_connection(camera_id)["camera_connected"]

    def test_stream_openable(self, stream_type: StreamType) -> bool:
        if settings.is_ip_camera():
            url = settings.rtsp_sub_url() if stream_type == "sub" else settings.rtsp_main_url()
            if not url:
                return False

        cap = None
        try:
            cap = self._open_capture(stream_type)
            ok, _ = self._read_with_retries(cap, attempts=3)
            return ok
        except RuntimeError:
            return False
        finally:
            if cap is not None:
                cap.release()

    def get_diagnostics(self) -> dict:
        from ..utils.time_utils import utc_now_iso

        devices = camera_registry.discover()
        usb_devices = [d for d in devices if d.kind == "usb"]
        ip_devices = [d for d in devices if d.kind == "ip"]
        available = [d for d in devices if d.available]

        if settings.is_ip_camera():
            main_configured = bool(settings.rtsp_main_url())
            sub_configured = bool(settings.rtsp_sub_url())
            main_openable = any(d.available for d in ip_devices)
            sub_openable = any(d.available and d.has_sub_stream for d in ip_devices)
        else:
            main_configured = True
            sub_configured = False
            main_openable = any(d.available for d in usb_devices)
            sub_openable = False

        if available:
            message = f"{len(available)} camera(s) reachable: " + ", ".join(d.label for d in available)
        elif ip_devices and not usb_devices:
            message = "No camera reachable. Verify camera IP, credentials, and RTSP URL."
        else:
            message = "No camera could be opened. Check connections."

        return {
            "camera_type": settings.camera_type,
            "camera_host": settings.ip_camera_host if settings.is_ip_camera() else None,
            "rtsp_port": settings.ip_camera_port if settings.is_ip_camera() else None,
            "main_stream_configured": main_configured,
            "sub_stream_configured": sub_configured,
            "main_stream_openable": main_openable,
            "sub_stream_openable": sub_openable,
            "device_count": len(devices),
            "available_device_count": len(available),
            "last_checked_at": utc_now_iso(),
            "message": message,
        }

    # ------------------------------------------------------------------ preview

    def start_preview(self, camera_id: int | str | None = None, device_id: str | None = None) -> None:
        if self._active_session_id is not None:
            raise RuntimeError("RECORDING_ALREADY_ACTIVE")
        resolved = resolve_device_id(device_id if device_id is not None else camera_id)
        device_pool.resume()
        device_pool.warm(resolved)
        self._preview_device_id = resolved
        self._last_error = None

    def stop_preview(self, device_id: str | None = None) -> None:
        if self._active_session_id is not None:
            return
        target = resolve_device_id(device_id) if device_id else self._preview_device_id
        if target is not None:
            device_pool.release(target)
            if target == self._preview_device_id:
                self._preview_device_id = None

    def warm_all_available(self) -> list[str]:
        """Open every reachable camera for preview (used by the landing page).

        Only *available* devices are warmed — an unreachable RTSP stream would
        otherwise tie up a reader thread for nothing.
        """
        device_pool.resume()
        device_ids = camera_registry.available_device_ids()
        device_pool.warm_many(device_ids)
        return device_ids

    def get_device_jpeg(self, device_id: str, warm_if_cold: bool = True) -> bytes | None:
        resolved = resolve_device_id(device_id)
        if self._active_session_id is not None and resolved == self._active_device_id:
            return self._latest_jpeg
        return device_pool.latest_jpeg(resolved, warm_if_cold=warm_if_cold)

    def iter_device_mjpeg(self, device_id: str):
        resolved = resolve_device_id(device_id)
        if self._active_session_id is not None and resolved == self._active_device_id:
            return self.iter_mjpeg()
        device_pool.warm(resolved)
        return device_pool.iter_mjpeg(resolved)

    def iter_mjpeg(self):
        """Multipart JPEG stream of the in-progress recording."""
        boundary = b"frame"
        while self._active_session_id is not None:
            frame = self._latest_jpeg
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
            time.sleep(1 / 15)

    # ---------------------------------------------------------------- recording

    def read_frame(self) -> bool:
        with self._lock:
            if self._capture is None:
                return False
            ok, frame = self._capture.read()
            if not ok or frame is None:
                self._consecutive_read_failures += 1
                if self._consecutive_read_failures >= self.MAX_FRAME_READ_FAILURES:
                    self._last_error = "RECORDING_STREAM_FAILED"
                return False

            self._consecutive_read_failures = 0
            if self._video_writer is not None:
                self._video_writer.write(frame)
                self._frames_written += 1
            self._cache_frame(frame)
            return True

    @property
    def recording_stream_failed(self) -> bool:
        return self._consecutive_read_failures >= self.MAX_FRAME_READ_FAILURES

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def start_recording(self, session_id: str, camera_id: int | str | None = None, device_id: str | None = None) -> Path:
        if self._active_session_id is not None:
            raise RuntimeError("RECORDING_ALREADY_ACTIVE")

        resolved = resolve_device_id(device_id if device_id is not None else camera_id)

        # Recording owns the camera alone: drop every preview first so nothing
        # competes for USB / network bandwidth during the take, and claim the
        # device so discovery will not reopen it behind our back.
        device_pool.suspend(exclusive_device_id=resolved)
        self._preview_device_id = None

        with self._lock:
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            self._latest_jpeg = None
            self._consecutive_read_failures = 0
            self._last_error = None

            try:
                self._capture = self._open_device_capture(resolved, "main")
            except RuntimeError:
                device_pool.resume()
                raise

            width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or settings.camera_width
            height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or settings.camera_height
            fps = self._capture.get(cv2.CAP_PROP_FPS) or settings.camera_fps
            if fps <= 0:
                fps = float(settings.camera_fps)

            output_path = RAW_MEDIA_DIR / f"{session_id}.{settings.recording_format.lstrip('.')}"
            if output_path.exists():
                output_path.unlink()

            fourcc = self._fourcc()
            writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            if not writer.isOpened():
                self._capture.release()
                self._capture = None
                device_pool.resume()
                raise RuntimeError("CAMERA_NOT_FOUND")

            self._video_writer = writer
            self._active_session_id = session_id
            self._active_device_id = resolved
            self._output_path = output_path
            self._frames_written = 0
            return output_path

    def write_frame(self) -> bool:
        return self.read_frame()

    def stop_recording(self) -> Path:
        if self._active_session_id is None or self._output_path is None:
            raise RuntimeError("NO_ACTIVE_RECORDING")

        with self._lock:
            frames_written = self._frames_written
            if self._video_writer is not None:
                self._video_writer.release()
                self._video_writer = None
            if self._capture is not None:
                self._capture.release()
                self._capture = None

            output_path = self._output_path
            self._active_session_id = None
            self._active_device_id = None
            self._output_path = None
            self._latest_jpeg = None
            self._frames_written = 0
            self._consecutive_read_failures = 0

        device_pool.resume()

        if frames_written == 0 or not output_path.exists() or output_path.stat().st_size < 1024:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            raise RuntimeError(
                "RECORDING_EMPTY: No video frames were captured. "
                "Keep recording for at least a few seconds and ensure the camera stream is stable."
            )

        return output_path

    # ---------------------------------------------------------------- snapshots

    def get_latest_jpeg(self) -> bytes | None:
        if self._active_session_id is not None:
            return self._latest_jpeg
        if self._preview_device_id:
            frame = device_pool.latest_jpeg(self._preview_device_id, warm_if_cold=False)
            if frame is not None:
                return frame
        for status in device_pool.status():
            frame = device_pool.latest_jpeg(status.device_id, warm_if_cold=False)
            if frame is not None:
                return frame
        return None

    def capture_snapshot(self, usb_index: int | None = None, device_id: str | None = None) -> bytes | None:
        """Grab one frame from a device, opening and closing it immediately."""
        resolved = resolve_device_id(device_id if device_id is not None else usb_index)

        warm = device_pool.latest_jpeg(resolved, warm_if_cold=False)
        if warm is not None:
            self._persist_snapshot(warm)
            return warm

        kind, _ = parse_device_id(resolved)
        stream: StreamType = "sub" if kind == "ip" and settings.preview_use_substream else "main"
        cap = None
        try:
            cap = self._open_device_capture(resolved, stream)
            ok, frame = self._read_with_retries(cap)
            if not ok or frame is None:
                return None
            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                return None
            data = encoded.tobytes()
            self._persist_snapshot(data)
            return data
        except RuntimeError:
            return None
        finally:
            if cap is not None:
                cap.release()

    def _persist_snapshot(self, data: bytes) -> None:
        SNAPSHOTS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        (SNAPSHOTS_MEDIA_DIR / "latest.jpg").write_bytes(data)

    # ------------------------------------------------------------------- state

    def release_camera(self) -> None:
        with self._lock:
            if self._video_writer is not None:
                self._video_writer.release()
                self._video_writer = None
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            self._active_session_id = None
            self._active_device_id = None
            self._output_path = None
            self._latest_jpeg = None
        self._preview_device_id = None
        device_pool.release_all()
        device_pool.resume()

    @property
    def active_session_id(self) -> str | None:
        return self._active_session_id

    @property
    def active_device_id(self) -> str | None:
        return self._active_device_id

    @property
    def preview_active(self) -> bool:
        return bool(device_pool.status())

    @property
    def stream_available(self) -> bool:
        return self.preview_active or self._active_session_id is not None

    @property
    def active_stream_label(self) -> str:
        if self._active_session_id is not None:
            return "main"
        if self._open_stream_type:
            return self._open_stream_type
        if settings.is_ip_camera() and settings.preview_use_substream and settings.rtsp_sub_url():
            return "sub"
        return settings.ip_camera_active_stream if settings.is_ip_camera() else "usb"


camera_service = CameraService()
