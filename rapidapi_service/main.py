import os
import re
import time
import json
import socket
import asyncio
import logging
import ipaddress
import urllib.parse
from typing import Optional, List, Dict, Any, Tuple
from contextlib import asynccontextmanager

# ------------------------------------------------------------------------------
# Structured Logging
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
logger = logging.getLogger("metadata-api")

import httpx
from selectolax.parser import HTMLParser
from cachetools import TTLCache
from fastapi import FastAPI, HTTPException, Header, Depends, Query, Request

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, ORJSONResponse
from pydantic import BaseModel

# ------------------------------------------------------------------------------
# Global Caches & Shared HTTP Client (HTTP/2 Enabled)
# ------------------------------------------------------------------------------
# Metadata Cache: 5000 URLs max, 15 minutes expiration (900 seconds)
cache: TTLCache = TTLCache(maxsize=5000, ttl=900)

# DNS TTL Cache: 2000 hostnames max, 5 minutes expiration (300 seconds)
dns_cache: TTLCache = TTLCache(maxsize=2000, ttl=300)

http_client: Optional[httpx.AsyncClient] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(
        http2=True,
        timeout=httpx.Timeout(4.5, connect=1.5, read=3.0),
        limits=httpx.Limits(max_keepalive_connections=500, max_connections=2000, keepalive_expiry=120.0),
        follow_redirects=False
    )
    yield
    if http_client:
        await http_client.aclose()

# ------------------------------------------------------------------------------
# FastAPI App Config (ORJSON Serializer + Native IP Rate Limiter & Security)
# ------------------------------------------------------------------------------
app = FastAPI(
    title="Web Metadata & Contact Extractor API",
    description="Ultra-fast, enterprise REST API with Async DNS (non-blocking), Error Message IP Sanitizer, Native IP Rate Limiter, DNS Caching, Early-Abort Streaming, Single-Source-of-Truth Scheme Shield, IP-Pinned Anti-SSRF, and Rust ORJSON serialization.",
    version="2.4.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan
)


# CORS Fix: allow_credentials=False for security (API Key / Header Auth, no cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

RAPIDAPI_PROXY_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET", None)

# TRUST_PROXY: Set to "true" only when deployed behind a trusted reverse proxy
# (e.g. Render, Fly.io, Nginx). Enables X-Forwarded-For for real client IP.
# When false (default), uses request.client.host only — prevents IP spoofing.
TRUST_PROXY = os.getenv("TRUST_PROXY", "false").lower() == "true"

# ------------------------------------------------------------------------------
# Native Application-Level IP Rate Limiter (60 Requests / Minute per IP)
# ------------------------------------------------------------------------------
ip_rate_tracker: TTLCache = TTLCache(maxsize=10000, ttl=60)

