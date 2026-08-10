"""Per-host circuit breaker (Plan §10)."""
import asyncio
import time
from unittest import mock

import httpx

import app.fetcher.client as fetcher_client
import app.fetcher.circuit_breaker as cb
from app.core.errors import AppError


async def _fake_ssrf(url):
    return (url, "circuitbreaker-fixture.ssrfcheck")


def _timeout_transport(counter: dict):
    class TimeoutTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            counter["n"] += 1
            raise httpx.ConnectTimeout("simulated", request=request)
    return TimeoutTransport()


def test_circuit_opens_after_threshold_failures_and_fails_fast():
    print("\n--- Circuit breaker: opens after threshold, then fails fast without hitting the network ---")
    cb._circuits.clear()
    counter = {"n": 0}
    fetcher_client.http_client = httpx.AsyncClient(transport=_timeout_transport(counter))

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            # Drive it past FAILURE_THRESHOLD real failures (each hits the network).
            for i in range(cb.FAILURE_THRESHOLD):
                try:
                    await fetcher_client.fetch_raw_page("https://circuitbreaker-fixture.ssrfcheck/x")
                    raise AssertionError("expected timeout")
                except AppError as e:
                    assert e.code == "CONNECTION_TIMEOUT"
            assert counter["n"] == cb.FAILURE_THRESHOLD
            print(f"  [OK] {cb.FAILURE_THRESHOLD} real failures recorded, circuit state="
                  f"{cb._circuits['circuitbreaker-fixture.ssrfcheck'].state}")

            # Next request should fail FAST (CIRCUIT_OPEN) without touching the network.
            calls_before = counter["n"]
            try:
                await fetcher_client.fetch_raw_page("https://circuitbreaker-fixture.ssrfcheck/y")
                raise AssertionError("expected circuit open")
            except AppError as e:
                assert e.code == "CIRCUIT_OPEN", f"expected CIRCUIT_OPEN, got {e.code}"
            assert counter["n"] == calls_before, "circuit-open request should NOT hit the network"
            print("  [OK] subsequent request fails fast with CIRCUIT_OPEN, no network call made")

    asyncio.run(go())


def test_circuit_recovers_after_cooldown_on_success():
    print("\n--- Circuit breaker: half-open probe succeeds -> circuit closes ---")
    cb._circuits.clear()
    hostname = "circuitbreaker-recovery.ssrfcheck"

    # Force the circuit straight into OPEN with an expired cooldown so the
    # next request is treated as a half-open probe, without a real 30s sleep.
    circuit = cb._get(hostname)
    circuit.state = cb.OPEN
    circuit.opened_at = time.time() - cb.COOLDOWN_SECONDS - 1
    circuit.failure_count = cb.FAILURE_THRESHOLD

    body = b"<html><head><title>recovered</title></head><body>ok</body></html>"

    class OkTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)

    fetcher_client.http_client = httpx.AsyncClient(transport=OkTransport())

    async def fake_ssrf(url):
        return (url, hostname)

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", fake_ssrf):
            result = await fetcher_client.fetch_raw_page(f"https://{hostname}/probe")
            assert result["status_code"] == 200

    asyncio.run(go())
    assert cb._circuits[hostname].state == cb.CLOSED, "successful half-open probe should close the circuit"
    assert cb._circuits[hostname].failure_count == 0
    print("  [OK] circuit closed again after a successful probe past cooldown")


def test_circuit_not_tripped_by_4xx():
    print("\n--- Circuit breaker: ordinary 4xx errors do NOT trip the breaker ---")
    cb._circuits.clear()
    hostname = "circuitbreaker-4xx.ssrfcheck"

    class NotFoundTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(404, headers={"content-type": "text/html"}, content=b"<html>missing</html>")

    fetcher_client.http_client = httpx.AsyncClient(transport=NotFoundTransport())

    async def fake_ssrf(url):
        return (url, hostname)

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", fake_ssrf):
            for _ in range(cb.FAILURE_THRESHOLD + 3):
                try:
                    await fetcher_client.fetch_raw_page(f"https://{hostname}/missing")
                    raise AssertionError("expected 404")
                except AppError as e:
                    assert e.code == "UPSTREAM_4XX"

    asyncio.run(go())
    circuit = cb._circuits.get(hostname)
    state = circuit.state if circuit else cb.CLOSED
    assert state == cb.CLOSED, f"repeated 404s must never open the circuit, got state={state}"
    print(f"  [OK] {cb.FAILURE_THRESHOLD + 3} consecutive 404s did not open the circuit (state={state})")


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_circuit_opens_after_threshold_failures_and_fails_fast()
        test_circuit_recovers_after_cooldown_on_success()
        test_circuit_not_tripped_by_4xx()
        print("\n[OK] ALL CIRCUIT BREAKER TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
