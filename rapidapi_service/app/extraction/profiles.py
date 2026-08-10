"""
Extraction profiles (Plan section 12: lazy extraction per endpoint).

Each specialized endpoint (`/contacts`, `/tech-stack`, ...) only needs a
fraction of the full pipeline's output. Rather than every endpoint always
running every extractor (the pre-existing behavior — see pipeline.py's
_fetch_and_extract_uncached, still used unchanged for FULL_PROFILE), a
request declares which atomic "groups" it needs; the pipeline runs only
those, plus their transitive dependencies.

Groups are intentionally coarse (matching what's separable without re-walking
the DOM or re-parsing per Plan §11/§64), not per-field:

- metadata            extract_metadata_fields() (title, OG, twitter, hreflang,
                       viewport, robots, h1s, images, favicon, content_length_bytes)
- links_and_socials    extract_links_and_socials() (social_links, internal/
                       external links, mailto/tel raw lists) — single pass
                       over a[href], never split further
- contacts_emails      extract_emails() — needs links_and_socials (for the
                       mailto list) and the clean-text second parse
- tech                 detect_technologies_detailed() — html_content only,
                       no tree at all
- jsonld               extract_json_ld() + extract_rss_feeds()
- product              extract_product_data() — needs jsonld
- security             extract_security_headers() — resp_headers only, no
                       tree at all (the biggest single win: /security skips
                       HTML parsing entirely)
- seo                  run_seo_audit() — needs metadata + jsonld
- summary_keywords     extract_summary_and_keywords() — needs metadata
                       (description) and the clean-text second parse
- markdown             html_to_markdown_clean() — its own tree (mutates via
                       strip_tags), never shared with the other groups
"""

_GROUP_DEPS = {
    "contacts_emails": frozenset({"links_and_socials"}),
    "product": frozenset({"jsonld"}),
    "seo": frozenset({"metadata", "jsonld"}),
    "summary_keywords": frozenset({"metadata"}),
}


def expand_profile(groups) -> frozenset:
    """Transitively closes `groups` over _GROUP_DEPS."""
    expanded = set(groups)
    changed = True
    while changed:
        changed = False
        for g in list(expanded):
            for dep in _GROUP_DEPS.get(g, ()):
                if dep not in expanded:
                    expanded.add(dep)
                    changed = True
    return frozenset(expanded)


FULL_PROFILE = frozenset({
    "metadata", "links_and_socials", "contacts_emails", "tech",
    "jsonld", "product", "security", "seo", "summary_keywords", "markdown",
})

# Endpoint-facing profiles (imported by app/api/*.py). Pre-expanded so callers
# don't need to think about dependencies.
PROFILE_LINK_PREVIEW = expand_profile({"metadata"})
PROFILE_CONTACTS = expand_profile({"contacts_emails"})
PROFILE_TECH = expand_profile({"tech"})
PROFILE_SCHEMA = expand_profile({"jsonld"})
PROFILE_SECURITY = expand_profile({"security"})
PROFILE_MARKDOWN = expand_profile({"markdown", "summary_keywords"})
PROFILE_SEO = expand_profile({"seo"})
PROFILE_LINKS = expand_profile({"links_and_socials"})

# Groups that require an HTMLParser tree at all (security/tech operate on
# resp_headers / raw html_content directly — no parse needed).
_TREE_GROUPS = frozenset({"metadata", "links_and_socials", "jsonld", "markdown"})
# Groups that need the a[href] node list specifically.
_A_NODES_GROUPS = frozenset({"metadata", "links_and_socials"})
# Groups that need the stripped-tags clean-text second parse.
_CLEAN_TEXT_GROUPS = frozenset({"contacts_emails", "summary_keywords"})


def needs_tree(profile: frozenset) -> bool:
    return bool(profile & _TREE_GROUPS)


def needs_a_nodes(profile: frozenset) -> bool:
    return bool(profile & _A_NODES_GROUPS)


def needs_clean_text(profile: frozenset) -> bool:
    return bool(profile & _CLEAN_TEXT_GROUPS)
