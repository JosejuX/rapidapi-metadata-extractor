"""
Extraction quality assessment — applies the same "confidence, not
certainty" philosophy already used for tech-stack detection (Plan §20) to
structured product data, plus an overall response-level quality summary.

Two independent pieces:

1. Multi-source product-field resolution + conflict detection. When the
   same field (price/currency/availability/brand) is found in more than one
   independent STRUCTURED source (JSON-LD, OpenGraph's product extension,
   schema.org Microdata — deliberately not freeform DOM text-scanning,
   which would be false-positive-prone) and they disagree, that's a real,
   actionable signal worth surfacing rather than silently picking one value.
   Priority when choosing which value ends up in product_data: JSON-LD >
   Microdata > OpenGraph — JSON-LD and Microdata are both direct schema.org
   serializations (Microdata ranked second: it's often present specifically
   on sites that DON'T have JSON-LD, i.e. it's frequently the *only*
   structured source, not a weaker fallback), OpenGraph's product extension
   is the least formally specified of the three.

2. `quality.score`: same explicitly-a-heuristic framing as
   seo_score_percentage/security_score_percentage (Plan §23/§24) — a
   composite signal, not a certified accuracy measurement. Never claims
   "94% of this data is correct"; claims "several independent signals
   suggest this response is trustworthy to this degree".
"""
from typing import Any, Dict, List, Optional

_SOURCE_PRIORITY = ("json_ld", "microdata", "opengraph")

# Same confidence tiers as tech-stack detection (Plan §20): more independent
# agreeing signals -> higher confidence. Disagreement is worse than a single
# unconfirmed source — it's active evidence the value is uncertain, not just
# unverified.
_CONFIDENCE_SINGLE_SOURCE = 0.75
_CONFIDENCE_SOURCES_AGREE = 0.98
_CONFIDENCE_SOURCES_CONFLICT = 0.5


def resolve_product_field(field_sources: Dict[str, Optional[Any]]) -> Optional[Any]:
    for source in _SOURCE_PRIORITY:
        value = field_sources.get(source)
        if value is not None:
            return value
    return None


def _normalize_for_compare(value: Any):
    """Numeric-looking strings/numbers compare by value (avoids a false
    SOURCE_CONFLICT for "39.99" vs 39.99 vs "39.990"); everything else
    compares case/whitespace-insensitively."""
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if isinstance(value, str):
        try:
            return round(float(value), 2)
        except ValueError:
            return value.strip().lower()
    return value


def product_field_confidence(field_sources: Dict[str, Dict[str, Optional[Any]]]) -> Dict[str, Dict[str, Any]]:
    """Per-field confidence/source for the resolved product_data values —
    additive detail alongside product_data, not a replacement for it (Plan
    §97: existing fields keep their exact type)."""
    result: Dict[str, Dict[str, Any]] = {}
    for field, sources in field_sources.items():
        present = {src: val for src, val in sources.items() if val is not None}
        if not present:
            continue
        distinct = {_normalize_for_compare(v) for v in present.values()}
        chosen_source = next((s for s in _SOURCE_PRIORITY if s in present), None)
        if len(present) == 1:
            confidence = _CONFIDENCE_SINGLE_SOURCE
        elif len(distinct) == 1:
            confidence = _CONFIDENCE_SOURCES_AGREE
        else:
            confidence = _CONFIDENCE_SOURCES_CONFLICT
        result[field] = {
            "value": resolve_product_field(sources),
            "confidence": confidence,
            "source": chosen_source,
            "agreement": sorted(present.keys()),
        }
    return result


def detect_product_conflicts(field_sources: Dict[str, Dict[str, Optional[Any]]]) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    for field, sources in field_sources.items():
        present = {src: val for src, val in sources.items() if val is not None}
        distinct = {_normalize_for_compare(v) for v in present.values()}
        if len(distinct) > 1:
            chosen_source = next((s for s in _SOURCE_PRIORITY if s in present), None)
            warnings.append({
                "field": f"product.{field}",
                "type": "SOURCE_CONFLICT",
                "values": present,
                "chosen_source": chosen_source,
                "chosen_value": present.get(chosen_source),
            })
    return warnings


def compute_quality(
    *,
    has_title: bool,
    has_description: bool,
    has_json_ld: bool,
    has_opengraph_product: bool,
    has_microdata_product: bool,
    content_truncated: bool,
    bot_protection_detected: bool,
    product_warnings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    sources_used: List[str] = []
    if has_json_ld:
        sources_used.append("json_ld")
    if has_microdata_product:
        sources_used.append("microdata")
    if has_opengraph_product:
        sources_used.append("opengraph")
    if has_title or has_description:
        sources_used.append("meta")

    warnings: List[Dict[str, Any]] = list(product_warnings)
    if bot_protection_detected:
        warnings.append({
            "field": None,
            "type": "BOT_PROTECTION_DETECTED",
        })
    if content_truncated:
        warnings.append({
            "field": None,
            "type": "CONTENT_TRUNCATED",
        })
    if not has_title:
        warnings.append({
            "field": "metadata.title",
            "type": "MISSING_FIELD",
        })
    if not has_description:
        warnings.append({
            "field": "metadata.description",
            "type": "MISSING_FIELD",
        })

    score = 1.0
    if bot_protection_detected:
        score -= 0.5
    if content_truncated:
        score -= 0.15
    if not has_title:
        score -= 0.1
    if not has_description:
        score -= 0.1
    score -= min(0.3, 0.1 * len(product_warnings))
    score = max(0.0, min(1.0, round(score, 2)))

    return {
        "score": score,
        "rendered": False,
        "sources_used": sources_used,
        "warnings": warnings,
    }
