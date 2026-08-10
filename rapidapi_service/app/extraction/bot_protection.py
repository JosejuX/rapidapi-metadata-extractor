"""
Bot-protection / challenge-page detection.

This API fetches raw HTML over HTTP — it doesn't run a browser or execute
JavaScript (Plan §89/§101: no Playwright in the fast path). When a target
site is behind Cloudflare/Akamai/PerimeterX/a CAPTCHA, what actually gets
fetched is often the *challenge page itself*, not the site's real content —
every extractor then silently returns near-empty results with no obvious
explanation. This is a cheap heuristic signature check (no network requests,
no JS execution, no proof of any specific vendor). It's used two ways:

- On a 2xx response (some anti-bot setups serve a 200 interstitial rather
  than tipping off simple scrapers via status code): pipeline.py sets
  `bot_protection_detected` on the normal response instead of a confusing
  near-empty extraction result.
- On a 403/429/503 response (the common case — e.g. classic Cloudflare
  challenges): app/fetcher/client.py peeks at a small bounded slice of the
  body before raising, and raises the specific BOT_PROTECTION_DETECTED
  error code instead of the generic UPSTREAM_4XX/UPSTREAM_5XX, so "the
  target blocked this request" is distinguishable from "the target genuinely
  has no title/description/etc." or "a real upstream outage".

Deliberately conservative to avoid false positives on legitimate pages that
happen to mention "captcha" or similar in passing: requires either a
suspicious status code alongside a signature match, or multiple independent
signature matches, and skips the check entirely on large pages (a real
challenge page is small; a 200KB article page matching one signature by
coincidence should not be flagged).
"""
_MAX_CANDIDATE_BYTES = 20_000
_SUSPICIOUS_STATUS_CODES = {403, 429, 503}

_SIGNATURES = (
    "checking your browser before accessing",
    "cf-browser-verification",
    "__cf_chl_",
    "cf_chl_opt",
    "attention required! | cloudflare",
    "just a moment...",
    "enable javascript and cookies to continue",
    "px-captcha",
    "perimeterx",
    "datadome",
    "hcaptcha.com",
    "g-recaptcha",
    "verify you are human",
)


def detect_bot_protection(html_content: str, status_code: int) -> bool:
    if len(html_content) > _MAX_CANDIDATE_BYTES:
        return False
    html_lower = html_content.lower()
    hits = sum(1 for sig in _SIGNATURES if sig in html_lower)
    if hits == 0:
        return False
    return hits >= 2 or status_code in _SUSPICIOUS_STATUS_CODES
