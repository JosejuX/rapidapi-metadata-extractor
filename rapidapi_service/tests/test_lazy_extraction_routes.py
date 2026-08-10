"""
End-to-end route-level check for lazy extraction (Plan §12): every
specialized endpoint must still return a valid, schema-conformant response
after being switched to a narrow extraction profile — this exercises the
actual FastAPI route + Pydantic response_model, not just the pipeline
function directly (test_lazy_extraction_profiles.py covers that level).
"""
from unittest import mock

import httpx
from fastapi.testclient import TestClient

import app.fetcher.client as fetcher_client
from app.cache.l1 import cache as l1_cache
from app.extraction import pipeline
from app.main import app

FIXTURE_HTML = b"""<!DOCTYPE html>
<html lang="en"><head><title>Route Fixture</title>
<meta name="description" content="A fixture page for route-level lazy-extraction tests.">
<meta property="og:image" content="https://example.com/og.png">
<link rel="canonical" href="https://route-fixture.ssrfcheck/page">
<link rel="icon" href="/favicon.ico">
</head><body>
<h1>Route Fixture</h1>
<p>Contact us at info@route-fixture.com.</p>
<p><a href="https://twitter.com/routefixture">Twitter</a></p>
<a href="/about">About</a>
<script type="application/ld+json">{"@context": "https://schema.org", "@type": "Organization", "name": "Route Fixture Co"}</script>
</body></html>"""


async def _fake_ssrf(url):
    return (url, "route-fixture.ssrfcheck")


def _fixed_transport(body: bytes):
    class FixedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)
    return FixedTransport()


def _hit(path: str):
    l1_cache.clear()
    pipeline._raw_page_cache.clear()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        return client.get(path)


def test_contacts_route_returns_valid_schema():
    res = _hit("/api/v1/contacts?url=https://route-fixture.ssrfcheck/page")
    assert res.status_code == 200
    data = res.json()
    assert data["emails"] == ["info@route-fixture.com"]
    assert "twitter" in data["social_links"]


def test_tech_stack_route_returns_valid_schema():
    res = _hit("/api/v1/tech-stack?url=https://route-fixture.ssrfcheck/page")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["detected_technologies"], list)
    assert isinstance(data["technology_details"], list)


def test_schema_route_returns_valid_schema():
    res = _hit("/api/v1/schema?url=https://route-fixture.ssrfcheck/page")
    assert res.status_code == 200
    data = res.json()
    assert data["json_ld_count"] == 1
    assert data["json_ld_schemas"][0]["name"] == "Route Fixture Co"


def test_security_route_returns_valid_schema():
    res = _hit("/api/v1/security?url=https://route-fixture.ssrfcheck/page")
    assert res.status_code == 200
    data = res.json()
    assert "security_score_percentage" in data
    assert isinstance(data["security_headers"], dict)


def test_markdown_route_returns_valid_schema():
    res = _hit("/api/v1/markdown?url=https://route-fixture.ssrfcheck/page")
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Route Fixture"
    assert "Route Fixture" in data["markdown_content"]


def test_seo_audit_route_returns_valid_schema():
    res = _hit("/api/v1/seo-audit?url=https://route-fixture.ssrfcheck/page")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["seo_score_percentage"], (int, float))
    assert isinstance(data["passed_checks"], list)


def test_links_route_returns_valid_schema():
    res = _hit("/api/v1/links?url=https://route-fixture.ssrfcheck/page")
    assert res.status_code == 200
    data = res.json()
    assert data["internal_links_count"] + data["external_links_count"] == data["total_links_count"]


def test_link_preview_route_returns_valid_schema():
    res = _hit("/api/v1/link-preview?url=https://route-fixture.ssrfcheck/page")
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Route Fixture"


def test_extract_route_still_returns_full_payload():
    res = _hit("/api/v1/extract?url=https://route-fixture.ssrfcheck/page")
    assert res.status_code == 200
    data = res.json()
    for key in ("metadata", "social_links", "contacts", "detected_technologies",
                "json_ld_schemas", "security_score_percentage", "seo_score_percentage",
                "internal_links", "markdown_content"):
        assert key in data, f"/extract response missing '{key}'"


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_contacts_route_returns_valid_schema()
        test_tech_stack_route_returns_valid_schema()
        test_schema_route_returns_valid_schema()
        test_security_route_returns_valid_schema()
        test_markdown_route_returns_valid_schema()
        test_seo_audit_route_returns_valid_schema()
        test_links_route_returns_valid_schema()
        test_link_preview_route_returns_valid_schema()
        test_extract_route_still_returns_full_payload()
        print("\n[OK] ALL LAZY EXTRACTION ROUTE TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
