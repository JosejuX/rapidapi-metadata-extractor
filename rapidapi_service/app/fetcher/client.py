"""
Shared HTTP client + the network-fetching half of the old fetch_and_extract_raw
monolith (Plan section 3): one upstream GET, IP-pinned SSRF-safe redirects,
adaptive byte streaming (64KB -> 256KB on SPA detection), content-type
validation. Returns raw bytes/decoded HTML — no parsing/extraction here.

`http_client` is a module global set by app.lifecycle on startup. Benchmarks
and tests that need to stub the network must patch `app.fetcher.client.http_client`
directly (module-qualified), not a copy imported elsewhere.
"""
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from app import config
from app.core.errors import (
    BOT_PROTECTION_DETECTED,
    CONNECTION_TIMEOUT,
    HEADERS_TOO_LARGE,
    REDIRECT_LIMIT,
    TLS_ERROR,
    UNSUPPORTED_CONTENT_TYPE,
    UPSTREAM_4XX,
    UPSTREAM_5XX,
    UPSTREAM_TIMEOUT,
    AppError,
)
from app.core.logging import logger
from app.extraction.bot_protection import detect_bot_protection
from app.fetcher import circuit_breaker
from app.observability import metrics
from app.security.limits import acquire_host_slot, release_host_slot
from app.security.ssrf import validate_url_ssrf

# Status codes commonly used by WAFs/CDNs to serve a challenge/CAPTCHA page
# instead of the real content (Plan §4/§34: distinguish "target blocked us"
# from a generic upstream failure). Only these three get the extra bounded
# peek below — everything else keeps failing fast without reading any body,
# same as before.
_BOT_PROTECTION_CHECK_STATUS_CODES = (403, 429, 503)
_BOT_PROTECTION_PEEK_LIMIT = 20_000  # matches bot_protection.detect_bot_protection's own size cap


