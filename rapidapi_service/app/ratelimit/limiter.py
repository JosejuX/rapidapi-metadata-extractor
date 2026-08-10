"""
IP-based rate limiter: distributed Redis fixed-window when available, per-process
TTLCache fallback otherwise (Plan section 8).

NOTE: Fixed-window algorithm — intentional design choice for simplicity and
Redis efficiency (single INCR + conditional EXPIRE per request). Trade-off: a
burst of up to 2x limit at the window boundary is acceptable for a public SaaS
API protected upstream by the RapidAPI Gateway. Token bucket / sliding window
is a Plan §8.3 follow-up, not part of this behavior-preserving refactor.
"""
import time
from cachetools import TTLCache
from fastapi import Request

from app import config
from app.core.logging import logger
from app.core.errors import AppError, RATE_LIMITED
from app.security.proxy import resolve_client_ip
from app.ratelimit import redis as redis_state
from app.observability import metrics

ip_rate_tracker: TTLCache = TTLCache(maxsize=config.RATE_LIMIT_TRACKER_MAXSIZE, ttl=60)


async def check_ip_rate_limit(request: Request):
    """Enforces N req/min (config.RATE_LIMIT_PER_MINUTE) per client IP.
    Uses non-blocking Redis when available; falls back to per-process TTLCache.
    On Redis failure mid-request the status is updated immediately."""
    client_ip = resolve_client_ip(request)

    if redis_state.redis_client and redis_state.redis_status == "connected":
        try:
            rate_key = f"rate:{client_ip}"
            count = await redis_state.redis_client.incr(rate_key)
            if count == 1:
                await redis_state.redis_client.expire(rate_key, 60)
            if count > config.RATE_LIMIT_PER_MINUTE:
                logger.warning("Rate limit exceeded via Redis for IP %s (%d/min)", client_ip, count)
                metrics.RATE_LIMITED_TOTAL.inc()
                raise AppError(
                    status_code=429,
                    code=RATE_LIMITED,
                    detail=f"Rate limit exceeded: {config.RATE_LIMIT_PER_MINUTE} requests per minute per client IP.",
                    headers={"Retry-After": "60"},
                )
            return
        except AppError:
            raise
        except Exception as exc:
            redis_state.mark_degraded(str(exc))

    # Local TTLCache fallback (per-process fixed window)
    now = time.time()
    history = ip_rate_tracker.get(client_ip, [])
    valid = [t for t in history if now - t < 60]
    if len(valid) >= config.RATE_LIMIT_PER_MINUTE:
        logger.warning("Rate limit exceeded via TTLCache for IP %s", client_ip)
        metrics.RATE_LIMITED_TOTAL.inc()
        raise AppError(
            status_code=429,
            code=RATE_LIMITED,
            detail=f"Rate limit exceeded: {config.RATE_LIMIT_PER_MINUTE} requests per minute per client IP.",
            headers={"Retry-After": "60"},
        )
    valid.append(now)
    ip_rate_tracker[client_ip] = valid
