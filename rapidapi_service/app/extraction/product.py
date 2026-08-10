"""
Product structured-data extraction from JSON-LD (Plan section 22), now also
cross-checked against two other independent structured sources: OpenGraph's
product extension (`product:price:amount` etc.) and schema.org Microdata
(`itemprop="price"` etc.) — both real, commonly-used alternative encodings
of the same data, not text/DOM heuristics, so they carry similar reliability
to JSON-LD without the false-positive risk a freeform "scan for $ signs"
approach would have.

Traverses top-level schemas AND schemas nested under `@graph` or a top-level
array (Plan §21 traversal, see app.extraction.jsonld.iter_schema_nodes) — a
real, common pattern the original name-only top-level scan missed entirely,
silently returning product_data=None for any page using it.

product_data is an existing but loosely-typed API field (Dict[str, Any] /
Optional), so adding new keys is additive and doesn't change its type for
existing v1 clients; the original 7 keys (name, price, currency,
availability, brand, rating, review_count) keep their exact original
semantics and values — resolve_product_field() picks a single winning value
per field (JSON-LD > Microdata > OpenGraph, see app.extraction.quality) the
exact same way a single JSON-LD-only lookup used to, so product_data's
VALUES are unchanged when sources agree or only one source has data. The
new `field_sources` return value (not itself part of product_data) is what
feeds the quality/conflict-detection layer.
"""
from typing import Any, Dict, List, Optional, Tuple

from app.extraction.jsonld import iter_schema_nodes
from app.extraction.quality import resolve_product_field

_OG_PRODUCT_KEYS = {
    "product:price:amount": "price",
    "og:price:amount": "price",
    "product:price:currency": "currency",
    "og:price:currency": "currency",
    "product:availability": "availability",
    "product:brand": "brand",
}

_MICRODATA_ITEMPROPS = ("price", "priceCurrency", "availability", "brand", "name")


def _first_str(value) -> Optional[str]:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        return value.get('name') or value.get('@id')
    if value is None:
        return None
    return str(value)


def _image_url(value) -> Optional[str]:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        return value.get('url') or value.get('contentUrl')
    if isinstance(value, str):
        return value
    return None


def _extract_json_ld_product_fields(json_ld_schemas: List[Any]) -> Optional[Dict[str, Any]]:
    """Returns the full product_data dict from the first Product-typed JSON-LD
    node found, or None — this is the original extract_product_data() body,
    kept as-is since it's still the primary/richest source."""
    for schema in iter_schema_nodes(json_ld_schemas):
        s_type = schema.get('@type', '')
        if isinstance(s_type, list):
            s_type = s_type[0] if s_type else ''
        if str(s_type).strip().lower() != 'product':
            continue

        product_data: Dict[str, Any] = {
            'name': schema.get('name'),
            'price': None,
            'currency': None,
            'availability': None,
            'brand': None,
            'rating': None,
            'review_count': None,
            'description': schema.get('description'),
            'image': _image_url(schema.get('image')),
            'sku': schema.get('sku'),
            'mpn': schema.get('mpn'),
            'gtin': schema.get('gtin') or schema.get('gtin13') or schema.get('gtin12') or schema.get('gtin8'),
            'isbn': schema.get('isbn'),
            'seller': None,
            'condition': None,
            'min_price': None,
            'max_price': None,
            'price_valid_until': None,
            'product_url': schema.get('url') or schema.get('@id'),
        }

        offers = schema.get('offers') or schema.get('Offers')
        if isinstance(offers, list):
            offers = offers[0] if offers else None
        if isinstance(offers, dict):
            product_data['price'] = offers.get('price') or offers.get('lowPrice')
            product_data['currency'] = offers.get('priceCurrency')
            avail = offers.get('availability', '') or ''
            product_data['availability'] = avail.split('/')[-1] if '/' in avail else avail or None
            product_data['min_price'] = offers.get('lowPrice')
            product_data['max_price'] = offers.get('highPrice')
            product_data['price_valid_until'] = offers.get('priceValidUntil')

            seller = offers.get('seller')
            if isinstance(seller, dict):
                product_data['seller'] = seller.get('name')
            elif isinstance(seller, str):
                product_data['seller'] = seller

            condition = offers.get('itemCondition')
            if isinstance(condition, str):
                product_data['condition'] = condition.rsplit('/', 1)[-1] or condition

        brand = schema.get('brand')
        if isinstance(brand, dict):
            product_data['brand'] = brand.get('name')
        elif isinstance(brand, str):
            product_data['brand'] = brand

        agg = schema.get('aggregateRating')
        if isinstance(agg, dict):
            product_data['rating'] = agg.get('ratingValue')
            product_data['review_count'] = agg.get('reviewCount')

        return product_data

    return None


