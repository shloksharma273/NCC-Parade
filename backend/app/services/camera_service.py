from __future__ import annotations

import cv2
from pathlib import Path

from ..config import RAW_MEDIA_DIR, settings


class CameraService:
    def __init__(self) -> None:
        self._capture: cv2.VideoCapture | None = None
        self._video_writer: cv2.VideoWriter | None = None
        self._active_session_id: str | None = None
        self._output_path: Path | None = None

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

    def start_recording(self, session_id: str, camera_id: int) -> Path:
        if self._active_session_id is not None:
            raise RuntimeError("RECORDING_ALREADY_ACTIVE")

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
            raise RuntimeError("CAMERA_NOT_FOUND")

        self._video_writer = writer
        self._active_session_id = session_id
        self._output_path = output_path
        return output_path

    def write_frame(self) -> bool:
        if self._capture is None or self._video_writer is None:
            return False
        ok, frame = self._capture.read()
        if not ok:
            return False
        self._video_writer.write(frame)
        return True

    def stop_recording(self) -> Path:
        if self._active_session_id is None or self._output_path is None:
            raise RuntimeError("NO_ACTIVE_RECORDING")

        if self._video_writer is not None:
            self._video_writer.release()
            self._video_writer = None
        if self._capture is not None:
            self._capture.release()
            self._capture = None

        output_path = self._output_path
        self._active_session_id = None
        self._output_path = None
        return output_path

    def get_preview_frame(self, camera_id: int | None = None) -> bytes | None:
        cam_id = settings.camera_id if camera_id is None else camera_id
        cap = cv2.VideoCapture(cam_id)
        if not cap.isOpened():
            return None
        ok, frame = cap.read()
        cap.release()
        if not ok:
            return None
        ok, encoded = cv2.imencode(".jpg", frame)
        return encoded.tobytes() if ok else None

    def release_camera(self) -> None:
        if self._video_writer is not None:
            self._video_writer.release()
            self._video_writer = None
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._active_session_id = None
        self._output_path = None

    @property
    def active_session_id(self) -> str | None:
        return self._active_session_id


camera_service = CameraService()
