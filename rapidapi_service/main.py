import os
import re
import time
import json
import urllib.parse
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import httpx
from selectolax.parser import HTMLParser
from cachetools import TTLCache
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, ORJSONResponse
from pydantic import BaseModel

# ------------------------------------------------------------------------------
# Global Cache & Shared HTTP Client (HTTP/2 Enabled)
# ------------------------------------------------------------------------------
# TTL Cache: 5000 URLs max, 15 minutes expiration (900 seconds)
cache: TTLCache = TTLCache(maxsize=5000, ttl=900)
http_client: Optional[httpx.AsyncClient] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(
        http2=True,
        timeout=httpx.Timeout(4.5, connect=1.5, read=3.0),
        limits=httpx.Limits(max_keepalive_connections=200, max_connections=1000, keepalive_expiry=60.0),
        follow_redirects=True
    )
    yield
    if http_client:
        await http_client.aclose()

# ------------------------------------------------------------------------------
# FastAPI App Config (ORJSON Serializer + uvloop/httptools)
# ------------------------------------------------------------------------------
app = FastAPI(
    title="Web Metadata & Contact Extractor API",
    description="Ultra-fast, enterprise REST API powered by C-Lexbor parser, Rust ORJSON serialization, and HTTP/2 streaming multiplexing.",
    version="1.4.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RAPIDAPI_PROXY_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET", None)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
