from __future__ import annotations

import threading
import time

import cv2
from pathlib import Path

from ..config import RAW_MEDIA_DIR, settings


class CameraService:
    def __init__(self) -> None:
        self._capture: cv2.VideoCapture | None = None
        self._video_writer: cv2.VideoWriter | None = None
        self._active_session_id: str | None = None
        self._output_path: Path | None = None
        self._preview_active = False
        self._latest_jpeg: bytes | None = None
        self._lock = threading.Lock()

    def check_camera(self, camera_id: int | None = None) -> bool:
        cam_id = settings.camera_id if camera_id is None else camera_id
        cap = cv2.VideoCapture(cam_id)
        if not cap.isOpened():
            return False
        ok, _ = cap.read()
        cap.release()
        return ok

    def _open_capture(self, camera_id: int) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            raise RuntimeError("CAMERA_NOT_FOUND")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.camera_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.camera_height)
        cap.set(cv2.CAP_PROP_FPS, settings.camera_fps)
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

    def start_preview(self, camera_id: int) -> None:
        if self._active_session_id is not None:
            raise RuntimeError("RECORDING_ALREADY_ACTIVE")

        with self._lock:
            if self._capture is None:
                self._capture = self._open_capture(camera_id)
            self._preview_active = True

    def stop_preview(self) -> None:
        with self._lock:
            if self._active_session_id is not None:
                return
            self._preview_active = False
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            self._latest_jpeg = None

    def read_frame(self) -> bool:
        with self._lock:
            if self._capture is None:
                return False
            ok, frame = self._capture.read()
            if not ok:
                return False
            if self._video_writer is not None:
                self._video_writer.write(frame)
            self._cache_frame(frame)
            return True

    def start_recording(self, session_id: str, camera_id: int) -> Path:
        if self._active_session_id is not None:
            raise RuntimeError("RECORDING_ALREADY_ACTIVE")

        with self._lock:
            if self._capture is None:
                self._capture = self._open_capture(camera_id)

            width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self._capture.get(cv2.CAP_PROP_FPS) or settings.camera_fps

            output_path = RAW_MEDIA_DIR / f"{session_id}.mp4"
            fourcc = self._fourcc()
            writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            if not writer.isOpened():
                self._capture.release()
                self._capture = None
                self._preview_active = False
                raise RuntimeError("CAMERA_NOT_FOUND")

            self._video_writer = writer
            self._active_session_id = session_id
            self._output_path = output_path
            self._preview_active = False
            return output_path

    def write_frame(self) -> bool:
        return self.read_frame()

    def stop_recording(self) -> Path:
        if self._active_session_id is None or self._output_path is None:
            raise RuntimeError("NO_ACTIVE_RECORDING")

        with self._lock:
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
            return output_path

    def get_latest_jpeg(self) -> bytes | None:
        return self._latest_jpeg

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


camera_service = CameraService()
