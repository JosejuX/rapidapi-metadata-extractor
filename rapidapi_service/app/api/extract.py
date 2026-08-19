"""Full extractor endpoint (Plan section 12.1: /extract may run the whole pipeline)."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.extraction.pipeline import fetch_and_extract_raw
from app.models.responses import MetadataResponse
from app.ratelimit.limiter import check_ip_rate_limit
from app.security.headers import verify_rapidapi_secret

router = APIRouter(tags=["Full Extractor"])

# Maps a response field name to the extraction group(s) that compute it
# (Plan §12/§37: "fields no debe significar automáticamente 'hacer todo y
# luego borrar'"). `fields=detected_technologies` now runs exactly the same
# narrow pipeline as GET /api/v1/tech-stack instead of paying for the full
# pipeline and discarding everything else — and since both route through
# the same cache_key/profile machinery, they now share cache entries too.
# `quality` is deliberately excluded: it's a whole-response summary derived
# from metadata+jsonld+product+bot-protection+truncation signals together,
# not cleanly owned by one group, so requesting it still runs the full
# pipeline rather than under-computing an incomplete quality object.
_FIELD_TO_GROUPS = {
    "metadata": {"metadata"},
    "social_links": {"links_and_socials"},
    "contacts": {"contacts_emails"},
    "phone_details": {"contacts_emails"},
    "detected_technologies": {"tech"},
    "technology_details": {"tech"},
    "rss_feeds": {"jsonld"},
    "json_ld_schemas": {"jsonld"},
    "product_data": {"product"},
    "product_field_confidence": {"product"},
    "security_headers": {"security"},
    "security_score_percentage": {"security"},
    "security_header_grades": {"security"},
    "seo_score_percentage": {"seo"},
    "seo_passed_checks": {"seo"},
    "seo_warnings": {"seo"},
    "seo_checks": {"seo"},
    "internal_links": {"links_and_socials"},
    "external_links": {"links_and_socials"},
    "total_internal_count": {"links_and_socials"},
    "total_external_count": {"links_and_socials"},
    "word_count": {"markdown"},
    "reading_time_minutes": {"markdown"},
    "markdown_content": {"markdown"},
    # readability is computed by both the "seo" and "markdown" groups (Plan
    # competitive-differentiator #2) — "seo" is the cheaper of the two (no
    # markdown-tree conversion), so that's what a bare `fields=readability`
    # request runs.
    "readability": {"seo"},
}


@router.get(
    "/api/v1/extract",
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_metadata(
    url: str = Query(..., description="The target website URL to analyze (e.g. https://example.com)"),
    fields: Optional[str] = Query(None, description="Optional comma-separated list of keys to filter response (e.g. metadata,contacts) — only runs the extractors those fields actually need, same as calling the matching specialized endpoint"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Extract full metadata payload (<200ms with Rust ORJSON + IP-Pinned Anti-SSRF Shield + HTTP/2 streaming):
    - **SEO Metadata**: Title, description, OG image, favicon, canonical URL, language, author, theme color, H1 tags.
    - **Page Health Metrics**: Content length (bytes), image count, accessibility missing alt count, link count.
    - **Contacts**: Public email addresses and telephone numbers.
    - **Social Links**: Profiles on Twitter/X, LinkedIn, Instagram, Facebook, GitHub, YouTube, Telegram, TikTok.
    - **Technologies**: Precision context-aware CMS and framework signatures.
    - **SEO Audit**: Automated 14-point SEO diagnostic score & warnings.
    - **Link Extractor**: Categorized internal vs external hyperlinks.
    - **Structured Data**: Schema.org JSON-LD schemas.
    - **Feeds**: RSS/Atom feed discovery.
    - **Security**: HTTP security headers score & IP-Pinned Anti-SSRF Protection.
    - **AI Reader**: Clean Markdown article text, word count & reading time.

    Without `fields`, runs the complete pipeline. With `fields`, only runs
    the extractors needed for the requested keys — `fields=detected_technologies`
    is exactly as cheap as `GET /api/v1/tech-stack`.
    """
    if fields:
        allowed_keys = [f.strip() for f in fields.split(',') if f.strip()]
        if "quality" in allowed_keys:
            profile = None  # whole-response signal — run the full pipeline
        else:
            groups = set()
            for key in allowed_keys:
                groups |= _FIELD_TO_GROUPS.get(key, set())
            profile = frozenset(groups)  # empty if no requested key is recognized

        data = await fetch_and_extract_raw(url, user_agent, profile=profile)
        filtered_data = {k: v for k, v in data.items() if k in allowed_keys or k in ['url', 'final_url', 'status_code', 'execution_time_ms']}
        return filtered_data

    data = await fetch_and_extract_raw(url, user_agent)
    return MetadataResponse(**data)
