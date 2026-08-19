"""Security headers audit endpoint."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.core.urls import safe_urlparse
from app.extraction.pipeline import fetch_and_extract_raw
from app.extraction.profiles import PROFILE_SECURITY
from app.extraction.tls import fetch_tls_details
from app.models.responses import SecurityHeadersResponse
from app.ratelimit.limiter import check_ip_rate_limit
from app.security.headers import verify_rapidapi_secret

router = APIRouter(tags=["Security Audit"])


@router.get(
    "/api/v1/security",
    response_model=SecurityHeadersResponse,
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_security_headers_endpoint(
    url: str = Query(..., description="The target URL to audit HTTP security headers"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header"),
    include_tls_details: bool = Query(
        False,
        description=(
            "Opt-in: perform a live TLS handshake to the target host's port 443 and return "
            "certificate issuer/subject/validity dates and negotiated TLS version as `tls_details`. "
            "Off by default — this is an extra network round-trip beyond the normal headers-only "
            "audit (which never opens a TLS connection itself, only reads headers already present "
            "on the page fetch), so it's opt-in to keep the default /security response fast. "
            "Never fails the request: an unreachable host, non-TLS port, or invalid/self-signed "
            "certificate results in `tls_details: null`, not an error."
        ),
    ),
):
    """
    Dedicated endpoint for HTTP Security Headers audit:
    Inspects HSTS, Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and calculates a percentage security score.
    Set `include_tls_details=true` to additionally perform a live TLS handshake and return certificate details (issuer, subject, validity dates, negotiated TLS version) — off by default to keep the base audit headers-only and fast.
    """
    data = await fetch_and_extract_raw(url, user_agent, profile=PROFILE_SECURITY)

    tls_details = None
    if include_tls_details:
        hostname = safe_urlparse(data["final_url"]).hostname
        if hostname:
            tls_details = await fetch_tls_details(hostname)

    return SecurityHeadersResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        bot_protection_detected=data.get("bot_protection_detected", False),
        redirect_count=data.get("redirect_count", 0),
        is_shortened_url=data.get("is_shortened_url", False),
        security_score_percentage=data["security_score_percentage"],
        security_headers=data["security_headers"],
        security_header_grades=data.get("security_header_grades", {}),
        tls_details=tls_details,
    )
