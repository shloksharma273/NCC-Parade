from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import quote, urlparse

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

SUPPORTED_DRILL_TYPES = {"kadam_tal", "salute", "baju_swing", "slow_march", "tez_chal", "hill_march"}


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


def _slugify(raw: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", raw.strip().lower()).strip("_")
    return cleaned or "camera"


def make_device_id(kind: str, key: str | int) -> str:
    """Stable id for one camera device, e.g. ``usb:0`` / ``ip:front_gate``."""
    return f"{kind}:{key}"


def parse_device_id(device_id: str) -> tuple[str, str]:
    """Split a device id into (kind, key).

    Bare numbers are accepted for backward compatibility with sessions
    created before device ids existed (``"0"`` means USB index 0).
    """
    raw = (device_id or "").strip()
    if ":" in raw:
        kind, _, key = raw.partition(":")
        kind = kind.strip().lower()
        if kind in {"usb", "ip"}:
            return kind, key.strip()
    if raw.isdigit():
        return "usb", raw
    if not raw:
        return "usb", str(settings.camera_id)
    return "ip", _slugify(raw)


class IPCameraConfig(BaseModel):
    """One declared IP camera."""

    slug: str
    label: str
    host: str = ""
    port: int = 554
    main_url: str = ""
    sub_url: str = ""

    @property
    def device_id(self) -> str:
        return make_device_id("ip", self.slug)

    @property
    def has_credentials(self) -> bool:
        """Whether the RTSP URL carries a non-empty password.

        ``rtsp://admin:@host/...`` — the shape produced when IP_CAMERA_PASSWORD
        is unset — counts as missing, since the camera will reject it.
        """
        url = self.main_url or self.sub_url
        if not url:
            return False
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        return bool(parsed.username) and bool(parsed.password)


def _parse_ip_camera_entry(entry: str, index: int) -> IPCameraConfig | None:
    """Parse one ``slug|Label|rtsp_main|rtsp_sub`` entry from IP_CAMERAS."""
    parts = [p.strip() for p in entry.split("|")]
    parts += [""] * (4 - len(parts)) if len(parts) < 4 else []
    slug, label, main_url, sub_url = parts[0], parts[1], parts[2], parts[3]
    if not main_url and slug.startswith("rtsp://"):
        # Shorthand: a bare RTSP URL with no slug/label.
        main_url, slug, label = slug, f"camera_{index + 1}", ""
    if not main_url:
        return None
    slug = _slugify(slug or f"camera_{index + 1}")
    host, port = _host_port_from_rtsp(main_url)
    return IPCameraConfig(
        slug=slug,
        label=label or slug.replace("_", " ").title(),
        host=host,
        port=port,
        main_url=main_url,
        sub_url=sub_url,
    )


def _host_port_from_rtsp(url: str) -> tuple[str, int]:
    try:
        parsed = urlparse(url)
        return parsed.hostname or "", parsed.port or 554
    except ValueError:
        return "", 554


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

    # Multi-camera declaration: comma-separated ``slug|Label|rtsp_main|rtsp_sub``
    # entries, e.g. "front|Front Gate|rtsp://.../main|rtsp://.../sub,side|Side|rtsp://..."
    ip_cameras_raw: str = os.getenv("IP_CAMERAS", "")

    # Device discovery
    usb_scan_max_index: int = int(os.getenv("USB_SCAN_MAX_INDEX", "5"))
    device_discovery_ttl_seconds: float = float(os.getenv("DEVICE_DISCOVERY_TTL_SECONDS", "30"))
    rtsp_preflight_timeout: float = float(os.getenv("RTSP_PREFLIGHT_TIMEOUT", "1.0"))
    ip_camera_autoscan: bool = Field(default=_env_bool("IP_CAMERA_AUTOSCAN", False))
    ip_camera_autoscan_timeout: float = float(os.getenv("IP_CAMERA_AUTOSCAN_TIMEOUT", "2.5"))

    # Low-resolution settings for the multi-camera chooser previews. Deliberately
    # small so several USB cameras can share one controller's bandwidth.
    preview_width: int = int(os.getenv("PREVIEW_WIDTH", "640"))
    preview_height: int = int(os.getenv("PREVIEW_HEIGHT", "360"))
    preview_fps: int = int(os.getenv("PREVIEW_FPS", "15"))
    preview_jpeg_quality: int = int(os.getenv("PREVIEW_JPEG_QUALITY", "70"))
    preview_idle_timeout_seconds: float = float(os.getenv("PREVIEW_IDLE_TIMEOUT_SECONDS", "60"))

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

    def _legacy_is_placeholder(self) -> bool:
        """Whether the legacy IP_CAMERA_* values are untouched defaults.

        With no .env file these fall back to the built-in example values
        (``192.168.1.50`` / ``admin`` / no password), which would otherwise be
        advertised as a real camera and offered for selection. Nothing was
        configured unless an explicit RTSP URL or a password was supplied.
        """
        return not self.ip_camera_rtsp_main and not self.ip_camera_password

    def ip_cameras(self) -> list[IPCameraConfig]:
        """All declared IP cameras.

        Entries from ``IP_CAMERAS`` come first; the legacy single-camera
        ``IP_CAMERA_*`` settings are appended as one more device so existing
        deployments keep working unchanged.
        """
        cameras: list[IPCameraConfig] = []
        seen: set[str] = set()

        for index, entry in enumerate(self.ip_cameras_raw.split(",")):
            entry = entry.strip()
            if not entry:
                continue
            parsed = _parse_ip_camera_entry(entry, index)
            if parsed and parsed.slug not in seen:
                seen.add(parsed.slug)
                cameras.append(parsed)

        legacy_main = self.rtsp_main_url()
        if legacy_main and "default" not in seen and not self._legacy_is_placeholder():
            legacy_host, legacy_port = _host_port_from_rtsp(legacy_main)
            cameras.append(
                IPCameraConfig(
                    slug="default",
                    label=f"IP Camera ({legacy_host or self.ip_camera_host})",
                    host=legacy_host or self.ip_camera_host,
                    port=legacy_port or self.ip_camera_port,
                    main_url=legacy_main,
                    sub_url=self.rtsp_sub_url(),
                )
            )
        return cameras

    def find_ip_camera(self, slug: str) -> IPCameraConfig | None:
        for camera in self.ip_cameras():
            if camera.slug == slug:
                return camera
        return None

    def resolve_device_source(self, device_id: str, stream_type: str = "main") -> str | int:
        """Resolve a device id to something OpenCV can open.

        Unlike :meth:`get_camera_source` this ignores the global ``CAMERA_TYPE``
        mode, so USB and IP cameras can be used side by side.
        """
        kind, key = parse_device_id(device_id)
        if kind == "usb":
            return int(key) if str(key).isdigit() else self.camera_id

        camera = self.find_ip_camera(key)
        if camera is None:
            raise ValueError("DEVICE_NOT_FOUND")
        if stream_type == "sub" and self.preview_use_substream and camera.sub_url:
            return camera.sub_url
        if not camera.main_url:
            raise ValueError("RTSP_URL_MISSING")
        return camera.main_url

    def default_device_id(self) -> str:
        if self.is_ip_camera():
            cameras = self.ip_cameras()
            if cameras:
                return cameras[0].device_id
        return make_device_id("usb", self.camera_id)


settings = Settings()


# ---------------------------------------------------------------------------
# Runtime configuration writes
#
# The camera-configuration screen edits credentials while the server is
# running, so values are persisted to backend/.env and then re-read into the
# existing ``settings`` object. Every module does ``from .config import
# settings``, so the object is updated in place — rebinding it here would leave
# every importer holding the stale one.
# ---------------------------------------------------------------------------

ENV_PATH = BACKEND_ROOT / ".env"


def _format_env_line(key: str, value: str) -> str:
    # Quote only when needed, so a hand-edited .env stays readable.
    if value and (value[0] in "'\"" or any(ch in value for ch in " #\t")):
        escaped = value.replace('"', '\\"')
        return f'{key}="{escaped}"'
    return f"{key}={value}"


def write_env_values(values: dict[str, str]) -> Path:
    """Persist *values* to backend/.env, preserving comments and unrelated keys.

    Written to a temporary file and moved into place, so an interrupted write
    cannot leave a half-truncated .env behind.
    """
    existing_lines: list[str] = []
    if ENV_PATH.exists():
        existing_lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    remaining = dict(values)
    output: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            output.append(_format_env_line(key, remaining.pop(key)))
        else:
            output.append(line)

    if remaining:
        if output and output[-1].strip():
            output.append("")
        output.append("# Written by the camera configuration screen")
        for key, value in remaining.items():
            output.append(_format_env_line(key, value))

    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = ENV_PATH.with_suffix(".env.tmp")
    temp_path.write_text("\n".join(output) + "\n", encoding="utf-8")
    temp_path.replace(ENV_PATH)
    return ENV_PATH


# Camera fields the configuration screen can change at runtime, mapped to the
# environment variable each one reads.
#
# This mapping cannot be derived from the model: every field default is written
# as ``os.getenv(...)``, which Python evaluates once when the class body runs, so
# a freshly constructed ``Settings()`` reuses the values captured at import and
# would silently ignore an updated .env. Anything added to the configuration
# screen must be listed here too, or its changes will not take effect until the
# server restarts.
_CAMERA_ENV_BINDINGS: dict[str, tuple[str, str]] = {
    "camera_type": ("CAMERA_TYPE", "lower_str"),
    "ip_cameras_raw": ("IP_CAMERAS", "str"),
    "ip_camera_host": ("IP_CAMERA_HOST", "str"),
    "ip_camera_port": ("IP_CAMERA_PORT", "int"),
    "ip_camera_username": ("IP_CAMERA_USERNAME", "str"),
    "ip_camera_password": ("IP_CAMERA_PASSWORD", "str"),
    "ip_camera_rtsp_main": ("IP_CAMERA_RTSP_MAIN", "str"),
    "ip_camera_rtsp_sub": ("IP_CAMERA_RTSP_SUB", "str"),
    "ip_camera_main_path": ("IP_CAMERA_MAIN_PATH", "str"),
    "ip_camera_sub_path": ("IP_CAMERA_SUB_PATH", "str"),
    "ip_camera_active_stream": ("IP_CAMERA_ACTIVE_STREAM", "str"),
    "camera_id": ("USB_CAMERA_INDEX", "int"),
}


def reload_settings() -> None:
    """Re-read .env and refresh the camera settings in place.

    Updates the existing ``settings`` object rather than replacing it, because
    every module holds a direct reference to it.
    """
    load_dotenv(ENV_PATH, override=True)

    for field, (env_var, kind) in _CAMERA_ENV_BINDINGS.items():
        raw = os.getenv(env_var)
        if raw is None:
            continue
        raw = raw.strip()
        if kind == "int":
            if not raw.isdigit():
                continue
            value: object = int(raw)
        elif kind == "lower_str":
            value = raw.lower()
        else:
            value = raw
        settings.__dict__[field] = value


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
