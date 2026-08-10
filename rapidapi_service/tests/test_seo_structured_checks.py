"""Structured per-check SEO data (Plan §23): `seo_checks` carries the same
information as passed_checks/warnings but machine-readable, with a severity
per check reflecting how much a *failed* check matters."""
from app.extraction.seo import run_seo_audit

_BASE = dict(
    title="A title of reasonable length for the test",
    description="A description in the sweet spot range for SEO purposes, comfortably between fifty and one sixty characters long.",
    canonical_url="https://example.com/",
    h1_tags=["H1"],
    og_image="https://example.com/og.png",
    favicon="https://example.com/favicon.ico",
    images_count=0,
    images_missing_alt_count=0,
    final_url="https://example.com/",
    language="en",
    viewport="width=device-width",
    twitter_card="summary",
    has_structured_data=True,
)


def test_backward_compatible_lists_unchanged_alongside_new_checks():
    passed, warnings, score, checks = run_seo_audit(**_BASE)
    assert isinstance(passed, list) and all(isinstance(p, str) for p in passed)
    assert isinstance(warnings, list) and all(isinstance(w, str) for w in warnings)
    assert isinstance(checks, list)
    assert len(checks) == len(passed) + len(warnings)


def test_missing_title_is_critical_severity_and_not_passed():
    _, _, _, checks = run_seo_audit(**{**_BASE, "title": None})
    title_check = next(c for c in checks if c["check"] == "title")
    assert title_check["passed"] is False
    assert title_check["severity"] == "critical"


def test_missing_favicon_is_minor_severity():
    _, _, _, checks = run_seo_audit(**{**_BASE, "favicon": None})
    favicon_check = next(c for c in checks if c["check"] == "favicon")
    assert favicon_check["passed"] is False
    assert favicon_check["severity"] == "minor"


def test_each_check_has_required_fields():
    _, _, _, checks = run_seo_audit(**_BASE)
    for check in checks:
        assert set(check.keys()) == {"check", "passed", "severity", "evidence"}
        assert check["severity"] in ("critical", "important", "minor")
        assert isinstance(check["evidence"], str) and check["evidence"]


def test_passed_check_still_recorded_with_evidence():
    _, _, _, checks = run_seo_audit(**_BASE)
    https_check = next(c for c in checks if c["check"] == "https")
    assert https_check["passed"] is True
    assert "HTTPS" in https_check["evidence"]
