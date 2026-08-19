"""
DNS / WHOIS domain intelligence (competitive-differentiator #5).

Standalone lookups only — this module never touches the target's HTTP
content and is never given a full page fetch. GET /api/v1/domain (see
app/api/domain.py) resolves DNS records and WHOIS registration data
directly against a hostname; it doesn't open an HTTP connection to
arbitrary attacker-controlled response content, so it does not need the
SSRF-fetch machinery in app/fetcher/client.py.

WHOIS servers for many TLDs are flaky/rate-limited/slow (Plan feedback:
"many TLDs have flaky/rate-limited WHOIS servers") — a WHOIS failure must
never fail the whole request when DNS succeeded, so fetch_whois_info()
swallows every failure mode into `None` the same way app/extraction/tls.py
does for TLS handshake failures.
"""
import asyncio
from typing import Any, Dict, List, Optional

import dns.asyncresolver
import dns.exception
import whois

from app.core.logging import logger

DNS_TIMEOUT_SECONDS = 3.0
WHOIS_TIMEOUT_SECONDS = 5.0
_RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT")


async def _resolve_record(hostname: str, record_type: str) -> List[str]:
    """One record type. NXDOMAIN/no-answer/timeout/etc all just mean "this
    hostname doesn't have that record type" for our purposes — return an
    empty list rather than raising, so one missing record type (e.g. no MX
    on a domain with no mail) doesn't fail the other four."""
    try:
        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = DNS_TIMEOUT_SECONDS
        resolver.lifetime = DNS_TIMEOUT_SECONDS
        answer = await resolver.resolve(hostname, record_type)
        return [rdata.to_text() for rdata in answer]
    except dns.exception.DNSException as e:
        logger.info("DNS %s lookup found nothing for %s: %s", record_type, hostname, e)
        return []
    except Exception as e:
        logger.info("DNS %s lookup failed for %s: %s", record_type, hostname, e)
        return []


async def fetch_dns_records(hostname: str) -> Dict[str, List[str]]:
    """A/AAAA/MX/NS/TXT records, resolved concurrently. Always returns a
    dict with all five keys present (each an empty list on failure/absence)."""
    results = await asyncio.gather(*(_resolve_record(hostname, rt) for rt in _RECORD_TYPES))
    return dict(zip(_RECORD_TYPES, results))


def _first(value: Any) -> Any:
    """python-whois frequently returns a list for a field that's usually
    scalar (some registries report the same date/registrar multiple times
    across nested records) — take the first value consistently rather than
    leaking a sometimes-list-sometimes-scalar shape into the typed response."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _iso(value: Any) -> Optional[str]:
    value = _first(value)
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


def _blocking_whois_lookup(hostname: str) -> Optional[Dict[str, Any]]:
    """Blocking: python-whois shells out to a system `whois`-like TCP query
    and can hang on a slow/rate-limiting registry server — called only via
    fetch_whois_info()'s executor+timeout wrapper below. Any failure
    (unsupported TLD, no WHOIS server, parse error, ...) returns None."""
    try:
        w = whois.whois(hostname)
        if not w or not (w.get("domain_name") or w.get("registrar")):
            return None
        return {
            "registrar": _first(w.get("registrar")),
            "creation_date": _iso(w.get("creation_date")),
            "expiration_date": _iso(w.get("expiration_date")),
            "name_servers": [ns for ns in (w.get("name_servers") or []) if ns] if isinstance(w.get("name_servers"), list)
            else ([w["name_servers"]] if w.get("name_servers") else []),
        }
    except Exception as e:
        logger.info("WHOIS lookup failed for %s: %s", hostname, e)
        return None


async def fetch_whois_info(hostname: str) -> Optional[Dict[str, Any]]:
    """Async wrapper: the blocking lookup runs off the event loop in the
    default executor with a hard timeout. Returns None on any failure or
    timeout — never raises, so a flaky WHOIS server never fails the whole
    /api/v1/domain request when DNS already succeeded."""
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, _blocking_whois_lookup, hostname),
            timeout=WHOIS_TIMEOUT_SECONDS,
        )
    except Exception as e:
        logger.info("WHOIS lookup timed out for %s: %s", hostname, e)
        return None
