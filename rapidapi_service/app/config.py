"""
Centralized application configuration (Plan section 46).

Kept as plain module-level constants read from environment variables — the
same values and defaults as the pre-refactor main.py, just grouped in one
place instead of scattered across the monolith. Migrating to pydantic-settings
with full startup validation is a later, separate improvement (not required
to preserve behavior for this pass).
"""
import ipaddress
import os
from typing import List, Optional

# ------------------------------------------------------------------------------
# Auth / proxy trust
# ------------------------------------------------------------------------------
RAPIDAPI_PROXY_SECRET: Optional[str] = os.getenv("RAPIDAPI_PROXY_SECRET", None)
HEALTH_DETAILS_SECRET: Optional[str] = os.getenv("HEALTH_DETAILS_SECRET", None)

# ALLOWED_ORIGINS: comma-separated origins for CORS. Defaults to "*" — this API
# is auth'd by header/API-key (not cookies; allow_credentials=False), so a
# wildcard is the standard, safe pattern for a public multi-tenant API that
# RapidAPI subscribers embed from arbitrary browser origins. Only narrow this
# if you're self-hosting for a fixed set of known frontends.
_ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS: List[str] = (
    ["*"] if _ALLOWED_ORIGINS_RAW.strip() == "*"
    else [o.strip() for o in _ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
)

# TRUST_PROXY / TRUSTED_PROXY_IPS:
# If TRUSTED_PROXY_IPS is set (comma-separated CIDRs or IPs), only X-Forwarded-For
# from those IPs is trusted. If empty and TRUST_PROXY=true, all proxies trusted (legacy).
# When false (default), uses request.client.host only — prevents IP spoofing.
TRUST_PROXY: bool = os.getenv("TRUST_PROXY", "false").lower() == "true"
_TRUSTED_PROXY_IPS_RAW = os.getenv("TRUSTED_PROXY_IPS", "")
TRUSTED_PROXY_NETWORKS: List[ipaddress.IPv4Network] = []
if _TRUSTED_PROXY_IPS_RAW:
    for _cidr in _TRUSTED_PROXY_IPS_RAW.split(","):
        try:
            TRUSTED_PROXY_NETWORKS.append(ipaddress.ip_network(_cidr.strip(), strict=False))
        except ValueError:
            pass

# ------------------------------------------------------------------------------
# Redis
# ------------------------------------------------------------------------------
REDIS_URL: Optional[str] = os.getenv("REDIS_URL", None)

# ------------------------------------------------------------------------------
# Fetcher limits
# ------------------------------------------------------------------------------
MAX_REDIRECTS = 5

# Adaptive Byte Limit — SPA Detection.
# Sites built with React / Next.js / Vue / Angular etc. render content via JS;
# their HTML shell often exceeds 64 KB. We stream up to SOFT_LIMIT (64 KB) and
# scan for SPA signatures. If any are found we silently expand to HARD_LIMIT
# (256 KB) so we capture the server-side-rendered payload.
STREAM_SOFT_LIMIT = 64 * 1024   # 64 KB  — default for static / SSR sites
STREAM_HARD_LIMIT = 256 * 1024  # 256 KB — expanded for SPA / Next.js sites

# Response header limits (Plan §3.6) — bound memory from malicious/bloated
# upstream responses before we do anything else with them.
MAX_HEADER_COUNT = 100
MAX_HEADER_VALUE_LENGTH = 8192       # bytes, per header value
MAX_TOTAL_HEADER_BYTES = 64 * 1024   # combined size of all header names+values

# Per-target-host outbound concurrency (Plan §9) — stop a client from turning
# this API into an involuntary crawler against one victim host.
MAX_CONCURRENT_REQUESTS_PER_HOST = 6
HOST_SEMAPHORE_IDLE_TTL_SECONDS = 300

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

# ------------------------------------------------------------------------------
# Cache
# ------------------------------------------------------------------------------
CACHE_MAXSIZE = 5000
CACHE_TTL_SECONDS = 900          # 15 minutes

# Raw-fetch cache for lazy extraction (Plan §12) — bridges a short window so
# a burst of different-profile requests for the same URL (e.g. /tech-stack
# then /security moments apart) top up one cache entry without a second
# upstream fetch. Deliberately much smaller/shorter-lived than CACHE_*
# above: it only needs to survive a short window, not the full response TTL.
RAW_PAGE_CACHE_MAXSIZE = 1000
RAW_PAGE_CACHE_TTL_SECONDS = 60

DNS_CACHE_MAXSIZE = 2000
DNS_CACHE_TTL_SECONDS = 300      # 5 minutes

# ------------------------------------------------------------------------------
# Rate limiting
# ------------------------------------------------------------------------------
RATE_LIMIT_PER_MINUTE = 60
RATE_LIMIT_TRACKER_MAXSIZE = 10000

APP_VERSION = "4.0.0"
