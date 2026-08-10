"""
Backward-compatibility shim (Plan section 2: "don't break the public API" during
the module refactor). The real application now lives under app/ — this file
just re-exports what external entrypoints and tests still expect from
`main:...`:

- Deploy/runtime: `uvicorn main:app` / `gunicorn main:app` (Dockerfile,
  README_DEPLOY.md) keep working unchanged.
- test_api.py: `from main import app`, `from main import cache`,
  `from main import ip_rate_tracker`.

Object-identity-stable singletons (TTLCache instances, the FastAPI app,
plain functions) are re-exported directly below — safe because they're
mutated in place, never rebound. A few globals ARE rebound elsewhere
(http_client on startup, redis_client/redis_status/redis_mode on
connect/reconnect); those are proxied live via module __getattr__ (PEP 562)
so `main.http_client` etc. always reflect the current value instead of a
stale import-time copy.
"""
from app.main import app

from app.cache.l1 import cache
from app.fetcher.dns import dns_cache
from app.ratelimit.limiter import ip_rate_tracker

from app.core.urls import normalize_and_validate_url
from app.security.ssrf import validate_url_ssrf
from app.fetcher.client import sanitize_user_agent
from app.cache.keys import normalize_cache_url
from app.extraction.pipeline import fetch_and_extract_raw

from app.fetcher import client as _fetcher_client
from app.ratelimit import redis as _redis_state

# Old private name, still used by .github/workflows/ci.yml's Redis integration step.
_try_connect_redis = _redis_state.try_connect_redis

_LIVE_PROXIES = {
    "http_client": (_fetcher_client, "http_client"),
    "redis_client": (_redis_state, "redis_client"),
    "redis_status": (_redis_state, "redis_status"),
    "redis_mode": (_redis_state, "redis_mode"),
}


def __getattr__(name):
    """PEP 562 module __getattr__: proxies attributes that get rebound at
    runtime (not just mutated in place) so callers always see the live value."""
    if name in _LIVE_PROXIES:
        module, attr = _LIVE_PROXIES[name]
        return getattr(module, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
