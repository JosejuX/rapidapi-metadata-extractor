"""
Readability metrics + full heading structure (competitive-differentiator
#2): sentence_count/paragraph_count/avg_words_per_sentence from
markdown.compute_readability_metrics(), and h1-h6 heading counts from
metadata.extract_heading_structure() — plus the end-to-end `readability`
field on GET /api/v1/seo-audit.
"""
from unittest import mock

import httpx
from fastapi.testclient import TestClient
from selectolax.parser import HTMLParser

import app.fetcher.client as fetcher_client
from app.cache.l1 import cache as l1_cache
from app.extraction import pipeline
from app.extraction.markdown import compute_readability_metrics
from app.extraction.metadata import extract_heading_structure
from app.main import app

FIXTURE_HTML = b"""<!DOCTYPE html>
<html lang="en"><head><title>Readability Fixture</title>
<meta name="description" content="A fixture page for readability metrics testing purposes here.">
</head><body>
<article>
<h1>Main Heading</h1>
<p>Intro paragraph text.</p>
<h2>Section One</h2>
<p>First section body text.</p>
<h2>Section Two</h2>
<h3>Subsection A</h3>
<h3>Subsection B</h3>
<h3>Subsection C</h3>
</article>
</body></html>"""


async def _fake_ssrf(url):
    return (url, "readability-fixture.ssrfcheck")


def _fixed_transport(body: bytes):
    class FixedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)
    return FixedTransport()


def _hit(path: str):
    l1_cache.clear()
    pipeline._raw_page_cache.clear()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        return client.get(path)


# ----------------------------------------------------------------------------
# Unit-level: compute_readability_metrics()
# ----------------------------------------------------------------------------
def test_compute_readability_metrics_counts_sentences_and_words():
    text = "This is the first sentence. This is the second sentence! Is this the third one?"
    stats = compute_readability_metrics(text)
    assert stats["sentence_count"] == 3
    # 15 words total / 3 sentences = 5.0
    assert stats["avg_words_per_sentence"] == 5.0


def test_compute_readability_metrics_counts_paragraphs_on_blank_line_boundaries():
    text = "First paragraph, one sentence.\n\nSecond paragraph, another sentence.\n\nThird one here."
    stats = compute_readability_metrics(text)
    assert stats["paragraph_count"] == 3


def test_compute_readability_metrics_empty_text_is_all_zero():
    stats = compute_readability_metrics("")
    assert stats == {"sentence_count": 0, "paragraph_count": 0, "avg_words_per_sentence": 0.0}
    stats_ws = compute_readability_metrics("   \n\n  ")
    assert stats_ws["sentence_count"] == 0


def test_compute_readability_metrics_text_with_no_punctuation_is_one_sentence():
    stats = compute_readability_metrics("just some words with no terminal punctuation")
    assert stats["sentence_count"] == 1
    assert stats["avg_words_per_sentence"] == 7.0


# ----------------------------------------------------------------------------
# Unit-level: extract_heading_structure()
# ----------------------------------------------------------------------------
def test_extract_heading_structure_counts_every_level():
    tree = HTMLParser(FIXTURE_HTML)
    structure = extract_heading_structure(tree)
    assert structure == {"h1": 1, "h2": 2, "h3": 3, "h4": 0, "h5": 0, "h6": 0}


def test_extract_heading_structure_all_zero_when_no_headings():
    tree = HTMLParser(b"<html><body><p>No headings here.</p></body></html>")
    structure = extract_heading_structure(tree)
    assert structure == {"h1": 0, "h2": 0, "h3": 0, "h4": 0, "h5": 0, "h6": 0}


# ----------------------------------------------------------------------------
# Route-level: GET /api/v1/seo-audit's `readability` field
# ----------------------------------------------------------------------------
def test_seo_audit_route_returns_readability_with_correct_heading_structure():
    res = _hit("/api/v1/seo-audit?url=https://readability-fixture.ssrfcheck/page")
    assert res.status_code == 200
    data = res.json()
    assert data["readability"] is not None
    assert data["readability"]["heading_structure"] == {"h1": 1, "h2": 2, "h3": 3, "h4": 0, "h5": 0, "h6": 0}
    assert data["readability"]["sentence_count"] > 0
    assert data["readability"]["paragraph_count"] > 0
    assert isinstance(data["readability"]["avg_words_per_sentence"], (int, float))


def test_extract_route_also_returns_readability():
    """FULL_PROFILE (/extract, no fields=) goes through the separate
    _fetch_and_extract_uncached code path — must also carry `readability`."""
    res = _hit("/api/v1/extract?url=https://readability-fixture.ssrfcheck/page")
    assert res.status_code == 200
    data = res.json()
    assert data["readability"]["heading_structure"] == {"h1": 1, "h2": 2, "h3": 3, "h4": 0, "h5": 0, "h6": 0}


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_compute_readability_metrics_counts_sentences_and_words()
        test_compute_readability_metrics_counts_paragraphs_on_blank_line_boundaries()
        test_compute_readability_metrics_empty_text_is_all_zero()
        test_compute_readability_metrics_text_with_no_punctuation_is_one_sentence()
        test_extract_heading_structure_counts_every_level()
        test_extract_heading_structure_all_zero_when_no_headings()
        test_seo_audit_route_returns_readability_with_correct_heading_structure()
        test_extract_route_also_returns_readability()
        print("\n[OK] ALL READABILITY METRICS TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
