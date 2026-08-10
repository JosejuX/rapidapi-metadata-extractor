"""Shared OpenAPI response documentation (Plan section 34)."""

COMMON_RESPONSES = {
    400: {"description": "Bad Request: Invalid URL format, missing domain hostname, or blocked by IP-Pinned Anti-SSRF Shield"},
    403: {"description": "Forbidden: Invalid or missing X-RapidAPI-Proxy-Secret authentication header"},
    429: {"description": "Too Many Requests: Rate limit exceeded (60 requests/min per IP)"}
}