def check_ip_rate_limit(request: Request):
    """Enforces native 60 requests/minute limit per client IP address.
    
    X-Forwarded-For is only trusted when TRUST_PROXY=true env var is set,
    preventing IP spoofing bypasses in non-proxied deployments.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    if TRUST_PROXY:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

    current_time = time.time()
    history = ip_rate_tracker.get(client_ip, [])
    valid_history = [t for t in history if current_time - t < 60]

    if len(valid_history) >= 60:
        logger.warning("Rate limit exceeded for IP: %s", client_ip)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded: 60 requests per minute limit reached per client IP address."
        )

    valid_history.append(current_time)
    ip_rate_tracker[client_ip] = valid_history

# Standard Error Responses for OpenAPI Documentation
COMMON_RESPONSES = {
    400: {"description": "Bad Request: Invalid URL format, missing domain hostname, or blocked by IP-Pinned Anti-SSRF Shield"},
    403: {"description": "Forbidden: Invalid or missing X-RapidAPI-Proxy-Secret authentication header"},
    429: {"description": "Too Many Requests: Native rate limit exceeded (60 requests/min per IP)"}
}


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
FAVICON_REL_REGEX = re.compile(r'^(shortcut )?icon$|^apple-touch-icon$', re.I)
MAILTO_HREF_REGEX = re.compile(r'^mailto:', re.I)
TEL_HREF_REGEX = re.compile(r'^tel:', re.I)
MULTI_NEWLINE_REGEX = re.compile(r'\n{3,}')

SOCIAL_DOMAINS = {
    'twitter': re.compile(r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[a-zA-Z0-9_]+', re.I),
    'facebook': re.compile(r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+', re.I),
    'instagram': re.compile(r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._-]+', re.I),
    'linkedin': re.compile(r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9._-]+', re.I),
    'github': re.compile(r'https?://(?:www\.)?github\.com/[a-zA-Z0-9._-]+', re.I),
    'youtube': re.compile(r'https?://(?:www\.)?youtube\.com/(?:c/|channel/|@)?[a-zA-Z0-9._-]+', re.I),
    'telegram': re.compile(r'https?://(?:t\.me|telegram\.me)/[a-zA-Z0-9._-]+', re.I),
    'tiktok': re.compile(r'https?://(?:www\.)?tiktok\.com/@[a-zA-Z0-9._-]+', re.I)
}

TECH_SIGNATURES = {
    "WordPress": [r'wp-content', r'wp-includes', r'generator" content="wordpress'],
    "Shopify": [r'cdn\.shopify\.com', r'shopify\.theme', r'myshopify\.com'],
    "WooCommerce": [r'woocommerce', r'wc-ajax'],
    "Wix": [r'wix\.com', r'_wix', r'wix-code'],
    "Squarespace": [r'squarespace\.com', r'sqsp\.net'],
    "Webflow": [r'uploads-ssl\.webflow\.com', r'webflow\.js', r'html class="w-mod-'],
    "Framer": [r'framerusercontent\.com', r'framer\.com'],
    "Ghost": [r'ghost\.io', r'ghost-sdk', r'generator" content="ghost'],
    "Drupal": [r'drupal\.js', r'sites/default/files', r'generator" content="drupal'],
    "Joomla": [r'/components/com_', r'generator" content="joomla'],
    "Magento": [r'skin/frontend', r'mage/cookies\.js'],
    "PrestaShop": [r'prestashop', r'_ps_version'],
    "BigCommerce": [r'cdn11\.bigcommerce\.com', r'stencil'],
    "Contentful": [r'contentful\.com', r'ctfassets\.net'],
    "Strapi": [r'strapi'],
    "Sanity": [r'cdn\.sanity\.io'],

    "React": [r'data-reactroot', r'_reactListening', r'react-dom'],
    "Next.js": [r'_next/static', r'__next', r'__next_f'],
    "Vue.js": [r'data-v-', r'vue\.js', r'vue\.min\.js'],
    "Nuxt.js": [r'_nuxt', r'__nuxt'],
    "Angular": [r'ng-version', r'angular\.js', r'ng-app'],
    "Svelte": [r'svelte-', r'svelte\.js'],
    "SvelteKit": [r'_app/immutable', r'__sveltekit'],
    "Astro": [r'astro-island', r'data-astro-cid'],
    "Gatsby": [r'___gatsby', r'gatsby-static'],
    "Remix": [r'__remix', r'remix-run'],
    "Alpine.js": [r'x-data', r'alpine\.js', r'x-init'],
    "HTMX": [r'hx-get', r'hx-post', r'htmx\.js'],
    "jQuery": [r'jquery\.min\.js', r'jquery\.js'],
    "Bootstrap": [r'bootstrap\.min\.css', r'bootstrap\.bundle'],
    "TailwindCSS": [r'cdn\.tailwindcss\.com', r'tailwind'],

    "Google Analytics 4": [r'googletagmanager\.com/gtag/js', r'ga4'],
    "Google Tag Manager": [r'googletagmanager\.com/gtm\.js'],
    "Hotjar": [r'static\.hotjar\.com', r'hjid:'],
    "Segment": [r'cdn\.segment\.com/analytics\.js'],
    "Plausible Analytics": [r'plausible\.io/js/script\.js'],
    "PostHog": [r'posthog\.com/static/array\.js'],
    "Stripe": [r'js\.stripe\.com'],
    "PayPal": [r'paypal\.com/sdk/js'],
    "Vercel": [r'_vercel', r'vercel\.app'],
    "Netlify": [r'netlify\.app'],
    "Cloudflare": [r'cf-beacon', r'cloudflare\.com'],
    "Fastly": [r'fastly\.net']
}

COMPILED_TECH_SIGS = {
    tech: [re.compile(pattern, re.I) for pattern in patterns]
    for tech, patterns in TECH_SIGNATURES.items()
}

class MetadataResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    metadata: Dict[str, Any]
    social_links: Dict[str, Optional[str]]
    contacts: Dict[str, List[str]]
    detected_technologies: List[str]
    rss_feeds: List[str]
    json_ld_schemas: List[Any]
    security_score_percentage: float
    seo_score_percentage: float
    seo_passed_checks: List[str]
    seo_warnings: List[str]
    internal_links: List[str]
    external_links: List[str]
    total_internal_count: int
    total_external_count: int
    word_count: int
    reading_time_minutes: float
    markdown_content: str

class LinkPreviewResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    title: Optional[str]
    description: Optional[str]
    og_image: Optional[str]
    favicon: Optional[str]
    site_name: Optional[str]
    language: Optional[str]

class ContactsResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    emails: List[str]
    phones: List[str]
    social_links: Dict[str, Optional[str]]

class TechStackResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    detected_technologies: List[str]

class SchemaResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    json_ld_count: int
    json_ld_schemas: List[Any]

class SecurityHeadersResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    security_score_percentage: float
    security_headers: Dict[str, Optional[str]]

class MarkdownResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    title: Optional[str]
    word_count: int
    reading_time_minutes: float
    markdown_content: str

class SeoAuditResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    seo_score_percentage: float
    passed_checks: List[str]
    warnings: List[str]

class LinksResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    total_links_count: int
    internal_links_count: int
    external_links_count: int
    internal_links: List[str]
    external_links: List[str]

def verify_rapidapi_secret(x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    if RAPIDAPI_PROXY_SECRET and x_rapidapi_proxy_secret != RAPIDAPI_PROXY_SECRET:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Invalid or missing X-RapidAPI-Proxy-Secret header."
        )

def sanitize_user_agent(ua: Optional[str]) -> str:
    """Sanitize User-Agent header to prevent CRLF injection and cap length at 500 chars."""
    if not ua or hasattr(ua, 'default'):
        return USER_AGENTS[0]
    ua_clean = str(ua).replace('\r', '').replace('\n', '').strip()
    if len(ua_clean) > 500:
        ua_clean = ua_clean[:500]
    return ua_clean or USER_AGENTS[0]

def normalize_and_validate_url(url: str) -> str:
    """
    Single Source of Truth URL Normalizer & Scheme Validator.
    Prepends https:// to scheme-less inputs (e.g. github.com -> https://github.com)
    and strictly validates that scheme is http or https (rejecting ftp, file, gopher, etc.).
    """
    raw_url = url.strip()
    parsed = urllib.parse.urlparse(raw_url)
    
    if parsed.scheme:
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise HTTPException(
                status_code=400,
                detail=f"SSRF Protection: Forbidden scheme '{scheme}:'. Only 'http' and 'https' protocols are permitted."
            )
        return raw_url
    else:
        return "https://" + raw_url

# ------------------------------------------------------------------------------
# IP-Pinned Anti-SSRF Shield (Prevents DNS Rebinding / TOCTOU Race Conditions)
# ------------------------------------------------------------------------------
async def validate_url_ssrf(url: str) -> Tuple[str, str]:
    """
    Async IP-Pinned Anti-SSRF Shield.
    Resolves DNS hostname ONCE via asyncio.to_thread (non-blocking),
    validates IP against private/loopback/cloud-metadata ranges,
    and returns (ip_pinned_url, original_hostname) to eliminate DNS Rebinding.
    """
    url = normalize_and_validate_url(url)
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(
            status_code=400,
            detail="SSRF Protection: Invalid or missing domain hostname."
        )

    hostname_lower = hostname.lower()
    if hostname_lower in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "169.254.169.254"):
        logger.warning("SSRF block — loopback/internal hostname: %s", hostname)
        raise HTTPException(
            status_code=400,
            detail="SSRF Protection: Access to loopback, internal, or cloud metadata hostnames is forbidden."
        )

    port = parsed.port or (443 if scheme == "https" else 80)

    # 1. Resolve DNS ONCE (non-blocking) with 5-minute TTL DNS Caching
    dns_key = (hostname, port)
    if dns_key in dns_cache:
        addr_info = dns_cache[dns_key]
    else:
        try:
            addr_info = await asyncio.to_thread(
                socket.getaddrinfo, hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM
            )
            dns_cache[dns_key] = addr_info
        except socket.gaierror:
            raise HTTPException(
                status_code=400,
                detail=f"SSRF Protection: Unable to resolve hostname '{hostname}' via DNS."
            )

    # 2. Validate all resolved IP addresses against private/reserved ranges
    resolved_ip = None
    for item in addr_info:
        ip_str = item[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if (
                ip_obj.is_private or
                ip_obj.is_loopback or
                ip_obj.is_link_local or
                ip_obj.is_multicast or
                ip_obj.is_reserved or
                ip_obj.is_unspecified or
                str(ip_obj) == "169.254.169.254"
            ):
                logger.warning("SSRF block — private IP: %s -> %s", hostname, ip_str)
                raise HTTPException(
                    status_code=400,
                    detail=f"SSRF Protection: Target domain resolves to private/internal IP address ({ip_str}), which is forbidden."
                )
            if not resolved_ip:
                resolved_ip = ip_str
        except ValueError:
            pass

    if not resolved_ip:
        raise HTTPException(
            status_code=400,
            detail="SSRF Protection: No valid public IP address found for target domain."
        )

    # 3. Construct IP-Pinned Connection URL (eliminates second DNS resolution)
    path_and_query = parsed.path or "/"
    if parsed.query:
        path_and_query += "?" + parsed.query

    formatted_ip = f"[{resolved_ip}]" if ":" in resolved_ip else resolved_ip
    ip_pinned_url = f"{scheme}://{formatted_ip}:{port}{path_and_query}"

    return ip_pinned_url, hostname

def normalize_cache_url(url: str) -> str:
    url = normalize_and_validate_url(url)
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]

    query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    clean_params = [(k, v) for k, v in query_params if not k.lower().startswith(('utm_', 'fbclid', 'gclid', 'msclkid'))]
    clean_query = urllib.parse.urlencode(clean_params)

    return urllib.parse.urlunparse((scheme, netloc, parsed.path or "/", parsed.params, clean_query, ""))

def html_to_markdown_clean(html_str: str, base_url: str) -> tuple[str, int, float]:
    tree = HTMLParser(html_str)
    
    target_node = (
        tree.css_first('article') or 
        tree.css_first('main') or 
        tree.css_first('[role="main"]') or 
        tree.css_first('.post-content') or 
        tree.css_first('.article-body') or 
        tree.css_first('body') or 
        tree.root
    )
    
    if not target_node:
        return "", 0, 0.0

    target_node.strip_tags([
        "nav", "header", "footer", "aside", "script", "style", 
        "noscript", "svg", "iframe", "form", "button", "input"
    ])

    lines = []
    
    for element in target_node.css('h1, h2, h3, h4, h5, h6, p, li, blockquote, pre'):
        tag = element.tag
        raw_txt = element.text(deep=True, separator=' ')
        txt = raw_txt.strip() if raw_txt else ""
        if not txt:
            continue

        if tag == 'h1':
            lines.append(f"\n# {txt}\n")
        elif tag == 'h2':
            lines.append(f"\n## {txt}\n")
        elif tag == 'h3':
            lines.append(f"\n### {txt}\n")
        elif tag == 'h4':
            lines.append(f"\n#### {txt}\n")
        elif tag == 'h5':
            lines.append(f"\n##### {txt}\n")
        elif tag == 'h6':
            lines.append(f"\n###### {txt}\n")
        elif tag == 'p':
            lines.append(f"{txt}\n")
        elif tag == 'li':
            lines.append(f"* {txt}")
        elif tag == 'blockquote':
            lines.append(f"> {txt}\n")
        elif tag == 'pre':
            lines.append(f"\n```\n{txt}\n```\n")

    markdown_str = "\n".join(lines).strip()
    markdown_str = MULTI_NEWLINE_REGEX.sub("\n\n", markdown_str)
    
    words = markdown_str.split()
    word_count = len(words)
    reading_time = round(word_count / 200.0, 1) if word_count > 0 else 0.0
    
    return markdown_str, word_count, reading_time

async def fetch_and_extract_raw(url: str, user_agent: Optional[str] = None) -> Dict[str, Any]:
    start_time = time.time()
    url = normalize_and_validate_url(url)

    # Normalized Cache Lookup
    cache_key = normalize_cache_url(url)

    if cache_key in cache:
        cached_data = cache[cache_key].copy()
        cached_data["execution_time_ms"] = 0.01
        logger.info("Cache hit: %s", cache_key)
        return cached_data

    clean_ua = sanitize_user_agent(user_agent)
    
    client = http_client
    should_close_client = False
    if client is None:
        client = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(4.5, connect=1.5, read=3.0),
            limits=httpx.Limits(max_keepalive_connections=500, max_connections=2000, keepalive_expiry=120.0),
            follow_redirects=False
        )
        should_close_client = True

    MAX_BYTES = 64 * 1024  # 64 KB Stream cap for maximum speed
    MAX_REDIRECTS = 5
    redirect_count = 0
    current_url = url

    content_chunks = []
    total_bytes = 0
    status_code = 200
    final_url = url
    resp_headers: Dict[str, str] = {}
    response = None  # Initialized to prevent UnboundLocalError on empty redirect loops

    try:
        while redirect_count <= MAX_REDIRECTS:
            # IP-Pinning Anti-SSRF Validation (Eliminates DNS Rebinding & Redirect SSRF)
            ip_pinned_url, original_hostname = await validate_url_ssrf(current_url)

            req_headers = {
                "User-Agent": clean_ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Host": original_hostname
            }

            async with client.stream(
                "GET",
                ip_pinned_url,
                headers=req_headers,
                extensions={"sni_hostname": original_hostname},
                follow_redirects=False
            ) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    redirect_location = response.headers.get("location") or response.headers.get("Location")
                    if not redirect_location:
                        break
                    current_url = urllib.parse.urljoin(current_url, redirect_location)
                    redirect_count += 1
                    if redirect_count > MAX_REDIRECTS:
                        raise HTTPException(
                            status_code=400,
                            detail="SSRF Protection: Exceeded maximum allowed HTTP redirects (5 hops)."
                        )
                    continue

                response.raise_for_status()
                status_code = response.status_code
                final_url = current_url
                resp_headers = {k.lower(): v for k, v in response.headers.items()}

                # Optimized streaming: use tail_buffer to search for </head>
                # without reconstructing the full buffer on every chunk.
                tail_buffer = b""
                async for chunk in response.aiter_bytes():
                    content_chunks.append(chunk)
                    total_bytes += len(chunk)
                    if total_bytes >= MAX_BYTES:
                        break
                    # Only keep last 128 bytes to check for </head> sentinel
                    tail_buffer = (tail_buffer + chunk)[-128:]
                    if b"</head>" in tail_buffer.lower() and total_bytes >= 16 * 1024:
                        break
                break


        raw_bytes = b"".join(content_chunks)
        try:
            encoding = response.encoding or "utf-8"
            html_content = raw_bytes.decode(encoding, errors="replace")
        except Exception:
            html_content = raw_bytes.decode("utf-8", errors="replace")

    except Exception as e:
        if should_close_client:
            await client.aclose()
        err_msg = str(e)
        if 'original_hostname' in locals() and original_hostname:
            err_msg = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', original_hostname, err_msg)
        logger.error("Fetch error for %s: %s", url, err_msg)
        raise HTTPException(
            status_code=400,
            detail=f"Unable to access target URL: {err_msg}"
        )



    finally:
        if should_close_client:
            await client.aclose()

    tree = HTMLParser(html_content)
    
    # 1. SEO & OpenGraph Metadata
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
    keywords = get_meta('keywords')
    author = get_meta('author') or get_meta('article:author')
    site_name = get_meta('og:site_name')
    theme_color = get_meta('theme-color')
    
    html_node = tree.css_first('html')
    language = html_node.attributes.get('lang') if html_node else None
    if not language:
        og_locale = get_meta('og:locale')
        if og_locale:
            language = og_locale.split('_')[0]
    
    canonical_url = None
    canonical_node = tree.css_first('link[rel="canonical"]')
    if canonical_node and canonical_node.attributes.get('href'):
        canonical_url = urllib.parse.urljoin(final_url, canonical_node.attributes.get('href'))

    favicon = None
    for link in tree.css('link[rel]'):
        rel = link.attributes.get('rel', '') or ''
        if FAVICON_REL_REGEX.search(rel):
            href = link.attributes.get('href')
            if href:
                favicon = urllib.parse.urljoin(final_url, href)
                break
    if not favicon:
        favicon = urllib.parse.urljoin(final_url, "/favicon.ico")

    h1_tags = [h.text().strip() for h in tree.css('h1') if (h and h.text() and h.text().strip())]
    img_nodes = tree.css('img')
    images_count = len(img_nodes)
    images_missing_alt_count = sum(1 for img in img_nodes if not img.attributes.get('alt'))
    
    a_nodes = tree.css('a[href]')
    final_domain = urllib.parse.urlparse(final_url).netloc.lower()

    internal_links = []
    external_links = []
    social_links: Dict[str, Optional[str]] = {platform: None for platform in SOCIAL_DOMAINS}
    mailto_emails = []
    tel_phones = []

    # Single-pass loop over all <a href> nodes for links, socials, emails, and phones
    for a in a_nodes:
        raw_href = a.attributes.get('href')
        href = raw_href.strip() if raw_href else ""
        if not href:
            continue

        # Classify links (skip anchors and inline JS)
        if not href.startswith('#') and not href.startswith('javascript:'):
            full_link = urllib.parse.urljoin(final_url, href)
            link_domain = urllib.parse.urlparse(full_link).netloc.lower()
            if link_domain == final_domain or not link_domain:
                if full_link not in internal_links and len(internal_links) < 50:
                    internal_links.append(full_link)
            else:
                if full_link not in external_links and len(external_links) < 50:
                    external_links.append(full_link)

        # Detect social profiles
        for platform, pattern in SOCIAL_DOMAINS.items():
            if not social_links[platform] and pattern.search(href):
                social_links[platform] = href

        # Collect mailto: emails and tel: phone numbers
        if MAILTO_HREF_REGEX.search(href):
            mail = href.replace('mailto:', '').split('?')[0].strip()
            if mail and mail not in mailto_emails:
                mailto_emails.append(mail)
        elif TEL_HREF_REGEX.search(href):
            phone = href.replace('tel:', '').strip()
            if phone and phone not in tel_phones:
                tel_phones.append(phone)

    clean_tree = HTMLParser(html_content)
    clean_tree.strip_tags(["script", "style", "code", "noscript", "svg"])
    body_txt = clean_tree.body.text(separator=' ') if clean_tree.body else clean_tree.text(separator=' ')
    clean_text = body_txt if body_txt else ""
    emails = list(set(EMAIL_REGEX.findall(clean_text)))
    emails = [
        e for e in emails 
        if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js'))
        and not any(domain in e.lower() for domain in ['example.com', 'schema.org', 'w3.org', 'domain.com'])
    ]
    
    for mail in mailto_emails:
        if mail not in emails:
            emails.append(mail)

    detected_tech = []
    for tech, patterns in COMPILED_TECH_SIGS.items():
        if any(pattern.search(html_content) for pattern in patterns):
            detected_tech.append(tech)

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

    rss_feeds = []
    for link in tree.css('link[type]'):
        raw_t = link.attributes.get('type')
        t_attr = raw_t.lower() if raw_t else ""
        if 'rss' in t_attr or 'atom' in t_attr or 'xml' in t_attr:
            href = link.attributes.get('href')
            if href:
                rss_feeds.append(urllib.parse.urljoin(final_url, href))

    sec_headers = {
        "strict_transport_security": resp_headers.get("strict-transport-security"),
        "content_security_policy": resp_headers.get("content-security-policy"),
        "x_frame_options": resp_headers.get("x-frame-options"),
        "x_content_type_options": resp_headers.get("x-content-type-options"),
        "referrer_policy": resp_headers.get("referrer-policy"),
        "permissions_policy": resp_headers.get("permissions-policy")
    }
    present_sec = sum(1 for v in sec_headers.values() if v is not None)
    security_score = round((present_sec / len(sec_headers)) * 100, 1)

    passed_seo = []
    warnings_seo = []

    if title:
        if 10 <= len(title) <= 70:
            passed_seo.append("Title tag present with optimal length (10-70 chars)")
        else:
            warnings_seo.append(f"Title tag present but sub-optimal length ({len(title)} chars)")
    else:
        warnings_seo.append("Missing <title> tag")

    if description:
        if 50 <= len(description) <= 160:
            passed_seo.append("Meta description present with optimal length (50-160 chars)")
        else:
            warnings_seo.append(f"Meta description present but sub-optimal length ({len(description)} chars)")
    else:
        warnings_seo.append("Missing <meta name='description'> tag")

    if canonical_url:
        passed_seo.append("Canonical link tag present")
    else:
        warnings_seo.append("Missing <link rel='canonical'> tag")

    if h1_tags:
        passed_seo.append(f"Primary H1 heading present ({len(h1_tags)} found)")
    else:
        warnings_seo.append("Missing <h1> primary heading")

    if og_image:
        passed_seo.append("OpenGraph image present for social sharing")
    else:
        warnings_seo.append("Missing og:image social preview tag")

    if favicon:
        passed_seo.append("Favicon icon present")
    else:
        warnings_seo.append("Missing favicon icon")

    if images_count > 0:
        alt_coverage = round(((images_count - images_missing_alt_count) / images_count) * 100, 1)
        if alt_coverage >= 80.0:
            passed_seo.append(f"High image accessibility ALT coverage ({alt_coverage}%)")
        else:
            warnings_seo.append(f"Low image accessibility ALT coverage ({alt_coverage}% of images have ALT text)")

    if final_url.startswith("https://"):
        passed_seo.append("HTTPS secure protocol active")
    else:
        warnings_seo.append("Non-secure HTTP protocol used")

    total_seo_checks = len(passed_seo) + len(warnings_seo)
    seo_score = round((len(passed_seo) / total_seo_checks) * 100, 1) if total_seo_checks > 0 else 0.0

    markdown_content, word_count, reading_time = html_to_markdown_clean(html_content, final_url)

    execution_time = round((time.time() - start_time) * 1000, 2)
    
    response_data = {
        "url": url,
        "final_url": final_url,
        "status_code": status_code,
        "execution_time_ms": execution_time,
        "metadata": {
            "title": title,
            "description": description,
            "og_image": og_image,
            "keywords": keywords,
            "author": author,
            "site_name": site_name,
            "language": language,
            "favicon": favicon,
            "canonical_url": canonical_url,
            "theme_color": theme_color,
            "h1_tags": h1_tags[:5],
            "images_count": images_count,
            "images_missing_alt_count": images_missing_alt_count,
            "links_count": len(a_nodes),
            "content_length_bytes": len(raw_bytes)
        },
        "social_links": social_links,
        "contacts": {
            "emails": emails[:10],
            "phones": tel_phones[:5]
        },
        "detected_technologies": detected_tech,
        "rss_feeds": rss_feeds,
        "json_ld_schemas": json_ld_schemas,
        "security_headers": sec_headers,
        "security_score_percentage": security_score,
        "seo_score_percentage": seo_score,
        "seo_passed_checks": passed_seo,
        "seo_warnings": warnings_seo,
        "internal_links": internal_links,
        "external_links": external_links,
        "total_internal_count": len(internal_links),
        "total_external_count": len(external_links),
        "word_count": word_count,
        "reading_time_minutes": reading_time,
        "markdown_content": markdown_content
    }

    cache[cache_key] = response_data
    return response_data

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home_ui():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Web Metadata & Contact Extractor API</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
            body { background: #0f172a; color: #f8fafc; padding: 2rem; min-height: 100vh; }
            .container { max-width: 900px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 2.5rem; }
            .header h1 { font-size: 2.5rem; font-weight: 700; background: linear-gradient(135deg, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem; }
            .header p { color: #94a3b8; font-size: 1.1rem; }
            .card { background: #1e293b; border-radius: 16px; padding: 2rem; border: 1px solid #334155; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); margin-bottom: 2rem; }
            .input-group { display: flex; gap: 1rem; }
            input[type="url"] { flex: 1; padding: 1rem 1.25rem; background: #0f172a; border: 1px solid #475569; border-radius: 10px; color: #fff; font-size: 1rem; outline: none; transition: border-color 0.2s; }
            input[type="url"]:focus { border-color: #38bdf8; }
            button { background: linear-gradient(135deg, #0284c7, #6366f1); color: #fff; border: none; padding: 1rem 2rem; font-size: 1rem; font-weight: 600; border-radius: 10px; cursor: pointer; transition: transform 0.1s, opacity 0.2s; }
            button:hover { opacity: 0.9; }
            button:active { transform: scale(0.98); }
            .quick-links { margin-top: 1rem; display: flex; gap: 0.5rem; align-items: center; }
            .quick-links span { color: #64748b; font-size: 0.875rem; }
            .chip { background: #334155; color: #cbd5e1; padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.85rem; cursor: pointer; transition: background 0.2s; }
            .chip:hover { background: #475569; color: #fff; }
            #loading { display: none; text-align: center; padding: 2rem; color: #38bdf8; font-weight: 600; }
            #results { display: none; }
            .res-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; padding-bottom: 1rem; border-bottom: 1px solid #334155; }
            .badge-status { background: #059669; color: #ecfdf5; padding: 0.25rem 0.75rem; border-radius: 6px; font-size: 0.875rem; font-weight: 600; }
            .res-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; }
            .res-block { background: #0f172a; padding: 1.25rem; border-radius: 12px; border: 1px solid #1e293b; }
            .res-block h3 { font-size: 1rem; color: #38bdf8; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem; }
            .data-item { margin-bottom: 0.5rem; word-break: break-word; }
            .data-label { color: #64748b; font-size: 0.8rem; display: block; }
            .data-val { color: #e2e8f0; font-size: 0.95rem; font-weight: 500; }
            .social-tag { display: inline-block; background: #1e293b; color: #38bdf8; text-decoration: none; padding: 0.4rem 0.8rem; border-radius: 6px; font-size: 0.85rem; margin: 0.25rem; border: 1px solid #334155; }
            .social-tag:hover { background: #38bdf8; color: #0f172a; }
            .tech-tag { display: inline-block; background: #4f46e5; color: #fff; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.8rem; margin: 0.2rem; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Web Metadata & Contact Extractor</h1>
                <p>Live Playground for your monetizable RapidAPI Service</p>
            </div>

            <div class="card">
                <div class="input-group">
                    <input type="url" id="urlInput" value="https://github.com" placeholder="Enter target URL (e.g. https://example.com)">
                    <button onclick="analyzeUrl()">Analyze Webpage</button>
                </div>
                <div class="quick-links">
                    <span>Quick presets:</span>
                    <div class="chip" onclick="setUrl('https://github.com')">GitHub</div>
                    <div class="chip" onclick="setUrl('https://amazon.com')">Amazon</div>
                    <div class="chip" onclick="setUrl('https://wikipedia.org')">Wikipedia</div>
                </div>
            </div>

            <div id="loading">Analyzing target URL and extracting metadata in real-time...</div>

            <div id="results" class="card">
                <div class="res-header">
                    <div>
                        <span style="color: #94a3b8;">Result for:</span>
                        <strong id="resUrl" style="color: #fff; margin-left: 0.5rem;"></strong>
                    </div>
                    <div style="display: flex; gap: 1rem; align-items: center;">
                        <span id="resTime" style="color: #38bdf8; font-size: 0.9rem;"></span>
                        <span class="badge-status" id="resStatus">200 OK</span>
                    </div>
                </div>

                <div class="res-grid">
                    <div class="res-block" style="grid-column: 1 / -1;">
                        <h3>SEO & OpenGraph Metadata</h3>
                        <div class="data-item">
                            <span class="data-label">Page Title</span>
                            <span class="data-val" id="metaTitle"></span>
                        </div>
                        <div class="data-item">
                            <span class="data-label">Description</span>
                            <span class="data-val" id="metaDesc"></span>
                        </div>
                    </div>

                    <div class="res-block">
                        <h3>Social Profiles</h3>
                        <div id="socialsContainer"></div>
                    </div>

                    <div class="res-block">
                        <h3>Contacts & Language</h3>
                        <div class="data-item">
                            <span class="data-label">Public Email Addresses</span>
                            <div id="emailsContainer" class="data-val"></div>
                        </div>
                        <div class="data-item">
                            <span class="data-label">Detected Language</span>
                            <span class="data-val" id="metaLang"></span>
                        </div>
                    </div>

                    <div class="res-block" style="grid-column: 1 / -1;">
                        <h3>Detected Technologies</h3>
                        <div id="techContainer"></div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function setUrl(url) {
                document.getElementById('urlInput').value = url;
                analyzeUrl();
            }

            async function analyzeUrl() {
                const url = document.getElementById('urlInput').value;
                if(!url) return;

                document.getElementById('loading').style.display = 'block';
                document.getElementById('results').style.display = 'none';

                try {
                    const res = await fetch(`/api/v1/extract?url=${encodeURIComponent(url)}`);
                    const data = await res.json();

                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('results').style.display = 'block';

                    document.getElementById('resUrl').innerText = data.final_url || data.url;
                    document.getElementById('resStatus').innerText = `${data.status_code} OK`;
                    document.getElementById('resTime').innerText = `⚡ ${data.execution_time_ms} ms`;

                    document.getElementById('metaTitle').innerText = data.metadata.title || 'Not detected';
                    document.getElementById('metaDesc').innerText = data.metadata.description || 'Not detected';
                    document.getElementById('metaLang').innerText = data.metadata.language || 'Unspecified';

                    // Socials
                    const socialsDiv = document.getElementById('socialsContainer');
                    socialsDiv.innerHTML = '';
                    let foundSocials = false;
                    for (const [net, link] of Object.entries(data.social_links)) {
                        if (link) {
                            foundSocials = true;
                            socialsDiv.innerHTML += `<a href="${link}" target="_blank" class="social-tag">${net.toUpperCase()}</a>`;
                        }
                    }
                    if(!foundSocials) socialsDiv.innerHTML = '<span style="color: #64748b;">No social links found</span>';

                    // Emails
                    const emailsDiv = document.getElementById('emailsContainer');
                    if (data.contacts.emails && data.contacts.emails.length > 0) {
                        emailsDiv.innerHTML = data.contacts.emails.map(e => `<span style="color: #38bdf8;">${e}</span>`).join(', ');
                    } else {
                        emailsDiv.innerHTML = '<span style="color: #64748b;">No public emails on main page</span>';
                    }

                    // Tech Stack
                    const techDiv = document.getElementById('techContainer');
                    techDiv.innerHTML = '';
                    if (data.detected_technologies && data.detected_technologies.length > 0) {
                        data.detected_technologies.forEach(t => {
                            techDiv.innerHTML += `<span class="tech-tag">${t}</span>`;
                        });
                    } else {
                        techDiv.innerHTML = '<span style="color: #64748b;">Standard HTML / No known CMS signatures</span>';
                    }

                } catch(err) {
                    document.getElementById('loading').innerText = 'Error connecting to API: ' + err.message;
                }
            }

            window.onload = analyzeUrl;
        </script>
    </body>
    </html>
    """

