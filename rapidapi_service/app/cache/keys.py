"""Cache key construction (Plan section 6.3): canonical URL + head_only flag +
custom User-Agent participate in the key so cache entries never cross-contaminate."""
import urllib.parse
from typing import Optional

from app.core.urls import normalize_and_validate_url

_TRACKING_PARAM_PREFIXES = ('utm_', 'fbclid', 'gclid', 'msclkid')


def normalize_cache_url(url: str) -> str:
    url = normalize_and_validate_url(url)
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]

    query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    clean_params = [(k, v) for k, v in query_params if not k.lower().startswith(_TRACKING_PARAM_PREFIXES)]
    clean_query = urllib.parse.urlencode(clean_params)

    return urllib.parse.urlunparse((scheme, netloc, parsed.path or "/", parsed.params, clean_query, ""))


def build_cache_key(url: str, clean_ua: str, head_only: bool, user_agent_provided: Optional[str]) -> str:
    base_cache_key = normalize_cache_url(url)
    cache_key_parts = [base_cache_key]
    if head_only:
        cache_key_parts.append("head_only")
    if user_agent_provided and str(user_agent_provided).strip():
        cache_key_parts.append(f"ua={clean_ua}")
    return ":".join(cache_key_parts)
