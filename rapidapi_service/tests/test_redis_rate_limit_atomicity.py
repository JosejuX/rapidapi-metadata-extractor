"""
Redis rate-limit atomicity (Plan §77): INCR and the first-hit EXPIRE must run
as a single atomic Lua script, not two separate round-trips. A plain
`INCR` then `EXPIRE` leaves a window where a crash/disconnect between the two
calls leaves the key with no TTL — every request after that keeps
incrementing a counter that never resets, permanently rate-limiting that IP
until someone manually flushes Redis.

Needs a real Redis; skipped when REDIS_URL isn't set (exercised in CI's
redis-integration job, which runs a live redis:7-alpine service).
"""
import asyncio
import os

import pytest

from app.ratelimit import redis as redis_state
from app.ratelimit.limiter import _INCR_WITH_TTL_SCRIPT

pytestmark = pytest.mark.skipif(not os.getenv("REDIS_URL"), reason="requires a live Redis (set REDIS_URL)")


def test_incr_with_ttl_script_is_atomic_and_correct():
    async def _go():
        ok = await redis_state.try_connect_redis()
        assert ok, "Redis connection failed — is REDIS_URL reachable?"
        client = redis_state.redis_client
        key = "test:rate:atomicity:ttl"
        await client.delete(key)
        try:
            # First hit: counter starts at 1 and a TTL is set in the same
            # round-trip — there is no intermediate state where the key
            # exists without an expiry.
            count = await client.eval(_INCR_WITH_TTL_SCRIPT, 1, key, 60)
            assert count == 1
            ttl = await client.ttl(key)
            assert 0 < ttl <= 60

            # Second hit: counter increments, TTL from the first hit is
            # preserved (not reset/extended) — fixed-window semantics.
            count2 = await client.eval(_INCR_WITH_TTL_SCRIPT, 1, key, 60)
            assert count2 == 2
            ttl2 = await client.ttl(key)
            assert 0 < ttl2 <= 60
        finally:
            await client.delete(key)
            await client.aclose()

    asyncio.run(_go())
