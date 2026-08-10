"""Lightweight link-preview endpoint (Plan section 12.2 — head_only fetch profile)."""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.security.headers import verify_rapidapi_secret
from app.ratelimit.limiter import check_ip_rate_limit
from app.extraction.pipeline import fetch_and_extract_raw
from app.models.responses import LinkPreviewResponse

router = APIRouter(tags=["Link Preview"])


@router.get(
    "/api/v1/link-preview",
    response_model=LinkPreviewResponse,
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_link_preview(
    url: str = Query(..., description="The target URL to generate link preview for"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Lightweight endpoint optimized for link preview cards (Social Cards / Unfurl):
    Returns title, description, og_image, favicon, favicon_high_res, site_name, and language.
    """
    data = await fetch_and_extract_raw(url, user_agent, head_only=True)
    meta = data["metadata"]
    return LinkPreviewResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        title=meta["title"],
        description=meta["description"],
        og_image=meta["og_image"],
        favicon=meta["favicon"],
        favicon_high_res=meta.get("favicon_high_res"),
        site_name=meta["site_name"],
        language=meta["language"]
    )
