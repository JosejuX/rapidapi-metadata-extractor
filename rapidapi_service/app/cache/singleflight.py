"""
Generic async single-flight / request-coalescing primitive (Plan §5, §6.7,
§52): if N concurrent callers ask for the same key while a computation for
that key is already in progress, only the first (the "leader") actually runs
it; the rest ("followers") await and share its result. Used for both upstream
fetch+extraction (keyed by cache_key) and DNS resolution (keyed by hostname:port).

Deliberately NOT built on asyncio.Future — a Future whose exception is never
`await`ed logs an "exception was never retrieved" warning at GC time, which
would fire on every ordinary (non-concurrent) failure since most requests
have no followers. An Event + plain result/exception slot avoids that
entirely: followers only touch `.exception`/`.result` after explicitly
waiting on the event, so nothing is ever silently dropped.
"""
import asyncio
from typing import Awaitable, Callable, Dict, TypeVar

from app.observability import metrics

T = TypeVar("T")

coalesced_total = 0  # Plan §39 singleflight_coalesced_total — simple counter for now


class _InFlight:
    __slots__ = ("event", "result", "exception")

    def __init__(self):
        self.event = asyncio.Event()
        self.result = None
        self.exception = None


_in_flight: Dict[str, _InFlight] = {}


async def single_flight(key: str, factory: Callable[[], Awaitable[T]]) -> T:
    """Runs `factory()` for `key`, coalescing concurrent callers. The leader
    actually awaits `factory()`; followers wait for the leader's result
    (or re-raise its exception) without doing any work themselves."""
    global coalesced_total

    existing = _in_flight.get(key)
    if existing is not None:
        coalesced_total += 1
        metrics.SINGLEFLIGHT_COALESCED_TOTAL.inc()
        await existing.event.wait()
        if existing.exception is not None:
            raise existing.exception
        return existing.result

    entry = _InFlight()
    _in_flight[key] = entry
    try:
        result = await factory()
        entry.result = result
        return result
    except Exception as e:
        entry.exception = e
        raise
    finally:
        entry.event.set()
        _in_flight.pop(key, None)
