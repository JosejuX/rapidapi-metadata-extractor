"""Security headers audit endpoint."""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.security.headers import verify_rapidapi_secret
from app.ratelimit.limiter import check_ip_rate_limit
from app.extraction.pipeline import fetch_and_extract_raw
from app.models.responses import SecurityHeadersResponse

router = APIRouter(tags=["Security Audit"])


@router.get(
    "/api/v1/security",
    response_model=SecurityHeadersResponse,
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_security_headers_endpoint(
    url: str = Query(..., description="The target URL to audit HTTP security headers"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for HTTP Security Headers audit:
    Inspects HSTS, Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and calculates a percentage security score.
    """
    data = await fetch_and_extract_raw(url, user_agent)
    return SecurityHeadersResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        security_score_percentage=data["security_score_percentage"],
        security_headers=data["security_headers"]
    )
