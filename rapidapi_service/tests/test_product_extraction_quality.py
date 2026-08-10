"""Phase 5: JSON-LD @graph traversal + expanded product fields (Plan §21/§22)."""
import json

from selectolax.parser import HTMLParser

from app.extraction.jsonld import extract_json_ld, iter_schema_nodes
from app.extraction.product import extract_product_data


def _tree_with_jsonld(payload) -> HTMLParser:
    html = f'<html><head><script type="application/ld+json">{json.dumps(payload)}</script></head><body></body></html>'
    return HTMLParser(html)


def test_top_level_product_still_works():
    print("\n--- Product: plain top-level Product schema (original behavior) ---")
    payload = {
        "@context": "https://schema.org", "@type": "Product", "name": "Widget",
        "offers": {"price": "19.99", "priceCurrency": "USD", "availability": "https://schema.org/InStock"},
        "brand": {"name": "Acme"},
        "aggregateRating": {"ratingValue": "4.5", "reviewCount": "120"},
    }
    tree = _tree_with_jsonld(payload)
    schemas = extract_json_ld(tree)
    product, _ = extract_product_data(tree, schemas)
    assert product["name"] == "Widget"
    assert product["price"] == "19.99"
    assert product["brand"] == "Acme"
    assert product["rating"] == "4.5"
    print("  [OK] top-level Product extracted correctly")


def test_product_inside_at_graph_is_now_found():
    print("\n--- Product: nested inside @graph (previously invisible, now found) ---")
    payload = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebPage", "name": "Store Page"},
            {
                "@type": "Product", "name": "Graph Widget", "sku": "GW-001", "mpn": "MPN123",
                "description": "A widget found via @graph.",
                "image": ["https://example.com/w.jpg"],
                "offers": {
                    "price": "29.99", "priceCurrency": "EUR", "availability": "https://schema.org/InStock",
                    "lowPrice": "24.99", "highPrice": "34.99", "priceValidUntil": "2026-12-31",
                    "seller": {"name": "GraphSeller"}, "itemCondition": "https://schema.org/NewCondition",
                },
            },
        ],
    }
    tree = _tree_with_jsonld(payload)
    schemas = extract_json_ld(tree)
    # sanity: the raw json_ld_schemas field is untouched (still just the raw parsed object)
    assert schemas == [payload], "raw json_ld_schemas must stay exactly as parsed (API backward compat)"

    product, _ = extract_product_data(tree, schemas)
    assert product is not None, "Product nested under @graph should now be found"
    assert product["name"] == "Graph Widget"
    assert product["sku"] == "GW-001"
    assert product["mpn"] == "MPN123"
    assert product["description"] == "A widget found via @graph."
    assert product["image"] == "https://example.com/w.jpg"
    assert product["price"] == "29.99"
    assert product["currency"] == "EUR"
    assert product["min_price"] == "24.99"
    assert product["max_price"] == "34.99"
    assert product["price_valid_until"] == "2026-12-31"
    assert product["seller"] == "GraphSeller"
    assert product["condition"] == "NewCondition"
    print("  [OK] Product inside @graph found with all expanded fields populated")


def test_product_inside_top_level_array():
    print("\n--- Product: top-level JSON array of schemas ---")
    payload = [
        {"@context": "https://schema.org", "@type": "Organization", "name": "Acme Corp"},
        {"@context": "https://schema.org", "@type": "Product", "name": "Array Widget"},
    ]
    html = f'<html><head><script type="application/ld+json">{json.dumps(payload)}</script></head><body></body></html>'
    tree = HTMLParser(html)
    schemas = extract_json_ld(tree)
    product, _ = extract_product_data(tree, schemas)
    assert product is not None
    assert product["name"] == "Array Widget"
    print("  [OK] Product found inside a top-level JSON-LD array")


def test_non_dict_schema_does_not_crash():
    """Regression: a JSON-LD script containing just a plain string/number
    must not crash product extraction (Plan §54: malformed JSON-LD must not
    break the request)."""
    print("\n--- Product: malformed/non-dict JSON-LD does not crash ---")
    schemas = ["just a string", 42, None, ["nested", "list"]]
    tree = HTMLParser("<html><head></head><body></body></html>")
    product, _ = extract_product_data(tree, schemas)
    assert product is None
    print("  [OK] non-dict JSON-LD entries handled gracefully, no crash")


def test_iter_schema_nodes_depth_bound():
    print("\n--- iter_schema_nodes: deeply nested @graph does not recurse unbounded ---")
    node = {"@type": "Product", "name": "Deep"}
    for _ in range(10):
        node = {"@graph": [node]}
    nodes = list(iter_schema_nodes([node]))
    assert len(nodes) < 10, "traversal should be depth-bounded, not unbounded"
    print(f"  [OK] traversal stopped early ({len(nodes)} nodes visited), no runaway recursion")


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_top_level_product_still_works()
        test_product_inside_at_graph_is_now_found()
        test_product_inside_top_level_array()
        test_non_dict_schema_does_not_crash()
        test_iter_schema_nodes_depth_bound()
        print("\n[OK] ALL PRODUCT/JSON-LD QUALITY TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
