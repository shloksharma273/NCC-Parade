"""Read and update IP camera configuration while the server is running.

Credentials entered on the camera-configuration screen are validated against the
camera first, then written to ``backend/.env`` and re-read into the live
settings, so a working camera appears without restarting the backend.

Cameras are stored in the ``IP_CAMERAS`` list. The legacy single-camera
``IP_CAMERA_*`` variables are still honoured on read and are migrated into that
list the first time a camera is saved, so nothing is silently dropped.
"""

from __future__ import annotations

import threading

from ..config import (
    ENV_PATH,
    reload_settings,
    settings,
    write_env_values,
)
from ..video_pipeline.camera_registry import camera_registry
from ..video_pipeline.device_pool import device_pool
from ..video_pipeline.rtsp_probe import build_rtsp_url, describe, find_working_paths

# Kept out of API responses; the screen only ever reports whether one is set.
_SECRET_PLACEHOLDER = "********"


class CameraConfigError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CameraConfigService:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    # -------------------------------------------------------------------- read

    def list_cameras(self) -> dict:
        cameras = []
        for camera in settings.ip_cameras():
            device = camera_registry.get(camera.device_id, discover_if_missing=False)
            cameras.append(
                {
                    "slug": camera.slug,
                    "device_id": camera.device_id,
                    "label": camera.label,
                    "host": camera.host,
                    "port": camera.port,
                    "username": settings.ip_camera_username if camera.slug == "default" else self._username_of(camera),
                    "password_set": camera.has_credentials,
                    "password": _SECRET_PLACEHOLDER if camera.has_credentials else "",
                    "main_url": self._redact(camera.main_url),
                    "sub_url": self._redact(camera.sub_url),
                    "status": device.status if device else "unknown",
                    "message": device.message if device else "Not checked yet.",
                    "available": bool(device and device.available),
                }
            )
        return {
            "cameras": cameras,
            "config_path": str(ENV_PATH),
            "config_exists": ENV_PATH.exists(),
            "message": (
                f"{len(cameras)} IP camera(s) configured."
                if cameras
                else "No IP cameras configured yet."
            ),
        }

    def _username_of(self, camera) -> str:
        from urllib.parse import urlparse

        url = camera.main_url or camera.sub_url
        if not url:
            return ""
        try:
            return urlparse(url).username or ""
        except ValueError:
            return ""

    def _redact(self, url: str) -> str:
        """Hide the password inside an RTSP URL before it leaves the server."""
        if not url or "@" not in url:
            return url
        scheme, _, rest = url.partition("://")
        creds, _, host_part = rest.rpartition("@")
        if ":" in creds:
            user, _, secret = creds.partition(":")
            # An empty password must stay visibly empty — masking it would imply
            # a password is configured when that is exactly what is missing.
            creds = f"{user}:{_SECRET_PLACEHOLDER}" if secret else f"{user}:"
        return f"{scheme}://{creds}@{host_part}"

    # -------------------------------------------------------------------- test

    def test_camera(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        main_path: str | None = None,
        slug: str | None = None,
    ) -> dict:
        """Check credentials against the camera and work out its stream paths.

        Reports *why* a camera fails — wrong password versus wrong stream path —
        which OpenCV alone cannot distinguish.
        """
        password = self._resolve_password(password, slug)

        if not host.strip():
            raise CameraConfigError("HOST_REQUIRED", "Camera IP address or hostname is required.")

        timeout = max(settings.rtsp_preflight_timeout * 4, 4.0)

        # An explicit path is honoured as-is; operators who know their camera
        # should not have to sit through a search.
        if main_path:
            result = describe(host, port, main_path, username, password, timeout)
            return {
                "success": result.ok,
                "outcome": result.outcome,
                "message": result.detail,
                "main_path": main_path if result.ok else None,
                "sub_path": None,
                "detected_family": None,
            }

        main, sub, family, last = find_working_paths(host, port, username, password, timeout)
        if main:
            return {
                "success": True,
                "outcome": "ok",
                "message": (
                    f"Connected. Detected a {family} camera."
                    if family
                    else "Connected to the camera stream."
                ),
                "main_path": main,
                "sub_path": sub,
                "detected_family": family,
            }

        return {
            "success": False,
            "outcome": last.outcome,
            "message": self._explain(last.outcome, last.detail, host, port),
            "main_path": None,
            "sub_path": None,
            "detected_family": None,
        }

    def _explain(self, outcome: str, detail: str, host: str, port: int) -> str:
        if outcome == "bad_credentials":
            return "The camera rejected this username and password."
        if outcome == "no_response":
            return (
                f"No RTSP response from {host}:{port}. Check the IP address, that the camera "
                "is powered, and that this PC is on the same network as the camera."
            )
        if outcome == "path_not_found":
            return (
                "The credentials were accepted but none of the known stream paths worked. "
                "Enter the RTSP path from the camera's manual."
            )
        return detail

    # -------------------------------------------------------------------- save

    def save_camera(
        self,
        slug: str,
        label: str,
        host: str,
        port: int,
        username: str,
        password: str,
        main_path: str | None = None,
        sub_path: str | None = None,
        verify: bool = True,
    ) -> dict:
        """Validate, persist to .env, and bring the camera online."""
        from ..config import _slugify

        password = self._resolve_password(password, slug)
        slug = _slugify(slug or label or host)
        if not host.strip():
            raise CameraConfigError("HOST_REQUIRED", "Camera IP address or hostname is required.")

        detected_family = None
        if verify:
            check = self.test_camera(host, port, username, password, main_path, slug=slug)
            if not check["success"]:
                raise CameraConfigError(check["outcome"].upper(), check["message"])
            main_path = check["main_path"] or main_path
            sub_path = check["sub_path"] or sub_path
            detected_family = check["detected_family"]

        if not main_path:
            raise CameraConfigError(
                "PATH_REQUIRED",
                "A main stream path is required when saving without verification.",
            )

        main_url = build_rtsp_url(host, port, username, password, main_path)
        sub_url = build_rtsp_url(host, port, username, password, sub_path) if sub_path else ""

        with self._lock:
            entries = self._current_entries()
            entries[slug] = (label or slug.replace("_", " ").title(), main_url, sub_url)
            self._persist(entries)

        device_id = f"ip:{slug}"
        # Drop any stale handle so the next preview uses the new credentials.
        device_pool.release(device_id)
        camera_registry.invalidate()
        device = camera_registry.get(device_id)

        return {
            "slug": slug,
            "device_id": device_id,
            "saved": True,
            "detected_family": detected_family,
            "status": device.status if device else "unknown",
            "message": (
                f"Camera saved to {ENV_PATH.name} and is ready to use."
                if device and device.available
                else "Camera saved, but it is not reporting as available yet."
            ),
        }

    def delete_camera(self, slug: str) -> dict:
        with self._lock:
            entries = self._current_entries()
            if slug not in entries:
                raise CameraConfigError("DEVICE_NOT_FOUND", f"No configured camera named '{slug}'.")
            del entries[slug]
            self._persist(entries)

        device_pool.release(f"ip:{slug}")
        camera_registry.invalidate()
        return {"slug": slug, "deleted": True, "message": "Camera removed."}

    # ----------------------------------------------------------------- helpers

    def _resolve_password(self, password: str, slug: str | None) -> str:
        """Keep the stored password when the form submits the masked placeholder."""
        if password != _SECRET_PLACEHOLDER:
            return password
        if not slug:
            return ""
        existing = settings.find_ip_camera(slug)
        if existing is None:
            return ""
        from urllib.parse import unquote, urlparse

        url = existing.main_url or existing.sub_url
        try:
            parsed = urlparse(url)
        except ValueError:
            return ""
        return unquote(parsed.password or "")

    def _current_entries(self) -> dict[str, tuple[str, str, str]]:
        """Every configured camera as {slug: (label, main_url, sub_url)}.

        Reads through ``settings.ip_cameras()``, so the legacy single-camera
        variables are picked up and migrated into IP_CAMERAS on the next write.
        """
        entries: dict[str, tuple[str, str, str]] = {}
        for camera in settings.ip_cameras():
            if not camera.main_url:
                continue
            entries[camera.slug] = (camera.label, camera.main_url, camera.sub_url)
        return entries

    def _persist(self, entries: dict[str, tuple[str, str, str]]) -> None:
        parts = []
        for slug, (label, main_url, sub_url) in entries.items():
            # "|" separates fields and "," separates cameras, so neither may
            # appear inside a label.
            safe_label = label.replace("|", "-").replace(",", " ")
            parts.append(f"{slug}|{safe_label}|{main_url}|{sub_url}")

        values = {"IP_CAMERAS": ",".join(parts)}

        # The legacy placeholders would otherwise be re-added as a phantom
        # "default" camera on every reload.
        if "default" in entries:
            values["IP_CAMERA_RTSP_MAIN"] = ""
            values["IP_CAMERA_RTSP_SUB"] = ""
            values["IP_CAMERA_HOST"] = ""

        write_env_values(values)
        reload_settings()


camera_config_service = CameraConfigService()
