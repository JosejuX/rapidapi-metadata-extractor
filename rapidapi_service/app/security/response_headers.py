"""Security response headers middleware (Plan section 69).

Applies baseline security headers to every response: a CSP scoped to what
the embedded demo page actually needs (self-hosted inline script/style,
same-origin fetch, no external resources), the standard clickjacking/
MIME-sniffing/referrer/permissions hardening headers, and HSTS.

HSTS is gated on the request having arrived over HTTPS. Render (and the
RapidAPI gateway) terminate TLS upstream and forward plain HTTP internally,
so `request.url.scheme` is unreliable here — `X-Forwarded-Proto` is what
actually carries the original scheme (confirmed via live request logs), with
`request.url.scheme` kept only as a fallback for local/CI runs with no proxy
in front.
"""
from fastapi import Request

CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = CSP

    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    if scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

    return response
