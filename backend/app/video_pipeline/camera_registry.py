"""Discovery of the camera devices this machine can actually use.

The rest of the stack addresses cameras by a stable *device id* (``usb:0``,
``ip:front_gate``) rather than by the global ``CAMERA_TYPE`` mode, so USB and IP
cameras can be listed and previewed side by side.

Discovery is deliberately cheap and fail-fast:

* USB cameras are found by opening indices ``0..USB_SCAN_MAX_INDEX``. An index
  only counts as a camera if it opens *and* yields a frame.
* IP cameras are never opened during discovery — opening a dead RTSP stream
  blocks the FFmpeg backend for 10-20 s. Instead we knock on the RTSP TCP port
  with a short timeout and only report reachability.
"""

from __future__ import annotations

import platform
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from typing import Literal

# pyrefly: ignore [missing-import]
import cv2

from ..config import make_device_id, parse_device_id, settings
from ..utils.network import connect_best_effort, get_local_ip
from .device_pool import device_pool

# See camera_service: DirectShow avoids the MSMF enumeration stall on Windows.
_USB_BACKEND = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY

DeviceKind = Literal["usb", "ip"]
DeviceStatus = Literal["ready", "unreachable", "unauthorized", "unconfigured", "detected"]


@dataclass
class DeviceInfo:
    device_id: str
    kind: DeviceKind
    label: str
    status: DeviceStatus
    available: bool
    message: str
    index: int | None = None
    host: str | None = None
    port: int | None = None
    has_sub_stream: bool = False
    capabilities: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _tcp_open(host: str, port: int, timeout: float) -> bool:
    """Return True if a TCP connection to host:port completes within *timeout*."""
    if not host:
        return False
    try:
        with connect_best_effort(host, port, timeout):
            return True
    except OSError:
        return False


def _probe_usb_index(index: int) -> DeviceInfo | None:
    """Open one USB index and confirm it yields a frame."""
    cap = None
    try:
        cap = cv2.VideoCapture(index, _USB_BACKEND)
        if not cap.isOpened():
            return None
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        height, width = frame.shape[:2]
        return DeviceInfo(
            device_id=make_device_id("usb", index),
            kind="usb",
            label=f"USB Camera {index}",
            status="ready",
            available=True,
            message="Camera is reachable.",
            index=index,
            capabilities={"width": int(width), "height": int(height)},
        )
    except cv2.error:
        return None
    finally:
        if cap is not None:
            cap.release()


def _rtsp_requires_auth(host: str, port: int, timeout: float) -> bool | None:
    """Ask the RTSP server for OPTIONS and report whether it demands credentials.

    Returns True if the camera answered 401/403, False if it answered without
    challenging, and None if it did not respond at all. This is how a camera
    that is present but misconfigured gets told apart from one that is absent.
    No credentials are sent and no stream is opened.
    """
    request = (
        f"OPTIONS rtsp://{host}:{port}/ RTSP/1.0@CSeq: 1@@"
    ).replace("@", "\r\n")
    try:
        with connect_best_effort(host, port, timeout) as sock:
            sock.sendall(request.encode())
            reply = sock.recv(256).decode("latin-1", "replace")
    except OSError:
        return None
    first_line = reply.split("\r\n", 1)[0]
    if " 401" in first_line or " 403" in first_line:
        return True
    return False if "RTSP/" in first_line else None


def _probe_ip_camera(camera) -> DeviceInfo:
    """TCP-knock a configured IP camera; never opens the RTSP stream itself."""
    if not camera.main_url:
        return DeviceInfo(
            device_id=camera.device_id,
            kind="ip",
            label=camera.label,
            status="unconfigured",
            available=False,
            message="No RTSP URL configured for this camera.",
            host=camera.host or None,
            port=camera.port,
        )

    reachable = _tcp_open(camera.host, camera.port, settings.rtsp_preflight_timeout)
    if not reachable:
        return DeviceInfo(
            device_id=camera.device_id,
            kind="ip",
            label=camera.label,
            status="unreachable",
            available=False,
            message=(
                f"No response from {camera.host}:{camera.port}. "
                "Check camera power, PoE switch, LAN cable, and IP address."
            ),
            host=camera.host or None,
            port=camera.port,
            has_sub_stream=bool(camera.sub_url),
        )

    # The camera answers, but that alone does not mean we can stream from it.
    # A camera that challenges for credentials we do not have would otherwise be
    # listed as ready and then sit on "starting..." forever.
    needs_auth = _rtsp_requires_auth(camera.host, camera.port, settings.rtsp_preflight_timeout)
    credentials_missing = needs_auth is True and not camera.has_credentials
    if credentials_missing:
        return DeviceInfo(
            device_id=camera.device_id,
            kind="ip",
            label=camera.label,
            status="unauthorized",
            available=False,
            message=(
                f"{camera.host} is online but requires a username and password. "
                "Set IP_CAMERA_USERNAME / IP_CAMERA_PASSWORD (or put full URLs in "
                "IP_CAMERAS) in backend/.env, then press Rescan."
            ),
            host=camera.host or None,
            port=camera.port,
            has_sub_stream=bool(camera.sub_url),
        )

    return DeviceInfo(
        device_id=camera.device_id,
        kind="ip",
        label=camera.label,
        status="ready",
        available=True,
        message="Camera is reachable.",
        host=camera.host or None,
        port=camera.port,
        has_sub_stream=bool(camera.sub_url),
    )


