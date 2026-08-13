"""Security response headers middleware (Plan section 69).

Applies baseline security headers to every response: a CSP scoped to what
the embedded demo page actually needs (same-origin fetch, no external
resources, and a fresh per-request nonce authorizing its inline
<style>/<script> tags instead of 'unsafe-inline'), the standard
clickjacking/MIME-sniffing/referrer/permissions hardening headers, and HSTS.

Our own security-audit grader (app/extraction/security.py) grades CSP
"weak" the moment `unsafe-inline` appears anywhere in the header value,
regardless of whether a nonce is also present - so the nonce has to fully
replace 'unsafe-inline', not sit alongside it, to grade "strong".

The nonce is generated here (before call_next) and stashed on
request.state so the "/" route handler can embed the exact same value in
the markup it renders - the header and the markup it authorizes must always
agree, or the browser blocks the page's own inline script/style.

HSTS is gated on the request having arrived over HTTPS. Render (and the
RapidAPI gateway) terminate TLS upstream and forward plain HTTP internally,
so `request.url.scheme` is unreliable here - `X-Forwarded-Proto` is what
actually carries the original scheme (confirmed via live request logs), with
`request.url.scheme` kept only as a fallback for local/CI runs with no proxy
in front.
"""
import secrets

from fastapi import Request


async def add_security_headers(request: Request, call_next):
    nonce = secrets.token_urlsafe(16)
    request.state.csp_nonce = nonce

    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        f"style-src 'self' 'nonce-{nonce}'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    if scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

    return response
