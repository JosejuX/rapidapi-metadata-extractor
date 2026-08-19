"""
TLS/SSL certificate inspection (competitive-differentiator #4): opt-in only
via `include_tls_details=true` on GET /api/v1/security. Must be `null` by
default (no extra handshake performed), and every failure mode inside
fetch_tls_details() must degrade to `None` rather than breaking the base
security-headers response.
"""
from unittest import mock

import httpx
from fastapi.testclient import TestClient

import app.fetcher.client as fetcher_client
from app.cache.l1 import cache as l1_cache
from app.extraction import pipeline
from app.extraction.tls import _cert_name_to_str, _parse_asn1_date
from app.main import app

FIXTURE_HTML = b"""<!DOCTYPE html>
<html><head><title>TLS Fixture</title></head><body><h1>TLS Fixture</h1></body></html>"""


async def _fake_ssrf(url):
    return (url, "tls-fixture.ssrfcheck")


def _fixed_transport(body: bytes):
    class FixedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(
                200,
                headers={"content-type": "text/html", "strict-transport-security": "max-age=63072000"},
                content=body,
            )
    return FixedTransport()


def _hit(path: str):
    l1_cache.clear()
    pipeline._raw_page_cache.clear()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        return client.get(path)


def test_tls_details_null_by_default():
    with mock.patch("app.api.security.fetch_tls_details") as mock_fetch:
        res = _hit("/api/v1/security?url=https://tls-fixture.ssrfcheck/page")
    assert res.status_code == 200
    assert res.json()["tls_details"] is None
    mock_fetch.assert_not_called()


def test_tls_details_populated_when_opted_in():
    fake_details = {
        "issuer": "CN=Fake CA",
        "subject": "CN=tls-fixture.ssrfcheck",
        "valid_from": "2026-01-01",
        "valid_until": "2027-01-01",
        "tls_version": "TLSv1.3",
        "is_expired": False,
    }

    async def _fake_fetch(hostname, port=443):
        return fake_details

    with mock.patch("app.api.security.fetch_tls_details", _fake_fetch):
        res = _hit("/api/v1/security?url=https://tls-fixture.ssrfcheck/page&include_tls_details=true")
    assert res.status_code == 200
    assert res.json()["tls_details"] == fake_details


def test_tls_lookup_failure_degrades_to_null_without_breaking_response():
    async def _failing_fetch(hostname, port=443):
        return None  # fetch_tls_details() itself never raises — every failure mode returns None

    with mock.patch("app.api.security.fetch_tls_details", _failing_fetch):
        res = _hit("/api/v1/security?url=https://tls-fixture.ssrfcheck/page&include_tls_details=true")
    assert res.status_code == 200
    assert res.json()["tls_details"] is None
    # Base security-headers audit still worked despite the TLS lookup failing.
    assert res.json()["security_score_percentage"] >= 0


def test_include_tls_details_false_is_equivalent_to_omitted():
    with mock.patch("app.api.security.fetch_tls_details") as mock_fetch:
        res = _hit("/api/v1/security?url=https://tls-fixture.ssrfcheck/page&include_tls_details=false")
    assert res.status_code == 200
    assert res.json()["tls_details"] is None
    mock_fetch.assert_not_called()


# ----------------------------------------------------------------------------
# Unit-level: date/name parsing helpers
# ----------------------------------------------------------------------------
def test_parse_asn1_date_valid():
    dt = _parse_asn1_date("Jan  1 00:00:00 2027 GMT")
    assert dt is not None
    assert dt.year == 2027 and dt.month == 1 and dt.day == 1


def test_parse_asn1_date_invalid_returns_none():
    assert _parse_asn1_date("not a date") is None
    assert _parse_asn1_date(None) is None


def test_cert_name_to_str_formats_rdn_tuples():
    name_tuple = (
        (("countryName", "US"),),
        (("organizationName", "Example Inc"),),
        (("commonName", "example.com"),),
    )
    result = _cert_name_to_str(name_tuple)
    assert result == "countryName=US, organizationName=Example Inc, commonName=example.com"


def test_cert_name_to_str_empty_returns_none():
    assert _cert_name_to_str(()) is None
    assert _cert_name_to_str(None) is None


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_tls_details_null_by_default()
        test_tls_details_populated_when_opted_in()
        test_tls_lookup_failure_degrades_to_null_without_breaking_response()
        test_include_tls_details_false_is_equivalent_to_omitted()
        test_parse_asn1_date_valid()
        test_parse_asn1_date_invalid_returns_none()
        test_cert_name_to_str_formats_rdn_tuples()
        test_cert_name_to_str_empty_returns_none()
        print("\n[OK] ALL TLS DETAILS TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
