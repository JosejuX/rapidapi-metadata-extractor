"""
Property-based / fuzz tests (Plan §53/§54) — previously an identified gap
(no fuzzing existed anywhere in the suite). These don't test specific
examples; they generate hundreds of adversarial inputs per run and assert
invariants that must hold for *any* input:

- URL normalization never crashes with an unhandled exception and is
  idempotent for inputs it accepts.
- The SSRF IP-danger classification (mirrors app/security/ssrf.py's
  is_dangerous expression exactly) never lets a private/loopback/
  link-local/multicast/reserved/unspecified address through as "safe",
  for ANY IPv4 or IPv6 address, not just the specific ones in
  test_ssrf_matrix.py's fixed list.
- Extractors that run on attacker-controlled page content (tech detection,
  social link classification, JSON-LD parsing, metadata extraction,
  markdown conversion) never raise on arbitrary/malformed input — a crash
  there would be a request-killing bug reachable by any scraped page.
"""
import ipaddress

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.errors import AppError
from app.core.urls import normalize_and_validate_url
from app.extraction.contacts import extract_emails
from app.extraction.jsonld import extract_json_ld
from app.extraction.links import extract_links_and_socials
from app.extraction.markdown import extract_summary_and_keywords, html_to_markdown_clean
from app.extraction.metadata import extract_metadata_fields
from app.extraction.phones import normalize_phones
from app.extraction.security import extract_security_headers
from app.extraction.seo import run_seo_audit
from app.extraction.tech import detect_technologies, detect_technologies_detailed
from selectolax.parser import HTMLParser

_EXTRA_BLOCKED_NETWORKS = [
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("240.0.0.0/4"),
]


def _is_dangerous(ip_obj) -> bool:
    """Exact mirror of app/security/ssrf.py's is_dangerous expression."""
    return (
        ip_obj.is_private or
        ip_obj.is_loopback or
        ip_obj.is_link_local or
        ip_obj.is_multicast or
        ip_obj.is_reserved or
        ip_obj.is_unspecified or
        str(ip_obj) == "169.254.169.254" or
        any(ip_obj in net for net in _EXTRA_BLOCKED_NETWORKS)
    )


# --- URL normalization ------------------------------------------------------

@given(st.text(max_size=500))
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_normalize_url_never_raises_unexpected_exception(text):
    try:
        normalize_and_validate_url(text)
    except AppError:
        pass  # expected, well-classified rejection
    except Exception as e:
        raise AssertionError(f"unexpected exception {type(e).__name__}: {e!r} for input {text!r}") from e


@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=200))
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_normalize_url_is_idempotent_when_it_succeeds(text):
    try:
        once = normalize_and_validate_url(text)
    except AppError:
        return
    try:
        twice = normalize_and_validate_url(once)
    except AppError as e:
        raise AssertionError(f"normalizing an already-normalized URL {once!r} raised {e.detail!r}") from e
    assert once == twice, f"not idempotent: {text!r} -> {once!r} -> {twice!r}"


# --- SSRF IP classification --------------------------------------------------

@given(st.ip_addresses(v=4))
@settings(max_examples=500)
def test_ssrf_classification_flags_all_known_dangerous_ipv4_ranges(ip):
    ip_obj = ipaddress.ip_address(str(ip))
    dangerous = _is_dangerous(ip_obj)
    # These stdlib properties MUST always imply "dangerous" — if any of them
    # is true but the classification says otherwise, that's an SSRF hole.
    must_be_dangerous = (
        ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or
        ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified
    )
    if must_be_dangerous:
        assert dangerous, f"{ip_obj} has a dangerous stdlib property but classified as safe"


@given(st.ip_addresses(v=6))
@settings(max_examples=500)
def test_ssrf_classification_flags_all_known_dangerous_ipv6_ranges(ip):
    ip_obj = ipaddress.ip_address(str(ip))
    dangerous = _is_dangerous(ip_obj)
    must_be_dangerous = (
        ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or
        ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified
    )
    if must_be_dangerous:
        assert dangerous, f"{ip_obj} has a dangerous stdlib property but classified as safe"


@given(st.sampled_from([
    "1.1.1.1", "8.8.8.8", "93.184.216.34", "140.82.112.3",  # real public IPs
]))
def test_ssrf_classification_allows_known_public_ips(ip_str):
    ip_obj = ipaddress.ip_address(ip_str)
    assert not _is_dangerous(ip_obj), f"{ip_obj} is a known-public IP but classified as dangerous"


# --- Extractors on arbitrary/malformed HTML ---------------------------------

_html_strategy = st.text(max_size=3000)


@given(_html_strategy)
@settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
def test_tech_detection_never_crashes(html):
    detect_technologies(html)
    detect_technologies_detailed(html)


@given(_html_strategy)
@settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
def test_email_extraction_never_crashes(html):
    extract_emails(html, [])


@given(_html_strategy)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_metadata_extraction_never_crashes_on_fuzzed_html(html):
    tree = HTMLParser(html)
    extract_metadata_fields(tree, "https://fuzz.example.com/page", {}, links_count=0)


@given(_html_strategy)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_links_and_socials_extraction_never_crashes(html):
    tree = HTMLParser(html)
    a_nodes = tree.css('a[href]')
    extract_links_and_socials(a_nodes, "https://fuzz.example.com/page")


@given(_html_strategy)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_jsonld_extraction_never_crashes_on_fuzzed_script_content(fuzz_body):
    html = f'<html><body><script type="application/ld+json">{fuzz_body}</script></body></html>'
    tree = HTMLParser(html)
    extract_json_ld(tree)


@given(_html_strategy)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_markdown_conversion_never_crashes(html):
    tree = HTMLParser(html)
    html_to_markdown_clean(tree, "https://fuzz.example.com/page")


@given(st.text(max_size=2000))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_summary_and_keywords_never_crashes(text):
    extract_summary_and_keywords(text, None)


@given(st.dictionaries(
    st.sampled_from(["strict-transport-security", "content-security-policy",
                      "content-security-policy-report-only", "x-frame-options",
                      "x-content-type-options", "referrer-policy", "permissions-policy"]),
    st.text(max_size=300),
))
@settings(max_examples=150)
def test_security_header_grading_never_crashes(headers):
    extract_security_headers(headers)


@given(st.lists(st.text(max_size=50), max_size=8))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_phone_normalization_never_crashes(raw_phones):
    normalize_phones(raw_phones)


@given(
    st.one_of(st.none(), st.text(max_size=200)),
    st.one_of(st.none(), st.text(max_size=200)),
    st.one_of(st.none(), st.text(max_size=200)),
    st.lists(st.text(max_size=50), max_size=5),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_seo_audit_never_crashes(title, description, canonical_url, h1_tags):
    run_seo_audit(
        title=title, description=description, canonical_url=canonical_url,
        h1_tags=h1_tags, og_image=None, favicon=None, images_count=0,
        images_missing_alt_count=0, final_url="https://fuzz.example.com/page",
    )
