"""
Bot-protection / challenge-page detection: this API fetches raw HTML, it
doesn't run a browser, so a Cloudflare/Akamai/PerimeterX/CAPTCHA challenge
page gets fetched (and extracted from) as-is. `bot_protection_detected`
gives the caller an explicit signal instead of a silently near-empty result.
"""
from app.extraction.bot_protection import detect_bot_protection

_CF_CHALLENGE = """<html><head><title>Just a moment...</title></head><body>
<div class="cf-browser-verification">Checking your browser before accessing example.com.</div>
<script>window.__cf_chl_opt = {};</script>
</body></html>"""

_NORMAL_PAGE = "<html><head><title>Normal Page</title></head><body><p>Welcome to our site.</p></body></html>"


def test_real_cloudflare_challenge_page_is_detected():
    assert detect_bot_protection(_CF_CHALLENGE, 503) is True


def test_normal_page_is_not_flagged():
    assert detect_bot_protection(_NORMAL_PAGE, 200) is False


def test_single_weak_signal_with_ok_status_is_not_flagged():
    # One incidental mention (e.g. a comment form using recaptcha) on a
    # normal 200 response shouldn't be enough to flag the whole page.
    html = "<html><body>Please complete the g-recaptcha below to comment.</body></html>"
    assert detect_bot_protection(html, 200) is False


def test_single_signal_with_suspicious_status_is_flagged():
    html = "<html><body>Please complete the g-recaptcha to continue.</body></html>"
    assert detect_bot_protection(html, 403) is True


def test_multiple_signals_flagged_even_with_ok_status():
    html = "<html><body>hcaptcha.com widget and datadome protection active.</body></html>"
    assert detect_bot_protection(html, 200) is True


def test_large_page_is_never_flagged_even_with_matching_text():
    # A real challenge page is small. A big legitimate article that happens
    # to mention "verify you are human" once (e.g. discussing CAPTCHAs)
    # should not be flagged just because of page size + one match.
    padding = "A" * 25_000
    html = f"<html><body>{padding}<p>Datadome and hcaptcha.com are common bot defenses.</p></body></html>"
    assert detect_bot_protection(html, 200) is False


def test_no_signatures_present_is_never_flagged_regardless_of_status():
    assert detect_bot_protection(_NORMAL_PAGE, 403) is False
    assert detect_bot_protection(_NORMAL_PAGE, 503) is False
