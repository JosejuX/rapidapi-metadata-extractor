"""
Per-target-host outbound concurrency limiting (Plan section 9): stop a client
from turning this API into an involuntary crawler/DDoS proxy against a single
victim host, without adding cost to the common case (different clients
usually target different hosts, so this is a no-op semaphore acquire/release
almost all the time).

Cheap by design: one asyncio.Semaphore per hostname, cached in a plain dict.
Idle semaphores (not currently held, unused for HOST_SEMAPHORE_IDLE_TTL_SECONDS)
are purged opportunistically whenever a new host is first seen and the table
has grown past a housekeeping threshold — no background task, no extra
event-loop wakeups on the hot path.
"""
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Tuple

from app import config
from app.core.errors import AppError, CONCURRENCY_LIMITED
from app.observability import metrics

_host_semaphores: Dict[str, asyncio.Semaphore] = {}
_host_last_used: Dict[str, float] = {}

_HOUSEKEEPING_THRESHOLD = 2000  # only bother scanning for idle entries past this size
_ACQUIRE_TIMEOUT_SECONDS = 4.5   # matches the fetcher's own connect+read budget


def _purge_idle_locked():
    now = time.time()
    idle_hosts = [
        host for host, sem in _host_semaphores.items()
        if sem._value == config.MAX_CONCURRENT_REQUESTS_PER_HOST  # fully released, nobody holding it
        and (now - _host_last_used.get(host, now)) > config.HOST_SEMAPHORE_IDLE_TTL_SECONDS
    ]
    for host in idle_hosts:
        _host_semaphores.pop(host, None)
        _host_last_used.pop(host, None)


def _get_semaphore(hostname: str) -> asyncio.Semaphore:
    if len(_host_semaphores) > _HOUSEKEEPING_THRESHOLD:
        _purge_idle_locked()
    sem = _host_semaphores.get(hostname)
    if sem is None:
        sem = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS_PER_HOST)
        _host_semaphores[hostname] = sem
    _host_last_used[hostname] = time.time()
    return sem


async def acquire_host_slot(hostname: str) -> None:
    """Blocks (briefly) until a concurrency slot for `hostname` is free.
    Raises AppError(429, CONCURRENCY_LIMITED) rather than queuing indefinitely
    if the limit stays saturated past _ACQUIRE_TIMEOUT_SECONDS — a stuck queue
    against one slow host shouldn't pile up server-side tasks."""
    sem = _get_semaphore(hostname)
    try:
        await asyncio.wait_for(sem.acquire(), timeout=_ACQUIRE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        metrics.CONCURRENCY_LIMITED_TOTAL.inc()
        raise AppError(
            status_code=429,
            code=CONCURRENCY_LIMITED,
            detail=f"Too many concurrent requests to '{hostname}' already in flight. Try again shortly.",
            retryable=True,
            headers={"Retry-After": "2"},
        )


def release_host_slot(hostname: str) -> None:
    sem = _host_semaphores.get(hostname)
    if sem is not None:
        sem.release()
        _host_last_used[hostname] = time.time()


@asynccontextmanager
async def host_concurrency_guard(hostname: str):
    """Context-manager convenience wrapper around acquire/release_host_slot,
    for callers that don't need to hold the slot across a redirect chain."""
    await acquire_host_slot(hostname)
    try:
        yield
    finally:
        release_host_slot(hostname)
