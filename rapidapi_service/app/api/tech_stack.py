"""Technology intelligence endpoint."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.extraction.pipeline import fetch_and_extract_raw
from app.extraction.profiles import PROFILE_TECH
from app.models.responses import TechStackResponse
from app.ratelimit.limiter import check_ip_rate_limit
from app.security.headers import verify_rapidapi_secret

router = APIRouter(tags=["Tech Stack"])


@router.get(
    "/api/v1/tech-stack",
    response_model=TechStackResponse,
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_tech_stack(
    url: str = Query(..., description="The target URL to inspect for CMS and technology stack signatures"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for technology intelligence & CMS auditing:
    Detects 100+ frameworks and CMS signatures with structural context-aware matching.
    """
    data = await fetch_and_extract_raw(url, user_agent, profile=PROFILE_TECH)
    return TechStackResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        detected_technologies=data["detected_technologies"],
        technology_details=data.get("technology_details", [])
    )
