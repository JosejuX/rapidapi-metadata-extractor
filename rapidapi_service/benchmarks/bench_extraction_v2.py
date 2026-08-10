"""
Same benchmark as bench_extraction.py, adapted for the post-refactor app/
package layout (module-qualified patch targets instead of the main.py monolith).
See bench_extraction.py for full rationale on why network I/O is stubbed.
"""
import sys
import os
import json
import time
import asyncio
import statistics
import tracemalloc
from unittest import mock

SERVICE_DIR = sys.argv[1] if len(sys.argv) > 1 else "."
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "post_refactor.json"
LABEL = sys.argv[3] if len(sys.argv) > 3 else "post-refactor"

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
    import app.fetcher.client as fetcher_client
    import app.security.ssrf as ssrf_mod
    from app.cache.l1 import cache
    from app.extraction.pipeline import fetch_and_extract_raw

    results = {"label": LABEL, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "scenarios": {}}

    async def fake_validate_url_ssrf(url):
        return (url, "fixture.local")

    ssrf_patch = mock.patch.object(ssrf_mod, "validate_url_ssrf", fake_validate_url_ssrf)
    pipeline_ssrf_patch = mock.patch("app.fetcher.client.validate_url_ssrf", fake_validate_url_ssrf)

    with ssrf_patch, pipeline_ssrf_patch:
        for fixture_name in FIXTURE_FILES:
            body = load_fixture(fixture_name)
            fetcher_client.http_client = make_fake_client(body)

            durations_ms = []
            for i in range(N_ITER):
                url = f"https://fixture-{fixture_name}-{i}.example.com/page"
                t0 = time.perf_counter()
                await fetch_and_extract_raw(url, user_agent=None)
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

        for fixture_name in ("basic", "large_256kb"):
            body = load_fixture(fixture_name)
            fetcher_client.http_client = make_fake_client(body)

            warm_url = f"https://fixture-hit-{fixture_name}.example.com/page"
            await fetch_and_extract_raw(warm_url, user_agent=None)

            durations_ms = []
            for i in range(N_CACHE_ITER):
                t0 = time.perf_counter()
                await fetch_and_extract_raw(warm_url, user_agent=None)
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

    cache.clear()
    tracemalloc.start()
    body = load_fixture("large_256kb")
    fetcher_client.http_client = make_fake_client(body)
    with mock.patch.object(ssrf_mod, "validate_url_ssrf", fake_validate_url_ssrf), \
         mock.patch("app.fetcher.client.validate_url_ssrf", fake_validate_url_ssrf):
        for i in range(100):
            await fetch_and_extract_raw(f"https://mem-test-{i}.example.com/page", user_agent=None)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    results["memory"] = {
        "scenario": "100x large_256kb sequential requests",
        "current_bytes": current,
        "peak_bytes": peak,
        "peak_mb": round(peak / (1024 * 1024), 2),
    }

    results["environment_note"] = (
        "Same stubbed-network methodology as baseline.json — see that file's "
        "environment_note for the full rationale."
    )

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(json.dumps(results, indent=2))
    print(f"\nWritten to {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
