"""
Negative-result caching (Plan §6.5): briefly cache upstream failures so a
broken/slow target doesn't repeat the same expensive failure (DNS lookup,
connection attempt, full timeout budget) for every request hitting it during
an outage. Deliberately excludes input-validation errors (SSRF_BLOCKED,
INVALID_URL, UNSUPPORTED_SCHEME, etc.) — those are already cheap/instant to
re-derive and caching them would just add complexity for no benefit.

A plain dict with manual (expiry_timestamp, error) tuples rather than a
TTLCache instance: different error codes need different TTLs (Plan example:
NXDOMAIN 30s, timeout 5-10s, 5xx 5s, 404 15s) and TTLCache only supports one
fixed TTL per instance.
"""
import time
from typing import Dict, Optional, Tuple

from app.core.errors import AppError

# TTL per error code (seconds). Codes not listed here are never cached as
# negative results (validation/SSRF errors are cheap to re-derive; caching
# them would risk masking a since-fixed client mistake for no real gain).
NEGATIVE_TTL_SECONDS: Dict[str, int] = {
    "DNS_FAILURE": 30,
    "CONNECTION_TIMEOUT": 8,
    "UPSTREAM_TIMEOUT": 8,
    "UPSTREAM_5XX": 5,
    "UPSTREAM_4XX": 15,
}

_negative_cache: Dict[str, Tuple[float, str, str, bool]] = {}  # key -> (expiry, code, detail, retryable)

NEGATIVE_CACHE_MAXSIZE = 5000


def get_cached_negative(key: str) -> Optional[AppError]:
    entry = _negative_cache.get(key)
    if entry is None:
        return None
    expiry, code, detail, retryable = entry
    if time.time() >= expiry:
        _negative_cache.pop(key, None)
        return None
    return AppError(status_code=400, code=code, detail=f"{detail} (cached failure, retry in a few seconds)", retryable=retryable)


def maybe_cache_negative(key: str, err: AppError) -> None:
    ttl = NEGATIVE_TTL_SECONDS.get(getattr(err, "code", None))
    if ttl is None:
        return
    if len(_negative_cache) >= NEGATIVE_CACHE_MAXSIZE:
        # Cheap bound: drop the whole table rather than tracking LRU for what
        # is meant to be a short-lived, self-expiring cache.
        _negative_cache.clear()
    _negative_cache[key] = (time.time() + ttl, err.code, err.detail, err.retryable)
