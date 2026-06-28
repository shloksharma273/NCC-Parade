from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

MEDIA_DIR = BACKEND_ROOT / "media"
RAW_MEDIA_DIR = MEDIA_DIR / "raw"
ANNOTATED_MEDIA_DIR = MEDIA_DIR / "annotated"
FRAMES_MEDIA_DIR = MEDIA_DIR / "frames"
REPORTS_MEDIA_DIR = MEDIA_DIR / "reports"
SNAPSHOTS_MEDIA_DIR = MEDIA_DIR / "snapshots"
REPORTS_DIR = BACKEND_ROOT / "reports"
DATABASE_DIR = BACKEND_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "drill_server.db"

SUPPORTED_DRILL_TYPES = {"kadam_tal", "salute"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _build_rtsp_url(host: str, port: int, username: str, password: str, path: str) -> str:
    user = quote(username, safe="")
    pwd = quote(password, safe="")
    clean_path = path.lstrip("/")
    return f"rtsp://{user}:{pwd}@{host}:{port}/{clean_path}"


class Settings(BaseModel):
    app_name: str = "Drill Recognition Backend"
    version: str = "0.2.0"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    # Camera mode: usb | ip
    camera_type: str = os.getenv("CAMERA_TYPE", "usb").strip().lower()

    # USB camera (legacy CAMERA_ID kept for backward compatibility)
    camera_id: int = int(os.getenv("USB_CAMERA_INDEX", os.getenv("CAMERA_ID", "0")))
    camera_width: int = int(os.getenv("CAMERA_WIDTH", os.getenv("RECORDING_WIDTH", "1280")))
    camera_height: int = int(os.getenv("CAMERA_HEIGHT", os.getenv("RECORDING_HEIGHT", "720")))
    camera_fps: int = int(os.getenv("CAMERA_FPS", os.getenv("RECORDING_FPS", "30")))

    # IP camera
    ip_camera_host: str = os.getenv("IP_CAMERA_HOST", "192.168.1.50")
    ip_camera_port: int = int(os.getenv("IP_CAMERA_PORT", "554"))
    ip_camera_username: str = os.getenv("IP_CAMERA_USERNAME", "admin")
    ip_camera_password: str = os.getenv("IP_CAMERA_PASSWORD", "")
    ip_camera_rtsp_main: str = os.getenv("IP_CAMERA_RTSP_MAIN", "")
    ip_camera_rtsp_sub: str = os.getenv("IP_CAMERA_RTSP_SUB", "")
    ip_camera_active_stream: str = os.getenv("IP_CAMERA_ACTIVE_STREAM", "main")
    ip_camera_main_path: str = os.getenv("IP_CAMERA_MAIN_PATH", "main")
    ip_camera_sub_path: str = os.getenv("IP_CAMERA_SUB_PATH", "sub")

    recording_backend: str = os.getenv("RECORDING_BACKEND", "opencv")
    recording_format: str = os.getenv("RECORDING_FORMAT", "mp4")
    preview_use_substream: bool = Field(default=_env_bool("PREVIEW_USE_SUBSTREAM", True))
    preview_refresh_seconds: float = float(os.getenv("PREVIEW_REFRESH_SECONDS", "1"))
    max_frame_read_failures: int = int(os.getenv("MAX_FRAME_READ_FAILURES", "30"))

    ml_difficulty: float = float(os.getenv("DIFFICULTY", "2.0"))
    ml_output_dir: Path = BACKEND_ROOT / "ml_output"

    def is_ip_camera(self) -> bool:
        return self.camera_type == "ip"

    def rtsp_main_url(self) -> str:
        if self.ip_camera_rtsp_main:
            return self.ip_camera_rtsp_main
        if not self.ip_camera_host:
            return ""
        return _build_rtsp_url(
            self.ip_camera_host,
            self.ip_camera_port,
            self.ip_camera_username,
            self.ip_camera_password,
            self.ip_camera_main_path,
        )

    def rtsp_sub_url(self) -> str:
        if self.ip_camera_rtsp_sub:
            return self.ip_camera_rtsp_sub
        if not self.ip_camera_host:
            return ""
        return _build_rtsp_url(
            self.ip_camera_host,
            self.ip_camera_port,
            self.ip_camera_username,
            self.ip_camera_password,
            self.ip_camera_sub_path,
        )

    def get_camera_source(self, stream_type: str = "main", usb_index: int | None = None) -> str | int:
        if self.is_ip_camera():
            if stream_type == "sub" and self.preview_use_substream and self.rtsp_sub_url():
                return self.rtsp_sub_url()
            url = self.rtsp_main_url()
            if not url:
                raise ValueError("RTSP_URL_MISSING")
            return url
        return usb_index if usb_index is not None else self.camera_id


settings = Settings()


def ensure_directories() -> None:
    for path in (
        RAW_MEDIA_DIR,
        ANNOTATED_MEDIA_DIR,
        FRAMES_MEDIA_DIR,
        REPORTS_MEDIA_DIR,
        SNAPSHOTS_MEDIA_DIR,
        REPORTS_DIR,
        DATABASE_DIR,
        settings.ml_output_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
