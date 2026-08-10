"""Public contact-info discovery endpoint.

Deliberately not called "lead enrichment" in code/docs (Plan feedback: this
finds public contact *signals* on a page — emails, phones, social links —
it does not identify companies, people, roles, or verify anything. Real
lead enrichment is domain -> company identification -> people -> roles ->
verification, which is out of scope here; conflating the two oversells
what this endpoint actually does."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.extraction.pipeline import fetch_and_extract_raw
from app.extraction.profiles import PROFILE_CONTACTS
from app.models.responses import ContactsResponse
from app.ratelimit.limiter import check_ip_rate_limit
from app.security.headers import verify_rapidapi_secret

router = APIRouter(tags=["Contact Discovery"])


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
    Dedicated endpoint for public contact-signal discovery:
    Returns public emails, telephone numbers, and official social media profile URLs
    found on the page. This surfaces raw public signals, not verified company/people
    data — it does not identify who these belong to or confirm they're monitored.
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
