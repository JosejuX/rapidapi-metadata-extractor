"""
Single source of truth URL normalization/validation (Plan section 30).
Shared by app.security.ssrf and app.cache.keys — kept dependency-free (no
FastAPI/security imports) to avoid circular imports between those two.
"""
import urllib.parse
from typing import Optional

from app.core.errors import INVALID_URL, UNSUPPORTED_SCHEME, AppError

# Competitive-differentiator #1: known URL-shortener hostnames — checked
# against the *original* input url's own hostname (not final_url after
# redirects resolve it), since the point is flagging "the caller handed us
# a shortener link", not "the destination happens to look like one".
KNOWN_URL_SHORTENER_HOSTS = frozenset({
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "rebrand.ly", "cutt.ly", "shorturl.at", "tiny.cc",
})


def normalize_and_validate_url(url: str) -> str:
    """
    Prepends https:// to scheme-less inputs (e.g. github.com -> https://github.com),
    strictly validates scheme is http/https, and rejects URLs containing userinfo
    (user:pass@host) which could leak credentials to upstream hosts (Plan §86).

    Scheme is normalized BEFORE parsing+validating (rather than only checking
    userinfo/scheme when the raw input already had one) so both checks apply
    uniformly to scheme-less input too — a fuzz test caught this: "0@" used to
    skip the userinfo check entirely (only checked inside the `if
    parsed.scheme:` branch), silently become "https://0@" and pass, then fail
    non-idempotently if normalized a second time.

    urllib.parse.urlparse can raise ValueError on malformed input (e.g. an
    unterminated IPv6-literal-looking "[") — reachable with a plain
    `?url=[` query string, and previously surfaced as an unhandled 500
    instead of a clean 400.
    """
    raw_url = url.strip()

    try:
        parsed = urllib.parse.urlparse(raw_url)
    except ValueError:
        parsed = None

    if parsed is not None and not parsed.scheme:
        raw_url = "https://" + raw_url
        try:
            parsed = urllib.parse.urlparse(raw_url)
        except ValueError:
            parsed = None

    if parsed is None:
        raise AppError(
            status_code=400,
            code=INVALID_URL,
            detail="SSRF Protection: Malformed URL could not be parsed."
        )

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise AppError(
            status_code=400,
            code=UNSUPPORTED_SCHEME,
            detail=f"SSRF Protection: Forbidden scheme '{scheme}:'. Only 'http' and 'https' protocols are permitted."
        )
    if parsed.username or parsed.password:
        raise AppError(
            status_code=400,
            code=INVALID_URL,
            detail="SSRF Protection: URLs with embedded credentials (user:pass@host) are not permitted."
        )
    return raw_url


def safe_urljoin(base: str, url: str) -> Optional[str]:
    """urljoin can raise ValueError on malformed input (same IPv6-bracket
    class of issue as above) — but here `url` is frequently an href/src
    attribute lifted straight from an arbitrary, attacker-controlled target
    page, not the caller's own input, so it must never propagate as an
    unhandled exception (Plan §54: extraction must not raise on arbitrary
    HTML). Returns None on failure; callers already handle missing/absent
    URLs for these fields."""
    try:
        return urllib.parse.urljoin(base, url)
    except ValueError:
        return None


def safe_urlparse(url: str) -> urllib.parse.ParseResult:
    """Same rationale as safe_urljoin — used where callers only read
    attributes off the result (e.g. .netloc) and an empty ParseResult is a
    safe, inert fallback."""
    try:
        return urllib.parse.urlparse(url)
    except ValueError:
        return urllib.parse.ParseResult("", "", "", "", "", "")


def is_shortened_url(url: str) -> bool:
    """True if `url`'s own hostname (the caller's original input, not
    final_url after redirects) matches a known URL-shortener service."""
    hostname = safe_urlparse(url).hostname
    return bool(hostname) and hostname.lower() in KNOWN_URL_SHORTENER_HOSTS
