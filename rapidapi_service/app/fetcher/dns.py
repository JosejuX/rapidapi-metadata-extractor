"""DNS resolution cache (Plan section 4.9 / 5). Module-level singleton — accessed
via `app.fetcher.dns.dns_cache` (not re-exported by value) so mutations are
visible everywhere it's imported."""
from cachetools import TTLCache
from app import config

dns_cache: TTLCache = TTLCache(maxsize=config.DNS_CACHE_MAXSIZE, ttl=config.DNS_CACHE_TTL_SECONDS)
