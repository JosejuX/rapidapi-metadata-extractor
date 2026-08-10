"""X-Request-ID middleware (Plan sections 32/40) — generate or preserve an
inbound request ID for end-to-end tracing across logs, responses and
monitoring. Also the single choke point for the two Plan §39 metrics that
apply to every request regardless of which route handled it
(requests_total, request_duration_seconds) and for the one structured log
line Plan §41 shows as its example (request completion, with request_id +
host + duration_ms + endpoint)."""
import time
import uuid

from fastapi import Request

from app.core.logging import logger
from app.observability import metrics


async def add_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = rid  # so exception handlers can include it in error bodies
    start = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = rid

    # Route path template (e.g. "/api/v1/extract"), not the raw URL — keeps
    # metric/log cardinality bounded regardless of query params or 404s on
    # arbitrary paths.
    route = request.scope.get("route")
    endpoint = getattr(route, "path", request.url.path)

    metrics.REQUESTS_TOTAL.labels(endpoint=endpoint, status=str(response.status_code)).inc()
    metrics.REQUEST_DURATION_SECONDS.labels(endpoint=endpoint).observe(duration_ms / 1000)

    logger.info("request_completed", extra={
        "event": "request_completed",
        "request_id": rid,
        "endpoint": endpoint,
        "method": request.method,
        "status": response.status_code,
        "duration_ms": duration_ms,
    })

    return response
