"""SEO diagnostic audit endpoint."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.extraction.pipeline import fetch_and_extract_raw
from app.extraction.profiles import PROFILE_SEO
from app.models.responses import SeoAuditResponse
from app.ratelimit.limiter import check_ip_rate_limit
from app.security.headers import verify_rapidapi_secret

router = APIRouter(tags=["SEO Audit"])


@router.get(
    "/api/v1/seo-audit",
    response_model=SeoAuditResponse,
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_seo_audit(
    url: str = Query(..., description="The target URL to perform automated 14-point SEO diagnostic audit"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for automated SEO diagnostic audit:
    Evaluates Title tag, Meta Description, Canonical URL, H1 heading, OpenGraph image, Favicon, Image ALT coverage,
    HTTPS security, lang attribute, viewport, indexability, multiple-H1, Twitter Card, and structured data.
    """
    data = await fetch_and_extract_raw(url, user_agent, profile=PROFILE_SEO)
    return SeoAuditResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        bot_protection_detected=data.get("bot_protection_detected", False),
        seo_score_percentage=data["seo_score_percentage"],
        passed_checks=data["seo_passed_checks"],
        warnings=data["seo_warnings"],
        checks=data.get("seo_checks", [])
    )
