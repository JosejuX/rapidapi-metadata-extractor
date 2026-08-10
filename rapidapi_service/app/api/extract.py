"""Full extractor endpoint (Plan section 12.1: /extract may run the whole pipeline)."""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.security.headers import verify_rapidapi_secret
from app.ratelimit.limiter import check_ip_rate_limit
from app.extraction.pipeline import fetch_and_extract_raw
from app.models.responses import MetadataResponse

router = APIRouter(tags=["Full Extractor"])


@router.get(
    "/api/v1/extract",
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_metadata(
    url: str = Query(..., description="The target website URL to analyze (e.g. https://example.com)"),
    fields: Optional[str] = Query(None, description="Optional comma-separated list of keys to filter response (e.g. metadata,contacts)"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Extract full metadata payload (<200ms with Rust ORJSON + IP-Pinned Anti-SSRF Shield + HTTP/2 streaming):
    - **SEO Metadata**: Title, description, OG image, favicon, canonical URL, language, author, theme color, H1 tags.
    - **Page Health Metrics**: Content length (bytes), image count, accessibility missing alt count, link count.
    - **Contacts**: Public email addresses and telephone numbers.
    - **Social Links**: Profiles on Twitter/X, LinkedIn, Instagram, Facebook, GitHub, YouTube, Telegram, TikTok.
    - **Technologies**: Precision context-aware CMS and framework signatures.
    - **SEO Audit**: Automated 8-point SEO diagnostic score & warnings.
    - **Link Extractor**: Categorized internal vs external hyperlinks.
    - **Structured Data**: Schema.org JSON-LD schemas.
    - **Feeds**: RSS/Atom feed discovery.
    - **Security**: HTTP security headers score & IP-Pinned Anti-SSRF Protection.
    - **AI Reader**: Clean Markdown article text, word count & reading time.
    """
    data = await fetch_and_extract_raw(url, user_agent)

    if fields:
        allowed_keys = [f.strip() for f in fields.split(',') if f.strip()]
        filtered_data = {k: v for k, v in data.items() if k in allowed_keys or k in ['url', 'final_url', 'status_code', 'execution_time_ms']}
        return filtered_data

    return MetadataResponse(**data)
