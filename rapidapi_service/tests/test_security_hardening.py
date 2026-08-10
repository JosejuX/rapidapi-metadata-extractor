"""
Phase 3 regression tests (Plan §3.6 header limits, §3.7 decompression bombs).

Uses httpx.MockTransport so the REAL httpx decoding pipeline (gzip/br decode,
chunked delivery) runs, not a hand-rolled fake — these tests would have caught
the decompression-bomb gap this phase found and fixed. No pytest-asyncio
dependency: each test wraps its async body in asyncio.run(), matching the
sync style of the rest of test_api.py (Plan §71: minimal dependencies).
"""
import asyncio
import gzip
from unittest import mock

import httpx

import app.fetcher.client as fetcher_client
from app import config


async def _fake_ssrf(url):
    return (url, "example.com")


def _run_fetch(handler, **fetch_kwargs):
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher_client.http_client = client

    async def _go():
        try:
            with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
                return await fetcher_client.fetch_raw_page("https://example.com/page", **fetch_kwargs)
        finally:
            await client.aclose()

    return asyncio.run(_go())


def test_decompression_bomb_bounded():
    """A small compressed payload that decompresses to ~7MB must not blow past
    STREAM_HARD_LIMIT — this is the real httpx gzip decoder driving the response,
    not a fake, so it exercises the actual bug this phase found and fixed."""
    print("\n--- Decompression bomb: 27KB compressed -> ~7MB decompressed must be capped ---")
    big_html = (b"<html><body><p>" + (b"A" * 200) + b"</p></body></html>") * 30000
    compressed = gzip.compress(big_html)
    assert len(compressed) < 50_000, "test fixture sanity: compressed body should be small"

    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-encoding": "gzip"},
            content=compressed,
        )

    result = _run_fetch(handler)
    assert result["bytes_downloaded"] <= config.STREAM_HARD_LIMIT, (
        f"Decompression bomb NOT bounded: got {result['bytes_downloaded']} bytes, "
        f"expected <= {config.STREAM_HARD_LIMIT}"
    )
    assert result["content_truncated"] is True
    print(f"  [OK] {len(compressed)} bytes compressed -> {len(big_html)} bytes decompressed "
          f"-> capped at {result['bytes_downloaded']} bytes")


def test_header_count_limit_rejects():
    print("\n--- Header count limit: upstream sending 200 headers must be rejected ---")

    def handler(request):
        headers = {"content-type": "text/html"}
        for i in range(200):
            headers[f"x-bloat-header-{i}"] = "v"
        return httpx.Response(200, headers=headers, content=b"<html></html>")

    try:
        _run_fetch(handler)
        assert False, "expected AppError for excessive header count"
    except Exception as e:
        assert getattr(e, "status_code", None) == 400
        assert getattr(e, "code", None) == "HEADERS_TOO_LARGE"
        print(f"  [OK] rejected with code={e.code}")


def test_header_value_is_truncated_not_rejected():
    print("\n--- Oversized single header value: truncated, request still succeeds ---")
    huge_value = "v" * (config.MAX_HEADER_VALUE_LENGTH * 2)

    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "x-custom-big": huge_value},
            content=b"<html><head><title>ok</title></head><body>hi</body></html>",
        )

    result = _run_fetch(handler)
    assert len(result["resp_headers"]["x-custom-big"]) == config.MAX_HEADER_VALUE_LENGTH
    print(f"  [OK] header value truncated to {config.MAX_HEADER_VALUE_LENGTH} bytes, request succeeded")


def test_spa_detection_still_reaches_hard_limit():
    """Regression check for the hard_room capping fix: a page whose SPA
    signature appears only after the 64KB soft limit must still be allowed to
    grow to the full 256KB hard limit, not get frozen at 64KB."""
    print("\n--- SPA expansion still works after the decompression-bomb fix ---")
    filler = b"<!-- padding -->" * 4500  # ~72KB of filler before the SPA marker
    html = b"<html><head></head><body>" + filler + b'<div id="__next"></div>' + (b"x" * 300000) + b"</body></html>"

    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, content=html)

    result = _run_fetch(handler)
    assert result["bytes_downloaded"] > config.STREAM_SOFT_LIMIT, (
        "SPA signature after the soft limit should still trigger expansion to the hard limit"
    )
    assert result["bytes_downloaded"] <= config.STREAM_HARD_LIMIT
    print(f"  [OK] SPA page expanded to {result['bytes_downloaded']} bytes (soft={config.STREAM_SOFT_LIMIT}, hard={config.STREAM_HARD_LIMIT})")


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_decompression_bomb_bounded()
        test_header_count_limit_rejects()
        test_header_value_is_truncated_not_rejected()
        test_spa_detection_still_reaches_hard_limit()
        print("\n[OK] ALL SECURITY HARDENING TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
