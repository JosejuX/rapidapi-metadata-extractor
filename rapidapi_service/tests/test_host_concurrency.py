"""Per-host outbound concurrency limit (Plan §9)."""
import asyncio
from unittest import mock

import httpx

import app.fetcher.client as fetcher_client
import app.security.limits as limits_mod
from app.core.errors import AppError


async def _fake_ssrf(url):
    return (url, "concurrency-fixture.ssrfcheck")


def test_concurrency_limit_enforced_and_released():
    print("\n--- Per-host concurrency: limit enforced, then released for the next batch ---")
    limits_mod._host_semaphores.clear()
    limits_mod._host_last_used.clear()

    in_flight = {"count": 0, "max_seen": 0}
    release_event = asyncio.Event()

    async def slow_handler():
        in_flight["count"] += 1
        in_flight["max_seen"] = max(in_flight["max_seen"], in_flight["count"])
        await release_event.wait()
        in_flight["count"] -= 1
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    # httpx.MockTransport handler must be sync; use a small async wrapper via
    # a custom AsyncClient transport instead so we can actually hold requests open.
    class SlowTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return await slow_handler()

    client = httpx.AsyncClient(transport=SlowTransport())
    fetcher_client.http_client = client

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            n = 12  # > MAX_CONCURRENT_REQUESTS_PER_HOST
            tasks = [
                asyncio.create_task(fetcher_client.fetch_raw_page(f"https://concurrency-fixture.ssrfcheck/page{i}"))
                for i in range(n)
            ]
            await asyncio.sleep(0.1)  # let them all queue up against the semaphore
            assert in_flight["max_seen"] <= fetcher_client.config.MAX_CONCURRENT_REQUESTS_PER_HOST, (
                f"expected at most {fetcher_client.config.MAX_CONCURRENT_REQUESTS_PER_HOST} concurrent, "
                f"saw {in_flight['max_seen']}"
            )
            print(f"  [OK] {n} concurrent requests queued, only {in_flight['max_seen']} in flight "
                  f"(limit={fetcher_client.config.MAX_CONCURRENT_REQUESTS_PER_HOST})")

            release_event.set()  # let them all finish
            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [r for r in results if isinstance(r, Exception)]
            assert not errors, f"unexpected errors: {errors}"
            print(f"  [OK] all {n} requests completed successfully once slots freed up")

        # semaphore must be fully released afterwards (no leaked permits)
        sem = limits_mod._host_semaphores.get("concurrency-fixture.ssrfcheck")
        assert sem is not None
        assert sem._value == fetcher_client.config.MAX_CONCURRENT_REQUESTS_PER_HOST, (
            f"semaphore leaked permits: value={sem._value}, expected={fetcher_client.config.MAX_CONCURRENT_REQUESTS_PER_HOST}"
        )
        print("  [OK] semaphore fully released, no leaked permits")

    asyncio.run(go())


def test_semaphore_released_on_error_path():
    """A request that fails partway through (e.g. redirect limit) must still
    release its concurrency slot — otherwise repeated failures would leak
    permits and eventually starve the host entirely."""
    print("\n--- Per-host concurrency: slot released even when the request errors ---")
    limits_mod._host_semaphores.clear()
    limits_mod._host_last_used.clear()

    def handler(request):
        return httpx.Response(302, headers={"location": str(request.url)})  # infinite self-redirect

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher_client.http_client = client

    async def go():
        with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
            try:
                await fetcher_client.fetch_raw_page("https://concurrency-fixture.ssrfcheck/loop")
                raise AssertionError("expected redirect limit error")
            except AppError as e:
                assert e.code == "REDIRECT_LIMIT"
        await client.aclose()

    asyncio.run(go())
    sem = limits_mod._host_semaphores.get("concurrency-fixture.ssrfcheck")
    assert sem is not None
    assert sem._value == fetcher_client.config.MAX_CONCURRENT_REQUESTS_PER_HOST, "slot leaked on error path"
    print("  [OK] slot released cleanly after an error")


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_concurrency_limit_enforced_and_released()
        test_semaphore_released_on_error_path()
        print("\n[OK] ALL HOST CONCURRENCY TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