def extract_opengraph_product_fields(tree) -> Dict[str, Optional[str]]:
    """OpenGraph's e-commerce product extension — a real, widely-used tag
    set (Shopify, WooCommerce, and most OG-aware storefronts emit these),
    distinct from JSON-LD/Microdata."""
    fields: Dict[str, Optional[str]] = {"price": None, "currency": None, "availability": None, "brand": None}
    for m in tree.css('meta[property]'):
        prop = (m.attributes.get('property') or '').lower()
        key = _OG_PRODUCT_KEYS.get(prop)
        if key and fields.get(key) is None:
            content = m.attributes.get('content')
            if content:
                fields[key] = content.strip()
    return fields


def extract_microdata_product_fields(tree) -> Dict[str, Optional[str]]:
    """schema.org Microdata (itemprop=...) — the pre-JSON-LD structured-data
    encoding, still common on older/simpler storefronts (frequently present
    specifically on sites that DON'T have JSON-LD)."""
    fields: Dict[str, Optional[str]] = {"price": None, "currency": None, "availability": None, "brand": None, "name": None}
    for prop in _MICRODATA_ITEMPROPS:
        node = tree.css_first(f'[itemprop="{prop}"]')
        if node is None:
            continue
        value = node.attributes.get('content') or node.text()
        if value:
            value = value.strip()
            if prop == "priceCurrency":
                fields["currency"] = value
            elif prop in fields:
                fields[prop] = value
    return fields


def extract_product_data(tree, json_ld_schemas: List[Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Dict[str, Optional[Any]]]]:
    """Returns (product_data, field_sources). field_sources maps each
    cross-checked field (price/currency/availability/brand) to the raw value
    each source independently found (None if that source didn't have it) —
    consumed by app.extraction.quality.detect_product_conflicts(), not part
    of the public product_data shape itself."""
    json_ld_product = _extract_json_ld_product_fields(json_ld_schemas)
    og_fields = extract_opengraph_product_fields(tree)
    microdata_fields = extract_microdata_product_fields(tree)

    field_sources: Dict[str, Dict[str, Optional[Any]]] = {
        field: {
            "json_ld": (json_ld_product or {}).get(field),
            "microdata": microdata_fields.get(field),
            "opengraph": og_fields.get(field),
        }
        for field in ("price", "currency", "availability", "brand")
    }

    if json_ld_product is not None:
        # JSON-LD already found a full Product node — still resolve the 4
        # cross-checked fields through the same priority function as the
        # no-JSON-LD case, so a JSON-LD offer missing e.g. `brand` can still
        # be filled in from OpenGraph/Microdata rather than staying None.
        for field in field_sources:
            resolved = resolve_product_field(field_sources[field])
            if resolved is not None:
                json_ld_product[field] = resolved
        return json_ld_product, field_sources

    # No JSON-LD Product node at all — build a minimal product_data purely
    # from OpenGraph/Microdata if either found anything, instead of giving
    # up (Plan §22 priority: JSON-LD -> OpenGraph -> meta -> HTML heuristics).
    resolved = {field: resolve_product_field(field_sources[field]) for field in field_sources}
    if all(v is None for v in resolved.values()) and microdata_fields.get("name") is None:
        return None, field_sources

    product_data = {
        'name': microdata_fields.get("name"),
        'price': resolved["price"],
        'currency': resolved["currency"],
        'availability': resolved["availability"],
        'brand': resolved["brand"],
        'rating': None,
        'review_count': None,
        'description': None,
        'image': None,
        'sku': None,
        'mpn': None,
        'gtin': None,
        'isbn': None,
        'seller': None,
        'condition': None,
        'min_price': None,
        'max_price': None,
        'price_valid_until': None,
        'product_url': None,
    }
    return product_data, field_sources
