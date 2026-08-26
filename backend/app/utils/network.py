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


def local_ipv4_addresses() -> list[str]:
    """Every non-loopback IPv4 address on this machine."""
    addresses = set(_all_interface_ips())
    for target_ip, target_port in _PROBE_TARGETS:
        ip = _udp_probe(target_ip, target_port)
        if ip:
            addresses.add(ip)
    return sorted(addresses)


def _same_slash24(a: str, b: str) -> bool:
    return a.rsplit(".", 1)[0] == b.rsplit(".", 1)[0]


def connect_best_effort(host: str, port: int, timeout: float) -> socket.socket:
    """Open a TCP connection, trying each local interface that could reach *host*.

    On a multi-homed PC with two NICs in the same subnet — a Wi-Fi network and a
    camera on Ethernet both numbered 192.168.1.x — the default route is a
    coin flip, and half the time the connection leaves via the interface that
    cannot see the camera and simply times out. So when the default route fails,
    retry explicitly bound to each local address on the target's subnet.

    Raises OSError if no interface can reach the target.
    """
    last_error: OSError | None = None

    def attempt(source_ip: str | None) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(timeout)
            if source_ip:
                sock.bind((source_ip, 0))
            sock.connect((host, port))
            return sock
        except OSError:
            sock.close()
            raise

    try:
        return attempt(None)
    except OSError as exc:
        last_error = exc

    for source_ip in local_ipv4_addresses():
        if source_ip.startswith("169.254.") or not _same_slash24(source_ip, host):
            continue
        try:
            return attempt(source_ip)
        except OSError as exc:
            last_error = exc

    raise last_error if last_error else OSError(f"Could not connect to {host}:{port}")


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
