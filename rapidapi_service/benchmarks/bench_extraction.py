"""
Phase 1 baseline benchmark (Plan section 120, Fase 1 / section 56).

Measures REAL server-side processing latency (cache lookup, HTML parse,
single-pass extraction, serialization) for main.fetch_and_extract_raw,
with network I/O and DNS/SSRF resolution stubbed out.

Why stub the network: this sandbox has no direct DNS resolution (proxy-only
egress), and the app's own IP-pinning Anti-SSRF shield correctly refuses to
fetch loopback/private targets by design — so a real end-to-end HTTP
benchmark against localhost fixtures is not possible here, and live internet
timings would measure this sandbox's proxy, not the app. What CAN be measured
honestly, and is what Plan section 1.3/103 actually cares about for hot-path
regressions, is internal processing time: parse + extraction + serialization.
Live upstream fetch latency must be measured in a real deployment (documented
as a known gap in baseline.json).

Usage:
    python3 bench_extraction.py <path-to-service-dir> <output-json> [label]
"""
import sys
import os
import json
import time
import asyncio
import statistics
import tracemalloc
from contextlib import asynccontextmanager
from unittest import mock

SERVICE_DIR = sys.argv[1] if len(sys.argv) > 1 else "."
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "baseline.json"
LABEL = sys.argv[3] if len(sys.argv) > 3 else "baseline"

sys.path.insert(0, SERVICE_DIR)

FIXTURES_DIR = os.path.join(SERVICE_DIR, "tests", "fixtures", "html")

FIXTURE_FILES = {
    "basic": "basic.html",
    "unicode": "unicode.html",
    "malformed": "malformed.html",
    "spa": "spa.html",
    "many_links": "many_links.html",
    "heavy_jsonld": "heavy_jsonld.html",
    "many_scripts": "many_scripts.html",
    "large_64kb": "large_64kb.html",
    "large_256kb": "large_256kb.html",
}

N_ITER = 200
N_CACHE_ITER = 500


def load_fixture(name: str) -> bytes:
    path = os.path.join(FIXTURES_DIR, FIXTURE_FILES[name])
    with open(path, "rb") as f:
        return f.read()


def percentile(data, pct):
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def make_fake_response(body: bytes, headers=None):
    class FakeResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = headers or {}
            self.encoding = "utf-8"

        def raise_for_status(self):
            pass

        async def aiter_bytes(self):
            chunk_size = 8192
            for i in range(0, len(body), chunk_size):
                yield body[i:i + chunk_size]

    return FakeResponse()


def make_fake_client(body: bytes):
    """Fakes httpx.AsyncClient enough for fetch_and_extract_raw's .stream() usage."""

    class FakeStreamCtx:
        def __init__(self, resp):
            self._resp = resp

        async def __aenter__(self):
            return self._resp

        async def __aexit__(self, *exc):
            return False

    class FakeClient:
        def stream(self, method, url, headers=None, extensions=None, follow_redirects=False):
            return FakeStreamCtx(make_fake_response(body))

        async def aclose(self):
            pass

    return FakeClient()


async def run_benchmark():
    import main  # the module under test (pre- or post-refactor entrypoint)

    results = {"label": LABEL, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "scenarios": {}}

    # Patch SSRF validation to skip real DNS resolution (network unavailable in sandbox).
    async def fake_validate_url_ssrf(url):
        parsed_hostname = "fixture.local"
        return (url, parsed_hostname)

    ssrf_patch = mock.patch.object(main, "validate_url_ssrf", fake_validate_url_ssrf)

    with ssrf_patch:
        # ---- cache-miss scenarios: one per fixture, unique URL per call to force full parse ----
        for fixture_name in FIXTURE_FILES:
            body = load_fixture(fixture_name)
            fake_client = make_fake_client(body)
            main.http_client = fake_client

            durations_ms = []
            for i in range(N_ITER):
                url = f"https://fixture-{fixture_name}-{i}.example.com/page"
                t0 = time.perf_counter()
                await main.fetch_and_extract_raw(url, user_agent=None)
                t1 = time.perf_counter()
                durations_ms.append((t1 - t0) * 1000.0)

            results["scenarios"][f"cache_miss_{fixture_name}"] = {
                "bytes": len(body),
                "n": len(durations_ms),
                "p50_ms": round(percentile(durations_ms, 50), 3),
                "p95_ms": round(percentile(durations_ms, 95), 3),
                "p99_ms": round(percentile(durations_ms, 99), 3),
                "mean_ms": round(statistics.mean(durations_ms), 3),
                "throughput_per_sec": round(1000.0 / statistics.mean(durations_ms), 1) if statistics.mean(durations_ms) > 0 else None,
            }

        # ---- cache-hit scenario: repeat the SAME url, measure dispatch overhead ----
        for fixture_name in ("basic", "large_256kb"):
            body = load_fixture(fixture_name)
            fake_client = make_fake_client(body)
            main.http_client = fake_client

            warm_url = f"https://fixture-hit-{fixture_name}.example.com/page"
            await main.fetch_and_extract_raw(warm_url, user_agent=None)  # warm the cache

            durations_ms = []
            for i in range(N_CACHE_ITER):
                t0 = time.perf_counter()
                await main.fetch_and_extract_raw(warm_url, user_agent=None)
                t1 = time.perf_counter()
                durations_ms.append((t1 - t0) * 1000.0)

            results["scenarios"][f"cache_hit_{fixture_name}"] = {
                "bytes": len(body),
                "n": len(durations_ms),
                "p50_ms": round(percentile(durations_ms, 50), 4),
                "p95_ms": round(percentile(durations_ms, 95), 4),
                "p99_ms": round(percentile(durations_ms, 99), 4),
                "mean_ms": round(statistics.mean(durations_ms), 4),
                "throughput_per_sec": round(1000.0 / statistics.mean(durations_ms), 1) if statistics.mean(durations_ms) > 0 else None,
            }

    # ---- memory: track peak allocation while processing the large fixture 100x ----
    main.cache.clear()
    tracemalloc.start()
    body = load_fixture("large_256kb")
    fake_client = make_fake_client(body)
    main.http_client = fake_client
    with mock.patch.object(main, "validate_url_ssrf", fake_validate_url_ssrf):
        for i in range(100):
            await main.fetch_and_extract_raw(f"https://mem-test-{i}.example.com/page", user_agent=None)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    results["memory"] = {
        "scenario": "100x large_256kb sequential requests",
        "current_bytes": current,
        "peak_bytes": peak,
        "peak_mb": round(peak / (1024 * 1024), 2),
    }

    results["environment_note"] = (
        "Network I/O and DNS/SSRF resolution were stubbed for this benchmark "
        "(sandbox has no direct DNS egress and the SSRF shield correctly blocks "
        "loopback targets by design). Numbers reflect internal server-side "
        "processing only: cache lookup, HTML parse, single-pass extraction, "
        "serialization. Live upstream fetch latency (DNS/connect/TLS/TTFB/"
        "download) must be measured separately in a real deployment."
    )

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(json.dumps(results, indent=2))
    print(f"\nWritten to {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
