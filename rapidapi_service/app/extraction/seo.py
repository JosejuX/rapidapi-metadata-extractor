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
"""
from typing import Any, Dict, List, Optional, Tuple


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
) -> Tuple[List[str], List[str], float]:
    passed_seo: List[str] = []
    warnings_seo: List[str] = []

    if title:
        if 10 <= len(title) <= 70:
            passed_seo.append("Title tag present with optimal length (10-70 chars)")
        else:
            warnings_seo.append(f"Title tag present but sub-optimal length ({len(title)} chars)")
    else:
        warnings_seo.append("Missing <title> tag")

    if description:
        if 50 <= len(description) <= 160:
            passed_seo.append("Meta description present with optimal length (50-160 chars)")
        else:
            warnings_seo.append(f"Meta description present but sub-optimal length ({len(description)} chars)")
    else:
        warnings_seo.append("Missing <meta name='description'> tag")

    if canonical_url:
        passed_seo.append("Canonical link tag present")
    else:
        warnings_seo.append("Missing <link rel='canonical'> tag")

    if h1_tags:
        passed_seo.append(f"Primary H1 heading present ({len(h1_tags)} found)")
    else:
        warnings_seo.append("Missing <h1> primary heading")

    if og_image:
        passed_seo.append("OpenGraph image present for social sharing")
    else:
        warnings_seo.append("Missing og:image social preview tag")

    if favicon:
        passed_seo.append("Favicon icon present")
    else:
        warnings_seo.append("Missing favicon icon")

    if images_count > 0:
        alt_coverage = round(((images_count - images_missing_alt_count) / images_count) * 100, 1)
        if alt_coverage >= 80.0:
            passed_seo.append(f"High image accessibility ALT coverage ({alt_coverage}%)")
        else:
            warnings_seo.append(f"Low image accessibility ALT coverage ({alt_coverage}% of images have ALT text)")

    if final_url.startswith("https://"):
        passed_seo.append("HTTPS secure protocol active")
    else:
        warnings_seo.append("Non-secure HTTP protocol used")

    # Plan §23 additional checks.
    if language:
        passed_seo.append(f"HTML lang attribute present ('{language}')")
    else:
        warnings_seo.append("Missing lang attribute on <html> element")

    if viewport:
        passed_seo.append("Responsive viewport meta tag present")
    else:
        warnings_seo.append("Missing viewport meta tag (mobile responsiveness)")

    if robots_directive and "noindex" in robots_directive.lower():
        warnings_seo.append("Page is marked noindex — excluded from search engine indexing")
    else:
        passed_seo.append("Page is indexable (no noindex directive)")

    if h1_count is not None and h1_count > 1:
        warnings_seo.append(f"Multiple <h1> headings found ({h1_count}) — should typically have exactly one")

    if twitter_card:
        passed_seo.append("Twitter Card meta tag present for social sharing")
    else:
        warnings_seo.append("Missing Twitter Card meta tag")

    if has_structured_data:
        passed_seo.append("Schema.org structured data (JSON-LD) present")
    else:
        warnings_seo.append("No structured data (JSON-LD) found")

    total_seo_checks = len(passed_seo) + len(warnings_seo)
    seo_score = round((len(passed_seo) / total_seo_checks) * 100, 1) if total_seo_checks > 0 else 0.0

    return passed_seo, warnings_seo, seo_score