FAVICON_REL_REGEX = re.compile(r'^(shortcut )?icon$|^apple-touch-icon$', re.I)
MAILTO_HREF_REGEX = re.compile(r'^mailto:', re.I)
TEL_HREF_REGEX = re.compile(r'^tel:', re.I)

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
    # --- CMS & Site Builders ---
    "WordPress": ["wp-content", "wp-includes", "wordpress"],
    "Shopify": ["cdn.shopify.com", "shopify.theme", "myshopify.com"],
    "WooCommerce": ["woocommerce", "wc-ajax"],
    "Wix": ["wix.com", "_wix", "wix-code"],
    "Squarespace": ["squarespace.com", "sqsp.net"],
    "Webflow": ["webflow.com", "uploads-ssl.webflow.com", "webflow.js"],
    "Framer": ["framerusercontent.com", "framer.com"],
    "Ghost": ["ghost.io", "ghost-sdk", "ghost-search"],
    "Drupal": ["drupal.js", "sites/default/files", "drupal-settings"],
    "Joomla": ["/components/com_", "joomla!"],
    "Magento": ["skin/frontend", "mage/cookies.js", "magento"],
    "PrestaShop": ["prestashop", "_ps_version"],
    "BigCommerce": ["cdn11.bigcommerce.com", "stencil"],
    "Contentful": ["contentful.com", "ctfassets.net"],
    "Strapi": ["strapi"],
    "Sanity": ["cdn.sanity.io"],
    "Bubble": ["bubble.io", "bubble.apps"],
    "Carrd": ["carrd.co", "carrd.net"],
    "Weebly": ["weebly.com", "editmysite.com"],
    "TYPO3": ["typo3"],
    "OpenCart": ["catalog/view/theme", "opencart"],
    "Salesforce Commerce Cloud": ["demandware.static", "demandware.store"],
    "HubSpot CMS": ["hs-scripts.com", "hubspot.com", "hs-content"],
    "GoDaddy Website Builder": ["godaddy.com/sites"],

    # --- Frontend Frameworks & Libraries ---
    "React": ["data-reactroot", "react-dom", "_reactListening"],
    "Next.js": ["_next/static", "__next", "__next_f"],
    "Vue.js": ["data-v-", "vue.js", "vue.min.js"],
    "Nuxt.js": ["_nuxt", "__nuxt"],
    "Angular": ["ng-version", "angular.js", "ng-app"],
    "Svelte": ["svelte-", "svelte.js"],
    "SvelteKit": ["_app/immutable", "__sveltekit"],
    "Astro": ["astro-island", "data-astro-cid"],
    "Gatsby": ["___gatsby", "gatsby-static"],
    "Remix": ["__remix", "remix-run"],
    "Alpine.js": ["x-data", "alpine.js", "x-init"],
    "HTMX": ["hx-get", "hx-post", "htmx.js"],
    "SolidJS": ["solid-js", "solid.js"],
    "Ember.js": ["ember-application", "ember.js"],
    "Backbone.js": ["backbone.js"],
    "jQuery": ["jquery.min.js", "jquery.js", "code.jquery.com"],
    "Bootstrap": ["bootstrap.min.css", "bootstrap.bundle", "bootstrap.min.js"],
    "TailwindCSS": ["tailwind", "cdn.tailwindcss.com"],
    "Bulma": ["bulma.min.css"],
    "Foundation": ["foundation.min.css"],
    "Material-UI (MUI)": ["MuiButton", "MuiTypography", "mui.com"],
    "Chakra UI": ["chakra-ui", "chakra-button"],
    "Ant Design": ["ant-btn", "antd.min.js"],
    "Semantic UI": ["semantic.min.css"],
    "DaisyUI": ["daisyui"],
    "Shadcn UI": ["shadcn"],
    "Lit": ["lit-element", "lit-html"],
    "Stencil.js": ["@stencil/core"],

    # --- Backend Frameworks & Runtimes ---
    "Laravel": ["laravel", "XSRF-TOKEN"],
    "Symfony": ["symfony"],
    "Django": ["csrfmiddlewaretoken", "__admin__"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi", "swagger-ui"],
    "Ruby on Rails": ["csrf-param", "rails"],
    "ASP.NET": ["__viewstate", "asp.net"],
    "Express.js": ["express"],
    "NestJS": ["nestjs"],
    "Phoenix (Elixir)": ["phx-", "_csrf_token"],
    "Spring Boot": ["spring-boot"],
    "CodeIgniter": ["codeigniter"],

    # --- Analytics & Tracking ---
    "Google Analytics 4": ["googletagmanager.com/gtag/js", "ga4"],
    "Google Tag Manager": ["googletagmanager.com/gtm.js"],
    "Hotjar": ["static.hotjar.com", "hjid:"],
    "Mixpanel": ["cdn.mxpnl.com", "mixpanel.init"],
    "Segment": ["cdn.segment.com/analytics.js"],
    "Plausible Analytics": ["plausible.io/js/script.js"],
    "PostHog": ["posthog.com/static/array.js"],
    "Amplitude": ["cdn.amplitude.com"],
    "Matomo": ["matomo.js", "piwik.js"],
    "Microsoft Clarity": ["clarity.ms/tag"],
    "Heap Analytics": ["heapanalytics.com"],
    "Simple Analytics": ["scripts.simpleanalyticscdn.com"],

    # --- Customer Support & Chat ---
    "Intercom": ["widget.intercom.io", "intercomSettings"],
    "Crisp": ["client.crisp.chat"],
    "Drift": ["js.driftt.com"],
    "Zendesk": ["static.zdassets.com", "zendesk.com"],
    "HubSpot Chat": ["js.hs-scripts.com", "hubspot.js"],
    "Mailchimp": ["chimpstatic.com", "mailchimp.com"],
    "Klaviyo": ["static.klaviyo.com"],
    "Brevo (Sendinblue)": ["sibautomation.com", "sendinblue.com"],
    "Tidio": ["code.tidio.co"],
    "LiveChat": ["cdn.livechatinc.com"],
    "Olark": ["static.olark.com"],

    # --- Payments & E-Commerce Tools ---
    "Stripe": ["js.stripe.com", "stripe.com"],
    "PayPal": ["paypal.com/sdk/js", "paypalobjects.com"],
    "Klarna": ["klarna.com"],
    "Square": ["squareup.com"],
    "Paddle": ["cdn.paddle.com"],
    "Lemon Squeezy": ["lemonsqueezy.com"],
    "Recharge": ["rechargeapps.com"],

    # --- Hosting, CDN & Cloud Infrastructure ---
    "Vercel": ["_vercel", "vercel.app"],
    "Netlify": ["netlify.app", "netlify"],
    "Cloudflare": ["cloudflare.com", "cf-beacon"],
    "AWS CloudFront": ["cloudfront.net"],
    "Fastly": ["fastly.net"],
    "Cloudinary": ["res.cloudinary.com"],
    "Imgix": ["imgix.net"],
    "Supabase": ["supabase.co"],
    "Firebase": ["firebaseapp.com", "firestore"],

    # --- SEO, Ads & Optimization ---
    "Yoast SEO": ["yoast-seo", "yoast"],
    "Rank Math": ["rank-math"],
    "Optimizely": ["optimizely.com"],
    "VWO": ["dev.visualwebsiteoptimizer.com"],
    "Google AdSense": ["pagead2.googlesyndication.com"],
    "Meta Pixel": ["connect.facebook.net/en_US/fbevents.js"]
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

def verify_rapidapi_secret(x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    if RAPIDAPI_PROXY_SECRET and x_rapidapi_proxy_secret != RAPIDAPI_PROXY_SECRET:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Invalid or missing X-RapidAPI-Proxy-Secret header."
        )

async def fetch_and_extract_raw(url: str, user_agent: Optional[str] = None) -> Dict[str, Any]:
    start_time = time.time()
    
    ua_str = str(user_agent) if (user_agent and not hasattr(user_agent, 'default')) else None
    
    parsed_url = urllib.parse.urlparse(url)
    if not parsed_url.scheme:
        url = "https://" + url
        parsed_url = urllib.parse.urlparse(url)

    # Fast-Path In-Memory Cache Hit (Sub-0.01ms)
    if url in cache:
        cached_data = cache[url].copy()
        cached_data["execution_time_ms"] = 0.01
        return cached_data

    headers = {
        "User-Agent": ua_str or USER_AGENTS[0],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        "Accept-Encoding": "gzip, deflate, br"
    }
    
    client = http_client
    should_close_client = False
    if client is None:
        client = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(4.5, connect=1.5, read=3.0),
            limits=httpx.Limits(max_keepalive_connections=200, max_connections=1000, keepalive_expiry=60.0),
            follow_redirects=True
        )
        should_close_client = True

    MAX_BYTES = 128 * 1024  # 128 KB Stream limit for maximum speed
    content_chunks = []
    total_bytes = 0
    status_code = 200
    final_url = url
    resp_headers: Dict[str, str] = {}

    try:
        async with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            status_code = response.status_code
            final_url = str(response.url)
            resp_headers = {k.lower(): v for k, v in response.headers.items()}
            
            async for chunk in response.aiter_bytes():
                content_chunks.append(chunk)
                total_bytes += len(chunk)
                if total_bytes >= MAX_BYTES:
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
        raise HTTPException(
            status_code=400,
            detail=f"Unable to access target URL: {str(e)}"
        )
    finally:
        if should_close_client:
            await client.aclose()

    tree = HTMLParser(html_content)
    
    # 1. SEO & OpenGraph Metadata
    title_node = tree.css_first('title')
    title = title_node.text().strip() if title_node else None
    
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
    
    html_node = tree.css_first('html')
    language = html_node.attributes.get('lang') if html_node else None
    if not language:
        og_locale = get_meta('og:locale')
        if og_locale:
            language = og_locale.split('_')[0]
    
    favicon = None
    for link in tree.css('link[rel]'):
        rel = link.attributes.get('rel', '')
        if FAVICON_REL_REGEX.search(rel):
            href = link.attributes.get('href')
            if href:
                favicon = urllib.parse.urljoin(final_url, href)
                break
    if not favicon:
        favicon = urllib.parse.urljoin(final_url, "/favicon.ico")

    # 2. Social Profiles & Direct Contacts
    social_links: Dict[str, Optional[str]] = {platform: None for platform in SOCIAL_DOMAINS}
    mailto_emails = []
    tel_phones = []
    
    a_nodes = tree.css('a[href]')
    for a in a_nodes:
        href = a.attributes.get('href', '')
        if not href:
            continue
        for platform, pattern in SOCIAL_DOMAINS.items():
            if not social_links[platform] and pattern.search(href):
                social_links[platform] = href
        if MAILTO_HREF_REGEX.search(href):
            mail = href.replace('mailto:', '').split('?')[0].strip()
            if mail and mail not in mailto_emails:
                mailto_emails.append(mail)
        elif TEL_HREF_REGEX.search(href):
            phone = href.replace('tel:', '').strip()
            if phone and phone not in tel_phones:
                tel_phones.append(phone)

    # 3. DOM Cleaning & Regex Email Extraction
    tree.strip_tags(["script", "style", "code", "noscript", "svg"])
    clean_text = tree.body.text(separator=' ') if tree.body else tree.text(separator=' ')
    emails = list(set(EMAIL_REGEX.findall(clean_text)))
    emails = [
        e for e in emails 
        if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js'))
        and not any(domain in e.lower() for domain in ['example.com', 'schema.org', 'w3.org', 'domain.com'])
    ]
    
    for mail in mailto_emails:
        if mail not in emails:
            emails.append(mail)

    # 4. Tech Stack Signatures
    detected_tech = []
    html_lower = html_content.lower()
    
    for tech, sigs in TECH_SIGNATURES.items():
        if any(sig in html_lower for sig in sigs):
            detected_tech.append(tech)

    # 5. Schema.org JSON-LD Extraction
    json_ld_schemas = []
    raw_tree = HTMLParser(html_content)
    for script in raw_tree.css('script[type="application/ld+json"]'):
        try:
            t = script.text().strip()
            if t:
                parsed_json = json.loads(t)
                json_ld_schemas.append(parsed_json)
        except Exception:
            pass

    # 6. RSS & Atom Feeds Discovery
    rss_feeds = []
    for link in raw_tree.css('link[type]'):
        t_attr = link.attributes.get('type', '').lower()
        if 'rss' in t_attr or 'atom' in t_attr or 'xml' in t_attr:
            href = link.attributes.get('href')
            if href:
                rss_feeds.append(urllib.parse.urljoin(final_url, href))

    # 7. Security Headers Audit
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
            "favicon": favicon
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
        "security_score_percentage": security_score
    }

    cache[url] = response_data
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

