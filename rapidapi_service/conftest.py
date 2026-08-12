"""Autouse isolation between tests, repo-wide (covers both test_api.py and
tests/*.py — pytest.ini has no testpaths restriction, so both are collected
in one session and share every module-level singleton below).

Several tests stub the network by reassigning `app.fetcher.client.http_client`
directly (per that module's own docstring: "tests that need to stub the
network must patch app.fetcher.client.http_client directly") but never
restore it afterward. Combined with the L1 cache, the raw-page cache, the
single-flight registry, the per-host circuit breaker, and the IP rate
limiter's TTLCache all being module-level singletons, one test's fixture
client/state — or, for test_api.py, its real request volume against the
shared TestClient IP — leaks into whatever test happens to run next. That
produced order-dependent failures (wrong/empty fields, spurious 429/circuit-
open responses) that don't reproduce when a file is run in isolation.

Resetting only in teardown isn't enough: the first test to run after a
dirty module (e.g. the first `tests/` test after test_api.py's real network
calls) would still inherit that pollution, since nothing cleaned up before
it. So this resets before *and* after every test.
"""
import pytest

import app.fetcher.client as fetcher_client
import app.extraction.pipeline as pipeline
import app.cache.singleflight as singleflight
import app.fetcher.circuit_breaker as circuit_breaker
import app.ratelimit.limiter as limiter
from app.cache.l1 import cache as l1_cache


def _reset():
    l1_cache.clear()
    pipeline._raw_page_cache.clear()
    singleflight._in_flight.clear()
    circuit_breaker._circuits.clear()
    limiter.ip_rate_tracker.clear()


@pytest.fixture(autouse=True)
def _isolate_global_state():
    original_http_client = fetcher_client.http_client
    _reset()
    yield
    fetcher_client.http_client = original_http_client
    _reset()
