"""
Regression test for a real bug found by the accuracy benchmark
(benchmarks/bench_accuracy.py): app/fetcher/client.py advertises
`Accept-Encoding: gzip, deflate, br`, but the `brotli` package wasn't in
requirements.txt. httpx silently passed through the still-compressed bytes
for any Brotli response (very common on modern CDN-fronted sites — Vercel,
Cloudflare, WordPress.org, and others), which then got force-decoded as
UTF-8 text, producing garbage/mostly-empty extraction results with NO
error raised anywhere — title, JSON-LD, tech detection all silently wrong
on any Brotli-compressed page. No unit test existed for this because
test_security_hardening.py's MockTransport tests only exercised gzip.

Live confirmation before the fix: wordpress.org's real (br-encoded)
response produced metadata.title=None; installing brotli fixed it with no
other code change, and it lifted the accuracy benchmark's overall pass
rate from 61% to 100% across a 29-URL real-world sample (13 of the sample
URLs happened to be Brotli-encoded).
"""
import asyncio
from unittest import mock

import brotli
import httpx

import app.fetcher.client as fetcher_client

_PAGE_HTML = b"<html><head><title>Brotli Test Page</title></head><body>hello</body></html>"


async def _fake_ssrf(url):
    return (url, "example.com")


def _run_fetch(handler):
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher_client.http_client = client

    async def _go():
        try:
            with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
                return await fetcher_client.fetch_raw_page("https://example.com/page")
        finally:
            await client.aclose()

    return asyncio.run(_go())


def test_brotli_encoded_response_is_correctly_decoded():
    compressed = brotli.compress(_PAGE_HTML)

    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-encoding": "br"},
            content=compressed,
        )

    result = _run_fetch(handler)
    assert "<title>Brotli Test Page</title>" in result["html_content"]
    assert "�" not in result["html_content"], "decoded content contains replacement characters — decompression likely failed"
