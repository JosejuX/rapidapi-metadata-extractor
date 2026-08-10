"""
Single-pass link classification + social/email/phone-from-href collection
(Plan section 29): one loop over all <a href> nodes for links, socials,
mailto: emails, and tel: phone numbers.
"""
import re
import urllib.parse
from typing import Any, Dict, List, Set

from selectolax.parser import HTMLParser

from app.extraction.social import SOCIAL_HOSTNAME_MAP, SOCIAL_PLATFORM_KEYS

MAILTO_HREF_REGEX = re.compile(r'^mailto:', re.I)
TEL_HREF_REGEX = re.compile(r'^tel:', re.I)

MAX_INTERNAL_LINKS = 50
MAX_EXTERNAL_LINKS = 50


def extract_links_and_socials(a_nodes, final_url: str) -> Dict[str, Any]:
    """`a_nodes` must be the SAME node list the caller already queried via
    `tree.css('a[href]')` — queried once in the pipeline and reused here and
    for `metadata.links_count`, per Plan §11 (parse/query once)."""
    final_domain = urllib.parse.urlparse(final_url).netloc.lower()

    social_links: Dict[str, Any] = {platform: None for platform in SOCIAL_PLATFORM_KEYS}
    internal_links: List[str] = []
    external_links: List[str] = []
    mailto_emails: List[str] = []
    tel_phones: List[str] = []
    internal_seen: Set[str] = set()
    external_seen: Set[str] = set()

    for a in a_nodes:
        raw_href = a.attributes.get('href')
        href = raw_href.strip() if raw_href else ""
        if not href:
            continue

        if not href.startswith('#') and not href.startswith('javascript:'):
            full_link = urllib.parse.urljoin(final_url, href)
            link_domain = urllib.parse.urlparse(full_link).netloc.lower()
            if link_domain == final_domain or not link_domain:
                if full_link not in internal_seen and len(internal_links) < MAX_INTERNAL_LINKS:
                    internal_seen.add(full_link)
                    internal_links.append(full_link)
            else:
                if full_link not in external_seen and len(external_links) < MAX_EXTERNAL_LINKS:
                    external_seen.add(full_link)
                    external_links.append(full_link)

        if href.startswith(('http://', 'https://')):
            try:
                href_host = urllib.parse.urlparse(href).netloc.lower().lstrip("www.")
                href_host_full = urllib.parse.urlparse(href).netloc.lower()
                platform = SOCIAL_HOSTNAME_MAP.get(href_host) or SOCIAL_HOSTNAME_MAP.get(href_host_full)
                if platform and social_links.get(platform) is None:
                    social_links[platform] = href
            except Exception:
                pass

        if MAILTO_HREF_REGEX.search(href):
            mail = href.replace('mailto:', '').split('?')[0].strip()
            if mail and mail not in mailto_emails:
                mailto_emails.append(mail)
        elif TEL_HREF_REGEX.search(href):
            phone = href.replace('tel:', '').strip()
            if phone and phone not in tel_phones:
                tel_phones.append(phone)

    return {
        "a_nodes_count": len(a_nodes),
        "social_links": social_links,
        "internal_links": internal_links,
        "external_links": external_links,
        "mailto_emails": mailto_emails,
        "tel_phones": tel_phones,
    }