@app.get("/health", tags=["Health"], responses=COMMON_RESPONSES)
def health_check():
    return {
        "status": "online",
        "service": "Web Metadata & Contact Extractor API",
        "version": "2.4.0",
        "engine": "FastAPI + ORJSON + Selectolax + HTTP/2 + Async DNS + Sanitized IP-Pinned Security Shield",
        "rapidapi_protected": bool(RAPIDAPI_PROXY_SECRET),
        "trust_proxy": TRUST_PROXY
    }


@app.get("/api/v1/extract", tags=["Full Extractor"], responses=COMMON_RESPONSES, dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)])
async def extract_metadata(
    url: str = Query(..., description="The target website URL to analyze (e.g. https://example.com)"),
    fields: Optional[str] = Query(None, description="Optional comma-separated list of keys to filter response (e.g. metadata,contacts)"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Extract full metadata payload (<200ms with Rust ORJSON + IP-Pinned Anti-SSRF Shield + HTTP/2 streaming):
    - **SEO Metadata**: Title, description, OG image, favicon, canonical URL, language, author, theme color, H1 tags.
    - **Page Health Metrics**: Content length (bytes), image count, accessibility missing alt count, link count.
    - **Contacts**: Public email addresses and telephone numbers.
    - **Social Links**: Profiles on Twitter/X, LinkedIn, Instagram, Facebook, GitHub, YouTube, Telegram, TikTok.
    - **Technologies**: Precision context-aware CMS and framework signatures.
    - **SEO Audit**: Automated 8-point SEO diagnostic score & warnings.
    - **Link Extractor**: Categorized internal vs external hyperlinks.
    - **Structured Data**: Schema.org JSON-LD schemas.
    - **Feeds**: RSS/Atom feed discovery.
    - **Security**: HTTP security headers score & IP-Pinned Anti-SSRF Protection.
    - **AI Reader**: Clean Markdown article text, word count & reading time.
    """
    data = await fetch_and_extract_raw(url, user_agent)
    
    if fields:
        allowed_keys = [f.strip() for f in fields.split(',') if f.strip()]
        filtered_data = {k: v for k, v in data.items() if k in allowed_keys or k in ['url', 'final_url', 'status_code', 'execution_time_ms']}
        return filtered_data
        
    return MetadataResponse(**data)

@app.get("/api/v1/link-preview", response_model=LinkPreviewResponse, tags=["Link Preview"], responses=COMMON_RESPONSES, dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)])
async def extract_link_preview(
    url: str = Query(..., description="The target URL to generate link preview for"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Lightweight endpoint optimized for link preview cards (Social Cards / Unfurl):
    Returns title, description, og_image, favicon, site_name, and language.
    """
    data = await fetch_and_extract_raw(url, user_agent)
    meta = data["metadata"]
    return LinkPreviewResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        title=meta["title"],
        description=meta["description"],
        og_image=meta["og_image"],
        favicon=meta["favicon"],
        site_name=meta["site_name"],
        language=meta["language"]
    )

@app.get("/api/v1/contacts", response_model=ContactsResponse, tags=["Lead Generation"], responses=COMMON_RESPONSES, dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)])
async def extract_contacts(
    url: str = Query(..., description="The target URL to extract contact information and social handles from"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for lead enrichment & B2B prospecting:
    Returns public emails, telephone numbers, and official social media profile URLs.
    """
    data = await fetch_and_extract_raw(url, user_agent)
    contacts = data["contacts"]
    return ContactsResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        emails=contacts["emails"],
        phones=contacts["phones"],
        social_links=data["social_links"]
    )

@app.get("/api/v1/tech-stack", response_model=TechStackResponse, tags=["Tech Stack"], responses=COMMON_RESPONSES, dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)])
async def extract_tech_stack(
    url: str = Query(..., description="The target URL to inspect for CMS and technology stack signatures"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for technology intelligence & CMS auditing:
    Detects 100+ frameworks and CMS signatures with structural context-aware matching.
    """
    data = await fetch_and_extract_raw(url, user_agent)
    return TechStackResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        detected_technologies=data["detected_technologies"]
    )

@app.get("/api/v1/schema", response_model=SchemaResponse, tags=["Structured Data"], responses=COMMON_RESPONSES, dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)])
async def extract_schema(
    url: str = Query(..., description="The target URL to extract Schema.org JSON-LD structured data from"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for Schema.org & JSON-LD structured data extraction:
    Returns parsed product pricing, e-commerce reviews, article schemas, event details, and organization metadata.
    """
    data = await fetch_and_extract_raw(url, user_agent)
    schemas = data["json_ld_schemas"]
    return SchemaResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        json_ld_count=len(schemas),
        json_ld_schemas=schemas
    )

@app.get("/api/v1/security", response_model=SecurityHeadersResponse, tags=["Security Audit"], responses=COMMON_RESPONSES, dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)])
async def extract_security_headers(
    url: str = Query(..., description="The target URL to audit HTTP security headers"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for HTTP Security Headers audit:
    Inspects HSTS, Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and calculates a percentage security score.
    """
    data = await fetch_and_extract_raw(url, user_agent)
    return SecurityHeadersResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        security_score_percentage=data["security_score_percentage"],
        security_headers=data["security_headers"]
    )

@app.get("/api/v1/markdown", response_model=MarkdownResponse, tags=["AI & LLM Reader"], responses=COMMON_RESPONSES, dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)])
async def extract_clean_markdown_article(
    url: str = Query(..., description="The target article/webpage URL to extract clean LLM-ready Markdown from"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for AI Agents, ChatGPT, Claude & RAG pipelines:
    Strips noise (ads, navs, footers, scripts) and converts webpage article text into clean, structured Markdown.
    """
    data = await fetch_and_extract_raw(url, user_agent)
    meta = data["metadata"]
    return MarkdownResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        title=meta["title"],
        word_count=data["word_count"],
        reading_time_minutes=data["reading_time_minutes"],
        markdown_content=data["markdown_content"]
    )

@app.get("/api/v1/seo-audit", response_model=SeoAuditResponse, tags=["SEO Audit"], responses=COMMON_RESPONSES, dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)])
async def extract_seo_audit(
    url: str = Query(..., description="The target URL to perform automated 8-point SEO diagnostic audit"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for automated SEO diagnostic audit:
    Evaluates Title tag, Meta Description, Canonical URL, H1 heading, OpenGraph image, Favicon, Image ALT coverage, and HTTPS security.
    """
    data = await fetch_and_extract_raw(url, user_agent)
    return SeoAuditResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        seo_score_percentage=data["seo_score_percentage"],
        passed_checks=data["seo_passed_checks"],
        warnings=data["seo_warnings"]
    )

@app.get("/api/v1/links", response_model=LinksResponse, tags=["Link Extractor"], responses=COMMON_RESPONSES, dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)])
async def extract_links(
    url: str = Query(..., description="The target URL to extract and classify internal vs external hyperlinks"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for hyperlink extraction and domain classification:
    Categorizes all page links into internal links (same domain) and external links (third-party websites).
    """
    data = await fetch_and_extract_raw(url, user_agent)
    return LinksResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        total_links_count=data["total_internal_count"] + data["total_external_count"],
        internal_links_count=data["total_internal_count"],
        external_links_count=data["total_external_count"],
        internal_links=data["internal_links"],
        external_links=data["external_links"]

    )

