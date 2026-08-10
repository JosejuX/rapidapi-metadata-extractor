"""
Lazy extraction per endpoint (Plan §12): specialized endpoints must only run
the extractor groups they actually need, must still share a cache entry
across profiles for the same URL, and a full-profile request must never be
satisfied by a narrower cached entry.
"""
import asyncio
from unittest import mock

import httpx

import app.fetcher.client as fetcher_client
from app.cache.l1 import cache as l1_cache
import app.cache.singleflight as sf_mod
from app.extraction import pipeline
from app.extraction.pipeline import fetch_and_extract_raw
from app.extraction.profiles import (
    FULL_PROFILE, PROFILE_SECURITY, PROFILE_TECH, PROFILE_CONTACTS, PROFILE_LINKS,
)
from app.observability import metrics

FIXTURE_HTML = b"""<!DOCTYPE html>
<html lang="en"><head><title>Fixture Page</title>
<meta name="description" content="A fixture page for lazy-extraction tests.">
<meta property="og:image" content="https://example.com/og.png">
<link rel="canonical" href="https://lazy-fixture.ssrfcheck/page">
<link rel="icon" href="/favicon.ico">
</head><body>
<h1>Fixture</h1>
<p>Contact us at info@fixture-example.com.</p>
<p><a href="https://twitter.com/fixtureco">Twitter</a></p>
<a href="/about">About</a>
<script type="application/ld+json">{"@context": "https://schema.org", "@type": "Organization", "name": "Fixture Co"}</script>
</body></html>"""


async def _fake_ssrf(url):
    return (url, "lazy-fixture.ssrfcheck")


def _fixed_transport(body: bytes, counter: dict = None):
    class FixedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if counter is not None:
                counter["n"] = counter.get("n", 0) + 1
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)
    return FixedTransport()


def _reset_state():
    l1_cache.clear()
    pipeline._raw_page_cache.clear()
    sf_mod._in_flight.clear()


def test_security_profile_never_builds_an_html_tree():
    """The biggest win: /security only needs resp_headers, so it must never
    even construct an HTMLParser — a malformed/huge body costs nothing extra."""
    _reset_state()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML))

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            with mock.patch("app.extraction.pipeline.HTMLParser") as mock_parser:
                data = await fetch_and_extract_raw(
                    "https://lazy-fixture.ssrfcheck/security-page", profile=PROFILE_SECURITY
                )
                mock_parser.assert_not_called()
                return data

    data = asyncio.run(go())
    assert "security_headers" in data
    assert "security_score_percentage" in data
    # Fields outside the requested profile were never computed.
    assert "markdown_content" not in data
    assert "detected_technologies" not in data
    print("  [OK] /security profile never builds an HTMLParser tree")


def test_tech_profile_skips_unrelated_fields():
    _reset_state()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML))

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            return await fetch_and_extract_raw("https://lazy-fixture.ssrfcheck/tech-page", profile=PROFILE_TECH)

    data = asyncio.run(go())
    assert data["detected_technologies"] == [] or isinstance(data["detected_technologies"], list)
    assert "technology_details" in data
    assert "markdown_content" not in data
    assert "metadata" not in data
    assert "contacts" not in data
    print("  [OK] /tech-stack profile computes only tech fields")


def test_narrow_profile_is_cached_and_hits_on_repeat():
    _reset_state()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML))
    hits_before = metrics.CACHE_HITS_TOTAL._value.get()
    misses_before = metrics.CACHE_MISSES_TOTAL._value.get()

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            await fetch_and_extract_raw("https://lazy-fixture.ssrfcheck/repeat-page", profile=PROFILE_TECH)
            return await fetch_and_extract_raw("https://lazy-fixture.ssrfcheck/repeat-page", profile=PROFILE_TECH)

    data = asyncio.run(go())
    assert metrics.CACHE_MISSES_TOTAL._value.get() == misses_before + 1
    assert metrics.CACHE_HITS_TOTAL._value.get() == hits_before + 1
    assert data["execution_time_ms"] == 0.01
    print("  [OK] second call with the same narrow profile is a real cache hit")


def test_different_narrow_profiles_accumulate_without_refetching():
    """/tech-stack then /security for the same URL: only ONE upstream fetch,
    and the cache entry ends up covering both profiles."""
    _reset_state()
    counter = {}
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML, counter))

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            d1 = await fetch_and_extract_raw("https://lazy-fixture.ssrfcheck/accum-page", profile=PROFILE_TECH)
            d2 = await fetch_and_extract_raw("https://lazy-fixture.ssrfcheck/accum-page", profile=PROFILE_SECURITY)
            return d1, d2

    d1, d2 = asyncio.run(go())
    assert counter["n"] == 1, f"expected exactly 1 upstream fetch, got {counter['n']}"
    assert "detected_technologies" in d1
    # Second call's returned data includes the newly-computed security fields.
    assert "security_headers" in d2

    cache_key = list(l1_cache.keys())[0]
    entry = l1_cache[cache_key]
    assert "tech" in entry["computed"]
    assert "security" in entry["computed"]
    assert "detected_technologies" in entry["data"]
    assert "security_headers" in entry["data"]
    print("  [OK] tech + security accumulated into one cache entry from a single fetch")


def test_full_profile_never_reuses_a_partial_entry():
    """A prior narrow-profile cache entry must never satisfy a full request —
    /extract always gets the complete, unmodified pipeline output."""
    _reset_state()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML))

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            await fetch_and_extract_raw("https://lazy-fixture.ssrfcheck/full-page", profile=PROFILE_TECH)
            return await fetch_and_extract_raw("https://lazy-fixture.ssrfcheck/full-page")  # default = FULL

    data = asyncio.run(go())
    assert "markdown_content" in data
    assert "seo_score_percentage" in data
    assert "contacts" in data
    assert "detected_technologies" in data
    print("  [OK] full-profile request returns the complete payload even after a narrower prior call")


def test_contacts_profile_also_satisfies_links_profile():
    """contacts_emails depends on links_and_socials, so a /contacts call
    should incidentally also satisfy a later /links request for the same URL
    without a second fetch."""
    _reset_state()
    counter = {}
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML, counter))

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            await fetch_and_extract_raw("https://lazy-fixture.ssrfcheck/contacts-then-links", profile=PROFILE_CONTACTS)
            hits_before = metrics.CACHE_HITS_TOTAL._value.get()
            data = await fetch_and_extract_raw("https://lazy-fixture.ssrfcheck/contacts-then-links", profile=PROFILE_LINKS)
            return data, hits_before

    data, hits_before = asyncio.run(go())
    assert counter["n"] == 1, f"expected exactly 1 upstream fetch, got {counter['n']}"
    assert metrics.CACHE_HITS_TOTAL._value.get() == hits_before + 1
    assert "internal_links" in data
    print("  [OK] /contacts's links_and_socials dependency pre-satisfies a later /links call")


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_security_profile_never_builds_an_html_tree()
        test_tech_profile_skips_unrelated_fields()
        test_narrow_profile_is_cached_and_hits_on_repeat()
        test_different_narrow_profiles_accumulate_without_refetching()
        test_full_profile_never_reuses_a_partial_entry()
        test_contacts_profile_also_satisfies_links_profile()
        print("\n[OK] ALL LAZY EXTRACTION PROFILE TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
