"""JSON-LD structured-data and RSS/Atom feed discovery (Plan section 21)."""
import json
from typing import Any, Dict, Iterator, List

from selectolax.parser import HTMLParser

from app.core.urls import safe_urljoin

_MAX_GRAPH_DEPTH = 4  # Plan §21.1: bound nesting so a malicious/malformed
                       # JSON-LD payload can't make traversal unbounded.


def extract_json_ld(tree: HTMLParser) -> List[Any]:
    json_ld_schemas = []
    for script in tree.css('script[type="application/ld+json"]'):
        try:
            stxt = script.text()
            if stxt:
                t = stxt.strip()
                if t:
                    parsed_json = json.loads(t)
                    json_ld_schemas.append(parsed_json)
        except Exception:
            pass
    return json_ld_schemas


def iter_schema_nodes(json_ld_schemas: List[Any]) -> Iterator[Dict[str, Any]]:
    """
    Yields every dict node found across the raw json_ld_schemas list,
    unwrapping the two patterns real sites actually use that a naive
    top-level-only scan misses (Plan §21): a top-level JSON array of
    schemas, and an object using `@graph` to bundle multiple entities
    under one shared @context. Does NOT mutate or replace json_ld_schemas
    itself — that field stays exactly as parsed for API backward
    compatibility; this is purely an internal traversal used to find
    Product/etc nodes wherever they actually live.
    """
    def _walk(node: Any, depth: int) -> Iterator[Dict[str, Any]]:
        if depth > _MAX_GRAPH_DEPTH:
            return
        if isinstance(node, dict):
            yield node
            graph = node.get('@graph')
            if isinstance(graph, list):
                for item in graph:
                    yield from _walk(item, depth + 1)
        elif isinstance(node, list):
            for item in node:
                yield from _walk(item, depth + 1)

    for schema in json_ld_schemas:
        yield from _walk(schema, 0)


def extract_rss_feeds(tree: HTMLParser, final_url: str) -> List[str]:
    rss_feeds = []
    for link in tree.css('link[type]'):
        raw_t = link.attributes.get('type')
        t_attr = raw_t.lower() if raw_t else ""
        if 'rss' in t_attr or 'atom' in t_attr or 'xml' in t_attr:
            href = link.attributes.get('href')
            if href:
                joined = safe_urljoin(final_url, href)
                if joined is not None:
                    rss_feeds.append(joined)
    return rss_feeds