async def _peek_body(response: httpx.Response, limit: int) -> bytes:
    """Bounded read for a small peek at an error response body. Same
    decompression-bomb defense as the main streaming loop below: always
    slice each incoming chunk down to remaining headroom before appending,
    never trust a single chunk to be small just because the limit is."""
    chunks: List[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        room = limit - total
        if room <= 0:
            break
        if len(chunk) > room:
            chunk = chunk[:room]
        chunks.append(chunk)
        total += len(chunk)
        if total >= limit:
            break
    return b"".join(chunks)

http_client: Optional[httpx.AsyncClient] = None

# Lowercase byte signatures — checked against the raw byte buffer (fast)
SPA_BYTE_SIGNATURES: List[bytes] = [
    b'_next/static',   # Next.js
    b'__next',         # Next.js
    b'data-reactroot', # React
    b'react-dom',      # React
    b'_nuxt',          # Nuxt
    b'__nuxt',         # Nuxt
    b'ng-version',     # Angular
    b'svelte-',        # Svelte / SvelteKit
    b'__sveltekit',    # SvelteKit
    b'___gatsby',      # Gatsby
    b'__remix',        # Remix
    b'data-v-',        # Vue.js (scoped component attributes)
    b'astro-island',   # Astro
]

_NON_HTML_TYPES = (
    "application/pdf", "application/zip", "application/octet-stream",
    "image/", "video/", "audio/", "font/",
    "application/msword", "application/vnd.",
)


def build_http_client() -> httpx.AsyncClient:
    """Factory for the shared client — used both at startup (app.lifecycle)
    and as a controlled per-request fallback if startup hasn't run yet."""
    return httpx.AsyncClient(
        http2=True,
        timeout=httpx.Timeout(4.5, connect=1.5, read=3.0),
        limits=httpx.Limits(max_keepalive_connections=500, max_connections=2000, keepalive_expiry=120.0),
        follow_redirects=False
    )


def sanitize_user_agent(ua: Optional[str]) -> str:
    """Sanitize User-Agent header to prevent CRLF injection and cap length at 500 chars."""
    if not ua or hasattr(ua, 'default'):
        return config.USER_AGENTS[0]
    ua_clean = str(ua).replace('\r', '').replace('\n', '').strip()
    if len(ua_clean) > 500:
        ua_clean = ua_clean[:500]
    return ua_clean or config.USER_AGENTS[0]


async def fetch_raw_page(url: str, user_agent: Optional[str] = None, head_only: bool = False) -> Dict[str, Any]:
    """
    Performs the single upstream fetch: SSRF-validated redirects, adaptive byte
    streaming, content-type gating, and decoding. Returns a dict with:
    html_content, status_code, final_url, resp_headers (lowercased), raw_bytes,
    bytes_downloaded, content_truncated.
    Raises HTTPException on any network/validation failure (same semantics as
    the pre-refactor monolith).
    """
    clean_ua = sanitize_user_agent(user_agent)
    fetch_start = time.perf_counter()

    client = http_client
    should_close_client = False
    if client is None:
        client = build_http_client()
        should_close_client = True

    redirect_count = 0
    current_url = url

    content_chunks = []
    total_bytes = 0
    status_code = 200
    final_url = url
    resp_headers: Dict[str, str] = {}
    response = None
    original_hostname = None
    held_host = None  # Plan §9: per-host outbound concurrency slot currently held, if any

    try:
        while redirect_count <= config.MAX_REDIRECTS:
            ip_pinned_url, original_hostname = await validate_url_ssrf(current_url)

            # §10: fail fast if this host's circuit is open (repeated
            # timeouts/connection failures/5xx recently) instead of spending
            # another full connect+read timeout budget on a host that's down.
            circuit_breaker.before_request(original_hostname)

            # §9: bound concurrent outbound requests to this target host. A redirect
            # can change hosts mid-fetch, so the slot is re-acquired per hostname,
            # not just once at the start.
            if held_host != original_hostname:
                if held_host is not None:
                    release_host_slot(held_host)
                    held_host = None
                await acquire_host_slot(original_hostname)
                held_host = original_hostname

            req_headers = {
                "User-Agent": clean_ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Host": original_hostname
            }

            async with client.stream(
                "GET",
                ip_pinned_url,
                headers=req_headers,
                extensions={"sni_hostname": original_hostname},
                follow_redirects=False
            ) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    redirect_location = response.headers.get("location") or response.headers.get("Location")
                    if not redirect_location:
                        break
                    current_url = urllib.parse.urljoin(current_url, redirect_location)
                    redirect_count += 1
                    if redirect_count > config.MAX_REDIRECTS:
                        raise AppError(
                            status_code=400,
                            code=REDIRECT_LIMIT,
                            detail=f"SSRF Protection: Exceeded maximum allowed HTTP redirects ({config.MAX_REDIRECTS} hops)."
                        )
                    continue

                if response.status_code in _BOT_PROTECTION_CHECK_STATUS_CODES:
                    peek_bytes = await _peek_body(response, _BOT_PROTECTION_PEEK_LIMIT)
                    peek_text = peek_bytes.decode(response.encoding or "utf-8", errors="replace")
                    if detect_bot_protection(peek_text, response.status_code):
                        raise AppError(
                            status_code=400,
                            code=BOT_PROTECTION_DETECTED,
                            detail=(
                                f"Target appears to be behind bot/challenge protection "
                                f"(HTTP {response.status_code}). This API fetches raw HTML "
                                f"and does not execute JavaScript or solve challenges."
                            ),
                            retryable=False,
                        )

                response.raise_for_status()
                status_code = response.status_code
                final_url = current_url
                circuit_breaker.record_success(original_hostname)

                # §3.6: Header limits — bound memory from malicious/bloated upstream
                # responses before we do anything else with them. Count and total-size
                # limits reject the response outright (something is very wrong with an
                # upstream sending 100+ headers or 64KB+ of header data); an oversized
                # individual value is truncated rather than rejecting the whole request,
                # since a single long-but-legitimate header (e.g. a big CSP) shouldn't
                # sink an otherwise-fine page.
                raw_header_items = list(response.headers.items())
                if len(raw_header_items) > config.MAX_HEADER_COUNT:
                    raise AppError(
                        status_code=400,
                        code=HEADERS_TOO_LARGE,
                        detail=f"Upstream response header count ({len(raw_header_items)}) exceeds the allowed limit ({config.MAX_HEADER_COUNT})."
                    )
                total_header_bytes = sum(len(k) + len(v) for k, v in raw_header_items)
                if total_header_bytes > config.MAX_TOTAL_HEADER_BYTES:
                    raise AppError(
                        status_code=400,
                        code=HEADERS_TOO_LARGE,
                        detail=f"Upstream response headers total size ({total_header_bytes} bytes) exceeds the allowed limit ({config.MAX_TOTAL_HEADER_BYTES} bytes)."
                    )
                resp_headers = {
                    k.lower(): (v if len(v) <= config.MAX_HEADER_VALUE_LENGTH else v[:config.MAX_HEADER_VALUE_LENGTH])
                    for k, v in raw_header_items
                }

                # §3.4: Validate Content-Type before streaming — reject non-HTML content
                content_type_raw = resp_headers.get("content-type", "").lower()
                if content_type_raw and not any(
                    ct in content_type_raw for ct in ("text/html", "application/xhtml", "text/xml", "application/xml")
                ) and any(ct in content_type_raw for ct in _NON_HTML_TYPES):
                    raise AppError(
                        status_code=400,
                        code=UNSUPPORTED_CONTENT_TYPE,
                        detail=f"Unsupported content type: '{content_type_raw.split(';')[0].strip()}'. Only HTML pages are supported."
                    )

                # Adaptive streaming: start at SOFT_LIMIT (64 KB). At soft limit,
                # scan for SPA byte signatures; if found expand to HARD_LIMIT
                # (256 KB) so the SSR payload is fully captured.
                current_limit = config.STREAM_SOFT_LIMIT
                spa_check_done = False
                tail_buffer = b""

                async for chunk in response.aiter_bytes():
                    # §3.7 decompression-bomb guard: httpx decodes gzip/br/deflate
                    # BEFORE we see this chunk, and a single `aiter_bytes()` step
                    # can hand us an arbitrarily large amount of decoded data if the
                    # transport delivers it in one burst (a small compressed body,
                    # local/fast attacker server, or a chunk that happens to land on
                    # a socket read boundary). Checking `total_bytes >= limit` only
                    # AFTER appending the whole chunk does not bound memory in that
                    # case. So: always slice the incoming chunk down to whatever
                    # headroom remains under the absolute HARD_LIMIT first — this
                    # caps peak memory at HARD_LIMIT regardless of chunk size, even
                    # before the SPA check below decides the final soft/hard limit.
                    hard_room = config.STREAM_HARD_LIMIT - total_bytes
                    if hard_room <= 0:
                        break
                    if len(chunk) > hard_room:
                        chunk = chunk[:hard_room]

                    content_chunks.append(chunk)
                    total_bytes += len(chunk)

                    if not spa_check_done and total_bytes >= config.STREAM_SOFT_LIMIT:
                        spa_check_done = True
                        partial_lower = b"".join(content_chunks).lower()
                        if any(sig in partial_lower for sig in SPA_BYTE_SIGNATURES):
                            current_limit = config.STREAM_HARD_LIMIT
                            logger.info("SPA detected — expanding byte limit to 256 KB for %s", current_url)

                    if total_bytes >= current_limit:
                        break

                    # Tail-buffer early exit: ONLY when head_only=True (e.g. link-preview)
                    if head_only:
                        tail_buffer = (tail_buffer + chunk)[-128:]
                        if b"</head>" in tail_buffer.lower() and total_bytes >= 16 * 1024:
                            break
                break

        raw_bytes = b"".join(content_chunks)
        try:
            encoding = response.encoding or "utf-8"
            html_content = raw_bytes.decode(encoding, errors="replace")
        except Exception:
            html_content = raw_bytes.decode("utf-8", errors="replace")

    except AppError:
        # Already a well-classified error (SSRF/DNS/scheme/redirect-limit/content-type) —
        # propagate as-is instead of mangling it into a generic "Unable to access" message.
        if should_close_client:
            await client.aclose()
        raise
    except Exception as e:
        if should_close_client:
            await client.aclose()
        err_msg = str(e)
        if original_hostname:
            err_msg = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', original_hostname, err_msg)
        logger.error("Fetch error for %s: %s", url, err_msg)

        # Best-effort classification of the underlying network failure (Plan §34).
        # Status code stays 400 for v1 backward compatibility — only the `error.code`
        # in the structured body changes; see app/core/errors.py for rationale.
        if isinstance(e, (httpx.ConnectTimeout,)):
            code = CONNECTION_TIMEOUT
        elif isinstance(e, (httpx.ReadTimeout, httpx.PoolTimeout, httpx.WriteTimeout, httpx.TimeoutException)):
            code = UPSTREAM_TIMEOUT
        elif isinstance(e, httpx.HTTPStatusError):
            resp_status = e.response.status_code if e.response is not None else None
            code = UPSTREAM_5XX if (resp_status and resp_status >= 500) else UPSTREAM_4XX
        elif "ssl" in type(e).__name__.lower() or "tls" in type(e).__name__.lower():
            code = TLS_ERROR
        else:
            code = CONNECTION_TIMEOUT

        if original_hostname:
            circuit_breaker.record_failure(original_hostname, code)

        if code in (CONNECTION_TIMEOUT, UPSTREAM_TIMEOUT):
            metrics.UPSTREAM_TIMEOUTS_TOTAL.inc()

        raise AppError(
            status_code=400,
            code=code,
            detail=f"Unable to access target URL: {err_msg}"
        )
    finally:
        if should_close_client:
            await client.aclose()
        if held_host is not None:
            release_host_slot(held_host)
        # Covers the whole fetch attempt (SSRF/circuit-breaker preflight +
        # network I/O), not just socket time — a fast SSRF rejection still
        # lands in the histogram's smallest bucket, which is informative
        # (near-zero cost) rather than misleading.
        metrics.UPSTREAM_DURATION_SECONDS.observe(time.perf_counter() - fetch_start)

    content_truncated = total_bytes >= (config.STREAM_HARD_LIMIT if any(
        sig in b"".join(content_chunks).lower() for sig in SPA_BYTE_SIGNATURES
    ) else config.STREAM_SOFT_LIMIT)
    bytes_downloaded = len(raw_bytes)

    metrics.BYTES_DOWNLOADED_TOTAL.inc(bytes_downloaded)
    if content_truncated:
        metrics.TRUNCATED_RESPONSES_TOTAL.inc()

    return {
        "html_content": html_content,
        "raw_bytes": raw_bytes,
        "status_code": status_code,
        "final_url": final_url,
        "resp_headers": resp_headers,
        "bytes_downloaded": bytes_downloaded,
        "content_truncated": content_truncated,
        "clean_ua": clean_ua,
    }
