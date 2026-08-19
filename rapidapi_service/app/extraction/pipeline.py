"""
Extraction pipeline orchestrator (Plan section 11): parse the HTML ONCE, then
run every extractor against the same tree, single-pass where the original
code did. This is the direct replacement for the old fetch_and_extract_raw
monolith — same cache semantics, same field names, same ordering constraints
(markdown extraction mutates the tree via strip_tags and must run LAST).

Plan §12 lazy extraction: a `profile` (see extraction/profiles.py) says which
extractor groups a caller actually needs. `/api/v1/extract` doesn't pass one,
so it defaults to FULL_PROFILE and goes through the exact same code path as
before this feature existed (_fetch_and_extract_uncached, untouched) — zero
behavior/performance change for the full-payload endpoint. Specialized
endpoints (`/contacts`, `/tech-stack`, `/security`, ...) pass a narrow
profile and are routed to _fetch_and_extract_partial instead, which only
runs the extractors that profile's groups need (e.g. /security never
constructs an HTMLParser tree at all).

Cache entries are `{"data": {...fields...}, "computed": frozenset(groups)}`.
A lookup is a hit only if the requested profile is a subset of what's already
computed for that cache_key. Narrow profiles accumulate into the same entry
(so /tech-stack then /security for the same URL reuses the raw fetch and
merges into one entry) but a FULL request always re-runs the full pipeline
and overwrites whatever was cached — it never tries to top up from a partial
entry, to keep the well-trodden FULL/`/extract` path completely unchanged.
"""
import time
from typing import Any, Dict, Optional

from cachetools import TTLCache
from selectolax.parser import HTMLParser

from app import config
from app.cache.keys import build_cache_key
from app.cache.l1 import cache
from app.cache.negative import get_cached_negative, maybe_cache_negative
from app.cache.singleflight import single_flight
from app.core.errors import AppError
from app.core.logging import logger
from app.core.urls import is_shortened_url, normalize_and_validate_url
from app.extraction.bot_protection import detect_bot_protection
from app.extraction.contacts import extract_emails
from app.extraction.jsonld import extract_json_ld, extract_rss_feeds
from app.extraction.links import extract_links_and_socials
from app.extraction.markdown import compute_readability_metrics, extract_summary_and_keywords, html_to_markdown_clean
from app.extraction.metadata import extract_heading_structure, extract_metadata_fields
from app.extraction.phones import normalize_phones
from app.extraction.product import extract_product_data
from app.extraction.profiles import (
    FULL_PROFILE,
    expand_profile,
    needs_a_nodes,
    needs_clean_text,
    needs_tree,
)
from app.extraction.quality import (
    compute_quality,
    detect_product_conflicts,
    product_field_confidence,
)
from app.extraction.security import extract_security_headers
from app.extraction.seo import run_seo_audit
from app.extraction.tech import detect_technologies_detailed, names_in_signature_order
from app.fetcher.client import fetch_raw_page, sanitize_user_agent
from app.observability import metrics

# Short-lived, small cache for raw fetch results (Plan §12.2: specialized
# endpoints "must reuse the same fetcher and parser" as each other) — lets a
# burst of different-profile requests for the same URL (e.g. /tech-stack then
# /security called moments apart) top up the same cache entry without a
# second upstream fetch. Deliberately much smaller/shorter-lived than the
# main L1 cache: it only needs to bridge a short window, not the full
# CACHE_TTL_SECONDS, so it doesn't meaningfully add to steady-state RAM.
_raw_page_cache: TTLCache = TTLCache(maxsize=config.RAW_PAGE_CACHE_MAXSIZE, ttl=config.RAW_PAGE_CACHE_TTL_SECONDS)


def _entry_expired(entry: Dict[str, Any]) -> bool:
    expires_at = entry.get("expires_at")
    return expires_at is not None and time.time() >= expires_at


def _compute_entry_expiry(response_fields: Dict[str, Any]) -> Optional[float]:
    """Product listings with a price get a much shorter effective TTL than
    the rest of the cache (PRODUCT_CACHE_TTL_SECONDS, default 3 minutes vs
    the general 15) — a stale price/availability is a materially worse
    problem than a stale <title>. None means "use the cache's normal TTL"."""
    product_data = response_fields.get("product_data")
    if product_data and product_data.get("price") is not None:
        return time.time() + config.PRODUCT_CACHE_TTL_SECONDS
    return None


