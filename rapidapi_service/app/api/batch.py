"""Batch URL processing endpoint (competitive-differentiator #3).

Runs a lightweight PROFILE_LINK_PREVIEW extraction (title/description/
og_image/favicon/site_name/language — same narrow profile as
GET /api/v1/link-preview, not the full pipeline) over up to MAX_BATCH_SIZE
urls per request. One failing URL must never take down the rest of the
batch: each item runs through asyncio.gather(..., return_exceptions=True)
and is reported individually as {"success": true, ...} or
{"success": false, "error": ...}.

Rate limiting: a batch of N URLs does exactly N upstream fetches, so it
must count as N requests against check_ip_rate_limit — not 1 — otherwise a
client could bypass the per-minute limit entirely by moving traffic through
/batch. check_ip_rate_limit is therefore called manually once per URL
(rather than declared once via `dependencies=[Depends(...)]`, which would
only count the batch call itself as a single request) before any fetching
starts, so an over-limit batch is rejected up front rather than partially
processed.
"""
import asyncio
from typing import List

from fastapi import APIRouter, Depends, Request, Response

from app.api.common import COMMON_RESPONSES
from app.core.errors import BATCH_SIZE_EXCEEDED, INVALID_URL, AppError
from app.extraction.pipeline import fetch_and_extract_raw
from app.extraction.profiles import PROFILE_LINK_PREVIEW
from app.models.responses import BatchItemResult, BatchRequest, BatchResponse
from app.ratelimit.limiter import check_ip_rate_limit
from app.security.headers import verify_rapidapi_secret

router = APIRouter(tags=["Batch Processing"])

MAX_BATCH_SIZE = 10


async def _fetch_one_raw(url: str):
    """Thin wrapper so a per-URL AppError/exception is a normal return value
    for asyncio.gather(return_exceptions=True) to collect below, tagged with
    which url it came from (fetch_and_extract_raw's own exceptions don't
    carry the caller's original url string once normalization happens)."""
    return await fetch_and_extract_raw(url, profile=PROFILE_LINK_PREVIEW)


@router.post(
    "/api/v1/batch",
    response_model=BatchResponse,
    responses=COMMON_RESPONSES,
    dependencies=[Depends(verify_rapidapi_secret)],
)
async def batch_extract(request: Request, response: Response, body: BatchRequest):
    """
    Batch URL processing: run a lightweight link-preview extraction (title, description,
    OG image, favicon, site name, language) over up to 10 URLs in one request. Each URL is
    fetched independently — one failing URL returns `{"success": false, "error": ...}` for
    that item without affecting the others. Counts as N requests (one per URL) against the
    per-IP rate limit, not one.
    """
    if not body.urls:
        raise AppError(status_code=400, code=INVALID_URL, detail="Batch request must include at least one URL.")
    if len(body.urls) > MAX_BATCH_SIZE:
        raise AppError(
            status_code=400,
            code=BATCH_SIZE_EXCEEDED,
            detail=f"Batch request exceeds the maximum of {MAX_BATCH_SIZE} URLs (got {len(body.urls)}).",
        )

    # A batch of N URLs does N upstream fetches — count as N against the
    # per-IP rate limit up front, before any fetching starts, so an
    # over-limit batch is rejected outright rather than partially processed.
    for _ in body.urls:
        await check_ip_rate_limit(request, response)

    raw_results = await asyncio.gather(
        *(_fetch_one_raw(u) for u in body.urls),
        return_exceptions=True,
    )

    items: List[BatchItemResult] = []
    for url, result in zip(body.urls, raw_results):
        if isinstance(result, AppError):
            items.append(BatchItemResult(url=url, success=False, error=result.detail))
        elif isinstance(result, BaseException):
            items.append(BatchItemResult(url=url, success=False, error=str(result)))
        else:
            meta = result["metadata"]
            items.append(BatchItemResult(
                url=result["url"],
                success=True,
                error=None,
                final_url=result["final_url"],
                status_code=result["status_code"],
                title=meta.get("title"),
                description=meta.get("description"),
                og_image=meta.get("og_image"),
                favicon=meta.get("favicon"),
                site_name=meta.get("site_name"),
                language=meta.get("language"),
                redirect_count=result.get("redirect_count", 0),
                is_shortened_url=result.get("is_shortened_url", False),
            ))

    succeeded = sum(1 for i in items if i.success)
    return BatchResponse(total=len(items), succeeded=succeeded, failed=len(items) - succeeded, results=items)
