"""
Regression guard for the embedded playground UI (Plan §67: no innerHTML with
scraped/untrusted data, no target="_blank" without rel="noopener noreferrer").

app/ui/templates.py renders fields that originate from an arbitrary,
attacker-controlled target page (social_links, contacts.emails). If that
HTML ever goes back to injecting them via `innerHTML += `<...>${value}</...>``
instead of textContent/createElement, a scraped page could run script in the
API's own playground page. These are static string checks on the template
source, not a browser-driven test, but they're cheap and catch the exact
regression class Plan §67 calls out.
"""
from app.ui.templates import HOME_HTML


def test_no_innerhtml_template_literal_injection():
    # `innerHTML += `...${...}...`` (or `innerHTML = `...${...}...``) would
    # inject untrusted values (social link URLs, scraped emails) as raw HTML.
    assert "innerHTML +=" not in HOME_HTML
    assert "innerHTML = `" not in HOME_HTML


def test_target_blank_has_noopener_noreferrer():
    assert "target = '_blank'" in HOME_HTML or 'target="_blank"' in HOME_HTML
    assert "noopener noreferrer" in HOME_HTML


def test_social_link_href_is_scheme_validated():
    # href for scraped social links must go through a scheme allowlist
    # (http/https only) before being assigned, not straight from the API response.
    assert "isSafeHttpUrl" in HOME_HTML
    assert "u.protocol === 'http:' || u.protocol === 'https:'" in HOME_HTML


def test_untrusted_fields_use_textcontent():
    assert "a.textContent = net.toUpperCase()" in HOME_HTML
    assert "span.textContent = e" in HOME_HTML
