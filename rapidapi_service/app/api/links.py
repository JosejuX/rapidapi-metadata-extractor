"""Hyperlink extraction/classification endpoint."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.extraction.pipeline import fetch_and_extract_raw
from app.extraction.profiles import PROFILE_LINKS
from app.models.responses import LinksResponse
from app.ratelimit.limiter import check_ip_rate_limit
from app.security.headers import verify_rapidapi_secret

router = APIRouter(tags=["Link Extractor"])


@router.get(
    "/api/v1/links",
    response_model=LinksResponse,
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_links_endpoint(
    url: str = Query(..., description="The target URL to extract and classify internal vs external hyperlinks"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for hyperlink extraction and domain classification:
    Categorizes all page links into internal links (same domain) and external links (third-party websites).
    """
    data = await fetch_and_extract_raw(url, user_agent, profile=PROFILE_LINKS)
    return LinksResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        bot_protection_detected=data.get("bot_protection_detected", False),
        redirect_count=data.get("redirect_count", 0),
        is_shortened_url=data.get("is_shortened_url", False),
        total_links_count=data["total_internal_count"] + data["total_external_count"],
        internal_links_count=data["total_internal_count"],
        external_links_count=data["total_external_count"],
        internal_links=data["internal_links"],
        external_links=data["external_links"]
    )
