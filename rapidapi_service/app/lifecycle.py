"""Application lifespan: startup/shutdown of the shared HTTP client and Redis
connection + reconnect loop (Plan section 45: graceful shutdown ordering)."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import config
from app.fetcher import client as fetcher_client
from app.ratelimit import redis as redis_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    fetcher_client.http_client = fetcher_client.build_http_client()

    reconnect_task = None
    if config.REDIS_URL:
        await redis_state.try_connect_redis()
        reconnect_task = asyncio.create_task(redis_state.redis_reconnect_loop())

    yield

    # Graceful shutdown (Plan §45): stop background tasks, then close clients.
    if reconnect_task:
        reconnect_task.cancel()
        try:
            await reconnect_task
        except asyncio.CancelledError:
            pass
    if fetcher_client.http_client:
        await fetcher_client.http_client.aclose()
    await redis_state.shutdown()
