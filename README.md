<div align="center">

  ![Web Metadata & Contact Extractor API](assets/banner.png)

  # 🚀 Web Metadata, OpenGraph & Contact Extractor API

  **Ultra-fast (<200ms) REST API to extract SEO metadata, contacts, social profiles, tech stack, Schema.org JSON-LD, Security Headers, and AI-ready Markdown from any URL.**

  [![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
  [![Version](https://img.shields.io/badge/Version-2.6.0-blueviolet.svg)]()
  [![Rust ORJSON](https://img.shields.io/badge/JSON%20Engine-Rust%20ORJSON-orange.svg)]()
  [![RapidAPI](https://img.shields.io/badge/RapidAPI-Available-0052CC.svg)](https://rapidapi.com/)
  [![Response Time](https://img.shields.io/badge/Response%20Time-%3C200ms-brightgreen.svg)]()
  [![Cache Speed](https://img.shields.io/badge/Cache%20Speed-0.01ms-flash.svg)]()
  [![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
  [![CI](https://github.com/JosejuX/rapidapi-metadata-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/JosejuX/rapidapi-metadata-extractor/actions)

  [🔑 Get Free API Key on RapidAPI](https://rapidapi.com/) • [📖 API Documentation](#-api-endpoint-documentation) • [⚡ Code Examples](#-quick-start)

</div>

---

## 🌟 Key Features

| Feature | Detail |
|:---|:---|
| ⚡ **Ultra-Fast Performance** | ~150–300ms live fetch. Powered by `selectolax` (C-Lexbor parser), Rust `ORJSON`, `uvloop`, HTTP/2 multiplexing, async DNS (non-blocking), 5-min DNS TTL cache. |
| 🧠 **Adaptive SPA Byte Limit** | Auto-detects React, Next.js, Vue, Angular, Nuxt, Svelte, Gatsby, Remix, Astro and expands download to 256 KB for richer data extraction. Static sites stay at 64 KB. |
| 🛡️ **IP-Pinned Anti-SSRF Shield** | DNS resolved once, IP validated against private/loopback/cloud-metadata ranges, connection pinned to IP with TLS SNI. Eliminates DNS Rebinding & Redirect SSRF. |
| 🎯 **Rich SEO & OpenGraph Metadata** | Title, Description, OG Image, OG Type, OG URL, OG Video, Favicon, Canonical URL, Language, Author, Theme Color, Robots directive, hreflang tags, H1 headings, image count. |
| 📧 **Contact Extractor** | Public emails and phone numbers with smart DOM cleaning to eliminate false positives. |
| 📲 **Social Profile Finder** | Auto-detects Twitter/X, LinkedIn, Facebook, Instagram, GitHub, YouTube, Telegram, TikTok. |
| 🛠️ **100+ Tech Stack Detector** | WordPress, Shopify, WooCommerce, Webflow, React, Next.js, Vue, Angular, Svelte, TailwindCSS, Stripe, GA4, and 100+ more. |
| 📦 **Schema.org JSON-LD + Product Parser** | Parses all structured data schemas AND auto-extracts Product price, currency, availability, brand, rating and review count. |
| 📊 **SEO Audit Score** | 8-point automated SEO diagnostic (0–100%) with actionable warnings list. |
| 🔗 **Internal vs External Link Classifier** | Categorizes up to 100 hyperlinks per page. |
| 🤖 **AI & LLM Clean Markdown Reader** | Converts article text to clean Markdown for ChatGPT, Claude, RAG, and AI agents. Includes word count and reading time. |
| 📡 **RSS / Atom Feed Discovery** | Auto-discovers RSS and Atom feed URLs. |
| 🔒 **Security Headers Audit** | HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer Policy, Permissions Policy — with percentage score. |
| 🚀 **15-Min In-Memory Cache** | Cached responses served in **< 0.01 ms** server-side processing time. |

---

## 🎯 Performance SLA & Technical Architecture Notes

> [!NOTE]
> - **Latency & Performance SLA**: Server-side processing overhead (DOM cleaning, C-Lexbor parsing, Rust serialization) averages **< 5ms**. Live execution times depend on the target website's network latency and origin server response time. Repeating requests for the same URL hit the in-memory cache and return in **< 0.01ms**.
> - **Heuristic Technology Signatures**: Technology detection relies on precision context-aware HTML/meta/header signatures. While highly accurate for major frameworks (React, Next.js, WordPress, Shopify), results represent signature detection and not a 100% guarantee against custom-built obfuscated frameworks.
> - **Zero-Trust Self-Hosting Option**: For enterprise production environments requiring zero third-party data transit, this repository provides complete self-hosting assets (Dockerfile, Uvicorn, Python test suite) to run the API inside your own infrastructure.

---


## ⚡ Quick Start

### Python

```python
import requests

url = "https://web-metadata-and-contact-extractor-p.rapidapi.com/api/v1/extract"
headers = {
    "X-RapidAPI-Key": "YOUR_RAPIDAPI_KEY_HERE",
    "X-RapidAPI-Host": "web-metadata-and-contact-extractor-p.rapidapi.com"
}
params = {"url": "https://github.com"}

data = requests.get(url, headers=headers, params=params).json()

print(f"Title:        {data['metadata']['title']}")
print(f"OG Type:      {data['metadata']['og_type']}")
print(f"Robots:       {data['metadata']['robots']}")
print(f"hreflang:     {data['metadata']['hreflang_tags']}")
print(f"Product:      {data['product_data']}")
print(f"Emails:       {data['contacts']['emails']}")
print(f"Tech Stack:   {data['detected_technologies']}")
print(f"Time:         {data['execution_time_ms']} ms")
```

### JavaScript / Node.js

```javascript
const url = 'https://web-metadata-and-contact-extractor-p.rapidapi.com/api/v1/extract?url=https%3A%2F%2Fgithub.com';
const response = await fetch(url, {
  headers: {
    'X-RapidAPI-Key': 'YOUR_RAPIDAPI_KEY_HERE',
    'X-RapidAPI-Host': 'web-metadata-and-contact-extractor-p.rapidapi.com'
  }
});
const data = await response.json();
console.log('Title:', data.metadata.title);
console.log('OG Type:', data.metadata.og_type);
console.log('Product:', data.product_data);
console.log('Time:', data.execution_time_ms, 'ms');
```

### cURL

```bash
curl --request GET \
  --url 'https://web-metadata-and-contact-extractor-p.rapidapi.com/api/v1/extract?url=https%3A%2F%2Fgithub.com' \
  --header 'X-RapidAPI-Host: web-metadata-and-contact-extractor-p.rapidapi.com' \
  --header 'X-RapidAPI-Key: YOUR_RAPIDAPI_KEY_HERE'
```

---

## 📊 Sample API Response (JSON)

```json
{
  "url": "https://github.com",
  "final_url": "https://github.com",
  "status_code": 200,
  "execution_time_ms": 183.72,
  "metadata": {
    "title": "GitHub · Change is constant. GitHub keeps you ahead.",
    "description": "Join the world's most widely adopted AI-powered developer platform.",
    "og_image": "https://github.githubassets.com/assets/campaign-social-04.png",
    "og_type": "website",
    "og_url": "https://github.com/",
    "og_video": null,
    "og_locale_alternate": [],
    "keywords": null,
    "author": null,
    "site_name": "GitHub",
    "language": "en",
    "favicon": "https://github.githubassets.com/favicons/favicon.svg",
    "canonical_url": "https://github.com/",
    "theme_color": null,
    "robots": "index, follow",
    "hreflang_tags": [
      {"lang": "en", "url": "https://github.com/"},
      {"lang": "es", "url": "https://github.com/?locale=es"}
    ],
    "h1_tags": ["The AI-powered developer platform"],
    "images_count": 12,
    "images_missing_alt_count": 2,
    "links_count": 64,
    "content_length_bytes": 65024
  },
  "social_links": {
    "twitter": null, "facebook": null, "instagram": null,
    "linkedin": null, "github": "https://github.com/features/copilot",
    "youtube": null, "telegram": null, "tiktok": null
  },
  "contacts": {"emails": [], "phones": []},
  "detected_technologies": ["Contentful"],
  "product_data": null,
  "rss_feeds": [],
  "json_ld_schemas": [],
  "security_score_percentage": 83.3,
  "seo_score_percentage": 71.4,
  "seo_passed_checks": ["Title tag present", "Meta description present", "Favicon icon present"],
  "seo_warnings": ["Missing canonical tag"],
  "internal_links": ["https://github.com/features", "https://github.com/pricing"],
  "external_links": [],
  "total_internal_count": 50,
  "total_external_count": 9,
  "word_count": 320,
  "reading_time_minutes": 1.6,
  "markdown_content": "# The AI-powered developer platform\n\nGitHub is where..."
}
```

---

## 📖 API Endpoint Documentation

| Endpoint | Method | Description |
|:---|:---|:---|
| `/api/v1/extract` | `GET` | **Full payload** — SEO, contacts, social, tech stack, schema, security, AI markdown, SEO audit, links, product data. Supports `fields` filter. |
| `/api/v1/link-preview` | `GET` | **Social link preview card** — title, description, OG image, favicon, site name, language. |
| `/api/v1/contacts` | `GET` | **Lead enrichment** — public emails, phone numbers, social profiles. |
| `/api/v1/tech-stack` | `GET` | **Framework & CMS detector** — 100+ technology signatures. |
| `/api/v1/schema` | `GET` | **Schema.org JSON-LD parser** — product prices, articles, events, organizations. |
| `/api/v1/security` | `GET` | **Security headers audit** — HSTS, CSP, X-Frame-Options, Referrer Policy with percentage score. |
| `/api/v1/markdown` | `GET` | **AI & LLM Markdown reader** — clean article text, word count, reading time. |
| `/api/v1/seo-audit` | `GET` | **Automated SEO diagnostic** — 8-point audit score with warnings list. |
| `/api/v1/links` | `GET` | **Link classifier** — internal vs external hyperlinks (up to 100 per page). |
| `/health` | `GET` | **Health check** — status, version, protection mode. |

### Query Parameters

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `url` | `string` | **Yes** | Target URL (e.g. `https://example.com`). Scheme-less inputs auto-normalized. |
| `fields` | `string` | No | Comma-separated response filter (e.g. `metadata,contacts`). |
| `user_agent` | `string` | No | Custom User-Agent header string. |

---

## 🔧 Self-Hosting & Local Development

```bash
# 1. Clone
git clone https://github.com/JosejuX/rapidapi-metadata-extractor.git
cd rapidapi-metadata-extractor/rapidapi_service

# 2. Install
pip install -r requirements.txt

# 3. Test suite (14 SSRF vectors + 12 global domains)
python test_api.py

# 4. Load test (concurrent requests benchmark)
python load_test.py

# 5. Dev server
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the interactive Swagger UI.

---

## 🏷️ Keywords

`metadata-extractor` • `opengraph-parser` • `email-scraper` • `contact-extractor` • `social-links-finder` • `tech-stack-detector` • `seo-parser` • `fastapi` • `rapidapi` • `python-web-scraper` • `link-preview-generator` • `lead-generation-api` • `hreflang` • `schema-org` • `product-data-extractor` • `ssrf-protection`

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
