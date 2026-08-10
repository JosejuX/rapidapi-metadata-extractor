"""
Centralized application configuration (Plan section 46), backed by
pydantic-settings for startup validation.

Field names stay UPPERCASE to preserve the module-attribute access pattern
used throughout this codebase (`from app import config; config.SOME_NAME`) —
every module reads `config.SOME_NAME` directly, so a low-risk migration
means the same flat set of module attributes has to keep working exactly as
before, not a smaller set of grouped sub-settings objects (Plan §46's
"AppSettings/FetcherSettings/..." grouping would mean touching every
consumer's import — out of scope for this pass).

Invalid configuration (wrong types, negative sizes, soft-limit above
hard-limit) now fails at import time with a clear Pydantic ValidationError
instead of surfacing as a confusing runtime bug. Most of these values were
previously hardcoded constants with no env var at all — they keep their
exact same default values (zero behavior change out of the box) but are now
opportunistically overridable via env vars too, with validation either way.
"""
import ipaddress
from typing import List, Optional, Union

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_NetworkType = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    # --------------------------------------------------------------------------
    # Auth / proxy trust
    # --------------------------------------------------------------------------
    RAPIDAPI_PROXY_SECRET: Optional[str] = None
    HEALTH_DETAILS_SECRET: Optional[str] = None

    # Comma-separated origins for CORS, or "*" (kept as a raw string here;
    # parsed into ALLOWED_ORIGINS: List[str] below). Defaults to "*" — this
    # API is auth'd by header/API-key (not cookies; allow_credentials=False
    # in app/main.py), so a wildcard is the standard, safe pattern for a
    # public multi-tenant API embedded from arbitrary browser origins.
    ALLOWED_ORIGINS: str = "*"

    # If set, only X-Forwarded-For from these IPs/CIDRs is trusted. If empty
    # and TRUST_PROXY=true, all proxies are trusted (legacy). When
    # TRUST_PROXY=false (default), uses request.client.host only — prevents
    # IP spoofing.
    TRUST_PROXY: bool = False
    TRUSTED_PROXY_IPS: str = ""

    # --------------------------------------------------------------------------
    # Redis
    # --------------------------------------------------------------------------
    REDIS_URL: Optional[str] = None

    # --------------------------------------------------------------------------
    # Fetcher limits
    # --------------------------------------------------------------------------
    MAX_REDIRECTS: int = Field(default=5, ge=0)

    # Adaptive Byte Limit — SPA Detection. Sites built with React / Next.js /
    # Vue / Angular etc. render content via JS; their HTML shell often
    # exceeds 64 KB. We stream up to SOFT_LIMIT and scan for SPA signatures;
    # if found, silently expand to HARD_LIMIT to capture the SSR payload.
    STREAM_SOFT_LIMIT: int = Field(default=64 * 1024, gt=0)   # 64 KB  — static/SSR sites
    STREAM_HARD_LIMIT: int = Field(default=256 * 1024, gt=0)  # 256 KB — SPA/Next.js sites

    # Response header limits (Plan §3.6) — bound memory from malicious/
    # bloated upstream responses before doing anything else with them.
    MAX_HEADER_COUNT: int = Field(default=100, gt=0)
    MAX_HEADER_VALUE_LENGTH: int = Field(default=8192, gt=0)      # bytes, per header value
    MAX_TOTAL_HEADER_BYTES: int = Field(default=64 * 1024, gt=0)  # combined size of all headers

    # Per-target-host outbound concurrency (Plan §9) — stop a client from
    # turning this API into an involuntary crawler against one victim host.
    MAX_CONCURRENT_REQUESTS_PER_HOST: int = Field(default=6, gt=0)
    HOST_SEMAPHORE_IDLE_TTL_SECONDS: int = Field(default=300, gt=0)

    # --------------------------------------------------------------------------
    # Cache
    # --------------------------------------------------------------------------
    CACHE_MAXSIZE: int = Field(default=5000, gt=0)
    CACHE_TTL_SECONDS: int = Field(default=900, gt=0)  # 15 minutes

    # Shorter TTL specifically for responses whose product_data includes a
    # price — a stale product listing (price/availability) is a materially
    # different kind of "wrong" than a 15-minutes-stale <title> tag. Applies
    # to the whole cached response, not just the product fields (Plan
    # feedback: "yo querría que el TTL fuese configurable por tipo de
    # endpoint/dato" — this is the bounded version of that: one override
    # for the one field type where staleness has real consequences, not a
    # full per-endpoint TTL matrix).
    PRODUCT_CACHE_TTL_SECONDS: int = Field(default=180, gt=0)  # 3 minutes

    # Raw-fetch cache for lazy extraction (Plan §12) — bridges a short window
    # so a burst of different-profile requests for the same URL (e.g.
    # /tech-stack then /security moments apart) top up one cache entry
    # without a second upstream fetch. Deliberately much smaller/
    # shorter-lived than CACHE_* above.
    RAW_PAGE_CACHE_MAXSIZE: int = Field(default=1000, gt=0)
    RAW_PAGE_CACHE_TTL_SECONDS: int = Field(default=60, gt=0)

    DNS_CACHE_MAXSIZE: int = Field(default=2000, gt=0)
    DNS_CACHE_TTL_SECONDS: int = Field(default=300, gt=0)  # 5 minutes

    # --------------------------------------------------------------------------
    # Rate limiting
    # --------------------------------------------------------------------------
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, gt=0)
    RATE_LIMIT_TRACKER_MAXSIZE: int = Field(default=10000, gt=0)

    APP_VERSION: str = "4.0.0"

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def _allowed_origins_not_blank(cls, v: str) -> str:
        return v if v.strip() else "*"

    @model_validator(mode="after")
    def _soft_limit_not_above_hard_limit(self) -> "Settings":
        if self.STREAM_SOFT_LIMIT > self.STREAM_HARD_LIMIT:
            raise ValueError(
                f"STREAM_SOFT_LIMIT ({self.STREAM_SOFT_LIMIT}) must not exceed "
                f"STREAM_HARD_LIMIT ({self.STREAM_HARD_LIMIT})"
            )
        return self


