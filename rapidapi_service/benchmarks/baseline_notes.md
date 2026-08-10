# Phase 1 Baseline — rapidapi-metadata-extractor

Recorded before the Phase 2 module refactor. Source: `main.py` at commit `be5fd79` (v3.0.0) plus
the uncommitted working-tree patches already present (request-ID middleware, TRUSTED_PROXY_IPS,
expanded social hostname map, Redis backoff+jitter).

## Environment constraint

This benchmark environment has no direct DNS egress (proxy-only network access) and the app's
own IP-pinned Anti-SSRF shield correctly refuses loopback/private targets by design — so neither
real internet fetches nor a local fixture HTTP server can be used for an honest end-to-end timing
run here. Live upstream fetch latency (DNS/connect/TLS/TTFB/download) must be measured in a real
deployment; this baseline instead isolates and measures internal server-side processing time
(cache lookup, HTML parse, single-pass extraction, serialization) with network I/O stubbed —
exactly the number Plan §1.3/§103 flags as the one under this project's control.

See `benchmarks/bench_extraction.py` for the harness and `benchmarks/baseline.json` for raw numbers.

## Test suite (`test_api.py`, offline in this sandbox)

7 / 12 tests pass without any network access:
`test_health`, `test_ssrf_security_shield`, `test_error_ip_sanitizer`,
`test_deterministic_local_mock_server`, `test_redis_rate_limiter_integration`,
`test_health_redis_observability`.

5 / 12 tests fail here only because they call live sites (github.com, python.org, httpb...) which
require DNS resolution unavailable in this sandbox: `test_schemeless_urls`,
`test_crlf_user_agent_sanitizer`, `test_field_filtering`, `test_all_sub_endpoints`,
`test_edge_case_resilience`. These should pass in CI/production where DNS works — this is a sandbox
limitation, not a code regression. It's also the exact problem Plan §47 calls out: don't depend on
live sites for the primary test suite. A follow-up (not in this pass) should port these to the
local fixture files now available in `tests/fixtures/html/`.

## Server-side processing latency (network stubbed), selected scenarios

| Scenario                    | Bytes    | p50 (ms) | p95 (ms) | p99 (ms) | throughput/s |
|------------------------------|---------|---------|---------|---------|--------------|
| cache_miss_basic              | 1,188   | 0.34    | 0.43    | 0.49    | 2,857        |
| cache_miss_unicode            | ~1,300  | see json |         |         |              |
| cache_miss_many_links (600 links) | 33,313 | 23.06 | 24.39 | 25.61 | 42.4 |
| cache_miss_heavy_jsonld (50 blocks) | 9,632 | 4.73 | 5.19 | 6.05 | 205.4 |
| cache_miss_many_scripts (200 tags) | 9,863 | 4.76 | 4.90 | 5.41 | 208.8 |
| cache_miss_large_64kb         | 72,538  | 34.10   | 35.16   | 36.49   | 29.1 |
| cache_miss_large_256kb        | 287,517 | 34.24   | 36.01   | 38.32   | 28.9 |
| cache_hit_basic                | 1,188   | 0.064   | 0.078   | 0.090   | 15,171 |
| cache_hit_large_256kb          | 287,517 | 0.065   | 0.074   | 0.082   | 15,172 |

Peak memory for 100 sequential 256 KB-page requests: **8.82 MB** (tracemalloc).

## Notable signal already visible in the baseline

The `many_links` fixture (33 KB, 600 `<a href>` tags) takes **23 ms** — slower than the 72 KB and
287 KB text-heavy fixtures (34 ms each, page-size-independent past ~64 KB because both are capped
by the same adaptive byte limit and dominated by fixed per-request parse cost). Link-heavy pages
are the current single-pass extraction loop's worst case: per-href `urljoin`/`urlparse` calls plus
two regex searches (`mailto:`, `tel:`) for every anchor. This matches Plan §64 ("Link extraction
performance") and is a good first-target for a later optimization pass — noted here, not touched
in this Phase 1/2 pass per the "measure before changing" rule.

Cache-hit dispatch overhead (~0.065 ms, independent of page size, as expected since `cache[key].copy()`
is O(payload dict shallow copy) not O(bytes)) already looks healthy against Plan §1.4's "no
perceptible degradation" bar — this is the number every future Phase 2+ change must be compared
against.
