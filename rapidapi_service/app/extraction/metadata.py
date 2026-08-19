"""SEO/OpenGraph metadata extraction from an already-parsed HTML tree (Plan section 15)."""
import re
from typing import Any, Dict, Optional

from selectolax.parser import HTMLParser

from app.core.urls import safe_urljoin, safe_urlparse

FAVICON_REL_REGEX = re.compile(r'^(shortcut )?icon$|^apple-touch-icon$', re.I)

_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")


def extract_heading_structure(tree: HTMLParser) -> Dict[str, int]:
    """Full h1-h6 heading counts (competitive-differentiator #2), alongside
    the h1-specific extraction in extract_metadata_fields() below. Kept as
    its own standalone function (rather than folded into that dict) so
    pipeline.py can call it against whichever tree is at hand — the shared
    `tree` when the "metadata"/"seo" groups already parsed one, or a
    "markdown" group's own md_tree, queried before html_to_markdown_clean()
    mutates it — and assemble it into ReadabilityMetrics.heading_structure
    without it also leaking into the Metadata response sub-object."""
    return {tag: len(tree.css(tag)) for tag in _HEADING_TAGS}


def extract_metadata_fields(tree: HTMLParser, final_url: str, resp_headers: Dict[str, str], links_count: int) -> Dict[str, Any]:
    title_node = tree.css_first('title')
    title = title_node.text().strip() if (title_node and title_node.text()) else None

    meta_tags = {}
    for m in tree.css('meta'):
        k = m.attributes.get('property') or m.attributes.get('name')
        v = m.attributes.get('content')
        if k and v:
            meta_tags[k.lower()] = v.strip()

    def get_meta(k: str) -> Optional[str]:
        return meta_tags.get(k.lower())

    description = get_meta('description') or get_meta('og:description') or get_meta('twitter:description')
    og_image = get_meta('og:image') or get_meta('twitter:image')
    og_type = get_meta('og:type')
    og_url = get_meta('og:url')
    og_video = get_meta('og:video') or get_meta('og:video:url')
    keywords = get_meta('keywords')
    author = get_meta('author') or get_meta('article:author')
    site_name = get_meta('og:site_name')
    theme_color = get_meta('theme-color')
    robots_directive = get_meta('robots')

    og_locale_alternate = [
        m.attributes['content']
        for m in tree.css('meta[property="og:locale:alternate"]')
        if m.attributes.get('content')
    ]

    html_node = tree.css_first('html')
    language = html_node.attributes.get('lang') if html_node else None
    if not language:
        og_locale = get_meta('og:locale')
        if og_locale:
            language = og_locale.split('_')[0]

    canonical_url = None
    canonical_node = tree.css_first('link[rel="canonical"]')
    if canonical_node and canonical_node.attributes.get('href'):
        canonical_url = safe_urljoin(final_url, canonical_node.attributes.get('href'))

    hreflang_tags = []
    for link in tree.css('link[hreflang]'):
        lang = link.attributes.get('hreflang')
        href = link.attributes.get('href')
        if lang and href and len(hreflang_tags) < 50:
            joined = safe_urljoin(final_url, href)
            if joined is not None:
                hreflang_tags.append({'lang': lang, 'url': joined})

    favicon = None
    for link in tree.css('link[rel]'):
        rel = link.attributes.get('rel', '') or ''
        if FAVICON_REL_REGEX.search(rel):
            href = link.attributes.get('href')
            if href:
                favicon = safe_urljoin(final_url, href)
                if favicon is not None:
                    break
    if not favicon:
        favicon = safe_urljoin(final_url, "/favicon.ico")

    h1_tags = [h.text().strip() for h in tree.css('h1') if (h and h.text() and h.text().strip())]
    img_nodes = tree.css('img')
    images_count = len(img_nodes)
    images_missing_alt_count = sum(1 for img in img_nodes if not img.attributes.get('alt'))

    # Plan §23 additions — feed the expanded SEO audit checks (viewport,
    # Twitter Card, true H1 count for "multiple H1" detection).
    viewport = get_meta('viewport')
    twitter_card = get_meta('twitter:card')
    h1_count = len(h1_tags)

    final_domain = safe_urlparse(final_url).netloc.lower()
    favicon_high_res = f"https://www.google.com/s2/favicons?domain={final_domain}&sz=128" if final_domain else None

    video_embed_code = None
    if og_video:
        video_embed_code = f'<iframe src="{og_video}" width="100%" height="360" frameborder="0" allowfullscreen></iframe>'
    elif "youtube.com/watch" in final_url or "youtu.be/" in final_url:
        yt_match = re.search(r'(?:v=|\/)([a-zA-Z0-9_-]{11})', final_url)
        if yt_match:
            video_embed_code = f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{yt_match.group(1)}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>'
    elif "vimeo.com/" in final_url:
        vm_match = re.search(r'vimeo\.com\/(\d+)', final_url)
        if vm_match:
            video_embed_code = f'<iframe src="https://player.vimeo.com/video/{vm_match.group(1)}" width="640" height="360" frameborder="0" allowfullscreen></iframe>'

    ssl_status = {
        "enabled": final_url.startswith("https://"),
        "hsts_active": resp_headers.get("strict-transport-security") is not None,
        "protocol": "HTTPS" if final_url.startswith("https://") else "HTTP"
    }

    return {
        "title": title,
        "description": description,
        "og_image": og_image,
        "og_type": og_type,
        "og_url": og_url,
        "og_video": og_video,
        "og_locale_alternate": og_locale_alternate,
        "keywords": keywords,
        "author": author,
        "site_name": site_name,
        "language": language,
        "favicon": favicon,
        "favicon_high_res": favicon_high_res,
        "canonical_url": canonical_url,
        "theme_color": theme_color,
        "robots": robots_directive,
        "hreflang_tags": hreflang_tags,
        "h1_tags": h1_tags[:5],
        "h1_count": h1_count,
        "images_count": images_count,
        "images_missing_alt_count": images_missing_alt_count,
        "links_count": links_count,
        "video_embed_code": video_embed_code,
        "ssl_status": ssl_status,
        "viewport": viewport,
        "twitter_card": twitter_card,
        # merged in by the pipeline after markdown/NLP extraction runs:
        "summary_snippet": None,
        "top_keywords": [],
        # merged in by the pipeline (needs raw_bytes length, computed earlier):
        "content_length_bytes": None,
    }
