"""Backs the embedded homepage playground only — not a public API endpoint.

Every real `/api/v1/*` endpoint requires `X-RapidAPI-Proxy-Secret` so requests
can't bypass the RapidAPI marketplace by hitting this origin directly. The
homepage playground is a same-origin browser demo with no API key, so it
can't send that header without shipping the secret in public JS — which
would let anyone read it from view-source and bypass the paid API entirely.

Instead this route runs the same pipeline with no secret requirement, is
excluded from the OpenAPI schema so it's never advertised as a real
endpoint, and relies on the same per-IP rate limiter as everything else to
bound abuse.
"""
from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.extraction.pipeline import fetch_and_extract_raw
from app.models.responses import MetadataResponse
from app.ratelimit.limiter import check_ip_rate_limit

router = APIRouter(include_in_schema=False)


@router.get(
    "/demo/extract",
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit)],
)
async def demo_extract(url: str = Query(..., description="Target URL for the homepage playground demo")):
    data = await fetch_and_extract_raw(url, None)
    return MetadataResponse(**data)
