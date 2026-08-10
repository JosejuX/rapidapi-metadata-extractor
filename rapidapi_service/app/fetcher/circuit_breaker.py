"""
Per-target-host circuit breaker (Plan section 10):

    CLOSED --(failures >= threshold)--> OPEN --(cooldown elapsed)--> HALF_OPEN
      ^                                                                  |
      +---------------------- success -----------------------------------+
                                    |
                              failure -> back to OPEN

Only trips on failures that plausibly indicate the *host* is down or
struggling (timeouts, connection failures, 5xx) — never on ordinary 4xx
client errors, which just mean "that URL doesn't exist," not "this host is
unavailable" (Plan §10: "No usar circuit breaker para errores normales 4xx").

State lives in a plain per-process dict, exactly like the per-host
concurrency semaphores in app/security/limits.py — each Gunicorn/Uvicorn
worker tracks circuits independently, which is an acceptable, deliberate
trade-off consistent with the rest of this codebase's per-process caches.
"""
import time
from typing import Dict, Set

from app.core.errors import CIRCUIT_OPEN, AppError

FAILURE_THRESHOLD = 5
COOLDOWN_SECONDS = 30

CLOSED = "CLOSED"
OPEN = "OPEN"
HALF_OPEN = "HALF_OPEN"

# Failure codes that count against a host's circuit — anything else (SSRF,
# validation, content-type, 4xx) is a property of the specific request, not
# evidence the host itself is unhealthy, and must not trip the breaker.
_TRIPPING_CODES: Set[str] = {"CONNECTION_TIMEOUT", "UPSTREAM_TIMEOUT", "UPSTREAM_5XX", "TLS_ERROR"}


class _HostCircuit:
    __slots__ = ("state", "failure_count", "opened_at", "half_open_probe_in_flight")

    def __init__(self):
        self.state = CLOSED
        self.failure_count = 0
        self.opened_at = 0.0
        self.half_open_probe_in_flight = False


_circuits: Dict[str, _HostCircuit] = {}


def _get(hostname: str) -> _HostCircuit:
    c = _circuits.get(hostname)
    if c is None:
        c = _HostCircuit()
        _circuits[hostname] = c
    return c


def before_request(hostname: str) -> None:
    """Raises AppError(CIRCUIT_OPEN) if this host's circuit is open (or the
    single allowed half-open probe is already in flight). Call once per
    outbound hop, before opening the connection."""
    c = _get(hostname)

    if c.state == OPEN:
        if time.time() - c.opened_at >= COOLDOWN_SECONDS:
            c.state = HALF_OPEN
            c.half_open_probe_in_flight = False
        else:
            retry_after = max(1, int(COOLDOWN_SECONDS - (time.time() - c.opened_at)))
            raise AppError(
                status_code=400,
                code=CIRCUIT_OPEN,
                detail=f"Circuit breaker open for '{hostname}': too many recent failures, cooling down.",
                retryable=True,
                headers={"Retry-After": str(retry_after)},
            )

    if c.state == HALF_OPEN:
        if c.half_open_probe_in_flight:
            raise AppError(
                status_code=400,
                code=CIRCUIT_OPEN,
                detail=f"Circuit breaker for '{hostname}' is testing recovery, try again shortly.",
                retryable=True,
                headers={"Retry-After": "2"},
            )
        c.half_open_probe_in_flight = True


def record_success(hostname: str) -> None:
    c = _circuits.get(hostname)
    if c is None:
        return
    c.state = CLOSED
    c.failure_count = 0
    c.half_open_probe_in_flight = False


def record_failure(hostname: str, code: str) -> None:
    if code not in _TRIPPING_CODES:
        return
    c = _get(hostname)

    if c.state == HALF_OPEN:
        # Probe failed — back to OPEN immediately, fresh cooldown.
        c.state = OPEN
        c.opened_at = time.time()
        c.half_open_probe_in_flight = False
        return

    c.failure_count += 1
    if c.failure_count >= FAILURE_THRESHOLD:
        c.state = OPEN
        c.opened_at = time.time()
