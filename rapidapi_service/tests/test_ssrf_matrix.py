"""
Exhaustive SSRF test matrix (Plan §48). Uses mocked DNS resolution (no live
network needed — deterministic in any environment, including this sandbox
which has no direct DNS egress) to exercise app.security.ssrf.validate_url_ssrf
against every IPv4/IPv6 range class called out in the plan, mixed
public+private DNS answers, forbidden URL schemes, and end-to-end redirect
SSRF (a public host redirecting to a private one must still be blocked).
"""
import asyncio
import socket
from unittest import mock

import httpx

from app.security.ssrf import validate_url_ssrf
from app.core.errors import AppError
from app.core.urls import normalize_and_validate_url
from app.fetcher.dns import dns_cache
import app.fetcher.client as fetcher_client


def _addrinfo_v4(ips, port=443):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips]


def _addrinfo_v6(ips, port=443):
    return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ip, port, 0, 0)) for ip in ips]


def _expect_blocked(hostname, addr_info, label):
    dns_cache.clear()
    with mock.patch("app.security.ssrf.socket.getaddrinfo", return_value=addr_info):
        try:
            asyncio.run(validate_url_ssrf(f"https://{hostname}/"))
            raise AssertionError(f"[{label}] expected SSRF block for {hostname} -> {addr_info!r}, but it was ALLOWED")
        except AppError as e:
            assert e.status_code == 400, f"[{label}] expected 400, got {e.status_code}"
            print(f"  [BLOCKED OK] {label}: {hostname} -> {[a[4][0] for a in addr_info]}")


def _expect_allowed(hostname, addr_info, label):
    dns_cache.clear()
    with mock.patch("app.security.ssrf.socket.getaddrinfo", return_value=addr_info):
        ip_pinned_url, resolved_hostname = asyncio.run(validate_url_ssrf(f"https://{hostname}/"))
        assert resolved_hostname == hostname
        print(f"  [ALLOWED OK] {label}: {hostname} -> {[a[4][0] for a in addr_info]} -> {ip_pinned_url}")


# ----------------------------------------------------------------------------
# IPv4 dangerous ranges (Plan §48 IPv4 list)
# ----------------------------------------------------------------------------
IPV4_BLOCKED_CASES = [
    ("loopback.ssrfcheck", "127.0.0.1", "loopback"),
    ("rfc1918-10.ssrfcheck", "10.1.2.3", "10/8 private"),
    ("rfc1918-172.ssrfcheck", "172.16.5.5", "172.16/12 private"),
    ("rfc1918-192.ssrfcheck", "192.168.1.1", "192.168/16 private"),
    ("linklocal.ssrfcheck", "169.254.1.1", "169.254/16 link-local"),
    ("unspecified.ssrfcheck", "0.0.0.0", "0.0.0.0 unspecified"),
    ("multicast.ssrfcheck", "224.0.0.1", "multicast"),
    ("reserved.ssrfcheck", "240.0.0.1", "reserved (240/4)"),
    ("testnet1.ssrfcheck", "192.0.2.1", "documentation TEST-NET-1"),
    ("testnet2.ssrfcheck", "198.51.100.1", "documentation TEST-NET-2"),
    ("testnet3.ssrfcheck", "203.0.113.1", "documentation TEST-NET-3"),
    ("cgnat.ssrfcheck", "100.64.0.1", "carrier-grade NAT (100.64/10)"),
    ("benchmarking.ssrfcheck", "198.18.0.1", "benchmarking (198.18/15)"),
    ("metadata.ssrfcheck", "169.254.169.254", "cloud metadata address"),
]


def test_ipv4_dangerous_ranges_blocked():
    print("\n--- SSRF matrix: IPv4 dangerous ranges ---")
    for hostname, ip, label in IPV4_BLOCKED_CASES:
        _expect_blocked(hostname, _addrinfo_v4([ip]), label)


def test_ipv4_public_allowed():
    print("\n--- SSRF matrix: IPv4 public address allowed ---")
    _expect_allowed("public-v4.ssrfcheck", _addrinfo_v4(["93.184.216.34"]), "public IPv4")


