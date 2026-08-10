"""Rate-limit response headers (Plan §8.6): X-RateLimit-Limit/Remaining/Reset
on every response, success or 429, local-TTLCache path (no Redis in this
test environment — the Redis-eval path is exercised by
test_redis_rate_limit_atomicity.py against a live Redis in CI)."""
from unittest import mock

import httpx
from fastapi.testclient import TestClient

import app.fetcher.client as fetcher_client
from app import config
from app.main import app
from app.ratelimit.limiter import ip_rate_tracker


async def _fake_ssrf(url):
    return (url, "ratelimit-header-fixture.ssrfcheck")


def _fixed_transport(body: bytes):
    class FixedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)
    return FixedTransport()


def test_success_response_has_rate_limit_headers():
    ip_rate_tracker.clear()
    fetcher_client.http_client = httpx.AsyncClient(
        transport=_fixed_transport(b"<html><head><title>Fixture</title></head><body>x</body></html>")
    )
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        res = client.get("/api/v1/tech-stack?url=https://ratelimit-header-fixture.ssrfcheck/headers-success")

    assert res.status_code == 200
    assert res.headers["x-ratelimit-limit"] == str(config.RATE_LIMIT_PER_MINUTE)
    assert res.headers["x-ratelimit-remaining"] == str(config.RATE_LIMIT_PER_MINUTE - 1)
    assert int(res.headers["x-ratelimit-reset"]) <= 60


def test_429_response_has_rate_limit_headers_with_zero_remaining():
    ip_rate_tracker.clear()
    fetcher_client.http_client = httpx.AsyncClient(
        transport=_fixed_transport(b"<html><head><title>Fixture</title></head><body>x</body></html>")
    )
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        last = None
        for _ in range(config.RATE_LIMIT_PER_MINUTE + 1):
            last = client.get("/api/v1/tech-stack?url=https://ratelimit-header-fixture.ssrfcheck/headers-429")

    assert last.status_code == 429
    assert last.headers["retry-after"] == "60"
    assert last.headers["x-ratelimit-remaining"] == "0"
    assert last.headers["x-ratelimit-limit"] == str(config.RATE_LIMIT_PER_MINUTE)
