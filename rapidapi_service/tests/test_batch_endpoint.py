"""
Batch URL processing (competitive-differentiator #3): POST /api/v1/batch
runs a lightweight link-preview extraction over up to MAX_BATCH_SIZE urls,
one failing URL never taking down the rest of the batch, and counts as N
requests (not 1) against the per-IP rate limit.
"""
from unittest import mock

import httpx
from fastapi.testclient import TestClient

import app.fetcher.client as fetcher_client
from app import config
from app.api.batch import MAX_BATCH_SIZE
from app.cache.l1 import cache as l1_cache
from app.extraction import pipeline
from app.main import app
from app.ratelimit.limiter import ip_rate_tracker

FIXTURE_HTML = b"""<!DOCTYPE html>
<html lang="en"><head><title>Batch Fixture</title>
<meta name="description" content="A fixture page for batch endpoint tests.">
<meta property="og:image" content="https://example.com/og.png">
</head><body><h1>Batch Fixture</h1></body></html>"""


async def _fake_ssrf(url):
    return (url, "batch-fixture.ssrfcheck")


def _fixed_transport(body: bytes):
    class FixedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)
    return FixedTransport()


def _post(urls):
    l1_cache.clear()
    pipeline._raw_page_cache.clear()
    ip_rate_tracker.clear()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        return client.post("/api/v1/batch", json={"urls": urls})


def test_batch_mixed_valid_and_invalid_urls():
    res = _post([
        "https://batch-fixture.ssrfcheck/page1",
        "ftp://invalid-scheme-should-fail.example/page",  # rejected by normalize_and_validate_url before any fetch
    ])
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] == 2
    assert data["succeeded"] == 1
    assert data["failed"] == 1

    by_url = {r["url"]: r for r in data["results"]}
    good = by_url["https://batch-fixture.ssrfcheck/page1"]
    assert good["success"] is True
    assert good["title"] == "Batch Fixture"
    assert good["error"] is None

    bad = by_url["ftp://invalid-scheme-should-fail.example/page"]
    assert bad["success"] is False
    assert bad["error"]


def test_batch_all_valid_urls_all_succeed():
    res = _post([
        "https://batch-fixture.ssrfcheck/a",
        "https://batch-fixture.ssrfcheck/b",
        "https://batch-fixture.ssrfcheck/c",
    ])
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert data["succeeded"] == 3
    assert data["failed"] == 0
    assert all(r["success"] for r in data["results"])


def test_batch_size_exceeded_returns_400():
    urls = [f"https://batch-fixture.ssrfcheck/{i}" for i in range(MAX_BATCH_SIZE + 1)]
    res = _post(urls)
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "BATCH_SIZE_EXCEEDED"


def test_batch_exactly_max_size_is_allowed():
    urls = [f"https://batch-fixture.ssrfcheck/{i}" for i in range(MAX_BATCH_SIZE)]
    res = _post(urls)
    assert res.status_code == 200
    assert res.json()["total"] == MAX_BATCH_SIZE


def test_batch_empty_urls_list_returns_400():
    res = _post([])
    assert res.status_code == 400


def test_batch_counts_as_n_requests_against_rate_limit():
    """A batch of N urls must consume N slots from the per-IP rate limit,
    not just 1 — otherwise a client could bypass the limit by routing
    traffic through /batch instead of individual endpoint calls."""
    original_limit = config.RATE_LIMIT_PER_MINUTE
    try:
        config.RATE_LIMIT_PER_MINUTE = 3
        res = _post([
            "https://batch-fixture.ssrfcheck/1",
            "https://batch-fixture.ssrfcheck/2",
            "https://batch-fixture.ssrfcheck/3",
            "https://batch-fixture.ssrfcheck/4",
            "https://batch-fixture.ssrfcheck/5",
        ])
        assert res.status_code == 429, res.text
    finally:
        config.RATE_LIMIT_PER_MINUTE = original_limit
        ip_rate_tracker.clear()


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_batch_mixed_valid_and_invalid_urls()
        test_batch_all_valid_urls_all_succeed()
        test_batch_size_exceeded_returns_400()
        test_batch_exactly_max_size_is_allowed()
        test_batch_empty_urls_list_returns_400()
        test_batch_counts_as_n_requests_against_rate_limit()
        print("\n[OK] ALL BATCH ENDPOINT TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