# ----------------------------------------------------------------------------
# IPv6 dangerous ranges (Plan §48 IPv6 list)
# ----------------------------------------------------------------------------
IPV6_BLOCKED_CASES = [
    ("v6-loopback.ssrfcheck", "::1", "IPv6 loopback"),
    ("v6-uniquelocal.ssrfcheck", "fc00::1", "unique local fc00::/7"),
    ("v6-linklocal.ssrfcheck", "fe80::1", "link-local fe80::/10"),
    ("v6-multicast.ssrfcheck", "ff02::1", "IPv6 multicast"),
    ("v6-unspecified.ssrfcheck", "::", "IPv6 unspecified"),
    ("v6-mapped-loopback.ssrfcheck", "::ffff:127.0.0.1", "IPv4-mapped IPv6 loopback"),
    ("v6-mapped-private.ssrfcheck", "::ffff:10.0.0.1", "IPv4-mapped IPv6 private"),
]


def test_ipv6_dangerous_ranges_blocked():
    print("\n--- SSRF matrix: IPv6 dangerous ranges ---")
    for hostname, ip, label in IPV6_BLOCKED_CASES:
        _expect_blocked(hostname, _addrinfo_v6([ip]), label)


def test_ipv6_public_allowed():
    print("\n--- SSRF matrix: IPv6 public address allowed ---")
    _expect_allowed("public-v6.ssrfcheck", _addrinfo_v6(["2606:2800:220:1:248:1893:25c8:1946"]), "public IPv6")


# ----------------------------------------------------------------------------
# Mixed DNS answers (Plan §48 DNS list): ANY dangerous address blocks the host
# ----------------------------------------------------------------------------
def test_dns_mixed_public_and_private_blocked():
    print("\n--- SSRF matrix: mixed DNS answers (public + private) ---")
    mixed = _addrinfo_v4(["93.184.216.34"]) + _addrinfo_v4(["10.0.0.1"])
    _expect_blocked("mixed-a-then-private.ssrfcheck", mixed, "public A + private A (order 1)")

    mixed_reversed = _addrinfo_v4(["10.0.0.1"]) + _addrinfo_v4(["93.184.216.34"])
    _expect_blocked("mixed-private-then-public.ssrfcheck", mixed_reversed, "private A + public A (order 2)")

    mixed_v4v6 = _addrinfo_v4(["93.184.216.34"]) + _addrinfo_v6(["fc00::1"])
    _expect_blocked("mixed-v4-public-v6-private.ssrfcheck", mixed_v4v6, "public IPv4 + private IPv6")


def test_dns_all_public_multi_answer_allowed():
    print("\n--- SSRF matrix: multiple public DNS answers allowed ---")
    all_public = _addrinfo_v4(["93.184.216.34", "93.184.216.35"])
    _expect_allowed("multi-public.ssrfcheck", all_public, "two public A records")


def test_dns_resolution_failure_blocked():
    print("\n--- SSRF matrix: DNS resolution failure (NXDOMAIN) blocked ---")
    dns_cache.clear()
    with mock.patch("app.security.ssrf.socket.getaddrinfo", side_effect=socket.gaierror("nxdomain")):
        try:
            asyncio.run(validate_url_ssrf("https://this-does-not-resolve.ssrfcheck/"))
            raise AssertionError("expected DNS_FAILURE block")
        except AppError as e:
            assert e.status_code == 400
            assert e.code == "DNS_FAILURE"
            print(f"  [BLOCKED OK] DNS failure -> code={e.code}")


# ----------------------------------------------------------------------------
# Forbidden schemes (Plan §48 Schemes list)
# ----------------------------------------------------------------------------
FORBIDDEN_SCHEMES = ["file", "gopher", "ftp", "data", "javascript", "customscheme"]


def test_forbidden_schemes_blocked():
    print("\n--- SSRF matrix: forbidden URL schemes ---")
    for scheme in FORBIDDEN_SCHEMES:
        try:
            normalize_and_validate_url(f"{scheme}://example.com/x")
            raise AssertionError(f"expected scheme '{scheme}' to be rejected")
        except AppError as e:
            assert e.status_code == 400
            print(f"  [BLOCKED OK] scheme='{scheme}' -> code={e.code}")


