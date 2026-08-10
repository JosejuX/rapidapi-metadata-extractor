"""
Prometheus metrics (Plan section 39): "Add Prometheus/OpenTelemetry only if
the hot-path cost is negligible." All instruments here are plain
prometheus_client Counter/Histogram objects — `.inc()` and `.observe()` are
O(1) atomic operations on a plain float behind a lock-free CAS loop in the
C extension when available, which is the standard justification the
Prometheus client itself gives for calling them unconditionally on hot
paths. This module has zero imports from the rest of `app/`, so importing
it anywhere can never create a circular-import problem.

Deliberate deviation from the plan's literal metric list: the plan lists
`requests_total`, `requests_by_endpoint` and `requests_by_status` as three
separate metrics. Standard Prometheus practice (and the client library's
own guidance) is one labeled counter instead — three counters for the same
event would triple the increment cost and the label cardinality is
identical either way. `requests_total{endpoint=...,status=...}` covers all
three; `sum by (endpoint) (...)` / `sum by (status) (...)` in PromQL
reproduce the by-endpoint / by-status breakdowns.

Registered on a dedicated CollectorRegistry (not the global default
REGISTRY) so /metrics output stays focused on this API's own instruments —
no default Python process/platform collectors (which pull in gc stats,
memory maps, etc.) unless explicitly wanted later.
"""
from prometheus_client import Counter, Histogram, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST

registry = CollectorRegistry()

_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

REQUESTS_TOTAL = Counter(
    "requests_total", "Total HTTP requests handled, by endpoint and status code.",
    ["endpoint", "status"], registry=registry,
)
REQUEST_DURATION_SECONDS = Histogram(
    "request_duration_seconds", "End-to-end request duration, by endpoint.",
    ["endpoint"], buckets=_DURATION_BUCKETS, registry=registry,
)
UPSTREAM_DURATION_SECONDS = Histogram(
    "upstream_duration_seconds", "Time spent fetching the target URL (connect through last byte read).",
    buckets=_DURATION_BUCKETS, registry=registry,
)
CACHE_HITS_TOTAL = Counter("cache_hits_total", "L1 extraction-result cache hits.", registry=registry)
CACHE_MISSES_TOTAL = Counter("cache_misses_total", "L1 extraction-result cache misses.", registry=registry)
CACHE_STALE_HITS_TOTAL = Counter(
    "cache_stale_hits_total", "Negative-result (recent-failure) cache hits — Plan §6.5.", registry=registry,
)
SINGLEFLIGHT_COALESCED_TOTAL = Counter(
    "singleflight_coalesced_total", "Requests that coalesced onto an in-flight fetch instead of triggering a new one.",
    registry=registry,
)
REDIS_ERRORS_TOTAL = Counter("redis_errors_total", "Redis connection/command failures.", registry=registry)
REDIS_RECONNECTS_TOTAL = Counter("redis_reconnects_total", "Successful Redis reconnections after an outage.", registry=registry)
SSRF_BLOCKS_TOTAL = Counter("ssrf_blocks_total", "Requests blocked by the anti-SSRF shield.", registry=registry)
DNS_FAILURES_TOTAL = Counter("dns_failures_total", "DNS resolution failures for target hostnames.", registry=registry)
UPSTREAM_TIMEOUTS_TOTAL = Counter("upstream_timeouts_total", "Connect or read timeouts against target hosts.", registry=registry)
BYTES_DOWNLOADED_TOTAL = Counter("bytes_downloaded_total", "Total bytes downloaded from target hosts.", registry=registry)
TRUNCATED_RESPONSES_TOTAL = Counter(
    "truncated_responses_total", "Responses cut off by the adaptive byte-limit streamer.", registry=registry,
)
RATE_LIMITED_TOTAL = Counter("rate_limited_total", "Requests rejected by the per-IP rate limiter.", registry=registry)
CONCURRENCY_LIMITED_TOTAL = Counter(
    "concurrency_limited_total", "Requests rejected by the per-host outbound concurrency limiter.", registry=registry,
)


def render_metrics() -> bytes:
    """Renders the current metric values in Prometheus text exposition format."""
    return generate_latest(registry)
