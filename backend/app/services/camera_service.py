from __future__ import annotations

import os
import platform
import threading
import time
from pathlib import Path
from typing import Literal

# pyrefly: ignore [missing-import]
import cv2

# On Windows, DirectShow (CAP_DSHOW) opens USB cameras ~40x faster than the
# default MSMF backend, which enumerates all devices and can block for 15-20 s.
_USB_BACKEND = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY

from ..config import RAW_MEDIA_DIR, SNAPSHOTS_MEDIA_DIR, settings

StreamType = Literal["main", "sub"]

# Prefer TCP transport for LAN RTSP streams (OpenCV FFmpeg backend).
if settings.is_ip_camera():
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")


class CameraService:
    MAX_FRAME_READ_FAILURES = settings.max_frame_read_failures

    def __init__(self) -> None:
        self._capture: cv2.VideoCapture | None = None
        self._video_writer: cv2.VideoWriter | None = None
        self._active_session_id: str | None = None
        self._output_path: Path | None = None
        self._preview_active = False
        self._latest_jpeg: bytes | None = None
        self._frames_written = 0
        self._consecutive_read_failures = 0
        self._open_stream_type: StreamType | None = None
        self._usb_index: int | None = None
        self._last_error: str | None = None
        self._lock = threading.Lock()

    def get_camera_source(self, stream_type: StreamType = "main", usb_index: int | None = None) -> str | int:
        return settings.get_camera_source(stream_type, usb_index=usb_index)

    def _open_capture(self, stream_type: StreamType = "main", usb_index: int | None = None) -> cv2.VideoCapture:
        try:
            source = self.get_camera_source(stream_type, usb_index=usb_index)
        except ValueError as exc:
            if str(exc) == "RTSP_URL_MISSING":
                raise RuntimeError(
                    "RTSP_URL_MISSING: IP camera mode is enabled, but RTSP URL is not configured."
                ) from exc
            raise

        if isinstance(source, str):
            cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        else:
            cap = cv2.VideoCapture(int(source), _USB_BACKEND)

        if not cap.isOpened():
            if settings.is_ip_camera():
                raise RuntimeError(
                    "IP_CAMERA_NOT_REACHABLE: Unable to reach IP camera. "
                    "Check camera power, PoE switch, LAN cable, and IP address."
                )
            raise RuntimeError("CAMERA_NOT_FOUND")

        if not settings.is_ip_camera():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.camera_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.camera_height)
            cap.set(cv2.CAP_PROP_FPS, settings.camera_fps)

        self._open_stream_type = stream_type
        self._usb_index = usb_index if usb_index is not None else settings.camera_id
        return cap

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

    def check_camera_connection(self, usb_index: int | None = None) -> dict:
        if settings.is_ip_camera() and not settings.rtsp_main_url():
            return {
                "camera_connected": False,
                "error": "RTSP_URL_MISSING",
                "message": "IP camera mode is enabled, but RTSP URL is not configured.",
            }

        cap = None
        try:
            cap = self._open_capture("main", usb_index=usb_index)
            ok, frame = self._read_with_retries(cap)
            if not ok:
                return {
                    "camera_connected": False,
                    "error": "FRAME_READ_FAILED",
                    "message": "Camera stream opened but frames could not be read.",
                }
            return {"camera_connected": True, "message": "Camera is reachable."}
        except RuntimeError as exc:
            code = str(exc).split(":")[0]
            return {
                "camera_connected": False,
                "error": code,
                "message": str(exc).split(": ", 1)[-1] if ": " in str(exc) else str(exc),
            }
        finally:
            if cap is not None:
                cap.release()

    def check_camera(self, camera_id: int | None = None) -> bool:
        usb_index = camera_id if camera_id is not None else settings.camera_id
        return self.check_camera_connection(usb_index=usb_index)["camera_connected"]

    def test_stream_openable(self, stream_type: StreamType) -> bool:
        if settings.is_ip_camera():
            url = settings.rtsp_sub_url() if stream_type == "sub" else settings.rtsp_main_url()
            if stream_type == "sub" and not url:
                return False
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

        if settings.is_ip_camera():
            main_configured = bool(settings.rtsp_main_url())
            sub_configured = bool(settings.rtsp_sub_url())
            main_openable = self.test_stream_openable("main") if main_configured else False
            sub_openable = self.test_stream_openable("sub") if sub_configured else False
            if main_openable or sub_openable:
                message = "Camera stream is reachable."
            elif not main_configured:
                message = "RTSP main stream URL is not configured."
            else:
                message = "RTSP stream could not be opened. Verify camera IP, credentials, and RTSP URL."
        else:
            main_configured = True
            sub_configured = False
            main_openable = self.check_camera()
            sub_openable = False
            message = "USB camera is reachable." if main_openable else "USB camera could not be opened."

        return {
            "camera_type": settings.camera_type,
            "camera_host": settings.ip_camera_host if settings.is_ip_camera() else None,
            "rtsp_port": settings.ip_camera_port if settings.is_ip_camera() else None,
            "main_stream_configured": main_configured,
            "sub_stream_configured": sub_configured,
            "main_stream_openable": main_openable,
            "sub_stream_openable": sub_openable,
            "last_checked_at": utc_now_iso(),
            "message": message,
        }

    def start_preview(self, camera_id: int | None = None) -> None:
        if self._active_session_id is not None:
            raise RuntimeError("RECORDING_ALREADY_ACTIVE")

        stream: StreamType = "sub" if settings.is_ip_camera() and settings.preview_use_substream else "main"
        usb_index = camera_id if camera_id is not None else settings.camera_id

        with self._lock:
            if self._capture is None:
                self._capture = self._open_capture(stream, usb_index=usb_index)
            self._preview_active = True
            self._consecutive_read_failures = 0
            self._last_error = None

    def stop_preview(self) -> None:
        with self._lock:
            if self._active_session_id is not None:
                return
            self._preview_active = False
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            self._latest_jpeg = None
            self._open_stream_type = None

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

    def start_recording(self, session_id: str, camera_id: int | None = None) -> Path:
        if self._active_session_id is not None:
            raise RuntimeError("RECORDING_ALREADY_ACTIVE")

        usb_index = camera_id if camera_id is not None else settings.camera_id

        with self._lock:
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            self._preview_active = False
            self._latest_jpeg = None
            self._consecutive_read_failures = 0
            self._last_error = None

            self._capture = self._open_capture("main", usb_index=usb_index)

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
                raise RuntimeError("CAMERA_NOT_FOUND")

            self._video_writer = writer
            self._active_session_id = session_id
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
            self._output_path = None
            self._preview_active = False
            self._latest_jpeg = None
            self._frames_written = 0
            self._consecutive_read_failures = 0

        if frames_written == 0 or not output_path.exists() or output_path.stat().st_size < 1024:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            raise RuntimeError(
                "RECORDING_EMPTY: No video frames were captured. "
                "Keep recording for at least a few seconds and ensure the camera stream is stable."
            )

        return output_path

    def get_latest_jpeg(self) -> bytes | None:
        return self._latest_jpeg

    def capture_snapshot(self, usb_index: int | None = None) -> bytes | None:
        stream: StreamType = "sub" if settings.is_ip_camera() and settings.preview_use_substream else "main"
        cap = None
        try:
            cap = self._open_capture(stream, usb_index=usb_index)
            ok, frame = self._read_with_retries(cap)
            if not ok or frame is None:
                return None
            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if ok:
                data = encoded.tobytes()
                SNAPSHOTS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                (SNAPSHOTS_MEDIA_DIR / "latest.jpg").write_bytes(data)
                return data
            return None
        except RuntimeError:
            return None
        finally:
            if cap is not None:
                cap.release()

    def iter_mjpeg(self):
        boundary = b"frame"
        while self._preview_active or self._active_session_id is not None:
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

    def release_camera(self) -> None:
        with self._lock:
            if self._video_writer is not None:
                self._video_writer.release()
                self._video_writer = None
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            self._active_session_id = None
            self._output_path = None
            self._preview_active = False
            self._latest_jpeg = None

    @property
    def active_session_id(self) -> str | None:
        return self._active_session_id

    @property
    def preview_active(self) -> bool:
        return self._preview_active

    @property
    def stream_available(self) -> bool:
        return self._preview_active or self._active_session_id is not None

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