def test_blocked_hostname_literals_and_suffixes():
    print("\n--- SSRF matrix: blocked hostname literals/suffixes (defense-in-depth) ---")
    for hostname in ["localhost", "internal", "metadata.google.internal", "foo.localhost", "foo.internal", "foo.local"]:
        dns_cache.clear()
        try:
            asyncio.run(validate_url_ssrf(f"https://{hostname}/"))
            raise AssertionError(f"expected hostname '{hostname}' to be blocked by name")
        except AppError as e:
            assert e.status_code == 400
            print(f"  [BLOCKED OK] hostname='{hostname}' -> code={e.code}")


def test_disallowed_port_blocked():
    print("\n--- SSRF matrix: non-standard port blocked ---")
    dns_cache.clear()
    with mock.patch("app.security.ssrf.socket.getaddrinfo", return_value=_addrinfo_v4(["93.184.216.34"], port=22)):
        try:
            asyncio.run(validate_url_ssrf("https://public-weird-port.ssrfcheck:22/"))
            raise AssertionError("expected port 22 to be blocked")
        except AppError as e:
            assert e.status_code == 400
            print(f"  [BLOCKED OK] port=22 -> code={e.code}")


# ----------------------------------------------------------------------------
# Redirect SSRF (Plan §48 Redirects list): public -> private must be blocked
# end-to-end through the real fetch path, re-validating SSRF on every hop.
# ----------------------------------------------------------------------------
def test_redirect_to_private_ip_is_blocked():
    print("\n--- SSRF matrix: redirect from public host to private target blocked ---")
    dns_cache.clear()

    call_count = {"n": 0}

    async def fake_ssrf(url):
        call_count["n"] += 1
        if "public-redirector.ssrfcheck" in url:
            return (url, "public-redirector.ssrfcheck")
        # any redirect target resolves "privately" for this test
        raise AppError(status_code=400, code="SSRF_BLOCKED", detail="SSRF Protection: redirect target is private.")

    def handler(request):
        if "public-redirector.ssrfcheck" in str(request.url):
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
        return httpx.Response(200, content=b"should never get here")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher_client.http_client = client

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", fake_ssrf):
            try:
                await fetcher_client.fetch_raw_page("https://public-redirector.ssrfcheck/")
                raise AssertionError("expected redirect-to-private to be blocked")
            except AppError as e:
                assert e.status_code == 400
                print(f"  [BLOCKED OK] redirect to private target -> code={e.code}")
        await client.aclose()

    asyncio.run(go())
    assert call_count["n"] == 2, f"expected SSRF validation on both hops (initial + redirect), got {call_count['n']}"
    print(f"  [OK] SSRF re-validated on every hop ({call_count['n']} validations for 1 redirect)")


def test_redirect_hop_limit_enforced():
    print("\n--- SSRF matrix: redirect hop limit enforced ---")
    dns_cache.clear()

    async def fake_ssrf(url):
        return (url, "redirect-loop.ssrfcheck")

    hop_counter = {"n": 0}

    def handler(request):
        hop_counter["n"] += 1
        return httpx.Response(302, headers={"location": f"https://redirect-loop.ssrfcheck/hop{hop_counter['n']}"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher_client.http_client = client

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", fake_ssrf):
            try:
                await fetcher_client.fetch_raw_page("https://redirect-loop.ssrfcheck/")
                raise AssertionError("expected redirect limit to trigger")
            except AppError as e:
                assert e.status_code == 400
                assert e.code == "REDIRECT_LIMIT"
                print(f"  [OK] redirect limit enforced after {hop_counter['n']} hops -> code={e.code}")
        await client.aclose()

    asyncio.run(go())


if __name__ == "__main__":
    import sys
    import traceback
    tests = [
        test_ipv4_dangerous_ranges_blocked,
        test_ipv4_public_allowed,
        test_ipv6_dangerous_ranges_blocked,
        test_ipv6_public_allowed,
        test_dns_mixed_public_and_private_blocked,
        test_dns_all_public_multi_answer_allowed,
        test_dns_resolution_failure_blocked,
        test_forbidden_schemes_blocked,
        test_blocked_hostname_literals_and_suffixes,
        test_disallowed_port_blocked,
        test_redirect_to_private_ip_is_blocked,
        test_redirect_hop_limit_enforced,
    ]
    try:
        for t in tests:
            t()
        print(f"\n[OK] ALL {len(tests)} SSRF MATRIX TEST GROUPS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
