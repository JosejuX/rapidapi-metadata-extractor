"""Social link detection (Plan §17): hostname-map lookup, including the
best-effort Mastodon coverage (decentralized platform, curated instance list)."""
from selectolax.parser import HTMLParser

from app.extraction.links import extract_links_and_socials

HTML = """
<html><body>
<a href="https://mastodon.social/@fixtureco">Mastodon</a>
<a href="https://twitter.com/fixtureco">Twitter</a>
<a href="https://example.com/mentions/twitter.com/foo">Not a real Twitter link</a>
</body></html>
"""


def _extract():
    tree = HTMLParser(HTML)
    a_nodes = tree.css('a[href]')
    return extract_links_and_socials(a_nodes, "https://fixture.example.com/page")


def test_mastodon_instance_is_detected():
    result = _extract()
    assert result["social_links"]["mastodon"] == "https://mastodon.social/@fixtureco"


def test_twitter_is_detected():
    result = _extract()
    assert result["social_links"]["twitter"] == "https://twitter.com/fixtureco"


def test_unrelated_domain_mentioning_twitter_in_path_is_not_misdetected():
    # Hostname-based lookup (not substring/regex matching against the whole
    # URL) means a link like example.com/mentions/twitter.com/foo — whose
    # actual hostname is example.com — is classified as external, not as a
    # false-positive Twitter match.
    result = _extract()
    assert "https://example.com/mentions/twitter.com/foo" in result["external_links"]
    assert result["social_links"]["twitter"] == "https://twitter.com/fixtureco"
