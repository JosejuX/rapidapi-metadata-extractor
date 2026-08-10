"""
Extraction quality layer (per-field confidence/source) and multi-source
conflict detection for product data — ChatGPT review items #2/#3. Product
data is now cross-checked against three independent STRUCTURED sources
(JSON-LD, OpenGraph's product extension, schema.org Microdata), not just
JSON-LD alone, so real disagreements between sources can be detected instead
of silently trusting whichever one happened to be read first.
"""
import json

from selectolax.parser import HTMLParser

from app.extraction.jsonld import extract_json_ld
from app.extraction.product import (
    extract_microdata_product_fields,
    extract_opengraph_product_fields,
    extract_product_data,
)
from app.extraction.quality import (
    compute_quality,
    detect_product_conflicts,
    product_field_confidence,
    resolve_product_field,
)


def _tree(head_extra: str = "", body_extra: str = "") -> HTMLParser:
    html = f"<html><head>{head_extra}</head><body>{body_extra}</body></html>"
    return HTMLParser(html)


# --- OpenGraph / Microdata extraction ---------------------------------------

def test_opengraph_product_fields_are_read():
    tree = _tree(head_extra='''
        <meta property="product:price:amount" content="19.99">
        <meta property="product:price:currency" content="USD">
        <meta property="product:brand" content="Acme">
    ''')
    fields = extract_opengraph_product_fields(tree)
    assert fields["price"] == "19.99"
    assert fields["currency"] == "USD"
    assert fields["brand"] == "Acme"


def test_microdata_product_fields_are_read():
    tree = _tree(body_extra='''
        <span itemprop="price" content="24.99"></span>
        <span itemprop="priceCurrency">EUR</span>
        <span itemprop="brand">Acme</span>
    ''')
    fields = extract_microdata_product_fields(tree)
    assert fields["price"] == "24.99"
    assert fields["currency"] == "EUR"
    assert fields["brand"] == "Acme"


def test_no_structured_data_at_all_returns_none_product():
    tree = _tree(body_extra="<p>Just a plain page, no product markup anywhere.</p>")
    product, sources = extract_product_data(tree, [])
    assert product is None
    assert all(v is None for s in sources.values() for v in s.values())


# --- Field resolution priority: JSON-LD > Microdata > OpenGraph ------------

def test_resolve_prefers_json_ld_over_others():
    assert resolve_product_field({"json_ld": "A", "microdata": "B", "opengraph": "C"}) == "A"


def test_resolve_falls_back_to_microdata_then_opengraph():
    assert resolve_product_field({"json_ld": None, "microdata": "B", "opengraph": "C"}) == "B"
    assert resolve_product_field({"json_ld": None, "microdata": None, "opengraph": "C"}) == "C"


def test_opengraph_only_product_is_still_extracted_without_json_ld():
    tree = _tree(head_extra='''
        <meta property="product:price:amount" content="15.00">
        <meta property="product:price:currency" content="USD">
    ''')
    product, sources = extract_product_data(tree, [])
    assert product is not None
    assert product["price"] == "15.00"
    assert product["currency"] == "USD"


# --- Conflict detection ------------------------------------------------------

def test_agreeing_sources_produce_no_conflict_and_high_confidence():
    sources = {"price": {"json_ld": "39.99", "microdata": "39.99", "opengraph": None}}
    assert detect_product_conflicts(sources) == []
    confidence = product_field_confidence(sources)
    assert confidence["price"]["confidence"] == 0.98
    assert confidence["price"]["value"] == "39.99"


def test_disagreeing_sources_produce_a_conflict_warning_and_lower_confidence():
    sources = {"price": {"json_ld": "39.99", "microdata": "39.99", "opengraph": "29.99"}}
    warnings = detect_product_conflicts(sources)
    assert len(warnings) == 1
    assert warnings[0]["field"] == "product.price"
    assert warnings[0]["type"] == "SOURCE_CONFLICT"
    assert warnings[0]["chosen_source"] == "json_ld"
    assert warnings[0]["chosen_value"] == "39.99"

    confidence = product_field_confidence(sources)
    assert confidence["price"]["confidence"] == 0.5


def test_numeric_string_vs_float_does_not_falsely_conflict():
    # "39.99" (string, as JSON-LD often encodes prices) vs 39.99 (float) must
    # compare equal — not a false SOURCE_CONFLICT from type mismatch alone.
    sources = {"price": {"json_ld": "39.99", "microdata": 39.99, "opengraph": None}}
    assert detect_product_conflicts(sources) == []


