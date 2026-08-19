"""
DNS / WHOIS domain intelligence (competitive-differentiator #5): GET
/api/v1/domain never fetches the target page (no SSRF-fetch machinery
involved) — only DNS record resolution and a best-effort WHOIS lookup
against the hostname. Mocked at the app.api.domain module boundary
(fetch_dns_records/fetch_whois_info), same fixture-first, no-live-network
approach the rest of tests/ uses (Plan §47).
"""
from unittest import mock

from fastapi.testclient import TestClient

from app.main import app
from app.ratelimit.limiter import ip_rate_tracker

FAKE_DNS_RECORDS = {
    "A": ["93.184.216.34"],
    "AAAA": ["2606:2800:220:1:248:1893:25c8:1946"],
    "MX": [],
    "NS": ["a.iana-servers.net.", "b.iana-servers.net."],
    "TXT": ['"v=spf1 -all"'],
}

FAKE_WHOIS_INFO = {
    "registrar": "RESERVED-Internet Assigned Numbers Authority",
    "creation_date": "1995-08-14T04:00:00+00:00",
    "expiration_date": "2027-08-13T04:00:00+00:00",
    "name_servers": ["A.IANA-SERVERS.NET", "B.IANA-SERVERS.NET"],
}


_UNSET = object()


def _get(url_param: str, mock_dns=_UNSET, mock_whois=_UNSET):
    ip_rate_tracker.clear()

    async def _dns(hostname):
        return FAKE_DNS_RECORDS if mock_dns is _UNSET else mock_dns

    async def _whois(hostname):
        return FAKE_WHOIS_INFO if mock_whois is _UNSET else mock_whois

    with mock.patch("app.api.domain.fetch_dns_records", _dns), \
         mock.patch("app.api.domain.fetch_whois_info", _whois):
        client = TestClient(app)
        return client.get(f"/api/v1/domain?url={url_param}")


def test_domain_basic_dns_and_whois_resolution():
    res = _get("https://example.com")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["hostname"] == "example.com"
    assert data["dns_records"]["A"] == ["93.184.216.34"]
    assert data["dns_records"]["NS"] == ["a.iana-servers.net.", "b.iana-servers.net."]
    assert data["whois_info"]["registrar"] == "RESERVED-Internet Assigned Numbers Authority"


def test_domain_accepts_scheme_less_input():
    res = _get("example.com")
    assert res.status_code == 200
    assert res.json()["hostname"] == "example.com"


def test_domain_whois_failure_degrades_to_null_without_failing_request():
    res = _get("https://example.com", mock_whois=None)
    assert res.status_code == 200
    data = res.json()
    assert data["whois_info"] is None
    assert data["dns_records"]["A"] == ["93.184.216.34"]


def test_domain_empty_dns_records_still_returns_200():
    empty_dns = {"A": [], "AAAA": [], "MX": [], "NS": [], "TXT": []}
    res = _get("https://example.com", mock_dns=empty_dns)
    assert res.status_code == 200
    assert res.json()["dns_records"] == empty_dns


def test_domain_invalid_scheme_returns_400():
    res = _get("ftp://example.com")
    assert res.status_code == 400


def test_domain_garbage_url_returns_400():
    res = _get("http://")
    assert res.status_code == 400


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_domain_basic_dns_and_whois_resolution()
        test_domain_accepts_scheme_less_input()
        test_domain_whois_failure_degrades_to_null_without_failing_request()
        test_domain_empty_dns_records_still_returns_200()
        test_domain_invalid_scheme_returns_400()
        test_domain_garbage_url_returns_400()
        print("\n[OK] ALL DOMAIN ENDPOINT TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
