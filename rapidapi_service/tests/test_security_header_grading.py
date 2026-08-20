"""Security header quality grading (Plan §24): presence alone is no longer
enough to score well — a weak/dangerous header value must score lower than
a strong one, and both must score higher than a missing header."""
from app.extraction.security import extract_security_headers


def test_unsafe_csp_scores_lower_than_strict_csp():
    weak_headers = {"content-security-policy": "default-src *; script-src * 'unsafe-inline'"}
    strong_headers = {"content-security-policy": "default-src 'self'; script-src 'self' 'nonce-abc123'"}

    _, weak_score, weak_grades, _ = extract_security_headers(weak_headers)
    _, strong_score, strong_grades, _ = extract_security_headers(strong_headers)

    assert weak_grades["content_security_policy"] == "weak"
    assert strong_grades["content_security_policy"] == "strong"
    assert strong_score > weak_score


def test_missing_header_scores_lower_than_weak_header():
    empty_headers = {}
    weak_headers = {"x-frame-options": "GARBAGE-VALUE"}

    _, empty_score, empty_grades, _ = extract_security_headers(empty_headers)
    _, weak_score, weak_grades, _ = extract_security_headers(weak_headers)

    assert empty_grades["x_frame_options"] == "missing"
    assert weak_grades["x_frame_options"] == "weak"
    assert weak_score > empty_score


def test_hsts_short_max_age_is_weak_long_max_age_with_subdomains_is_strong():
    short = {"strict-transport-security": "max-age=3600"}
    long_with_subdomains = {"strict-transport-security": "max-age=63072000; includeSubDomains"}

    _, _, short_grades, _ = extract_security_headers(short)
    _, _, long_grades, _ = extract_security_headers(long_with_subdomains)

    assert short_grades["strict_transport_security"] == "weak"
    assert long_grades["strict_transport_security"] == "strong"


def test_x_content_type_options_only_nosniff_is_strong():
    headers_nosniff = {"x-content-type-options": "nosniff"}
    headers_garbage = {"x-content-type-options": "something-else"}

    _, _, nosniff_grades, _ = extract_security_headers(headers_nosniff)
    _, _, garbage_grades, _ = extract_security_headers(headers_garbage)

    assert nosniff_grades["x_content_type_options"] == "strong"
    assert garbage_grades["x_content_type_options"] == "weak"


def test_referrer_policy_unsafe_url_is_weak_no_referrer_is_strong():
    weak = {"referrer-policy": "unsafe-url"}
    strong = {"referrer-policy": "no-referrer"}

    _, _, weak_grades, _ = extract_security_headers(weak)
    _, _, strong_grades, _ = extract_security_headers(strong)

    assert weak_grades["referrer_policy"] == "weak"
    assert strong_grades["referrer_policy"] == "strong"


def test_all_headers_missing_scores_zero():
    _, score, grades, _ = extract_security_headers({})
    assert score == 0.0
    assert all(g == "missing" for g in grades.values())


def test_best_possible_headers_score_highest_but_permissions_policy_caps_below_strong():
    # permissions-policy directives aren't individually parsed (Plan §24
    # notes this explicitly), so it can reach "reasonable" but never "strong"
    # — even a fully locked-down header set can't hit a perfect 100.
    headers = {
        "strict-transport-security": "max-age=63072000; includeSubDomains",
        "content-security-policy": "default-src 'self'",
        "x-frame-options": "DENY",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
        "permissions-policy": "camera=(), microphone=()",
    }
    _, score, grades, _ = extract_security_headers(headers)
    assert grades["permissions_policy"] == "reasonable"
    assert all(g == "strong" for k, g in grades.items() if k != "permissions_policy")
    expected = round((5 * 1.0 + 0.6) / 6 * 100, 1)
    assert score == expected


def test_report_only_csp_is_distinct_from_missing_and_from_enforced():
    report_only_headers = {
        "content-security-policy-report-only": "default-src 'self'; report-uri /csp-reports"
    }
    _, report_only_score, report_only_grades, _ = extract_security_headers(report_only_headers)
    _, missing_score, missing_grades, _ = extract_security_headers({})

    assert report_only_grades["content_security_policy"] == "report-only"
    assert missing_grades["content_security_policy"] == "missing"
    # Report-only is acknowledged (site is actively working towards a policy)
    # but must never be conflated with an enforced policy: it provides zero
    # real browser-side protection today.
    assert report_only_score > missing_score
    enforced_headers = {"content-security-policy": "default-src 'self'"}
    _, enforced_score, enforced_grades, _ = extract_security_headers(enforced_headers)
    assert enforced_grades["content_security_policy"] == "strong"
    assert enforced_score > report_only_score


def test_enforced_csp_present_ignores_report_only_header():
    headers = {
        "content-security-policy": "default-src 'self'",
        "content-security-policy-report-only": "default-src *",
    }
    _, _, grades, _ = extract_security_headers(headers)
    assert grades["content_security_policy"] == "strong"


def test_report_only_raw_value_exposed_additively():
    headers = {"content-security-policy-report-only": "default-src 'self'"}
    sec_headers, _, _, _ = extract_security_headers(headers)
    assert sec_headers["content_security_policy_report_only"] == "default-src 'self'"
    assert sec_headers["content_security_policy"] is None


def test_every_header_has_a_why_this_matters_explanation():
    _, _, grades, explanations = extract_security_headers({})
    for header_key in grades:
        assert header_key in explanations
        assert len(explanations[header_key]) > 20