def test_single_source_field_has_medium_confidence_and_no_conflict():
    sources = {"brand": {"json_ld": "Acme", "microdata": None, "opengraph": None}}
    assert detect_product_conflicts(sources) == []
    assert product_field_confidence(sources)["brand"]["confidence"] == 0.75


def test_field_with_no_sources_is_omitted_from_confidence_map():
    sources = {"brand": {"json_ld": None, "microdata": None, "opengraph": None}}
    assert product_field_confidence(sources) == {}


# --- Overall quality score ---------------------------------------------------

def test_clean_response_scores_high_with_no_warnings():
    quality = compute_quality(
        has_title=True, has_description=True, has_json_ld=True,
        has_opengraph_product=False, has_microdata_product=False,
        content_truncated=False, bot_protection_detected=False, product_warnings=[],
    )
    assert quality["score"] == 1.0
    assert quality["warnings"] == []
    assert quality["rendered"] is False
    assert "json_ld" in quality["sources_used"]


def test_bot_protection_tanks_the_score_and_adds_a_warning():
    quality = compute_quality(
        has_title=True, has_description=True, has_json_ld=False,
        has_opengraph_product=False, has_microdata_product=False,
        content_truncated=False, bot_protection_detected=True, product_warnings=[],
    )
    assert quality["score"] <= 0.5
    assert any(w["type"] == "BOT_PROTECTION_DETECTED" for w in quality["warnings"])


def test_missing_title_and_description_lower_score_and_warn():
    quality = compute_quality(
        has_title=False, has_description=False, has_json_ld=False,
        has_opengraph_product=False, has_microdata_product=False,
        content_truncated=False, bot_protection_detected=False, product_warnings=[],
    )
    assert quality["score"] == 0.8
    assert len(quality["warnings"]) == 2
    assert all(w["type"] == "MISSING_FIELD" for w in quality["warnings"])
    assert {w["field"] for w in quality["warnings"]} == {"metadata.title", "metadata.description"}


def test_score_never_goes_below_zero():
    quality = compute_quality(
        has_title=False, has_description=False, has_json_ld=False,
        has_opengraph_product=False, has_microdata_product=False,
        content_truncated=True, bot_protection_detected=True,
        product_warnings=[{"field": f"product.f{i}", "type": "SOURCE_CONFLICT"} for i in range(10)],
    )
    assert quality["score"] == 0.0


# --- End-to-end through the real /api/v1/extract route ----------------------

from unittest import mock

import httpx
from fastapi.testclient import TestClient

import app.fetcher.client as fetcher_client
from app.cache.l1 import cache as l1_cache
from app.main import app


async def _fake_ssrf(url):
    return (url, "quality-fixture.ssrfcheck")


def test_three_way_price_conflict_end_to_end():
    body = b'''<html><head><title>Quality Fixture</title>
<meta name="description" content="A fixture page for end-to-end quality/conflict testing today.">
<meta property="product:price:amount" content="29.99">
<meta property="product:price:currency" content="EUR">
<span itemprop="price" content="39.99"></span>
<span itemprop="priceCurrency">EUR</span>
<script type="application/ld+json">{"@context": "https://schema.org", "@type": "Product", "name": "Widget", "offers": {"price": "39.99", "priceCurrency": "EUR", "availability": "https://schema.org/InStock"}}</script>
</head><body>x</body></html>'''

    l1_cache.clear()
    fetcher_client.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, headers={"content-type": "text/html"}, content=body))
    )
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        res = client.get("/api/v1/extract?url=https://quality-fixture.ssrfcheck/page")

    assert res.status_code == 200
    data = res.json()

    # product_data itself: unchanged shape/type, JSON-LD wins the conflict.
    assert data["product_data"]["price"] == "39.99"

    # New additive fields carry the full picture.
    price_confidence = data["product_field_confidence"]["price"]
    assert price_confidence["confidence"] == 0.5
    assert set(price_confidence["agreement"]) == {"json_ld", "microdata", "opengraph"}

    conflicts = [w for w in data["quality"]["warnings"] if w["type"] == "SOURCE_CONFLICT"]
    assert len(conflicts) == 1
    assert conflicts[0]["field"] == "product.price"
    assert conflicts[0]["values"]["opengraph"] == "29.99"
    assert data["quality"]["score"] < 1.0
