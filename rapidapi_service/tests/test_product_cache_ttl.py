"""
Shorter cache TTL for product/price data (Plan feedback: "yo querría que el
TTL fuese configurable por tipo de endpoint/dato" — a stale price is a
materially different problem than a stale <title>). Responses whose
product_data includes a price get PRODUCT_CACHE_TTL_SECONDS (3 min default)
instead of the general CACHE_TTL_SECONDS (15 min default), for the whole
entry.
"""
from unittest import mock

import httpx
from fastapi.testclient import TestClient

import app.fetcher.client as fetcher_client
from app import config
from app.cache.l1 import cache as l1_cache
from app.main import app

PRODUCT_HTML = b"""<html><head><title>Product Fixture</title>
<script type="application/ld+json">{"@context": "https://schema.org", "@type": "Product", "name": "Widget", "offers": {"price": "39.99", "priceCurrency": "EUR"}}</script>
</head><body>x</body></html>"""

NON_PRODUCT_HTML = b"<html><head><title>Plain Fixture</title></head><body>x</body></html>"


async def _fake_ssrf(url):
    return (url, "product-ttl-fixture.ssrfcheck")


def _fixed_transport(body: bytes):
    class FixedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)
    return FixedTransport()


def test_product_response_gets_expires_at_set():
    l1_cache.clear()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(PRODUCT_HTML))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        res = client.get("/api/v1/extract?url=https://product-ttl-fixture.ssrfcheck/product")
    assert res.status_code == 200

    cache_key = list(l1_cache.keys())[0]
    entry = l1_cache[cache_key]
    assert entry["expires_at"] is not None


def test_non_product_response_has_no_custom_expiry():
    l1_cache.clear()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(NON_PRODUCT_HTML))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        res = client.get("/api/v1/extract?url=https://product-ttl-fixture.ssrfcheck/plain")
    assert res.status_code == 200

    cache_key = list(l1_cache.keys())[0]
    entry = l1_cache[cache_key]
    assert entry["expires_at"] is None


def test_expired_product_entry_is_refetched_not_served_stale():
    l1_cache.clear()
    call_counter = {"n": 0}

    def handler(request):
        call_counter["n"] += 1
        return httpx.Response(200, headers={"content-type": "text/html"}, content=PRODUCT_HTML)

    fetcher_client.http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        res1 = client.get("/api/v1/extract?url=https://product-ttl-fixture.ssrfcheck/expiring")
        assert res1.status_code == 200
        assert call_counter["n"] == 1

        # Force the cached entry into the past, simulating PRODUCT_CACHE_TTL_SECONDS elapsing.
        cache_key = list(l1_cache.keys())[0]
        l1_cache[cache_key]["expires_at"] = 0.0

        res2 = client.get("/api/v1/extract?url=https://product-ttl-fixture.ssrfcheck/expiring")
        assert res2.status_code == 200
        assert res2.json()["execution_time_ms"] != 0.01, "expired product entry must not be served as a cache hit"
        assert call_counter["n"] == 2, "expired product entry must trigger a real re-fetch"


def test_default_product_ttl_is_shorter_than_general_ttl():
    assert config.PRODUCT_CACHE_TTL_SECONDS < config.CACHE_TTL_SECONDS