async def fetch_and_extract_raw(
    url: str,
    user_agent: Optional[str] = None,
    head_only: bool = False,
    profile: Optional[frozenset] = None,
) -> Dict[str, Any]:
    profile = FULL_PROFILE if profile is None else expand_profile(profile)

    url = normalize_and_validate_url(url)
    clean_ua = sanitize_user_agent(user_agent)

    cache_key = build_cache_key(url, clean_ua, head_only, user_agent)

    entry = cache.get(cache_key)
    if entry is not None and _entry_expired(entry):
        # Whole entry has a shorter custom expiry (Plan feedback: a stale
        # price is a materially different problem than a stale <title>) —
        # treat it exactly like a cache miss, including for the
        # top-up/accumulation logic in _fetch_and_extract_partial below.
        entry = None
    if entry is not None and profile <= entry["computed"]:
        cached_data = entry["data"].copy()
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

    if profile == FULL_PROFILE:
        # §6.7/§52 single-flight: N concurrent requests for the same
        # cache_key while a fetch+extract is already in progress share that
        # one result instead of triggering N upstream fetches.
        return await single_flight(cache_key, lambda: _fetch_and_extract_uncached(url, user_agent, head_only, cache_key))

    return await _fetch_and_extract_partial(url, user_agent, head_only, cache_key, profile)


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
    redirect_count = fetched["redirect_count"]

    # ONE HTML parse — every extractor below runs against this same tree.
    tree = HTMLParser(html_content)

    # a[href] is queried exactly once and shared between metadata.links_count
    # and the single-pass link/social/mailto/tel classifier below (Plan §11/§64).
    a_nodes = tree.css('a[href]')

    metadata = extract_metadata_fields(tree, final_url, resp_headers, links_count=len(a_nodes))

    # Competitive-differentiator #2: full heading structure, queried against
    # `tree` BEFORE html_to_markdown_clean() mutates it below (that call must
    # still run LAST per the existing ordering constraint).
    heading_structure = extract_heading_structure(tree)

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
    product_data, product_field_sources = extract_product_data(tree, json_ld_schemas)
    product_warnings = detect_product_conflicts(product_field_sources)
    product_confidence = product_field_confidence(product_field_sources)

    sec_headers, security_score, security_grades = extract_security_headers(resp_headers)

    passed_seo, warnings_seo, seo_score, seo_checks = run_seo_audit(
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

    readability = {
        **compute_readability_metrics(clean_text),
        "heading_structure": heading_structure,
    }

    execution_time = round((time.time() - start_time) * 1000, 2)

    bot_protection = detect_bot_protection(html_content, status_code)
    quality = compute_quality(
        has_title=bool(metadata["title"]),
        has_description=bool(metadata["description"]),
        has_json_ld=bool(json_ld_schemas),
        has_opengraph_product=any(s.get("opengraph") is not None for s in product_field_sources.values()),
        has_microdata_product=any(s.get("microdata") is not None for s in product_field_sources.values()),
        content_truncated=content_truncated,
        bot_protection_detected=bot_protection,
        product_warnings=product_warnings,
    )

    response_data = {
        "url": url,
        "final_url": final_url,
        "status_code": status_code,
        "execution_time_ms": execution_time,
        "redirect_count": redirect_count,
        "is_shortened_url": is_shortened_url(url),
        "metadata": metadata,
        "readability": readability,
        "social_links": social_links,
        "contacts": {
            "emails": emails[:10],
            "phones": tel_phones[:5]
        },
        "phone_details": normalize_phones(tel_phones),
        "detected_technologies": detected_tech,
        "technology_details": technology_details,
        "rss_feeds": rss_feeds,
        "json_ld_schemas": json_ld_schemas,
        "product_data": product_data,
        "product_field_confidence": product_confidence,
        "quality": quality,
        "security_headers": sec_headers,
        "security_score_percentage": security_score,
        "security_header_grades": security_grades,
        "seo_score_percentage": seo_score,
        "seo_passed_checks": passed_seo,
        "seo_warnings": warnings_seo,
        "seo_checks": seo_checks,
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
        "bot_protection_detected": bot_protection,
    }

    cache[cache_key] = {
        "data": response_data,
        "computed": FULL_PROFILE,
        "expires_at": _compute_entry_expiry(response_data),
    }
    return response_data


async def _fetch_and_extract_partial(
    url: str,
    user_agent: Optional[str],
    head_only: bool,
    cache_key: str,
    profile: frozenset,
) -> Dict[str, Any]:
    """Lazy path for specialized endpoints (Plan §12): fetch once (reusing a
    recent raw fetch if another profile for this same URL already triggered
    one), then run only the extractor groups `profile` needs.

    Concurrency note: this function `await`s (the raw fetch, or a
    single-flight follower waiting on another in-flight fetch for the same
    URL) before it ever touches the cache for the merge/write below. Two
    concurrent requests for the same URL with different profiles are
    therefore racing to write `cache[cache_key]` — whichever finishes last
    must not clobber the other's freshly-cached groups. The cache entry is
    deliberately re-read here, right before the merge, rather than reusing
    the `entry` snapshot the caller looked up before this function's own
    `await`s (that snapshot can be stale by the time this write happens, and
    a naive merge against it silently drops whatever another concurrent
    request already committed for this same URL — see
    tests/test_lazy_extraction_profiles.py's concurrent-profile test). From
    this re-read to the write below there is no further `await`, so under
    asyncio's cooperative single-threaded scheduling no other coroutine can
    interleave and this read-merge-write is effectively atomic.
    """
    start_time = time.time()

    raw = _raw_page_cache.get(cache_key)
    if raw is None:
        try:
            raw = await single_flight(f"rawpage:{cache_key}", lambda: fetch_raw_page(url, user_agent, head_only))
        except AppError as e:
            maybe_cache_negative(cache_key, e)
            raise
        _raw_page_cache[cache_key] = raw

    new_fields = _compute_groups(raw, profile)

    base_fields = {
        "url": url,
        "final_url": raw["final_url"],
        "status_code": raw["status_code"],
        "content_truncated": raw["content_truncated"],
        "bytes_downloaded": raw["bytes_downloaded"],
        "bot_protection_detected": detect_bot_protection(raw["html_content"], raw["status_code"]),
        "redirect_count": raw["redirect_count"],
        "is_shortened_url": is_shortened_url(url),
    }

    current_entry = cache.get(cache_key)
    if current_entry is not None and _entry_expired(current_entry):
        current_entry = None

    if current_entry is not None:
        merged_data = {**current_entry["data"], **base_fields, **new_fields}
        merged_profile = current_entry["computed"] | profile
    else:
        merged_data = {**base_fields, **new_fields}
        merged_profile = profile

    merged_data["execution_time_ms"] = round((time.time() - start_time) * 1000, 2)
    cache[cache_key] = {
        "data": merged_data,
        "computed": merged_profile,
        "expires_at": _compute_entry_expiry(merged_data),
    }
    return merged_data


def _compute_groups(raw: Dict[str, Any], profile: frozenset) -> Dict[str, Any]:
    """Runs only the extractors `profile`'s groups need, against `raw`
    (the fetch_raw_page() output). Returns just the newly-computed fields —
    the caller merges them with any previously-cached fields for this URL."""
    html_content = raw["html_content"]
    raw_bytes = raw["raw_bytes"]
    final_url = raw["final_url"]
    resp_headers = raw["resp_headers"]

    fields: Dict[str, Any] = {}

    tree = HTMLParser(html_content) if needs_tree(profile) else None
    a_nodes = tree.css('a[href]') if (tree is not None and needs_a_nodes(profile)) else []

    link_data = None
    if "links_and_socials" in profile or "contacts_emails" in profile:
        link_data = extract_links_and_socials(a_nodes, final_url)
        if "links_and_socials" in profile:
            fields["social_links"] = link_data["social_links"]
            fields["internal_links"] = link_data["internal_links"]
            fields["external_links"] = link_data["external_links"]
            fields["total_internal_count"] = len(link_data["internal_links"])
            fields["total_external_count"] = len(link_data["external_links"])

    clean_text = ""
    if needs_clean_text(profile):
        clean_tree = HTMLParser(html_content)
        clean_tree.strip_tags(["script", "style", "code", "noscript", "svg"])
        body_txt = clean_tree.body.text(separator=' ') if clean_tree.body else clean_tree.text(separator=' ')
        clean_text = body_txt if body_txt else ""

    if "metadata" in profile:
        metadata = extract_metadata_fields(tree, final_url, resp_headers, links_count=len(a_nodes))
        metadata["content_length_bytes"] = len(raw_bytes)
        fields["metadata"] = metadata

    if "contacts_emails" in profile:
        mailto_emails = link_data["mailto_emails"] if link_data else []
        tel_phones = link_data["tel_phones"] if link_data else []
        emails = extract_emails(clean_text, mailto_emails)
        fields["contacts"] = {"emails": emails[:10], "phones": tel_phones[:5]}
        fields["phone_details"] = normalize_phones(tel_phones)

    if "tech" in profile:
        technology_details = detect_technologies_detailed(html_content)
        fields["technology_details"] = technology_details
        fields["detected_technologies"] = names_in_signature_order(technology_details)

    json_ld_schemas = None
    if "jsonld" in profile:
        json_ld_schemas = extract_json_ld(tree)
        fields["json_ld_schemas"] = json_ld_schemas
        fields["rss_feeds"] = extract_rss_feeds(tree, final_url)

    if "product" in profile:
        product_data, product_field_sources = extract_product_data(tree, json_ld_schemas or [])
        fields["product_data"] = product_data
        fields["product_field_confidence"] = product_field_confidence(product_field_sources)

    if "security" in profile:
        sec_headers, security_score, security_grades = extract_security_headers(resp_headers)
        fields["security_headers"] = sec_headers
        fields["security_score_percentage"] = security_score
        fields["security_header_grades"] = security_grades

    if "seo" in profile:
        meta_for_seo = fields["metadata"]  # "seo" always pulls in "metadata" via _GROUP_DEPS
        passed_seo, warnings_seo, seo_score, seo_checks = run_seo_audit(
            title=meta_for_seo["title"],
            description=meta_for_seo["description"],
            canonical_url=meta_for_seo["canonical_url"],
            h1_tags=meta_for_seo["h1_tags"],
            og_image=meta_for_seo["og_image"],
            favicon=meta_for_seo["favicon"],
            images_count=meta_for_seo["images_count"],
            images_missing_alt_count=meta_for_seo["images_missing_alt_count"],
            final_url=final_url,
            language=meta_for_seo["language"],
            viewport=meta_for_seo["viewport"],
            robots_directive=meta_for_seo["robots"],
            h1_count=meta_for_seo["h1_count"],
            twitter_card=meta_for_seo["twitter_card"],
            has_structured_data=bool(json_ld_schemas),
        )
        fields["seo_score_percentage"] = seo_score
        fields["seo_passed_checks"] = passed_seo
        fields["seo_warnings"] = warnings_seo
        fields["seo_checks"] = seo_checks

        # Competitive-differentiator #2: "seo" always pulls in "metadata"
        # (tree guaranteed non-None) and now also "seo" is in
        # _CLEAN_TEXT_GROUPS (profiles.py), so clean_text is available here —
        # reused, not a second extra parse.
        fields["readability"] = {
            **compute_readability_metrics(clean_text),
            "heading_structure": extract_heading_structure(tree),
        }

    if "summary_keywords" in profile:
        meta_for_summary = fields["metadata"]  # always pulled in via _GROUP_DEPS
        summary_snippet, top_keywords = extract_summary_and_keywords(clean_text, meta_for_summary["description"])
        meta_for_summary["summary_snippet"] = summary_snippet
        meta_for_summary["top_keywords"] = top_keywords

    if "markdown" in profile:
        # Own fresh tree — markdown mutates it via strip_tags(), so it must
        # never be the shared `tree` other groups above already read from.
        md_tree = HTMLParser(html_content)
        # Competitive-differentiator #2: heading structure queried BEFORE
        # html_to_markdown_clean() mutates md_tree below.
        md_heading_structure = extract_heading_structure(md_tree)
        markdown_content, word_count, reading_time = html_to_markdown_clean(md_tree, final_url)
        fields["markdown_content"] = markdown_content
        fields["word_count"] = word_count
        fields["reading_time_minutes"] = reading_time
        # Overwrites the "seo" branch's `readability` (above) if both groups
        # are requested together (e.g. a combined `fields=` request) — uses
        # markdown_content rather than clean_text since it's already
        # computed here and has real paragraph structure (see
        # compute_readability_metrics()'s docstring), a strictly better
        # source than falling back to a clean_text parse this group doesn't
        # otherwise need.
        fields["readability"] = {
            **compute_readability_metrics(markdown_content),
            "heading_structure": md_heading_structure,
        }

    return fields