def _scan_subnet_for_rtsp(timeout: float) -> list[str]:
    """Best-effort sweep of the local /24 for hosts with RTSP port 554 open.

    Only used when ``IP_CAMERA_AUTOSCAN`` is on. An open port tells us something
    is there but not its stream path or credentials, so such hosts are reported
    as ``detected`` and cannot be previewed.
    """
    local_ip = get_local_ip()
    if local_ip.startswith("127."):
        return []
    prefix = local_ip.rsplit(".", 1)[0]

    found: list[str] = []
    per_host_timeout = max(timeout / 4, 0.3)

    def knock(host: str) -> str | None:
        return host if _tcp_open(host, 554, per_host_timeout) else None

    targets = [f"{prefix}.{i}" for i in range(1, 255) if f"{prefix}.{i}" != local_ip]
    with ThreadPoolExecutor(max_workers=64) as pool:
        for result in pool.map(knock, targets):
            if result:
                found.append(result)
    return found


class CameraRegistry:
    """Caches the discovered device list so pages can poll it cheaply."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._devices: list[DeviceInfo] = []
        self._discovered_at: float = 0.0

    # ---------------------------------------------------------------- discovery

    def _discover_usb(self) -> list[DeviceInfo]:
        # A device the recorder holds is reported from its last known state
        # instead of being probed — reopening it mid-take could disturb the
        # footage being captured.
        exclusive = device_pool.exclusive_device_id
        previous = {d.device_id: d for d in self.cached()}

        devices: list[DeviceInfo] = []
        indices = []
        for index in range(max(settings.usb_scan_max_index, 1)):
            device_id = make_device_id("usb", index)
            if exclusive == device_id:
                known = previous.get(device_id)
                if known is not None:
                    devices.append(known)
                continue
            indices.append(index)

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(_probe_usb_index, indices))
        devices.extend(device for device in results if device is not None)
        devices.sort(key=lambda d: d.index if d.index is not None else 0)
        return devices

    def _discover_ip(self) -> list[DeviceInfo]:
        cameras = settings.ip_cameras()
        if not cameras:
            return []
        with ThreadPoolExecutor(max_workers=max(len(cameras), 1)) as pool:
            return list(pool.map(_probe_ip_camera, cameras))

    def _discover_unconfigured(self, known_hosts: set[str]) -> list[DeviceInfo]:
        if not settings.ip_camera_autoscan:
            return []
        devices: list[DeviceInfo] = []
        for host in _scan_subnet_for_rtsp(settings.ip_camera_autoscan_timeout):
            if host in known_hosts:
                continue
            devices.append(
                DeviceInfo(
                    device_id=make_device_id("ip", host.replace(".", "_")),
                    kind="ip",
                    label=f"Unconfigured camera at {host}",
                    status="detected",
                    available=False,
                    message=(
                        "RTSP port is open but no stream URL or credentials are "
                        "configured, so this camera cannot be previewed. Add it to "
                        "IP_CAMERAS in .env to use it."
                    ),
                    host=host,
                    port=554,
                )
            )
        return devices

    def discover(self, force: bool = False) -> list[DeviceInfo]:
        with self._lock:
            fresh = (time.monotonic() - self._discovered_at) < settings.device_discovery_ttl_seconds
            if self._devices and fresh and not force:
                return list(self._devices)

        usb_devices = self._discover_usb()
        ip_devices = self._discover_ip()
        known_hosts = {d.host for d in ip_devices if d.host}
        detected = self._discover_unconfigured(known_hosts)

        devices = usb_devices + ip_devices + detected

        with self._lock:
            self._devices = devices
            self._discovered_at = time.monotonic()
        return list(devices)

    # ------------------------------------------------------------------ lookup

    def cached(self) -> list[DeviceInfo]:
        with self._lock:
            return list(self._devices)

    def get(self, device_id: str, discover_if_missing: bool = True) -> DeviceInfo | None:
        kind, key = parse_device_id(device_id)
        normalized = make_device_id(kind, key)

        for device in self.cached():
            if device.device_id == normalized:
                return device
        if not discover_if_missing:
            return None
        for device in self.discover():
            if device.device_id == normalized:
                return device
        return None

    def available_device_ids(self) -> list[str]:
        return [device.device_id for device in self.discover() if device.available]

    def invalidate(self) -> None:
        with self._lock:
            self._discovered_at = 0.0


camera_registry = CameraRegistry()
