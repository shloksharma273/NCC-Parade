from __future__ import annotations

import os
import socket


# ---------------------------------------------------------------------------
# Probe targets used to discover the machine's outbound interface IP.
# We try multiple destinations in case some are blocked (no internet, etc.).
# These are never actually contacted — a UDP connect() only sets the routing
# table lookup, no packets are sent.
# ---------------------------------------------------------------------------
_PROBE_TARGETS: list[tuple[str, int]] = [
    ("8.8.8.8", 80),        # Google DNS (internet)
    ("1.1.1.1", 80),        # Cloudflare DNS (internet)
    ("192.168.1.1", 80),    # Typical home-LAN gateway
    ("10.0.0.1", 80),       # Corporate/VPN gateway
    ("172.16.0.1", 80),     # Another common LAN range
]


def _udp_probe(target_ip: str, target_port: int) -> str | None:
    """Return the local IP that the OS would use to reach *target_ip*, or None."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.1)
            sock.connect((target_ip, target_port))
            ip = sock.getsockname()[0]
            # Reject loopback — we only want a real LAN/Ethernet address
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return None


def _all_interface_ips() -> list[str]:
    """Return every non-loopback IPv4 address assigned to any local interface."""
    ips: list[str] = []
    try:
        hostname = socket.gethostname()
        infos = socket.getaddrinfo(hostname, None, socket.AF_INET)
        for info in infos:
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return ips


def get_local_ip() -> str:
    """
    Return the best local IPv4 address for LAN access, in priority order:

    1. HOST_IP env variable — operator-pinned, always wins.
    2. UDP routing probe to several targets (works for Ethernet, Wi-Fi, VPN).
    3. Enumerate all interface IPs and pick the first non-loopback one.
    4. Fallback to 127.0.0.1 (same-machine access only).

    The UDP probe never sends actual packets; it only triggers a kernel
    routing-table lookup so the OS tells us which interface it would use.
    """
    # 1. Explicit override
    env_ip = os.getenv("HOST_IP", "").strip()
    if env_ip:
        return env_ip

    # 2. Routing-table probe — try multiple destinations
    for target_ip, target_port in _PROBE_TARGETS:
        ip = _udp_probe(target_ip, target_port)
        if ip:
            return ip

    # 3. Enumerate all interface IPs (catches Ethernet-only machines where
    #    all probe targets are unreachable, e.g. completely offline network)
    interface_ips = _all_interface_ips()
    if interface_ips:
        return interface_ips[0]

    # 4. Last-resort loopback — same-PC access still works
    return "127.0.0.1"
