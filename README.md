<div align="center">

  ![Web Metadata & Contact Extractor API](assets/banner.png)

  # 🚀 Web Metadata, OpenGraph & Contact Extractor API

  **Ultra-fast (<200ms) REST API to extract SEO OpenGraph metadata, contact emails, phone numbers, social media profiles, 100+ CMS tech stacks, Schema.org JSON-LD, and Security Headers from any URL.**

  [![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
  [![Rust ORJSON](https://img.shields.io/badge/JSON%20Engine-Rust%20ORJSON-orange.svg)]()
  [![RapidAPI](https://img.shields.io/badge/RapidAPI-Available-0052CC.svg)](https://rapidapi.com/)
  [![Response Time](https://img.shields.io/badge/Response%20Time-%3C200ms-brightgreen.svg)]()
  [![Cache Speed](https://img.shields.io/badge/Cache%20Speed-0.01ms-flash.svg)]()
  [![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

  [🔑 Get Free API Key on RapidAPI](https://rapidapi.com/) • [📖 API Documentation](#-api-documentation) • [⚡ Code Examples](#-code-examples)

</div>

---

## 🌟 Key Features

- ⚡ **Blazing Fast (<200ms)**: Powered by `selectolax` (C-Lexbor parser), Rust `ORJSON` serialization, `uvloop` C-event loop, HTTP/2 multiplexing, and 256KB streaming limits.
- 🎯 **SEO & OpenGraph Metadata**: Instantly retrieves Page Title, Meta Description, OG Image, Keywords, Author, Site Name, Language, Favicon, and `final_url` redirect tracking.
- 📧 **Clean Contact Extractor**: Deep extraction of public email addresses and phone numbers with smart DOM cleaning (`<script>` / `<style>` removal) to eliminate false positives.
- 📲 **Social Profile Finder**: Auto-detects profiles on **Twitter/X, LinkedIn, Facebook, Instagram, GitHub, YouTube, Telegram, and TikTok**.
- 🛠️ **100+ Technology Stack Detector**: Recognizes 100+ CMS, frameworks, analytics, and e-commerce tools (**WordPress, Shopify, WooCommerce, Webflow, Framer, React, Next.js, Vue, Nuxt, Angular, Svelte, TailwindCSS, Stripe, Google Analytics 4**, etc.).
- 📦 **Schema.org JSON-LD Parser**: Parses structured data for e-commerce products (prices, reviews), articles, events, and organizations.
- 🛡️ **HTTP Security Audit**: Audits security headers (HSTS, CSP, X-Frame-Options, Referrer Policy) with automated percentage security scoring.
- 🚀 **Built-in 15-Min In-Memory Cache**: Repeated requests serve in **< 0.01 ms** (10 microseconds) with zero server overhead.


---

## ⚡ Quick Start

### 1. Python Example

```python
import requests

url = "https://web-metadata-and-contact-extractor-p.rapidapi.com/api/v1/extract"
headers = {
    "X-RapidAPI-Key": "YOUR_RAPIDAPI_KEY_HERE",
    "X-RapidAPI-Host": "web-metadata-and-contact-extractor-p.rapidapi.com"
}
params = {"url": "https://github.com"}

response = requests.get(url, headers=headers, params=params)
data = response.json()

print(f"Title: {data['metadata']['title']}")
print(f"Emails: {data['contacts']['emails']}")
print(f"Social Links: {data['social_links']}")
print(f"Execution Time: {data['execution_time_ms']} ms")
```

### 2. JavaScript / Node.js (Fetch) Example

```javascript
const url = 'https://web-metadata-and-contact-extractor-p.rapidapi.com/api/v1/extract?url=https%3A%2F%2Fgithub.com';
const options = {
  method: 'GET',
  headers: {
    'X-RapidAPI-Key': 'YOUR_RAPIDAPI_KEY_HERE',
    'X-RapidAPI-Host': 'web-metadata-and-contact-extractor-p.rapidapi.com'
  }
};

try {
  const response = await fetch(url, options);
  const result = await response.json();
  console.log('Title:', result.metadata.title);
  console.log('Social Links:', result.social_links);
  console.log('Response Time:', result.execution_time_ms, 'ms');
} catch (error) {
  console.error(error);
}
```

### 3. cURL Command

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
  "status_code": 200,
  "execution_time_ms": 185.42,
  "metadata": {
    "title": "GitHub · Change is constant. GitHub keeps you ahead. · GitHub",
    "description": "Join the world's most widely adopted, AI-powered developer platform...",
    "og_image": "https://github.githubassets.com/assets/campaign-social-04.png",
    "keywords": null,
    "author": null,
    "site_name": "GitHub",
    "language": "en",
    "favicon": "https://github.githubassets.com/favicons/favicon.svg"
  },
  "social_links": {
    "twitter": null,
    "facebook": null,
    "instagram": null,
    "linkedin": null,
    "github": "https://github.com/features/copilot",
    "youtube": null,
    "telegram": null,
    "tiktok": null
  },
  "contacts": {
    "emails": [],
    "phones": []
  },
  "detected_technologies": []
}
```

---

## 📖 API Endpoint Documentation

| Endpoint | Method | Category | Description |
| :--- | :--- | :--- | :--- |
| `/api/v1/extract` | `GET` | **Full Extractor** | Complete extraction payload (SEO metadata, contacts, social links, 100+ technologies, schema, security headers). Supports `fields` filter. |
| `/api/v1/link-preview` | `GET` | **Link Preview** | Lightweight payload optimized for social link previews (Title, OG Image, Favicon, Description). |
| `/api/v1/contacts` | `GET` | **Lead Generation** | Targeted lead extraction (Public Emails, Phone Numbers, Social Profiles). |
| `/api/v1/tech-stack` | `GET` | **Tech Stack** | Framework & CMS detector for 100+ technologies (WordPress, Shopify, React, Next.js, Tailwind, etc.). |
| `/api/v1/schema` | `GET` | **Structured Data** | Schema.org JSON-LD parser (Product prices, articles, reviews, events, organization data). |
| `/api/v1/security` | `GET` | **Security Audit** | HTTP security headers auditor (HSTS, CSP, X-Frame-Options, Referrer Policy) with percentage security score. |
| `/health` | `GET` | **Health** | Health check returning API status and version. |

### Query Parameters

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `url` | `string` | **Yes** | The target website URL (e.g. `https://example.com`). |
| `fields` | `string` | No | Optional comma-separated list of keys to filter in response (e.g. `metadata,contacts`). |
| `user_agent` | `string` | No | Custom User-Agent header (optional). |



---

## 🔧 Self-Hosting & Local Development

Want to run the API locally or deploy to Render/Fly.io?

```bash
# 1. Clone the repository
git clone https://github.com/JosejuX/rapidapi-metadata-extractor.git
cd rapidapi-metadata-extractor/rapidapi_service

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run test suite
python test_api.py

# 4. Start local dev server
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000/docs` in your browser for the interactive Swagger UI.

---

## 🏷️ Keywords & Search Topics

`metadata-extractor` • `opengraph-parser` • `email-scraper` • `contact-extractor` • `social-links-finder` • `tech-stack-detector` • `seo-parser` • `fastapi` • `rapidapi` • `python-web-scraper` • `link-preview-generator` • `lead-generation-api`

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
