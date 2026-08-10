"""
Extraction pipeline orchestrator (Plan section 11): parse the HTML ONCE, then
run every extractor against the same tree, single-pass where the original
code did. This is the direct replacement for the old fetch_and_extract_raw
monolith — same cache semantics, same field names, same ordering constraints
(markdown extraction mutates the tree via strip_tags and must run LAST).
"""
import time
from typing import Any, Dict, Optional

from selectolax.parser import HTMLParser

from app.core.urls import normalize_and_validate_url
from app.core.errors import AppError
from app.cache.l1 import cache
from app.cache.keys import build_cache_key
from app.cache.singleflight import single_flight
from app.cache.negative import get_cached_negative, maybe_cache_negative
from app.core.logging import logger
from app.observability import metrics
from app.fetcher.client import fetch_raw_page, sanitize_user_agent

from app.extraction.metadata import extract_metadata_fields
from app.extraction.links import extract_links_and_socials
from app.extraction.contacts import extract_emails
from app.extraction.tech import detect_technologies_detailed, names_in_signature_order
from app.extraction.jsonld import extract_json_ld, extract_rss_feeds
from app.extraction.product import extract_product_data
from app.extraction.security import extract_security_headers
from app.extraction.seo import run_seo_audit
from app.extraction.markdown import html_to_markdown_clean, extract_summary_and_keywords


async def fetch_and_extract_raw(url: str, user_agent: Optional[str] = None, head_only: bool = False) -> Dict[str, Any]:
    url = normalize_and_validate_url(url)
    clean_ua = sanitize_user_agent(user_agent)

    cache_key = build_cache_key(url, clean_ua, head_only, user_agent)

    if cache_key in cache:
        cached_data = cache[cache_key].copy()
        cached_data["execution_time_ms"] = 0.01
        logger.info("Cache hit: %s", cache_key)
        metrics.CACHE_HITS_TOTAL.inc()
        return cached_data

    # §6.5 negative-result cache: a target that just failed (DNS/timeout/5xx)
    # fails fast for a short TTL instead of repeating the same expensive
    # network attempt for every request that hits it during an outage.
    cached_failure = get_cached_negative(cache_key)
    if cached_failure is not None:
        logger.info("Negative cache hit: %s (code=%s)", cache_key, cached_failure.code)
        metrics.CACHE_STALE_HITS_TOTAL.inc()
        raise cached_failure

    metrics.CACHE_MISSES_TOTAL.inc()

    # §6.7/§52 single-flight: N concurrent requests for the same cache_key
    # while a fetch+extract is already in progress share that one result
    # instead of triggering N upstream fetches.
    return await single_flight(cache_key, lambda: _fetch_and_extract_uncached(url, user_agent, head_only, cache_key))


async def _fetch_and_extract_uncached(url: str, user_agent: Optional[str], head_only: bool, cache_key: str) -> Dict[str, Any]:
    start_time = time.time()
    try:
        fetched = await fetch_raw_page(url, user_agent, head_only)
    except AppError as e:
        maybe_cache_negative(cache_key, e)
        raise
    html_content = fetched["html_content"]
    raw_bytes = fetched["raw_bytes"]
    status_code = fetched["status_code"]
    final_url = fetched["final_url"]
    resp_headers = fetched["resp_headers"]
    bytes_downloaded = fetched["bytes_downloaded"]
    content_truncated = fetched["content_truncated"]

    # ONE HTML parse — every extractor below runs against this same tree.
    tree = HTMLParser(html_content)

    # a[href] is queried exactly once and shared between metadata.links_count
    # and the single-pass link/social/mailto/tel classifier below (Plan §11/§64).
    a_nodes = tree.css('a[href]')

    metadata = extract_metadata_fields(tree, final_url, resp_headers, links_count=len(a_nodes))

    link_data = extract_links_and_socials(a_nodes, final_url)
    social_links = link_data["social_links"]
    internal_links = link_data["internal_links"]
    external_links = link_data["external_links"]
    mailto_emails = link_data["mailto_emails"]
    tel_phones = link_data["tel_phones"]

    # Second parse for plain-text extraction (emails, keyword/summary NLP) —
    # matches the pre-refactor behavior exactly. Collapsing this into a single
    # parse is a real optimization opportunity (Plan §11/§60) but is a
    # performance change, not a module move, so it's left for a later phase.
    clean_tree = HTMLParser(html_content)
    clean_tree.strip_tags(["script", "style", "code", "noscript", "svg"])
    body_txt = clean_tree.body.text(separator=' ') if clean_tree.body else clean_tree.text(separator=' ')
    clean_text = body_txt if body_txt else ""

    emails = extract_emails(clean_text, mailto_emails)

    # Single regex pass covers both fields — detect_technologies_detailed()
    # already computes everything detect_technologies() would; deriving the
    # flat list from it instead of calling both avoids running every tech
    # signature against html_content twice (this doubled tech-detection cost
    # in an earlier version of this change; caught by the Phase 5 benchmark
    # gate, see benchmarks/ notes).
    technology_details = detect_technologies_detailed(html_content)
    detected_tech = names_in_signature_order(technology_details)

    json_ld_schemas = extract_json_ld(tree)
    rss_feeds = extract_rss_feeds(tree, final_url)
    product_data = extract_product_data(json_ld_schemas)

    sec_headers, security_score = extract_security_headers(resp_headers)

    passed_seo, warnings_seo, seo_score = run_seo_audit(
        title=metadata["title"],
        description=metadata["description"],
        canonical_url=metadata["canonical_url"],
        h1_tags=metadata["h1_tags"],
        og_image=metadata["og_image"],
        favicon=metadata["favicon"],
        images_count=metadata["images_count"],
        images_missing_alt_count=metadata["images_missing_alt_count"],
        final_url=final_url,
        language=metadata["language"],
        viewport=metadata["viewport"],
        robots_directive=metadata["robots"],
        h1_count=metadata["h1_count"],
        twitter_card=metadata["twitter_card"],
        has_structured_data=bool(json_ld_schemas),
    )

    summary_snippet, top_keywords = extract_summary_and_keywords(clean_text, metadata["description"])
    metadata["summary_snippet"] = summary_snippet
    metadata["top_keywords"] = top_keywords
    metadata["content_length_bytes"] = len(raw_bytes)

    # Markdown extraction mutates `tree` via strip_tags() — must run LAST.
    markdown_content, word_count, reading_time = html_to_markdown_clean(tree, final_url)

    execution_time = round((time.time() - start_time) * 1000, 2)

    response_data = {
        "url": url,
        "final_url": final_url,
        "status_code": status_code,
        "execution_time_ms": execution_time,
        "metadata": metadata,
        "social_links": social_links,
        "contacts": {
            "emails": emails[:10],
            "phones": tel_phones[:5]
        },
        "detected_technologies": detected_tech,
        "technology_details": technology_details,
        "rss_feeds": rss_feeds,
        "json_ld_schemas": json_ld_schemas,
        "product_data": product_data,
        "security_headers": sec_headers,
        "security_score_percentage": security_score,
        "seo_score_percentage": seo_score,
        "seo_passed_checks": passed_seo,
        "seo_warnings": warnings_seo,
        "internal_links": internal_links,
        "external_links": external_links,
        "total_internal_count": len(internal_links),
        "total_external_count": len(external_links),
        "word_count": word_count,
        "reading_time_minutes": reading_time,
        "markdown_content": markdown_content,
        # §13.4: Byte-level transparency
        "content_truncated": content_truncated,
        "bytes_downloaded": bytes_downloaded,
    }

    cache[cache_key] = response_data
    return response_data
