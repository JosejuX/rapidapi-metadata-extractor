"""
IP-based rate limiter: distributed Redis fixed-window when available, per-process
TTLCache fallback otherwise (Plan section 8).

NOTE: Fixed-window algorithm — intentional design choice for simplicity.
Trade-off: a burst of up to 2x limit at the window boundary is acceptable for
a public SaaS API protected upstream by the RapidAPI Gateway. Token bucket /
sliding window is a Plan §8.3 follow-up, not part of this behavior-preserving
refactor.

INCR+EXPIRE run as a single atomic Lua script (Plan §77), not two separate
round-trips: a plain `INCR` then `EXPIRE` leaves a window where, if the
process/connection dies between the two calls, the key survives with no TTL —
every request after that keeps incrementing a counter that never resets,
permanently rate-limiting that IP until Redis is flushed. The script also
collapses the common case to one round-trip instead of the previous
INCR-then-conditionally-EXPIRE two-trip path.
"""
import time

from cachetools import TTLCache
from fastapi import Request, Response

from app import config
from app.core.errors import RATE_LIMITED, AppError
from app.core.logging import logger
from app.observability import metrics
from app.ratelimit import redis as redis_state
from app.security.proxy import resolve_client_ip

ip_rate_tracker: TTLCache = TTLCache(maxsize=config.RATE_LIMIT_TRACKER_MAXSIZE, ttl=60)

# KEYS[1] = rate key, ARGV[1] = window TTL seconds. Atomic: either both the
# increment and the (first-hit-only) expire happen, or neither does.
_INCR_WITH_TTL_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


def _rate_limit_headers(remaining: int, reset_seconds: int) -> dict:
    return {
        "X-RateLimit-Limit": str(config.RATE_LIMIT_PER_MINUTE),
        "X-RateLimit-Remaining": str(max(0, remaining)),
        "X-RateLimit-Reset": str(reset_seconds),
    }


async def check_ip_rate_limit(request: Request, response: Response):
    """Enforces N req/min (config.RATE_LIMIT_PER_MINUTE) per client IP.
    Uses non-blocking Redis when available; falls back to per-process TTLCache.
    On Redis failure mid-request the status is updated immediately.

    Sets X-RateLimit-* on every response (success or 429) — `response` is the
    same object FastAPI ultimately returns, so headers set here on a
    `dependencies=[Depends(...)]`-style dependency (not just parameter-bound
    ones) still reach the client."""
    client_ip = resolve_client_ip(request)

    if redis_state.redis_client and redis_state.redis_status == "connected":
        try:
            rate_key = f"rate:{client_ip}"
            count = await redis_state.redis_client.eval(_INCR_WITH_TTL_SCRIPT, 1, rate_key, 60)
            # Redis doesn't tell us how far into the window we are without an
            # extra round-trip (TTL rate_key) — approximate with the fixed
            # window length rather than pay that cost on every request.
            headers = _rate_limit_headers(config.RATE_LIMIT_PER_MINUTE - count, 60)
            if count > config.RATE_LIMIT_PER_MINUTE:
                logger.warning("Rate limit exceeded via Redis for IP %s (%d/min)", client_ip, count)
                metrics.RATE_LIMITED_TOTAL.inc()
                raise AppError(
                    status_code=429,
                    code=RATE_LIMITED,
                    detail=f"Rate limit exceeded: {config.RATE_LIMIT_PER_MINUTE} requests per minute per client IP.",
                    headers={"Retry-After": "60", **headers},
                )
            response.headers.update(headers)
            return
        except AppError:
            raise
        except Exception as exc:
            redis_state.mark_degraded(str(exc))

    # Local TTLCache fallback (per-process fixed window)
    now = time.time()
    history = ip_rate_tracker.get(client_ip, [])
    valid = [t for t in history if now - t < 60]
    reset_seconds = 60 if not valid else max(1, round(60 - (now - min(valid))))
    if len(valid) >= config.RATE_LIMIT_PER_MINUTE:
        logger.warning("Rate limit exceeded via TTLCache for IP %s", client_ip)
        metrics.RATE_LIMITED_TOTAL.inc()
        raise AppError(
            status_code=429,
            code=RATE_LIMITED,
            detail=f"Rate limit exceeded: {config.RATE_LIMIT_PER_MINUTE} requests per minute per client IP.",
            headers={"Retry-After": "60", **_rate_limit_headers(0, reset_seconds)},
        )
    valid.append(now)
    ip_rate_tracker[client_ip] = valid
    response.headers.update(_rate_limit_headers(config.RATE_LIMIT_PER_MINUTE - len(valid), reset_seconds))
