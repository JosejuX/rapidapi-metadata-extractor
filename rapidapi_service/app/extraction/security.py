"""
HTTP security headers audit (Plan section 24).

The original implementation scored purely on presence/absence: a
Content-Security-Policy of `default-src *; script-src * 'unsafe-inline'`
(actively dangerous) scored identically to a strict, nonce-based policy. Each
header is now graded missing/weak/reasonable/strong based on its actual
value, not just whether it exists.

`security_headers` (raw header values) is unchanged — same keys, same
Optional[str] values, existing v1 clients see no difference there.
`security_score_percentage` VALUE will shift for pages with weak-but-present
headers (a page that used to score highly for merely having a CSP header may
now score lower if that CSP is `unsafe-inline`) — this is the intended
outcome of a more honest heuristic, not a bug, same framing as Plan §23's
SEO audit precedent. `security_header_grades` is a new, additive field.

CSP Report-Only handling (added in response to community feedback: a site
running `Content-Security-Policy-Report-Only` — logging violations without
blocking anything yet, typically mid-rollout of a stricter policy — used to
be entirely invisible to this audit, since only the enforcing
`Content-Security-Policy` header was ever read. That's worse than scoring it
the same as an enforced policy: it wasn't scored at all. A report-only-only
CSP is now surfaced as its own distinct `"report-only"` grade — weighted
above `"missing"` (the site is actively working towards a policy) but well
below `"weak"` (it provides zero real browser-enforced protection today) —
and the raw report-only header value is exposed additively as
`content_security_policy_report_only` so a consumer can tell rollout-in-
progress apart from no CSP effort at all.
"""
import re
from typing import Any, Dict, Tuple

_GRADE_WEIGHTS = {
    "missing": 0.0,
    "report-only": 0.1,
    "weak": 0.25,
    "reasonable": 0.6,
    "strong": 1.0,
}

_HEADER_EXPLANATIONS = {
    "strict_transport_security": (
        "Forces browsers to use HTTPS for future visits, closing the window "
        "where a man-in-the-middle can downgrade the very first request to plain HTTP."
    ),
    "content_security_policy": (
        "Restricts which sources scripts/styles/frames can load from, the primary "
        "browser-side defense against XSS — a permissive or missing policy lets "
        "injected script run with full page privileges."
    ),
    "x_frame_options": (
        "Prevents the page from being embedded in a hidden iframe on another site, "
        "the standard defense against clickjacking."
    ),
    "x_content_type_options": (
        "Stops the browser from guessing (\"sniffing\") a response's MIME type, closing "
        "off attacks where a file is served as one type but rendered/executed as another."
    ),
    "referrer_policy": (
        "Controls how much of the current URL leaks to third parties in the Referer "
        "header when a user follows an outbound link — relevant if URLs ever carry tokens or IDs."
    ),
    "permissions_policy": (
        "Explicitly disables browser features (camera, geolocation, etc.) the page "
        "doesn't use, shrinking what an attacker gains even if they get script execution."
    ),
}

_HSTS_MAX_AGE_RE = re.compile(r'max-age\s*=\s*(\d+)', re.I)
_SIX_MONTHS_SECONDS = 15552000
_ONE_YEAR_SECONDS = 31536000

_CSP_UNSAFE_RE = re.compile(r"unsafe-inline|unsafe-eval", re.I)
_CSP_WILDCARD_SRC_RE = re.compile(r"(?:^|;)\s*[\w-]*src\s+[^;]*\*", re.I)

_REFERRER_STRONG = {"no-referrer", "strict-origin", "strict-origin-when-cross-origin", "same-origin"}
_REFERRER_WEAK = {"unsafe-url"}


def _grade_hsts(value: str) -> str:
    match = _HSTS_MAX_AGE_RE.search(value)
    max_age = int(match.group(1)) if match else 0
    include_subdomains = "includesubdomains" in value.lower()
    if max_age >= _ONE_YEAR_SECONDS and include_subdomains:
        return "strong"
    if max_age >= _SIX_MONTHS_SECONDS:
        return "reasonable"
    return "weak"


def _grade_csp(value: str) -> str:
    if _CSP_UNSAFE_RE.search(value) or _CSP_WILDCARD_SRC_RE.search(value) or value.strip() == "*":
        return "weak"
    if "default-src" in value.lower() or "script-src" in value.lower():
        return "strong"
    return "reasonable"


def _grade_x_frame_options(value: str) -> str:
    normalized = value.strip().upper()
    if normalized in ("DENY", "SAMEORIGIN"):
        return "strong"
    if normalized.startswith("ALLOW-FROM"):
        return "reasonable"
    return "weak"


def _grade_x_content_type_options(value: str) -> str:
    return "strong" if value.strip().lower() == "nosniff" else "weak"


def _grade_referrer_policy(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in _REFERRER_WEAK:
        return "weak"
    if normalized in _REFERRER_STRONG:
        return "strong"
    return "reasonable"


def _grade_permissions_policy(value: str) -> str:
    # Grading individual feature directives (camera=(), geolocation=(), ...)
    # would need parsing a large, evolving directive vocabulary — presence
    # of a non-empty policy is treated as a reasonable baseline.
    return "reasonable" if value.strip() else "weak"


_GRADERS = {
    "strict_transport_security": _grade_hsts,
    "content_security_policy": _grade_csp,
    "x_frame_options": _grade_x_frame_options,
    "x_content_type_options": _grade_x_content_type_options,
    "referrer_policy": _grade_referrer_policy,
    "permissions_policy": _grade_permissions_policy,
}


def extract_security_headers(
    resp_headers: Dict[str, str],
) -> Tuple[Dict[str, Any], float, Dict[str, str], Dict[str, str]]:
    sec_headers = {
        "strict_transport_security": resp_headers.get("strict-transport-security"),
        "content_security_policy": resp_headers.get("content-security-policy"),
        "x_frame_options": resp_headers.get("x-frame-options"),
        "x_content_type_options": resp_headers.get("x-content-type-options"),
        "referrer_policy": resp_headers.get("referrer-policy"),
        "permissions_policy": resp_headers.get("permissions-policy"),
    }
    # Additive: raw report-only CSP value, kept separate from the enforcing
    # header above so existing consumers of `content_security_policy` see no change.
    sec_headers["content_security_policy_report_only"] = resp_headers.get(
        "content-security-policy-report-only"
    )

    grades: Dict[str, str] = {}
    for key, value in sec_headers.items():
        if key == "content_security_policy_report_only":
            continue
        if key == "content_security_policy" and value is None:
            report_only_value = sec_headers["content_security_policy_report_only"]
            grades[key] = "report-only" if report_only_value else "missing"
            continue
        grades[key] = "missing" if value is None else _GRADERS[key](value)

    security_score = round(
        sum(_GRADE_WEIGHTS[g] for g in grades.values()) / len(grades) * 100, 1
    )
    return sec_headers, security_score, grades, dict(_HEADER_EXPLANATIONS)
