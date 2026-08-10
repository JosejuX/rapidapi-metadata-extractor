"""Lead-generation contacts endpoint."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.extraction.pipeline import fetch_and_extract_raw
from app.extraction.profiles import PROFILE_CONTACTS
from app.models.responses import ContactsResponse
from app.ratelimit.limiter import check_ip_rate_limit
from app.security.headers import verify_rapidapi_secret

router = APIRouter(tags=["Lead Generation"])


@router.get(
    "/api/v1/contacts",
    response_model=ContactsResponse,
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_contacts(
    url: str = Query(..., description="The target URL to extract contact information and social handles from"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for lead enrichment & B2B prospecting:
    Returns public emails, telephone numbers, and official social media profile URLs.
    """
    data = await fetch_and_extract_raw(url, user_agent, profile=PROFILE_CONTACTS)
    contacts = data["contacts"]
    return ContactsResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        bot_protection_detected=data.get("bot_protection_detected", False),
        emails=contacts["emails"],
        phones=contacts["phones"],
        phone_details=data.get("phone_details", []),
        social_links=data["social_links"]
    )
