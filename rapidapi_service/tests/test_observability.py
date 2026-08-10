"""
Phase 6 tests: Prometheus metrics (Plan §39), the /metrics scrape endpoint,
structured JSON logging (Plan §41), and the secret-redaction safety net.
"""
import asyncio
import json
import logging
import socket
from io import StringIO
from unittest import mock

import httpx
from fastapi.testclient import TestClient

import app.fetcher.client as fetcher_client
import app.security.ssrf as ssrf_mod
import app.cache.singleflight as sf_mod
import app.cache.negative as neg_mod
from app.cache.l1 import cache as l1_cache
from app.extraction.pipeline import fetch_and_extract_raw
from app.core.errors import AppError
from app.core.logging import JsonFormatter, logger
from app.observability import metrics
from app.main import app


async def _fake_ssrf(url):
    return (url, "observability-fixture.ssrfcheck")


def _fixed_transport(body: bytes):
    class FixedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)
    return FixedTransport()


def test_cache_hit_and_miss_counters():
    print("\n--- Metrics: cache_hits_total / cache_misses_total ---")
    l1_cache.clear()
    sf_mod._in_flight.clear()
    neg_mod._negative_cache.clear()

    hits_before = metrics.CACHE_HITS_TOTAL._value.get()
    misses_before = metrics.CACHE_MISSES_TOTAL._value.get()

    body = b"<html><head><title>Cached Fixture</title></head><body>x</body></html>"
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(body))

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            await fetch_and_extract_raw("https://observability-fixture.ssrfcheck/metrics-page")  # miss
            await fetch_and_extract_raw("https://observability-fixture.ssrfcheck/metrics-page")  # hit

    asyncio.run(go())

    assert metrics.CACHE_MISSES_TOTAL._value.get() == misses_before + 1
    assert metrics.CACHE_HITS_TOTAL._value.get() == hits_before + 1
    print("  [OK] one miss then one hit recorded")


def test_ssrf_block_and_dns_failure_counters():
    print("\n--- Metrics: ssrf_blocks_total / dns_failures_total ---")
    ssrf_before = metrics.SSRF_BLOCKS_TOTAL._value.get()
    dns_before = metrics.DNS_FAILURES_TOTAL._value.get()

    try:
        asyncio.run(ssrf_mod.validate_url_ssrf("https://localhost/"))
        raise AssertionError("expected SSRF block")
    except AppError:
        pass
    assert metrics.SSRF_BLOCKS_TOTAL._value.get() == ssrf_before + 1

    from app.fetcher.dns import dns_cache
    dns_cache.clear()
    sf_mod._in_flight.clear()
    with mock.patch("app.security.ssrf.socket.getaddrinfo", side_effect=socket.gaierror("nxdomain")):
        try:
            asyncio.run(ssrf_mod.validate_url_ssrf("https://dns-fail-metrics-fixture.ssrfcheck/"))
            raise AssertionError("expected DNS failure")
        except AppError:
            pass
    assert metrics.DNS_FAILURES_TOTAL._value.get() == dns_before + 1
    print("  [OK] both counters incremented exactly once")


def test_singleflight_coalesced_counter():
    print("\n--- Metrics: singleflight_coalesced_total ---")
    l1_cache.clear()
    sf_mod._in_flight.clear()
    neg_mod._negative_cache.clear()
    coalesced_before = metrics.SINGLEFLIGHT_COALESCED_TOTAL._value.get()

    body = b"<html><head><title>Coalesce Fixture</title></head><body>x</body></html>"

    class SlowTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            await asyncio.sleep(0.1)
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)

    fetcher_client.http_client = httpx.AsyncClient(transport=SlowTransport())

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            tasks = [
                asyncio.create_task(fetch_and_extract_raw("https://observability-fixture.ssrfcheck/coalesce-page"))
                for _ in range(10)
            ]
            await asyncio.gather(*tasks)

    asyncio.run(go())
    assert metrics.SINGLEFLIGHT_COALESCED_TOTAL._value.get() == coalesced_before + 9
    print("  [OK] 9 of 10 concurrent identical requests recorded as coalesced")


def test_metrics_endpoint_exposes_prometheus_text_format():
    print("\n--- /metrics: valid Prometheus exposition format, key metrics present ---")
    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    for expected in (
        "requests_total", "request_duration_seconds", "cache_hits_total",
        "cache_misses_total", "singleflight_coalesced_total", "ssrf_blocks_total",
        "dns_failures_total", "rate_limited_total", "concurrency_limited_total",
    ):
        assert expected in body, f"expected metric family '{expected}' in /metrics output"
    print(f"  [OK] /metrics returned {len(body)} bytes containing all expected metric families")


