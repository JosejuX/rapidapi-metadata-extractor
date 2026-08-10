"""Typed response sub-models (Plan §35): known fields get real typing, but
`extra='allow'` means a field the model doesn't know about is preserved,
not silently dropped — the exact failure mode that left `product_data`
missing from /api/v1/extract despite being documented in README.md's sample
response (fixed in the same pass as this file)."""
from unittest import mock

import httpx
from fastapi.testclient import TestClient

import app.fetcher.client as fetcher_client
from app.cache.l1 import cache as l1_cache
from app.main import app
from app.models.responses import Metadata, PhoneDetail, SeoCheck, TechnologyDetail
from app.ratelimit.limiter import ip_rate_tracker

FIXTURE_HTML = b"""<!DOCTYPE html>
<html lang="en"><head><title>Typed Model Fixture</title>
<meta name="description" content="A fixture page for typed response model tests.">
<link rel="canonical" href="https://typed-model-fixture.ssrfcheck/page">
<link rel="alternate" hreflang="es" href="/es">
<script src="/_next/static/chunks/x.js"></script>
<script type="application/ld+json">{"@context": "https://schema.org", "@type": "Product", "name": "Widget", "offers": {"price": "9.99", "priceCurrency": "USD"}}</script>
</head><body><h1>Hi</h1><p>Call us at <a href="tel:+34600123456">+34 600 123 456</a>.</p></body></html>"""


async def _fake_ssrf(url):
    return (url, "typed-model-fixture.ssrfcheck")


def _fixed_transport(body: bytes):
    class FixedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)
    return FixedTransport()


def _extract():
    l1_cache.clear()
    ip_rate_tracker.clear()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        res = client.get("/api/v1/extract?url=https://typed-model-fixture.ssrfcheck/page")
    assert res.status_code == 200, res.text
    return res.json()


def test_product_data_is_no_longer_silently_dropped():
    # Regression test for the bug this pass found: product_data was
    # documented in README.md's sample /extract response but MetadataResponse
    # didn't declare the field, so Pydantic's default extra='ignore' silently
    # dropped it from every real response.
    data = _extract()
    assert data["product_data"] is not None
    assert data["product_data"]["name"] == "Widget"
    assert data["product_data"]["price"] == "9.99"


def test_metadata_nested_model_fields_present():
    data = _extract()
    assert data["metadata"]["title"] == "Typed Model Fixture"
    assert data["metadata"]["hreflang_tags"] == [{"lang": "es", "url": "https://typed-model-fixture.ssrfcheck/es"}]
    assert data["metadata"]["ssl_status"]["enabled"] is True


def test_technology_details_typed_and_populated():
    data = _extract()
    assert len(data["technology_details"]) >= 1
    nextjs = next(t for t in data["technology_details"] if t["name"] == "Next.js")
    assert 0.0 < nextjs["confidence"] <= 1.0
    assert nextjs["category"] == "framework"


def test_seo_checks_typed_and_populated():
    data = _extract()
    assert len(data["seo_checks"]) > 0
    assert all({"check", "passed", "severity", "evidence"} <= set(c.keys()) for c in data["seo_checks"])


def test_phone_details_typed_and_populated():
    data = _extract()
    assert len(data["phone_details"]) == 1
    assert data["phone_details"][0]["normalized"] == "+34600123456"
    assert data["phone_details"][0]["country"] == "ES"


def test_metadata_model_allows_unknown_extra_fields_instead_of_dropping_them():
    # The exact safety net that should have caught the product_data bug had
    # it been applied there too: a field the model doesn't declare must
    # survive construction and serialization, not vanish.
    m = Metadata(title="x", ssl_status={"enabled": True, "hsts_active": False, "protocol": "HTTPS"},
                 some_future_field="should not be dropped")
    dumped = m.model_dump()
    assert dumped["some_future_field"] == "should not be dropped"


def test_technology_detail_allows_unknown_extra_fields():
    t = TechnologyDetail(name="X", confidence=0.9, category="framework", future_signal="abc")
    assert t.model_dump()["future_signal"] == "abc"


def test_seo_check_allows_unknown_extra_fields():
    c = SeoCheck(check="x", passed=True, severity="minor", evidence="ok", future_field=123)
    assert c.model_dump()["future_field"] == 123


def test_phone_detail_allows_unknown_extra_fields():
    p = PhoneDetail(raw="+1234", future_field="abc")
    assert p.model_dump()["future_field"] == "abc"
