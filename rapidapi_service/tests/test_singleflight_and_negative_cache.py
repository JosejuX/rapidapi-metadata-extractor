"""
Phase 4 tests: request single-flight (Plan §6.7/§52), DNS single-flight
(Plan §5), and negative-result caching (Plan §6.5).
"""
import asyncio
import socket
from unittest import mock

import httpx

import app.fetcher.client as fetcher_client
import app.security.ssrf as ssrf_mod
import app.cache.singleflight as sf_mod
import app.cache.negative as neg_mod
from app.cache.l1 import cache as l1_cache
from app.extraction.pipeline import fetch_and_extract_raw
from app.core.errors import AppError
from app.fetcher.dns import dns_cache


async def _fake_ssrf(url):
    return (url, "singleflight-fixture.ssrfcheck")


def _slow_transport(body: bytes, delay: float, call_counter: dict):
    class SlowTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            call_counter["n"] += 1
            await asyncio.sleep(delay)
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)
    return SlowTransport()


def test_extraction_single_flight_coalesces_concurrent_identical_requests():
    print("\n--- Single-flight: 20 concurrent identical requests -> 1 upstream fetch ---")
    l1_cache.clear()
    sf_mod._in_flight.clear()
    neg_mod._negative_cache.clear()

    call_counter = {"n": 0}
    body = b"<html><head><title>Singleflight Fixture</title></head><body><p>hi</p></body></html>"
    fetcher_client.http_client = httpx.AsyncClient(transport=_slow_transport(body, 0.15, call_counter))

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            n = 20
            tasks = [
                asyncio.create_task(fetch_and_extract_raw("https://singleflight-fixture.ssrfcheck/same-page"))
                for _ in range(n)
            ]
            results = await asyncio.gather(*tasks)
            assert call_counter["n"] == 1, f"expected exactly 1 upstream fetch, got {call_counter['n']}"
            titles = {r["metadata"]["title"] for r in results}
            assert titles == {"Singleflight Fixture"}, f"all {n} callers should get the same result, got {titles}"
            print(f"  [OK] {n} concurrent requests -> {call_counter['n']} upstream fetch, "
                  f"all {n} callers got the coalesced result")

    asyncio.run(go())


def test_single_flight_does_not_wrongly_coalesce_different_urls():
    print("\n--- Single-flight: different URLs are NOT coalesced together ---")
    l1_cache.clear()
    sf_mod._in_flight.clear()
    neg_mod._negative_cache.clear()

    call_counter = {"n": 0}
    body = b"<html><head><title>T</title></head><body>x</body></html>"
    fetcher_client.http_client = httpx.AsyncClient(transport=_slow_transport(body, 0.05, call_counter))

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            tasks = [
                asyncio.create_task(fetch_and_extract_raw(f"https://singleflight-fixture.ssrfcheck/page-{i}"))
                for i in range(5)
            ]
            await asyncio.gather(*tasks)
            assert call_counter["n"] == 5, f"expected 5 distinct fetches for 5 distinct URLs, got {call_counter['n']}"
            print(f"  [OK] 5 distinct URLs -> {call_counter['n']} distinct upstream fetches")

    asyncio.run(go())


def test_dns_single_flight_coalesces_concurrent_lookups():
    print("\n--- DNS single-flight: 15 concurrent requests to same host -> 1 getaddrinfo() call ---")
    dns_cache.clear()
    sf_mod._in_flight.clear()

    call_counter = {"n": 0}
    addr_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    def slow_getaddrinfo(*args, **kwargs):
        call_counter["n"] += 1
        import time
        time.sleep(0.05)
        return addr_info

    async def go():
        with mock.patch("app.security.ssrf.socket.getaddrinfo", side_effect=slow_getaddrinfo):
            tasks = [
                asyncio.create_task(ssrf_mod.validate_url_ssrf("https://dns-singleflight-fixture.ssrfcheck/"))
                for _ in range(15)
            ]
            results = await asyncio.gather(*tasks)
            assert call_counter["n"] == 1, f"expected exactly 1 getaddrinfo() call, got {call_counter['n']}"
            assert all(r[1] == "dns-singleflight-fixture.ssrfcheck" for r in results)
            print(f"  [OK] 15 concurrent lookups -> {call_counter['n']} real DNS resolution "
                  f"(rest coalesced + cached)")

    asyncio.run(go())


def test_negative_cache_short_circuits_repeated_failures():
    print("\n--- Negative cache: repeated failures to a broken target skip the network ---")
    l1_cache.clear()
    sf_mod._in_flight.clear()
    neg_mod._negative_cache.clear()

    call_counter = {"n": 0}

    class FailingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            call_counter["n"] += 1
            raise httpx.ConnectTimeout("simulated connect timeout", request=request)

    fetcher_client.http_client = httpx.AsyncClient(transport=FailingTransport())

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            for i in range(3):
                try:
                    await fetch_and_extract_raw("https://negcache-fixture.ssrfcheck/broken")
                    raise AssertionError("expected failure")
                except AppError as e:
                    assert e.code == "CONNECTION_TIMEOUT"
            print(f"  [OK] 3 sequential requests to a broken target -> only {call_counter['n']} real network attempt(s)")
            assert call_counter["n"] == 1, f"expected only 1 real network attempt (rest served from negative cache), got {call_counter['n']}"

    asyncio.run(go())


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_extraction_single_flight_coalesces_concurrent_identical_requests()
        test_single_flight_does_not_wrongly_coalesce_different_urls()
        test_dns_single_flight_coalesces_concurrent_lookups()
        test_negative_cache_short_circuits_repeated_failures()
        print("\n[OK] ALL PHASE 4 CACHING/COALESCING TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