_settings = Settings()

# --------------------------------------------------------------------------
# Module-level attributes — the actual public interface every other module
# imports as `config.SOME_NAME`. Most are direct passthroughs; a few are
# derived/parsed from a raw settings field (documented per-field above).
# --------------------------------------------------------------------------
RAPIDAPI_PROXY_SECRET: Optional[str] = _settings.RAPIDAPI_PROXY_SECRET
HEALTH_DETAILS_SECRET: Optional[str] = _settings.HEALTH_DETAILS_SECRET

ALLOWED_ORIGINS: List[str] = (
    ["*"] if _settings.ALLOWED_ORIGINS.strip() == "*"
    else [o.strip() for o in _settings.ALLOWED_ORIGINS.split(",") if o.strip()]
)

TRUST_PROXY: bool = _settings.TRUST_PROXY
TRUSTED_PROXY_NETWORKS: List[_NetworkType] = []
if _settings.TRUSTED_PROXY_IPS:
    for _cidr in _settings.TRUSTED_PROXY_IPS.split(","):
        try:
            TRUSTED_PROXY_NETWORKS.append(ipaddress.ip_network(_cidr.strip(), strict=False))
        except ValueError:
            pass

REDIS_URL: Optional[str] = _settings.REDIS_URL

MAX_REDIRECTS: int = _settings.MAX_REDIRECTS
STREAM_SOFT_LIMIT: int = _settings.STREAM_SOFT_LIMIT
STREAM_HARD_LIMIT: int = _settings.STREAM_HARD_LIMIT
MAX_HEADER_COUNT: int = _settings.MAX_HEADER_COUNT
MAX_HEADER_VALUE_LENGTH: int = _settings.MAX_HEADER_VALUE_LENGTH
MAX_TOTAL_HEADER_BYTES: int = _settings.MAX_TOTAL_HEADER_BYTES
MAX_CONCURRENT_REQUESTS_PER_HOST: int = _settings.MAX_CONCURRENT_REQUESTS_PER_HOST
HOST_SEMAPHORE_IDLE_TTL_SECONDS: int = _settings.HOST_SEMAPHORE_IDLE_TTL_SECONDS

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

CACHE_MAXSIZE: int = _settings.CACHE_MAXSIZE
CACHE_TTL_SECONDS: int = _settings.CACHE_TTL_SECONDS
PRODUCT_CACHE_TTL_SECONDS: int = _settings.PRODUCT_CACHE_TTL_SECONDS
RAW_PAGE_CACHE_MAXSIZE: int = _settings.RAW_PAGE_CACHE_MAXSIZE
RAW_PAGE_CACHE_TTL_SECONDS: int = _settings.RAW_PAGE_CACHE_TTL_SECONDS
DNS_CACHE_MAXSIZE: int = _settings.DNS_CACHE_MAXSIZE
DNS_CACHE_TTL_SECONDS: int = _settings.DNS_CACHE_TTL_SECONDS

RATE_LIMIT_PER_MINUTE: int = _settings.RATE_LIMIT_PER_MINUTE
RATE_LIMIT_TRACKER_MAXSIZE: int = _settings.RATE_LIMIT_TRACKER_MAXSIZE

APP_VERSION: str = _settings.APP_VERSION
