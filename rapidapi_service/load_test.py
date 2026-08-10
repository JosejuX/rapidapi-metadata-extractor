"""
load_test.py — Concurrent Load Test for Web Metadata & Contact Extractor API
=============================================================================
Spins up the FastAPI app in a background thread, fires concurrent async
requests, and reports full latency statistics (min, avg, p50, p95, p99, max)
plus throughput (req/s) and error rate.

Usage:
    python load_test.py [--concurrency N] [--requests N] [--url URL]

Defaults:
    --concurrency 20   (simultaneous open connections)
    --requests    100  (total requests to fire)
    --url         https://github.com  (target page to extract)

No external packages required — uses only httpx + asyncio (already installed).
"""

import asyncio
import argparse
import statistics
import sys
import threading
import time
import uvicorn

# ── Start FastAPI server in a background daemon thread ──────────────────────

def start_server():
    config = uvicorn.Config(
        "main:app",
        host="127.0.0.1",
        port=18765,
        log_level="error",   # suppress access logs during test
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    server.run()

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

# Wait for the server to come online
import httpx, time as _t

BASE_URL = "http://127.0.0.1:18765"
_deadline = _t.time() + 10
while _t.time() < _deadline:
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=2)
        if r.status_code == 200:
            break
    except Exception:
        pass
    _t.sleep(0.1)
else:
    print("❌  Server failed to start within 10 seconds.")
    sys.exit(1)

# ── Async load-test engine ───────────────────────────────────────────────────

async def fire_request(client: httpx.AsyncClient, target_url: str) -> tuple[float, int]:
    """Fire one extraction request and return (latency_ms, status_code)."""
    start = _t.perf_counter()
    try:
        r = await client.get(
            f"{BASE_URL}/api/v1/extract",
            params={"url": target_url},
            timeout=30,
        )
        latency = (_t.perf_counter() - start) * 1000
        return latency, r.status_code
    except Exception as exc:
        latency = (_t.perf_counter() - start) * 1000
        return latency, 0  # 0 = connection error

BENCHMARK_DOMAINS = [
    "https://github.com",
    "https://wikipedia.org",
    "https://python.org",
    "https://news.ycombinator.com",
    "https://pypi.org",
    "https://dev.to",
    "https://reddit.com",
    "https://bbc.com",
    "https://stripe.com",
    "https://wordpress.org"
]

async def run_load_test(concurrency: int, total_requests: int, target_url: str, mode: str = "cache"):
    results: list[tuple[float, int]] = []
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_request(client, url_to_fetch):
        async with semaphore:
            return await fire_request(client, url_to_fetch)

    limits = httpx.Limits(max_connections=concurrency + 5, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits) as client:
        if mode == "cache":
            print(f"\n🔥  Mode: Cache Workload — Warm-up (2 requests to prime cache for {target_url})…")
            for _ in range(2):
                await fire_request(client, target_url)
            print(f"✅  Warm-up complete.\n")
            urls_to_test = [target_url] * total_requests
        else:
            print(f"\n🌐  Mode: Real Multi-Domain Workload — Testing across {len(BENCHMARK_DOMAINS)} live domains without cache priming…\n")
            urls_to_test = [BENCHMARK_DOMAINS[i % len(BENCHMARK_DOMAINS)] for i in range(total_requests)]

        # ── MAIN TEST ──
        print(f"⚡  Firing {total_requests} concurrent requests (concurrency={concurrency}, mode={mode})…")
        wall_start = _t.perf_counter()

        tasks = [asyncio.create_task(bounded_request(client, urls_to_test[i])) for i in range(total_requests)]
        results = await asyncio.gather(*tasks)

        wall_elapsed = _t.perf_counter() - wall_start

    return results, wall_elapsed

# ── Statistics & Report ──────────────────────────────────────────────────────

def percentile(data: list[float], p: float) -> float:
    """Return the p-th percentile of sorted data."""
    data_sorted = sorted(data)
    idx = max(0, int(len(data_sorted) * p / 100) - 1)
    return data_sorted[idx]

def print_report(results: list[tuple[float, int]], wall_elapsed: float, target_url: str, concurrency: int, mode: str):
    latencies = [lat for lat, _ in results]
    statuses  = [st  for _,  st in results]

    total      = len(results)
    successes  = sum(1 for s in statuses if 200 <= s < 300)
    errors     = total - successes
    error_rate = (errors / total) * 100 if total else 0
    rps        = total / wall_elapsed if wall_elapsed > 0 else 0

    print("\n" + "═" * 60)
    print("  📊  LOAD TEST RESULTS — Web Metadata Extractor API v2.7.0")
    print("═" * 60)
    print(f"  Benchmark Mode: {mode.upper()}")
    print(f"  Target URL    : {target_url if mode == 'cache' else '10 Multi-Site Domains'}")
    print(f"  Concurrency   : {concurrency} simultaneous connections")
    print(f"  Total requests: {total}")
    print(f"  Wall time     : {wall_elapsed:.2f}s")
    print(f"  Throughput    : {rps:.1f} req/s")
    print()
    print(f"  ── Latency (ms, {mode} mode) ──")
    print(f"  Min           : {min(latencies):.2f} ms")
    print(f"  Avg           : {statistics.mean(latencies):.2f} ms")
    print(f"  Median (P50)  : {percentile(latencies, 50):.2f} ms")
    print(f"  P95           : {percentile(latencies, 95):.2f} ms")
    print(f"  P99           : {percentile(latencies, 99):.2f} ms")
    print(f"  Max           : {max(latencies):.2f} ms")
    print()
    print("  ── Reliability ──")
    print(f"  Successes     : {successes}/{total} ({100 - error_rate:.1f}%)")
    print(f"  Errors        : {errors}/{total} ({error_rate:.1f}%)")

    if errors > 0:
        err_codes = {}
        for s in statuses:
            if not (200 <= s < 300):
                err_codes[s] = err_codes.get(s, 0) + 1
        print(f"  Error codes   : {err_codes}")

    print("═" * 60)

    # ── Verdict ──
    avg = statistics.mean(latencies)
    p99 = percentile(latencies, 99)
    if avg < 20 and p99 < 50 and error_rate == 0:
        print("  🏆  EXCELLENT — high throughput, zero errors. Production-ready.")
    elif error_rate < 5:
        print("  ✅  GOOD — fast multi-site processing with minimal errors.")
    else:
        print("  ⚠️   WARNING — error rate above 5%. Check server logs.")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description="Load test for Web Metadata Extractor API")
    parser.add_argument("--concurrency", type=int, default=20,  help="Simultaneous connections (default: 20)")
    parser.add_argument("--requests",    type=int, default=100, help="Total requests to fire (default: 100)")
    parser.add_argument("--url",         type=str, default="https://github.com", help="Target URL to extract")
    parser.add_argument("--mode",        type=str, choices=["cache", "real"], default="cache", help="Benchmark mode: 'cache' or 'real' multi-domain workload")
    args = parser.parse_args()

    results, wall_elapsed = asyncio.run(
        run_load_test(args.concurrency, args.requests, args.url, args.mode)
    )
    print_report(results, wall_elapsed, args.url, args.concurrency, args.mode)