def test_metrics_endpoint_not_in_openapi_schema():
    print("\n--- /metrics: excluded from public OpenAPI schema (internal endpoint) ---")
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    assert "/metrics" not in schema.get("paths", {})
    print("  [OK] /metrics hidden from schema")


def test_request_completion_emits_structured_json_log_with_request_id():
    print("\n--- Structured logging: request completion is one JSON line with request_id/endpoint/duration_ms ---")
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        client = TestClient(app)
        resp = client.get("/health", headers={"X-Request-ID": "test-rid-12345"})
        assert resp.status_code == 200
        assert resp.headers["x-request-id"] == "test-rid-12345"
    finally:
        root.removeHandler(handler)

    lines = [ln for ln in stream.getvalue().splitlines() if ln.strip()]
    assert lines, "expected at least one log line"
    matching = [json.loads(ln) for ln in lines if '"event": "request_completed"' in ln or '"event":"request_completed"' in ln]
    assert matching, f"expected a request_completed log line, got: {lines}"
    entry = matching[-1]
    assert entry["request_id"] == "test-rid-12345"
    assert entry["endpoint"] == "/health"
    assert entry["status"] == 200
    assert isinstance(entry["duration_ms"], (int, float))
    print(f"  [OK] structured log entry: {entry}")


def test_json_formatter_produces_valid_json_for_plain_log_calls():
    print("\n--- Structured logging: ordinary logger.info(...) calls still produce valid JSON ---")
    record = logging.LogRecord(
        name="metadata-api", level=logging.INFO, pathname=__file__, lineno=1,
        msg="Cache hit: %s", args=("some-key",), exc_info=None,
    )
    line = JsonFormatter().format(record)
    parsed = json.loads(line)
    assert parsed["message"] == "Cache hit: some-key"
    assert parsed["level"] == "INFO"
    print(f"  [OK] plain call -> {line}")


def test_json_formatter_redacts_credentials_embedded_in_an_arbitrary_url_field():
    print("\n--- Structured logging: credentials embedded in a URL value are redacted regardless of field name ---")
    record = logging.LogRecord(
        name="metadata-api", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="Connecting", args=(), exc_info=None,
    )
    # Field name deliberately NOT in the exact-match redact-key list, to
    # exercise the value-pattern fallback (any URL with embedded user:pass@).
    record.connection_string = "redis://user:supersecret@redis-host:6379/0"
    line = JsonFormatter().format(record)
    assert "supersecret" not in line
    assert "***" in line
    print(f"  [OK] redacted -> {line}")


def test_json_formatter_redacts_exact_key_match_regardless_of_value_shape():
    print("\n--- Structured logging: known-sensitive field names are redacted even without a URL shape ---")
    record = logging.LogRecord(
        name="metadata-api", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="Connecting", args=(), exc_info=None,
    )
    record.redis_url = "redis://user:supersecret@redis-host:6379/0"
    line = JsonFormatter().format(record)
    parsed = json.loads(line)
    assert parsed["redis_url"] == "***REDACTED***"
    print(f"  [OK] redacted -> {line}")


def test_json_formatter_redacts_known_sensitive_field_names():
    print("\n--- Structured logging: fields named like secrets are fully redacted regardless of value ---")
    record = logging.LogRecord(
        name="metadata-api", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="Auth check", args=(), exc_info=None,
    )
    record.authorization = "Bearer abc123"
    record.api_key = "sk-live-xyz"
    line = JsonFormatter().format(record)
    parsed = json.loads(line)
    assert parsed["authorization"] == "***REDACTED***"
    assert parsed["api_key"] == "***REDACTED***"
    print(f"  [OK] redacted fields -> {line}")


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_cache_hit_and_miss_counters()
        test_ssrf_block_and_dns_failure_counters()
        test_singleflight_coalesced_counter()
        test_metrics_endpoint_exposes_prometheus_text_format()
        test_metrics_endpoint_not_in_openapi_schema()
        test_request_completion_emits_structured_json_log_with_request_id()
        test_json_formatter_produces_valid_json_for_plain_log_calls()
        test_json_formatter_redacts_credentials_embedded_in_an_arbitrary_url_field()
        test_json_formatter_redacts_exact_key_match_regardless_of_value_shape()
        test_json_formatter_redacts_known_sensitive_field_names()
        print("\n[OK] ALL PHASE 6 OBSERVABILITY TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
