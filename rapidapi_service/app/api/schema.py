"""Schema.org / JSON-LD structured data endpoint."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.extraction.pipeline import fetch_and_extract_raw
from app.extraction.profiles import PROFILE_SCHEMA
from app.models.responses import SchemaResponse
from app.ratelimit.limiter import check_ip_rate_limit
from app.security.headers import verify_rapidapi_secret

router = APIRouter(tags=["Structured Data"])


@router.get(
    "/api/v1/schema",
    response_model=SchemaResponse,
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_schema(
    url: str = Query(..., description="The target URL to extract Schema.org JSON-LD structured data from"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for Schema.org & JSON-LD structured data extraction:
    Returns parsed product pricing, e-commerce reviews, article schemas, event details, and organization metadata.
    """
    data = await fetch_and_extract_raw(url, user_agent, profile=PROFILE_SCHEMA)
    schemas = data["json_ld_schemas"]
    return SchemaResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        json_ld_count=len(schemas),
        json_ld_schemas=schemas
    )
