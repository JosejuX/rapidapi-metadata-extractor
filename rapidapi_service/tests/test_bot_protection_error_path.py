"""
Bot-protection detection on the fetcher's error path (app/fetcher/client.py):
a 403/429/503 response gets a small bounded body peek before raising, so a
Cloudflare-style challenge page is classified as BOT_PROTECTION_DETECTED
instead of the generic UPSTREAM_4XX/UPSTREAM_5XX — while a genuine outage
(same status code, no challenge-page signature) still classifies normally.

Uses httpx.MockTransport so the real httpx response/streaming pipeline runs,
matching test_security_hardening.py's approach.
"""
import asyncio
from unittest import mock

import httpx
import pytest

import app.fetcher.client as fetcher_client
from app.core.errors import AppError, BOT_PROTECTION_DETECTED, UPSTREAM_5XX

_CF_CHALLENGE_BODY = b"""<html><head><title>Just a moment...</title></head><body>
<div class="cf-browser-verification">Checking your browser before accessing example.com.</div>
</body></html>"""


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


def test_cloudflare_challenge_503_is_classified_as_bot_protection():
    def handler(request):
        return httpx.Response(503, headers={"content-type": "text/html"}, content=_CF_CHALLENGE_BODY)

    with pytest.raises(AppError) as exc_info:
        _run_fetch(handler)
    assert exc_info.value.code == BOT_PROTECTION_DETECTED
    assert exc_info.value.retryable is False


def test_genuine_503_outage_without_challenge_signature_is_unaffected():
    def handler(request):
        return httpx.Response(503, headers={"content-type": "text/html"}, content=b"<html><body>Service Unavailable</body></html>")

    with pytest.raises(AppError) as exc_info:
        _run_fetch(handler)
    assert exc_info.value.code == UPSTREAM_5XX
    assert exc_info.value.retryable is True


def test_challenge_page_served_with_403_is_also_classified_as_bot_protection():
    def handler(request):
        return httpx.Response(403, headers={"content-type": "text/html"}, content=_CF_CHALLENGE_BODY)

    with pytest.raises(AppError) as exc_info:
        _run_fetch(handler)
    assert exc_info.value.code == BOT_PROTECTION_DETECTED


def test_ordinary_404_is_never_peeked_at_and_classifies_normally():
    # 404 isn't in the bot-protection check list — must classify as a plain
    # UPSTREAM_4XX even if the body happens to mention "captcha" in passing.
    from app.core.errors import UPSTREAM_4XX

    def handler(request):
        return httpx.Response(404, headers={"content-type": "text/html"}, content=b"<html><body>Not found. See our captcha docs.</body></html>")

    with pytest.raises(AppError) as exc_info:
        _run_fetch(handler)
    assert exc_info.value.code == UPSTREAM_4XX
