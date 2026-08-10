"""
SEO diagnostic audit (Plan section 23). Expanded beyond the original 8 checks
with lang attribute, viewport, robots noindex, multiple-H1, Twitter Card, and
structured-data presence (Plan §23 checklist) — additive checks appended to
the same List[str] passed_checks/warnings fields, so the response field
*types* are unchanged for v1 clients. The numeric seo_score_percentage VALUE
does shift (more checks -> different ratio) since the audit is now more
thorough; this is the intended outcome of Plan §23, not a bug — scores are
explicitly a heuristic, improvable metric per Plan §24's same framing for
security scores, not a fixed contract value.

Plan §23 also asks for structured per-check data (check id / passed /
severity / evidence) instead of only flat pass/warning strings — added as a
new, additive `seo_checks` return value / response field. `passed_seo` and
`warnings_seo` are unchanged; `seo_checks` carries the same information in a
machine-readable shape, with a `severity` reflecting how much a *failed*
check matters (critical/important/minor), not how "good" a pass is.
"""
from typing import Any, Dict, List, Optional, Tuple

_SEVERITY = {
    "title": "critical",
    "meta_description": "critical",
    "canonical": "important",
    "h1_present": "critical",
    "og_image": "important",
    "favicon": "minor",
    "image_alt_coverage": "important",
    "https": "critical",
    "lang_attribute": "important",
    "viewport": "important",
    "indexability": "critical",
    "multiple_h1": "minor",
    "twitter_card": "minor",
    "structured_data": "minor",
}


def run_seo_audit(
    title: Optional[str],
    description: Optional[str],
    canonical_url: Optional[str],
    h1_tags: List[str],
    og_image: Optional[str],
    favicon: Optional[str],
    images_count: int,
    images_missing_alt_count: int,
    final_url: str,
    language: Optional[str] = None,
    viewport: Optional[str] = None,
    robots_directive: Optional[str] = None,
    h1_count: Optional[int] = None,
    twitter_card: Optional[str] = None,
    has_structured_data: bool = False,
) -> Tuple[List[str], List[str], float, List[Dict[str, Any]]]:
    passed_seo: List[str] = []
    warnings_seo: List[str] = []
    checks: List[Dict[str, Any]] = []

    def record(check_id: str, passed: bool, message: str):
        (passed_seo if passed else warnings_seo).append(message)
        checks.append({
            "check": check_id,
            "passed": passed,
            "severity": _SEVERITY[check_id],
            "evidence": message,
        })

    if title:
        ok = 10 <= len(title) <= 70
        record("title", ok,
               "Title tag present with optimal length (10-70 chars)" if ok
               else f"Title tag present but sub-optimal length ({len(title)} chars)")
    else:
        record("title", False, "Missing <title> tag")

    if description:
        ok = 50 <= len(description) <= 160
        record("meta_description", ok,
               "Meta description present with optimal length (50-160 chars)" if ok
               else f"Meta description present but sub-optimal length ({len(description)} chars)")
    else:
        record("meta_description", False, "Missing <meta name='description'> tag")

    if canonical_url:
        record("canonical", True, "Canonical link tag present")
    else:
        record("canonical", False, "Missing <link rel='canonical'> tag")

    if h1_tags:
        record("h1_present", True, f"Primary H1 heading present ({len(h1_tags)} found)")
    else:
        record("h1_present", False, "Missing <h1> primary heading")

    if og_image:
        record("og_image", True, "OpenGraph image present for social sharing")
    else:
        record("og_image", False, "Missing og:image social preview tag")

    if favicon:
        record("favicon", True, "Favicon icon present")
    else:
        record("favicon", False, "Missing favicon icon")

    if images_count > 0:
        alt_coverage = round(((images_count - images_missing_alt_count) / images_count) * 100, 1)
        ok = alt_coverage >= 80.0
        record("image_alt_coverage", ok,
               f"High image accessibility ALT coverage ({alt_coverage}%)" if ok
               else f"Low image accessibility ALT coverage ({alt_coverage}% of images have ALT text)")

    if final_url.startswith("https://"):
        record("https", True, "HTTPS secure protocol active")
    else:
        record("https", False, "Non-secure HTTP protocol used")

    # Plan §23 additional checks.
    if language:
        record("lang_attribute", True, f"HTML lang attribute present ('{language}')")
    else:
        record("lang_attribute", False, "Missing lang attribute on <html> element")

    if viewport:
        record("viewport", True, "Responsive viewport meta tag present")
    else:
        record("viewport", False, "Missing viewport meta tag (mobile responsiveness)")

    if robots_directive and "noindex" in robots_directive.lower():
        record("indexability", False, "Page is marked noindex — excluded from search engine indexing")
    else:
        record("indexability", True, "Page is indexable (no noindex directive)")

    if h1_count is not None and h1_count > 1:
        record("multiple_h1", False, f"Multiple <h1> headings found ({h1_count}) — should typically have exactly one")

    if twitter_card:
        record("twitter_card", True, "Twitter Card meta tag present for social sharing")
    else:
        record("twitter_card", False, "Missing Twitter Card meta tag")

    if has_structured_data:
        record("structured_data", True, "Schema.org structured data (JSON-LD) present")
    else:
        record("structured_data", False, "No structured data (JSON-LD) found")

    total_seo_checks = len(passed_seo) + len(warnings_seo)
    seo_score = round((len(passed_seo) / total_seo_checks) * 100, 1) if total_seo_checks > 0 else 0.0

    return passed_seo, warnings_seo, seo_score, checks