@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "online",
        "service": "Web Metadata & Contact Extractor API",
        "version": "1.4.0",
        "engine": "FastAPI + ORJSON + Selectolax + HTTP/2",
        "rapidapi_protected": bool(RAPIDAPI_PROXY_SECRET)
    }

@app.get("/api/v1/extract", tags=["Full Extractor"])
async def extract_metadata(
    url: str = Query(..., description="The target website URL to analyze (e.g. https://example.com)"),
    fields: Optional[str] = Query(None, description="Optional comma-separated list of keys to filter response (e.g. metadata,contacts)"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header"),
    dependencies: None = Depends(verify_rapidapi_secret)
):
    """
    Extract full metadata payload (<200ms with Rust ORJSON + C-Lexbor parser + HTTP/2 streaming):
    - **SEO Metadata**: Title, description, OG image, favicon, language, author.
    - **Contacts**: Public email addresses and telephone numbers.
    - **Social Links**: Profiles on Twitter/X, LinkedIn, Instagram, Facebook, GitHub, YouTube, Telegram, TikTok.
    - **Technologies**: 100+ CMS and framework signatures.
    - **Structured Data**: Schema.org JSON-LD schemas.
    - **Feeds**: RSS/Atom feed discovery.
    - **Security**: HTTP security headers score.
    """
    data = await fetch_and_extract_raw(url, user_agent)
    
    if fields:
        allowed_keys = [f.strip() for f in fields.split(',') if f.strip()]
        filtered_data = {k: v for k, v in data.items() if k in allowed_keys or k in ['url', 'final_url', 'status_code', 'execution_time_ms']}
        return filtered_data
        
    return MetadataResponse(**data)

@app.get("/api/v1/link-preview", response_model=LinkPreviewResponse, tags=["Link Preview"])
async def extract_link_preview(
    url: str = Query(..., description="The target URL to generate link preview for"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header"),
    dependencies: None = Depends(verify_rapidapi_secret)
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

@app.get("/api/v1/contacts", response_model=ContactsResponse, tags=["Lead Generation"])
async def extract_contacts(
    url: str = Query(..., description="The target URL to extract contact information and social handles from"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header"),
    dependencies: None = Depends(verify_rapidapi_secret)
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

@app.get("/api/v1/tech-stack", response_model=TechStackResponse, tags=["Tech Stack"])
async def extract_tech_stack(
    url: str = Query(..., description="The target URL to inspect for CMS and technology stack signatures"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header"),
    dependencies: None = Depends(verify_rapidapi_secret)
):
    """
    Dedicated endpoint for technology intelligence & CMS auditing:
    Detects 100+ frameworks and CMS signatures (WordPress, Shopify, WooCommerce, Wix, React, Next.js, Vue, Nuxt, TailwindCSS, Bootstrap, etc.).
    """
    data = await fetch_and_extract_raw(url, user_agent)
    return TechStackResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        detected_technologies=data["detected_technologies"]
    )

@app.get("/api/v1/schema", response_model=SchemaResponse, tags=["Structured Data"])
async def extract_schema(
    url: str = Query(..., description="The target URL to extract Schema.org JSON-LD structured data from"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header"),
    dependencies: None = Depends(verify_rapidapi_secret)
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

@app.get("/api/v1/security", response_model=SecurityHeadersResponse, tags=["Security Audit"])
async def extract_security_headers(
    url: str = Query(..., description="The target URL to audit HTTP security headers"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header"),
    dependencies: None = Depends(verify_rapidapi_secret)
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
