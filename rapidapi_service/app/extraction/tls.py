"""
Best-effort TLS/SSL certificate inspection (competitive-differentiator #4).

Opt-in ONLY, via `include_tls_details=true` on GET /api/v1/security (see
app/api/security.py). This requires its own live TLS handshake to the
target host — an extra network round-trip beyond the existing
resp_headers-only /security path, which app/extraction/profiles.py's
"security" group docstring documents as deliberately not needing any extra
fetch ("the biggest single win: /security skips HTML parsing entirely").
This module must never run unless explicitly requested, and every failure
mode here is swallowed into `None` rather than raised — this is a
best-effort enrichment, not a new way for /security to fail.
"""
import asyncio
import socket
import ssl
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.logging import logger

TLS_HANDSHAKE_TIMEOUT_SECONDS = 3.0
_ASN1_DATE_FORMAT = "%b %d %H:%M:%S %Y %Z"


def _parse_asn1_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, _ASN1_DATE_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _cert_name_to_str(name_tuple) -> Optional[str]:
    """getpeercert()'s issuer/subject shape: a tuple of tuples of (key,
    value) pairs, e.g. ((('countryName', 'US'),), (('commonName', 'x'),))."""
    if not name_tuple:
        return None
    try:
        parts = [f"{key}={value}" for rdn in name_tuple for key, value in rdn]
        return ", ".join(parts) if parts else None
    except (TypeError, ValueError):
        return None


def _blocking_fetch_tls_details(hostname: str, port: int = 443) -> Optional[Dict[str, Any]]:
    """Blocking: opens a real TLS connection, reads the peer certificate.
    Every failure (timeout, connection refused, non-TLS host, self-signed/
    expired/untrusted cert, DNS failure, ...) is caught here and returns
    None — called only via fetch_tls_details()'s executor wrapper below."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=TLS_HANDSHAKE_TIMEOUT_SECONDS) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                tls_version = ssock.version()
    except Exception as e:
        logger.info("TLS certificate lookup failed for %s: %s", hostname, e)
        return None

    if not cert:
        return None

    not_before_dt = _parse_asn1_date(cert.get("notBefore"))
    not_after_dt = _parse_asn1_date(cert.get("notAfter"))
    is_expired = bool(not_after_dt and datetime.now(timezone.utc) >= not_after_dt)

    return {
        "issuer": _cert_name_to_str(cert.get("issuer")),
        "subject": _cert_name_to_str(cert.get("subject")),
        "valid_from": not_before_dt.date().isoformat() if not_before_dt else None,
        "valid_until": not_after_dt.date().isoformat() if not_after_dt else None,
        "tls_version": tls_version,
        "is_expired": is_expired,
    }


async def fetch_tls_details(hostname: str, port: int = 443) -> Optional[Dict[str, Any]]:
    """Async wrapper: the actual handshake is blocking ssl/socket code, run
    off the event loop in the default executor with a short timeout.
    Returns None on any failure — never raises."""
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, _blocking_fetch_tls_details, hostname, port),
            timeout=TLS_HANDSHAKE_TIMEOUT_SECONDS + 1.0,
        )
    except Exception as e:
        logger.info("TLS certificate lookup timed out for %s: %s", hostname, e)
        return None
