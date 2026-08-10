"""L1 process-local extraction result cache (Plan section 6.1). Module-level
singleton — accessed via `app.cache.l1.cache`, mutated in place."""
from cachetools import TTLCache
from app import config

cache: TTLCache = TTLCache(maxsize=config.CACHE_MAXSIZE, ttl=config.CACHE_TTL_SECONDS)
