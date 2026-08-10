"""
Redis client lifecycle: connect, verify (PING), atomic swap-on-reconnect, and
background reconnect loop with exponential backoff + jitter (Plan sections 7, 7.5).

State (redis_client / redis_status / redis_mode) lives here as module globals.
Other modules must read/write it via `app.ratelimit.redis.<name>` (module-qualified
access) rather than `from ... import redis_client`, so rebinding here stays visible
everywhere — the same reason the original monolith used `global`.
"""
import asyncio
import random as _random
import urllib.parse
from typing import Optional

from app import config
from app.core.logging import logger
from app.observability import metrics

redis_client = None
redis_status = "disabled"        # "connected" | "degraded_fallback" | "disabled"
redis_mode = "local_ttlcache"    # "distributed" | "local_ttlcache"


async def try_connect_redis() -> bool:
    """Attempt (re)connection to Redis. Returns True on success, False on failure.
    Never raises — all errors are logged and swallowed.
    Swap pattern (Plan §7.1): connect + ping new client BEFORE swapping the
    reference, then close the old client — never close a client while a
    concurrent operation could still be using it."""
    global redis_client, redis_status, redis_mode
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(config.REDIS_URL, decode_responses=True, socket_connect_timeout=2.0)
        await client.ping()
        old_client = redis_client
        redis_client = client
        redis_status = "connected"
        redis_mode = "distributed"
        if old_client:
            metrics.REDIS_RECONNECTS_TOTAL.inc()
            try:
                await old_client.aclose()
            except Exception:
                pass
        redis_hostname = urllib.parse.urlparse(config.REDIS_URL).hostname or "configured"
        logger.info("Redis rate-limiter connected & verified (Host: %s)", redis_hostname)
        return True
    except Exception as exc:
        redis_status = "degraded_fallback"
        redis_mode = "local_ttlcache"
        metrics.REDIS_ERRORS_TOTAL.inc()
        logger.warning("Redis unavailable — using local TTLCache fallback: %s", exc)
        return False


async def redis_reconnect_loop():
    """Background task: reconnects to Redis with exponential backoff + jitter.
    Interval: 2s -> 4s -> 8s -> ... -> 120s (cap). Resets on successful reconnect.
    Plan §7.5: avoids thundering herd after Redis restart with multiple workers."""
    base_delay = 2.0
    max_delay = 120.0
    delay = base_delay
    while True:
        jitter = _random.uniform(-delay * 0.25, delay * 0.25)
        await asyncio.sleep(max(1.0, delay + jitter))
        if redis_status != "connected" and config.REDIS_URL:
            logger.info("Redis reconnect attempt (backoff=%.1fs)...", delay)
            success = await try_connect_redis()
            if success:
                delay = base_delay
            else:
                delay = min(delay * 2, max_delay)


def mark_degraded(reason: str = ""):
    """Called by the rate limiter on a mid-request Redis failure so /health
    reflects reality immediately instead of waiting for the reconnect loop."""
    global redis_status, redis_mode
    redis_status = "degraded_fallback"
    redis_mode = "local_ttlcache"
    metrics.REDIS_ERRORS_TOTAL.inc()
    if reason:
        logger.warning("Redis rate-check failed — switched to local TTLCache: %s", reason)


async def shutdown():
    if redis_client:
        try:
            await redis_client.aclose()
        except Exception:
            pass
