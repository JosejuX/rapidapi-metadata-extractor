"""
Structured JSON logging (Plan section 41). Every log line is a single JSON
object on stdout — one line per event, ready for any log aggregator (no
regex parsing of a free-text format).

Backward compatible with every existing `logger.info("...", arg1, arg2)` /
`logger.warning(...)` / `logger.error(...)` call already scattered across
the codebase: those still work unchanged and simply produce a JSON line
with a "message" field. New call sites can additionally pass `extra={...}`
to get first-class structured fields, e.g.:

    logger.warning("upstream_timeout", extra={
        "event": "upstream_timeout", "request_id": rid,
        "host": host, "duration_ms": dur, "endpoint": endpoint,
    })

Plan §41 explicitly forbids logging secrets (API keys, Redis URLs with
passwords, cookies, Authorization headers, sensitive query params). Nothing
in this codebase logs those today (verified: no logger call formats
config.RAPIDAPI_PROXY_SECRET, config.REDIS_URL, or request Authorization/
Cookie headers) — `_redact` below is a defense-in-depth safety net in case
a future call site accidentally includes one of those field names in
`extra`, not a workaround for an existing leak.
"""
import json
import logging
import re

_REDACT_KEYS = {"authorization", "cookie", "api_key", "apikey", "secret", "password", "redis_url", "proxy_secret"}
_REDACTED = "***REDACTED***"

# Standard LogRecord attributes — anything else on the record was passed via
# `extra={...}` and should be surfaced as a top-level structured field.
_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {"message", "asctime"}

_URL_CREDENTIALS_RE = re.compile(r"://[^/@\s]+:[^/@\s]+@")


def _redact(value):
    if isinstance(value, str) and _URL_CREDENTIALS_RE.search(value):
        return _URL_CREDENTIALS_RE.sub("://***:***@", value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key in payload:
                continue
            payload[key.lower() if key.lower() in _REDACT_KEYS else key] = (
                _REDACTED if key.lower() in _REDACT_KEYS else _redact(value)
            )
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())

logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
logger = logging.getLogger("metadata-api")
