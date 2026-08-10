"""
Single source of truth URL normalization/validation (Plan section 30).
Shared by app.security.ssrf and app.cache.keys — kept dependency-free (no
FastAPI/security imports) to avoid circular imports between those two.
"""
import urllib.parse

from app.core.errors import AppError, UNSUPPORTED_SCHEME, INVALID_URL


def normalize_and_validate_url(url: str) -> str:
    """
    Prepends https:// to scheme-less inputs (e.g. github.com -> https://github.com),
    strictly validates scheme is http/https, and rejects URLs containing userinfo
    (user:pass@host) which could leak credentials to upstream hosts (Plan §86).
    """
    raw_url = url.strip()
    parsed = urllib.parse.urlparse(raw_url)

    if parsed.scheme:
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
    else:
        return "https://" + raw_url
