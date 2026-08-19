"""
Redirect chain + shortened-URL detection (competitive-differentiator #1):
`redirect_count` and `is_shortened_url` must be present on every response,
regardless of which profile/endpoint computed it, and must reflect the
*original* input url's hostname (not final_url after redirects resolve it).
"""
from unittest import mock

import httpx
from fastapi.testclient import TestClient

import app.fetcher.client as fetcher_client
from app.cache.l1 import cache as l1_cache
from app.core.urls import KNOWN_URL_SHORTENER_HOSTS, is_shortened_url, safe_urlparse
from app.extraction import pipeline
from app.main import app

FIXTURE_HTML = b"""<!DOCTYPE html>
<html lang="en"><head><title>Redirect Fixture</title>
<meta name="description" content="A fixture page for redirect-count tests.">
</head><body><h1>Redirect Fixture</h1></body></html>"""


async def _fake_ssrf_any_host(url):
    return (url, safe_urlparse(url).hostname)


def _redirecting_transport(hops: int, body: bytes):
    state = {"n": 0}

    class RedirectingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if state["n"] < hops:
                state["n"] += 1
                return httpx.Response(
                    302,
                    headers={"location": f"https://redirect-fixture.ssrfcheck/hop{state['n']}"},
                )
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)

    return RedirectingTransport()


def _hit(path: str, hops: int):
    l1_cache.clear()
    pipeline._raw_page_cache.clear()
    fetcher_client.http_client = httpx.AsyncClient(transport=_redirecting_transport(hops, FIXTURE_HTML))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf_any_host):
        client = TestClient(app)
        return client.get(path)


def test_redirect_count_is_zero_when_no_redirects_occur():
    res = _hit("/api/v1/extract?url=https://redirect-fixture.ssrfcheck/start", hops=0)
    assert res.status_code == 200
    assert res.json()["redirect_count"] == 0


def test_redirect_count_reflects_actual_hop_count():
    res = _hit("/api/v1/extract?url=https://redirect-fixture.ssrfcheck/start", hops=3)
    assert res.status_code == 200
    assert res.json()["redirect_count"] == 3


def test_redirect_count_present_on_narrow_profile_endpoint():
    """Not just /extract (FULL_PROFILE) — a narrow specialized endpoint
    routed through _fetch_and_extract_partial must carry it too."""
    res = _hit("/api/v1/security?url=https://redirect-fixture.ssrfcheck/start", hops=2)
    assert res.status_code == 200
    assert res.json()["redirect_count"] == 2


def test_is_shortened_url_true_for_known_shortener_hosts():
    for host in ("bit.ly", "tinyurl.com", "t.co", "goo.gl"):
        assert is_shortened_url(f"https://{host}/abc123") is True, host


def test_is_shortened_url_false_for_ordinary_domain():
    assert is_shortened_url("https://example.com/some/long/path") is False
    assert is_shortened_url("https://redirect-fixture.ssrfcheck/start") is False


def test_known_url_shortener_hosts_frozenset_covers_spec_list():
    expected = {
        "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
        "buff.ly", "rebrand.ly", "cutt.ly", "shorturl.at", "tiny.cc",
    }
    assert expected <= KNOWN_URL_SHORTENER_HOSTS


def test_is_shortened_url_field_true_on_shortener_input_url():
    res = _hit("/api/v1/link-preview?url=https://bit.ly/some-campaign-link", hops=0)
    assert res.status_code == 200
    assert res.json()["is_shortened_url"] is True


def test_is_shortened_url_field_false_on_ordinary_input_url():
    res = _hit("/api/v1/link-preview?url=https://redirect-fixture.ssrfcheck/start", hops=0)
    assert res.status_code == 200
    assert res.json()["is_shortened_url"] is False


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_redirect_count_is_zero_when_no_redirects_occur()
        test_redirect_count_reflects_actual_hop_count()
        test_redirect_count_present_on_narrow_profile_endpoint()
        test_is_shortened_url_true_for_known_shortener_hosts()
        test_is_shortened_url_false_for_ordinary_domain()
        test_known_url_shortener_hosts_frozenset_covers_spec_list()
        test_is_shortened_url_field_true_on_shortener_input_url()
        test_is_shortened_url_field_false_on_ordinary_input_url()
        print("\n[OK] ALL REDIRECT/SHORTENER FIELD TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
