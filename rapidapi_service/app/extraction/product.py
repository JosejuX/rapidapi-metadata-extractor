"""
Product structured-data extraction from JSON-LD (Plan section 22).

Traverses top-level schemas AND schemas nested under `@graph` or a top-level
array (Plan §21 traversal, see app.extraction.jsonld.iter_schema_nodes) — a
real, common pattern the original name-only top-level scan missed entirely,
silently returning product_data=None for any page using it.

product_data is an existing but loosely-typed API field (Dict[str, Any] /
Optional), so adding new keys is additive and doesn't change its type for
existing v1 clients; the original 7 keys (name, price, currency,
availability, brand, rating, review_count) keep their exact original
semantics and values.
"""
from typing import Any, Dict, List, Optional

from app.extraction.jsonld import iter_schema_nodes


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


def extract_product_data(json_ld_schemas: List[Any]) -> Optional[Dict[str, Any]]:
    for schema in iter_schema_nodes(json_ld_schemas):
        s_type = schema.get('@type', '')
        if isinstance(s_type, list):
            s_type = s_type[0] if s_type else ''
        if str(s_type).strip().lower() != 'product':
            continue

        product_data = {
            # Original fields — unchanged semantics for backward compatibility.
            'name': schema.get('name'),
            'price': None,
            'currency': None,
            'availability': None,
            'brand': None,
            'rating': None,
            'review_count': None,
            # Plan §22 additions.
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
                # e.g. "https://schema.org/NewCondition" -> "NewCondition"
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
