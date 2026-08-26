"""Authenticated RTSP probing, used to validate camera credentials and paths.

OpenCV can only tell us "the stream did not open", which is useless for fixing a
misconfigured camera — wrong password and wrong stream path look identical. A
raw RTSP ``DESCRIBE`` distinguishes them:

* ``401`` after we present credentials  -> credentials are wrong
* ``404`` / ``455``                     -> credentials fine, this path is wrong
* ``200``                               -> credentials and path both good

It is also far quicker than starting FFmpeg once per candidate path.
"""

from __future__ import annotations

import base64
import hashlib
import socket
from dataclasses import dataclass
from urllib.parse import quote

from ..utils.network import connect_best_effort

CRLF = "\r\n"

# Ordered by likelihood. CP Plus / Dahua first, since that family is the most
# common on this deployment, then Hikvision and other widespread schemes.
CANDIDATE_PATHS: list[tuple[str, str, str]] = [
    ("video/live?channel=1&subtype=0", "video/live?channel=1&subtype=1", "CP Plus (video/live)"),
    ("cam/realmonitor?channel=1&subtype=0", "cam/realmonitor?channel=1&subtype=1", "CP Plus / Dahua"),
    ("Streaming/Channels/101", "Streaming/Channels/102", "Hikvision"),
    ("live/ch00_0", "live/ch00_1", "Generic (ch00)"),
    ("h264/ch1/main/av_stream", "h264/ch1/sub/av_stream", "Hikvision (legacy)"),
    ("main", "sub", "Secureye / generic"),
    ("stream1", "stream2", "Generic (stream)"),
    ("11", "12", "Generic (numeric)"),
    ("live", "live", "Generic (live)"),
    ("video1", "video2", "Generic (video)"),
]


@dataclass
class ProbeResult:
    ok: bool
    status_code: int | None
    outcome: str  # "ok" | "bad_credentials" | "path_not_found" | "no_response" | "error"
    detail: str


def _parse_challenge(header: str) -> dict[str, str]:
    """Pull key="value" pairs out of a WWW-Authenticate header."""
    fields: dict[str, str] = {}
    body = header.split(" ", 1)[1] if " " in header else ""
    for part in body.split(","):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        fields[key.strip().lower()] = value.strip().strip('"')
    return fields


def _digest_header(username: str, password: str, method: str, uri: str, challenge: dict) -> str:
    realm = challenge.get("realm", "")
    nonce = challenge.get("nonce", "")
    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
    return (
        f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
        f'uri="{uri}", response="{response}"'
    )


def _basic_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def _request(sock: socket.socket, method: str, uri: str, cseq: int, auth: str | None) -> str:
    lines = [
        f"{method} {uri} RTSP/1.0",
        f"CSeq: {cseq}",
        "User-Agent: DrillServer/1.0",
        "Accept: application/sdp",
    ]
    if auth:
        lines.append(f"Authorization: {auth}")
    sock.sendall((CRLF.join(lines) + CRLF + CRLF).encode())
    chunks = []
    while True:
        try:
            data = sock.recv(4096)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
        blob = b"".join(chunks)
        if b"\r\n\r\n" in blob:
            break
    return b"".join(chunks).decode("latin-1", "replace")


def _status_of(reply: str) -> int | None:
    first = reply.split(CRLF, 1)[0]
    parts = first.split()
    if len(parts) > 1 and parts[1].isdigit():
        return int(parts[1])
    return None


def describe(
    host: str,
    port: int,
    path: str,
    username: str,
    password: str,
    timeout: float = 4.0,
) -> ProbeResult:
    """Send an authenticated DESCRIBE for one stream path."""
    uri = f"rtsp://{host}:{port}/{path.lstrip('/')}"
    try:
        # Not socket.create_connection: on a machine with two NICs in the camera's
        # subnet the default route may not reach it. See connect_best_effort.
        with connect_best_effort(host, port, timeout) as sock:
            sock.settimeout(timeout)

            reply = _request(sock, "DESCRIBE", uri, 1, None)
            status = _status_of(reply)
            if status is None:
                return ProbeResult(False, None, "no_response", "Camera did not answer RTSP.")

            if status == 401:
                header = next(
                    (
                        line
                        for line in reply.split(CRLF)
                        if line.lower().startswith("www-authenticate:")
                    ),
                    "",
                )
                challenge = _parse_challenge(header.split(":", 1)[1].strip()) if ":" in header else {}
                scheme = (
                    header.split(":", 1)[1].strip().split(" ", 1)[0].lower() if ":" in header else ""
                )
                if scheme == "digest":
                    auth = _digest_header(username, password, "DESCRIBE", uri, challenge)
                else:
                    auth = _basic_header(username, password)

                reply = _request(sock, "DESCRIBE", uri, 2, auth)
                status = _status_of(reply)

            if status == 200:
                return ProbeResult(True, 200, "ok", "Stream is available.")
            if status in (401, 403):
                return ProbeResult(
                    False, status, "bad_credentials", "Camera rejected the username or password."
                )
            if status in (404, 455, 451):
                return ProbeResult(
                    False, status, "path_not_found", "Credentials accepted but this stream path is wrong."
                )
            return ProbeResult(False, status, "error", f"Camera answered RTSP {status}.")
    except OSError as exc:
        return ProbeResult(False, None, "no_response", f"Could not reach {host}:{port} ({exc}).")


def find_working_paths(
    host: str,
    port: int,
    username: str,
    password: str,
    timeout: float = 4.0,
) -> tuple[str | None, str | None, str | None, ProbeResult]:
    """Discover which stream paths this camera actually serves.

    Returns ``(main_path, sub_path, family_label, last_result)``. Stops at the
    first family whose main stream answers 200, so a correctly guessed vendor
    costs a single round trip. Bad credentials abort immediately — trying every
    path with a wrong password would just repeat the same 401.
    """
    last = ProbeResult(False, None, "no_response", "No probe was attempted.")

    for main_path, sub_path, family in CANDIDATE_PATHS:
        result = describe(host, port, main_path, username, password, timeout)
        last = result
        if result.outcome == "bad_credentials":
            return None, None, None, result
        if result.outcome == "no_response":
            return None, None, None, result
        if result.ok:
            sub_result = describe(host, port, sub_path, username, password, timeout)
            return main_path, (sub_path if sub_result.ok else None), family, result

    return None, None, None, last


def build_rtsp_url(host: str, port: int, username: str, password: str, path: str) -> str:
    user = quote(username, safe="")
    pwd = quote(password, safe="")
    credentials = f"{user}:{pwd}@" if user or pwd else ""
    return f"rtsp://{credentials}{host}:{port}/{path.lstrip('/')}"
