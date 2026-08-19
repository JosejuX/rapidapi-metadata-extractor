"""DNS / WHOIS domain intelligence endpoint (competitive-differentiator #5).

Deliberately standalone: this endpoint never fetches the target's page at
all (no HTTP GET to the target, no HTML parse) — only DNS record resolution
and a WHOIS registration lookup against the hostname. Because there's no
page fetch, it doesn't need the SSRF-fetch machinery in
app/fetcher/client.py (IP-pinning, redirect following, byte streaming,
content-type gating all exist to safely fetch and parse HTML — none of that
applies to a DNS/WHOIS-only lookup), but it still runs the same URL
normalization/validation as every other endpoint so garbage input is
rejected the same way.
"""
import asyncio
import time

from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.core.errors import INVALID_URL, AppError
from app.core.urls import normalize_and_validate_url, safe_urlparse
from app.extraction.domain_intel import fetch_dns_records, fetch_whois_info
from app.models.responses import DnsRecords, DomainInfoResponse, WhoisInfo
from app.ratelimit.limiter import check_ip_rate_limit
from app.security.headers import verify_rapidapi_secret

router = APIRouter(tags=["Domain Intelligence"])


@router.get(
    "/api/v1/domain",
    response_model=DomainInfoResponse,
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_domain_intel(
    url: str = Query(..., description="The target URL to look up DNS records and WHOIS registration data for — only the hostname is used, the page itself is never fetched"),
):
    """
    Dedicated endpoint for DNS / WHOIS domain intelligence:
    Resolves A, AAAA, MX, NS, and TXT DNS records, plus registrar/creation_date/expiration_date
    WHOIS registration data, for the target URL's hostname. Never fetches the page itself —
    no HTTP GET, no HTML parsing, DNS/WHOIS lookups only. WHOIS servers are flaky/rate-limited
    for many TLDs; a WHOIS failure returns `whois_info: null` rather than failing the request
    when DNS already succeeded.
    """
    start_time = time.time()

    validated_url = normalize_and_validate_url(url)
    hostname = safe_urlparse(validated_url).hostname
    if not hostname:
        raise AppError(
            status_code=400,
            code=INVALID_URL,
            detail="SSRF Protection: Invalid or missing domain hostname."
        )

    dns_records, whois_info = await asyncio.gather(
        fetch_dns_records(hostname),
        fetch_whois_info(hostname),
    )

    return DomainInfoResponse(
        url=url,
        hostname=hostname,
        execution_time_ms=round((time.time() - start_time) * 1000, 2),
        dns_records=DnsRecords(**dns_records),
        whois_info=WhoisInfo(**whois_info) if whois_info else None,
    )
