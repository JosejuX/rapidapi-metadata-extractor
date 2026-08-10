"""
Structured error model (Plan section 34).

Deliberately ADDITIVE, not a v1 breaking change: existing HTTP status codes
(400/403/429) and the existing top-level "detail" string are preserved
exactly as before (test_api.py and the documented RapidAPI contract both
depend on them). This adds a machine-readable "error" object alongside
"detail" — new clients can key off `error.code` / `error.retryable`,
old clients keep working unchanged.

A full status-code remap per Plan §34.1 (e.g. upstream 5xx -> 502, timeout ->
504, content too large -> 413) is a genuine breaking change to the current
public contract and is deferred to a versioned v2 per Plan §36 ("cambios
breaking -> v2") rather than snuck into this pass.
"""
from typing import Optional
from fastapi import HTTPException, Request
from fastapi.responses import ORJSONResponse

# Error codes (Plan §34). A few additions beyond the plan's literal list
# (UNSUPPORTED_CONTENT_TYPE, AUTH_FORBIDDEN) to cover paths the plan's list
# didn't name explicitly — kept in the same style/case convention.
INVALID_URL = "INVALID_URL"
UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME"
SSRF_BLOCKED = "SSRF_BLOCKED"
DNS_FAILURE = "DNS_FAILURE"
CONNECTION_TIMEOUT = "CONNECTION_TIMEOUT"
TLS_ERROR = "TLS_ERROR"
UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
UPSTREAM_4XX = "UPSTREAM_4XX"
UPSTREAM_5XX = "UPSTREAM_5XX"
REDIRECT_LIMIT = "REDIRECT_LIMIT"
UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
CONTENT_TOO_LARGE = "CONTENT_TOO_LARGE"
HEADERS_TOO_LARGE = "HEADERS_TOO_LARGE"
RATE_LIMITED = "RATE_LIMITED"
CONCURRENCY_LIMITED = "CONCURRENCY_LIMITED"
AUTH_FORBIDDEN = "AUTH_FORBIDDEN"
REDIS_DEGRADED = "REDIS_DEGRADED"
CIRCUIT_OPEN = "CIRCUIT_OPEN"
INTERNAL_ERROR = "INTERNAL_ERROR"

# Codes considered safe to retry (transient/network) vs not (client input error).
_RETRYABLE_CODES = {
    CONNECTION_TIMEOUT, UPSTREAM_TIMEOUT, UPSTREAM_5XX, RATE_LIMITED, CONCURRENCY_LIMITED, CIRCUIT_OPEN,
}


class AppError(HTTPException):
    """HTTPException subclass carrying a stable machine-readable error code.
    Behaves exactly like HTTPException for anything that doesn't know about
    `code` (status_code + detail are unchanged), so existing exception
    handling / tests keep working."""

    def __init__(self, status_code: int, code: str, detail: str, retryable: Optional[bool] = None, headers=None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code
        self.retryable = retryable if retryable is not None else (code in _RETRYABLE_CODES)


async def app_error_handler(request: Request, exc: AppError):
    request_id = request.headers.get("x-request-id") or getattr(request.state, "request_id", None)
    body = {
        "detail": exc.detail,  # unchanged, backward compatible
        "error": {
            "code": exc.code,
            "message": exc.detail,
            "retryable": exc.retryable,
            "request_id": request_id,
        },
    }
    return ORJSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)
