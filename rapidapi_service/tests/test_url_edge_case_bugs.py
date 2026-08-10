"""
Regression tests for two bugs Hypothesis fuzzing found in this pass:

1. `url=[` (or any input where urlparse raises ValueError, e.g. an
   unterminated IPv6-literal-looking bracket) crashed with an unhandled
   500 instead of a clean 400 — reachable directly via the public
   /api/v1/extract?url= query parameter, and separately via a malformed
   href scraped from an arbitrary target page, or a malformed redirect
   Location header from an arbitrary target server.
2. normalize_and_validate_url() only checked for embedded userinfo
   (user:pass@host) when the raw input already had an explicit scheme —
   a scheme-less input like "0@" skipped that check, silently became
   "https://0@", and was accepted on the first call but rejected on a
   second (non-idempotent, and the credential check was bypassable by
   simply omitting the scheme).
"""
from unittest import mock

import httpx
import pytest
from fastapi.testclient import TestClient

import app.fetcher.client as fetcher_client
from app.cache.l1 import cache as l1_cache
from app.core.errors import AppError, INVALID_URL
from app.core.urls import normalize_and_validate_url, safe_urljoin, safe_urlparse
from app.main import app


# --- Unit level: app/core/urls.py -------------------------------------------

def test_unterminated_bracket_raises_clean_app_error_not_valueerror():
    with pytest.raises(AppError) as exc_info:
        normalize_and_validate_url("[")
    assert exc_info.value.code == INVALID_URL


def test_scheme_less_userinfo_is_rejected_consistently_with_scheme_present():
    # Both forms must be rejected the same way — previously only the
    # explicit-scheme form ("https://0@") was checked for userinfo.
    with pytest.raises(AppError) as exc_info_schemeless:
        normalize_and_validate_url("0@")
    with pytest.raises(AppError) as exc_info_scheme:
        normalize_and_validate_url("https://0@")
    assert exc_info_schemeless.value.code == INVALID_URL
    assert exc_info_scheme.value.code == INVALID_URL


def test_normalize_is_idempotent_for_previously_failing_case():
    # "0@" must now fail on the FIRST call rather than succeeding once and
    # failing differently on a second normalization pass.
    with pytest.raises(AppError):
        once = normalize_and_validate_url("0@")
        normalize_and_validate_url(once)  # would only run if the line above didn't raise


def test_safe_urljoin_returns_none_instead_of_raising():
    # A bare "[" is actually harmless to urljoin (treated as a relative path
    # segment) — it's an absolute malformed URL, e.g. from a scraped page's
    # <a href="http://["> or <link href="http://[">, that raises.
    assert safe_urljoin("https://example.com/", "http://[") is None


def test_safe_urlparse_returns_empty_result_instead_of_raising():
    result = safe_urlparse("http://[")
    assert result.netloc == ""


# --- End-to-end: the bracket bug was reachable via the public API ----------

async def _fake_ssrf(url):
    return (url, "url-edge-case-fixture.ssrfcheck")


def test_bracket_url_returns_400_not_500_via_real_route():
    l1_cache.clear()
    fetcher_client.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html></html>"))
    )
    client = TestClient(app)
    res = client.get("/api/v1/extract?url=%5B")  # url=[
    assert res.status_code == 400
    assert res.json()["error"]["code"] == INVALID_URL


def test_malformed_redirect_location_returns_clean_error_not_500():
    # A malicious/broken upstream sending a malformed absolute Location on a
    # redirect must not crash the fetcher — this is attacker/target-
    # controlled input, not the caller's own URL.
    l1_cache.clear()

    def handler(request):
        if "first" in str(request.url):
            return httpx.Response(302, headers={"location": "http://["})
        return httpx.Response(200, content=b"<html></html>")

    fetcher_client.http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        res = client.get("/api/v1/extract?url=" + "https://url-edge-case-fixture.ssrfcheck/first")
    assert res.status_code == 400
    assert res.status_code != 500
