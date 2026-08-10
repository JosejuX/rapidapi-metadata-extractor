"""
IP-Pinned Anti-SSRF Shield (Plan section 4). Prevents DNS Rebinding / TOCTOU
race conditions: resolve DNS hostname ONCE, validate every resolved IP against
private/loopback/reserved/cloud-metadata ranges, then connect to the pinned IP
with the original Host/SNI preserved.
"""
import socket
import asyncio
import ipaddress
import urllib.parse
from typing import Set, Tuple

from app.core.logging import logger
from app.core.urls import normalize_and_validate_url
from app.core.errors import AppError, INVALID_URL, SSRF_BLOCKED, DNS_FAILURE
from app.fetcher.dns import dns_cache
from app.cache.singleflight import single_flight
from app.observability import metrics

# §4.8: Block known internal/reserved hostnames by name (defense-in-depth before DNS)
_BLOCKED_HOSTNAME_LITERALS: Set[str] = {
    "localhost", "127.0.0.1", "::1", "0.0.0.0", "169.254.169.254",
    "metadata.google.internal", "metadata", "internal", "local"
}
_BLOCKED_HOSTNAME_SUFFIXES = (".localhost", ".local", ".internal", ".example", ".test", ".invalid")

# §4.2+4.3: Extra ranges beyond ipaddress' built-in private/loopback/etc. checks:
# benchmarking (198.18.0.0/15), documentation (192.0.2.0/24, 198.51.100.0/24,
# 203.0.113.0/24), carrier-grade NAT (100.64.0.0/10), shared address (192.0.0.0/24).
_EXTRA_BLOCKED_NETWORKS = [
    ipaddress.ip_network("100.64.0.0/10"),   # Carrier-grade NAT (RFC 6598)
    ipaddress.ip_network("192.0.0.0/24"),    # IETF Protocol Assignments (RFC 6890)
    ipaddress.ip_network("192.0.2.0/24"),    # Documentation (TEST-NET-1)
    ipaddress.ip_network("198.18.0.0/15"),   # Benchmarking (RFC 2544)
    ipaddress.ip_network("198.51.100.0/24"), # Documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),  # Documentation (TEST-NET-3)
    ipaddress.ip_network("240.0.0.0/4"),     # Reserved (RFC 1112)
]

ALLOWED_PORTS = (80, 443, 8080, 8443)


async def validate_url_ssrf(url: str) -> Tuple[str, str]:
    """
    Async IP-Pinned Anti-SSRF Shield.
    Resolves DNS hostname ONCE via asyncio.to_thread (non-blocking),
    validates IP against private/loopback/cloud-metadata ranges,
    and returns (ip_pinned_url, original_hostname) to eliminate DNS Rebinding.
    """
    url = normalize_and_validate_url(url)
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()

    hostname = parsed.hostname
    if not hostname:
        raise AppError(
            status_code=400,
            code=INVALID_URL,
            detail="SSRF Protection: Invalid or missing domain hostname."
        )

    hostname_lower = hostname.lower()

    if hostname_lower in _BLOCKED_HOSTNAME_LITERALS or hostname_lower.endswith(_BLOCKED_HOSTNAME_SUFFIXES):
        logger.warning("SSRF block — blocked hostname by name: %s", hostname)
        metrics.SSRF_BLOCKS_TOTAL.inc()
        raise AppError(
            status_code=400,
            code=SSRF_BLOCKED,
            detail="SSRF Protection: Access to loopback, internal, or cloud metadata hostnames is forbidden."
        )

    port = parsed.port or (443 if scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        metrics.SSRF_BLOCKS_TOTAL.inc()
        raise AppError(
            status_code=400,
            code=SSRF_BLOCKED,
            detail=f"SSRF Protection: Port {port} is not allowed. Only standard web ports (80, 443, 8080, 8443) are permitted."
        )

    # 1. Resolve DNS ONCE (non-blocking) with 5-minute TTL DNS Caching.
    # §5 DNS single-flight: if N concurrent requests hit the same hostname
    # while nothing is cached yet, only one actually calls getaddrinfo() —
    # the rest coalesce onto that lookup instead of firing N resolutions.
    dns_key = (hostname, port)
    if dns_key in dns_cache:
        addr_info = dns_cache[dns_key]
    else:
        async def _resolve():
            try:
                result = await asyncio.to_thread(
                    socket.getaddrinfo, hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM
                )
                dns_cache[dns_key] = result
                return result
            except socket.gaierror:
                metrics.DNS_FAILURES_TOTAL.inc()
                raise AppError(
                    status_code=400,
                    code=DNS_FAILURE,
                    detail=f"SSRF Protection: Unable to resolve hostname '{hostname}' via DNS."
                )

        addr_info = await single_flight(f"dns:{hostname}:{port}", _resolve)

    # §4.2+4.3: Validate ALL resolved IPs — if ANY is private/reserved, block the host.
    resolved_ip = None
    for item in addr_info:
        ip_str = item[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            is_dangerous = (
                ip_obj.is_private or
                ip_obj.is_loopback or
                ip_obj.is_link_local or
                ip_obj.is_multicast or
                ip_obj.is_reserved or
                ip_obj.is_unspecified or
                str(ip_obj) == "169.254.169.254" or
                any(ip_obj in net for net in _EXTRA_BLOCKED_NETWORKS)
            )
            if is_dangerous:
                logger.warning("SSRF block — dangerous IP: %s -> %s", hostname, ip_str)
                metrics.SSRF_BLOCKS_TOTAL.inc()
                raise AppError(
                    status_code=400,
                    code=SSRF_BLOCKED,
                    detail=f"SSRF Protection: Target domain resolves to private/internal/reserved IP address, which is forbidden."
                )
            if not resolved_ip:
                resolved_ip = ip_str
        except ValueError:
            pass

    if not resolved_ip:
        metrics.SSRF_BLOCKS_TOTAL.inc()
        raise AppError(
            status_code=400,
            code=SSRF_BLOCKED,
            detail="SSRF Protection: No valid public IP address found for target domain."
        )

    # 3. Construct IP-Pinned Connection URL (eliminates second DNS resolution)
    path_and_query = parsed.path or "/"
    if parsed.query:
        path_and_query += "?" + parsed.query

    formatted_ip = f"[{resolved_ip}]" if ":" in resolved_ip else resolved_ip
    ip_pinned_url = f"{scheme}://{formatted_ip}:{port}{path_and_query}"

    return ip_pinned_url, hostname
