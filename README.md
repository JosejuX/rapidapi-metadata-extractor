<div align="center">

  ![Web Metadata & Contact Extractor API](assets/banner.png)

  # 🚀 Web Metadata, OpenGraph & Contact Extractor API

  **Ultra-fast (<200ms) REST API to extract SEO metadata, contacts, social profiles, tech stack, Schema.org JSON-LD, Security Headers, and AI-ready Markdown from any URL.**

  [![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
  [![Version](https://img.shields.io/badge/Version-4.0.0-blueviolet.svg)]()
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
| 📧 **Contact Extractor** | Public emails and phone numbers with smart DOM cleaning to eliminate false positives. Phones are additionally normalized (`phone_details`) via libphonenumber — E.164 format, ISO country code, and possible/valid flags — for numbers that include a country code; numbers without one aren't guessed. |
| 📲 **Social Profile Finder** | Auto-detects Twitter/X, LinkedIn, Facebook, Instagram, GitHub, YouTube, Telegram, TikTok. |
| 🛠️ **100+ Tech Stack Detector** | WordPress, Shopify, WooCommerce, Webflow, React, Next.js, Vue, Angular, Svelte, TailwindCSS, Stripe, GA4, and 100+ more. |
| 📦 **Schema.org JSON-LD + Product Parser** | Parses all structured data schemas AND auto-extracts Product price, currency, availability, brand, rating and review count. |
| 🎯 **Multi-Source Data Quality & Conflict Detection** | Product price/currency/availability/brand are cross-checked across three distinct structured encodings — JSON-LD, OpenGraph's product extension, and schema.org Microdata. `product_field_confidence` reports a per-field confidence score (more of these encodings agreeing = higher confidence, same philosophy as tech-stack detection) and which source won. When they genuinely disagree, a `SOURCE_CONFLICT` warning names the field, every value found, and which one was chosen and why. A top-level `quality` object (`score`, `rendered: false`, `sources_used`, `warnings`) summarizes response trustworthiness for programmatic consumers. **Caveat**: these three encodings often come from the same underlying product record on a given site, so agreement means "internally consistent," not "independently verified" — see Honest Limitations below. |
| 📊 **On-Page SEO Health Audit Score** | 13-point automated on-page technical SEO diagnostic (0–100%) with actionable warnings list, plus a structured `seo_checks` breakdown (`check` id, `passed`, `severity`, `evidence`) for programmatic use. |
| 🔗 **Internal vs External Link Classifier** | Categorizes up to 100 hyperlinks per page. |
| 🤖 **AI & LLM Clean Markdown Reader** | Converts article text to clean Markdown for ChatGPT, Claude, RAG, and AI agents. Includes word count and reading time. |
| 📡 **RSS / Atom Feed Discovery** | Auto-discovers RSS and Atom feed URLs. |
| 🔒 **Graded Security Headers Audit** | HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer Policy, Permissions Policy — each graded `missing`/`weak`/`reasonable`/`strong` from its actual value (e.g. a CSP with `unsafe-inline` scores as weak, not as "present = full credit"), not just presence, rolled into the percentage score. `/api/v1/security` additionally returns `security_header_grades` with the per-header breakdown. |
| 🚀 **15-Min In-Memory Cache** | Cached responses served in **< 0.01 ms** server-side processing time. |
| ⚡ **4x Workers + Auto-Reconnect Redis** | Gunicorn multi-process cluster. Distributed rate limiting via Redis with startup ping validation, automatic reconnect every 30s, and immediate `degraded_fallback` status propagation to `/health/details`. |
| 🔒 **Split `/health` + `/health/details`** | Minimal public liveness probe (`/health`). Full operational details (Redis mode, status, engine) secured via `HEALTH_DETAILS_SECRET` header on `/health/details`. |
| 🧯 **Per-Host Circuit Breaker** | Trips after repeated timeouts/connection failures/5xx to one host, fails fast during the cooldown window instead of burning the full connect+read timeout budget on every request, and probes recovery automatically (never trips on ordinary 4xx). |
| 🧩 **Request Single-Flight + DNS Coalescing** | Concurrent requests for the same URL (or the same hostname's DNS lookup) share one in-flight fetch instead of hammering the origin N times. |
| 🩹 **Negative-Result Cache** | Short-TTL caching of recent upstream failures (DNS/timeout/5xx) so a broken target fails fast instead of repeating the same slow failure for every request during an outage. |
| 🧱 **Adaptive Byte-Limit Hardening** | Streaming byte cap is enforced on the *decoded* chunk, closing a decompression-bomb gap where a small gzip/br payload could otherwise expand to megabytes in a single read. Response headers are also count- and size-bounded. |
| 🏷️ **Structured Error Codes** | Every error response carries a machine-readable `error.code` / `error.retryable` object (e.g. `SSRF_BLOCKED`, `UPSTREAM_TIMEOUT`, `CIRCUIT_OPEN`) alongside the existing `detail` string — fully additive, v1 contract unchanged. |
| 📈 **Prometheus Metrics + Structured JSON Logs** | `/metrics` exposes request/cache/SSRF/circuit-breaker/rate-limit counters and latency histograms. Every log line is a JSON object with `request_id` for end-to-end tracing; known-sensitive fields are redacted automatically. |
| 🧠 **Confidence-Scored Tech Detection** | `/api/v1/tech-stack` now also returns `technology_details`: per-technology confidence score, matched evidence, and category (cms/ecommerce/framework/analytics/payment/hosting/…), alongside the original flat list. |
| 📦 **Deeper Product & JSON-LD Parsing** | Traverses `@graph` and top-level JSON-LD arrays (not just top-level objects), extracting SKU, MPN, GTIN/ISBN, seller, condition, price range, and images. |
| 🔎 **Unicode-Aware SEO & Keywords** | Keyword extraction now matches non-ASCII scripts correctly (accented/Cyrillic/etc. content), and the SEO audit adds `lang` attribute, viewport, noindex, multi-H1, Twitter Card, and structured-data checks. |
| ⚡ **Lazy Extraction Per Endpoint** | Specialized endpoints only run the extractors they actually need instead of the full pipeline — `/security` never even parses the HTML tree, `/tech-stack` skips links/metadata/markdown/SEO entirely. `/api/v1/extract` runs the complete pipeline by default, but `?fields=` now maps to the same narrow extraction as the matching specialized endpoint (`fields=detected_technologies` costs exactly what `/tech-stack` costs) instead of computing everything and filtering the response afterward. Results for different endpoints (or `fields=` combinations) hitting the same URL share one upstream fetch and accumulate into the same cache entry. |
| 🐘 **Mastodon Social Detection** | Best-effort detection of the largest public Mastodon instances (mastodon.social, fosstodon.org, hachyderm.io, ...) alongside the existing 20 platforms — decentralization means a hostname map can't cover every self-hosted instance, so this is intentionally partial rather than a false-positive risk. |
| 🚦 **Rate-Limit Response Headers** | Every response (success or `429`) now carries `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`, so clients can back off proactively instead of learning the limit by hitting `429`. |
| 🛡️ **Bot-Protection Detection** | Cheap heuristic signature check (no extra requests, no JS execution) flags when the fetched page is a Cloudflare/Akamai/PerimeterX/CAPTCHA challenge page rather than real content — either as `bot_protection_detected: true` on a normal response, or as a specific `BOT_PROTECTION_DETECTED` error code (instead of a generic upstream error) when the challenge is served with a 403/429/503 status. Distinguishes "the target blocked this request" from "the target genuinely has no title/description" or "a real outage". |

---

## 🎯 Performance SLA & Technical Architecture Notes

> [!NOTE]
> - **Latency & Performance SLA**: Server-side processing overhead (DOM cleaning, C-Lexbor parsing, Rust serialization) averages **< 5ms**. Live execution times depend on the target website's network latency and origin server response time. Repeating requests for the same URL hit the in-memory cache and return in **< 0.01ms**.
> - **IPv6 & IPv4-Mapped SSRF Shield**: The Anti-SSRF validation engine enforces strict resolution checks across both IPv4 and IPv6, blocking loopback (`127.0.0.1`, `::1`), link-local (`169.254.169.254`, `fe80::/10`), and IPv4-mapped IPv6 (`::ffff:127.0.0.1`) addresses.
> - **Redis Rate Limiter (Fixed-Window, Auto-Reconnect)**: When `REDIS_URL` is configured, rate limiting is distributed across all workers via a single atomic Redis Lua script (`INCR` + first-hit `EXPIRE` in one round-trip — no window where a dropped connection could leave a counter with no TTL). Redis is pinged at startup and re-validated every 30 seconds. On failure, the service falls back to per-process TTLCache immediately and marks `redis_status: degraded_fallback` in `/health/details`.
> - **Split Health Endpoints**: `/health` returns a minimal public liveness payload. `/health/details` returns full operational status (Redis mode, trust_proxy, engine) and requires the `X-Health-Secret` header when `HEALTH_DETAILS_SECRET` env var is set.
> - **Horizontal Scaling**: Single-instance → in-memory TTLCache (60 req/min/IP). Multi-worker → distributed Redis. Enterprise scale → RapidAPI Gateway or Nginx.
> - **Zero-Trust Self-Hosting**: Full Dockerfile, Gunicorn config, and test suite included for self-hosted production deployments.
> - **Modular Codebase**: The service is organized as an `app/` package (`security/`, `fetcher/`, `cache/`, `ratelimit/`, `extraction/`, `observability/`, `api/`) rather than a single file — `main.py` is a thin backward-compatibility shim so `uvicorn main:app` / `gunicorn main:app` keep working unchanged.
> - **Validated Configuration**: `app/config.py` is backed by `pydantic-settings` — every tunable (rate limits, cache sizes/TTLs, byte-fetch limits, header limits, ...) is validated at startup with the exact same defaults as before, and now opportunistically overridable via env vars. An invalid value (negative sizes, `STREAM_SOFT_LIMIT` above `STREAM_HARD_LIMIT`, ...) fails immediately with a clear error instead of surfacing as a runtime bug later.
> - **Lazy Extraction**: `/api/v1/extract` with no `fields=` runs the full pipeline. Specialized endpoints — and `/api/v1/extract?fields=...` — instead run only their required extractor groups — e.g. `/api/v1/security` skips HTML parsing entirely (headers-only), `/api/v1/tech-stack` skips metadata/links/markdown/SEO. Calling two different specialized endpoints (or field selections) for the same URL shares one upstream fetch and merges into one cache entry.
> - **Tech Signature Prefiltering**: Each of the 100+ technology signatures is gated by a cheap substring check against a once-lowercased copy of the page before its regex ever runs, instead of running every regex unconditionally — same detection output, substantially less CPU on pages with many `<script>` tags.
> - **Observability**: `GET /metrics` exposes Prometheus counters and latency histograms (requests, cache hit/miss, SSRF blocks, circuit-breaker trips, rate limiting, bytes downloaded, etc.) — open by default (standard Prometheus practice) but gate-able behind `METRICS_SECRET`/`X-Metrics-Secret` if you're self-hosting with the port exposed to the internet and no reverse-proxy rule in front of it. All application logs are single-line JSON with a `request_id` shared with the `X-Request-ID` response header, for correlating a request across logs and metrics.
> - **Property-Based Fuzz Testing**: Hypothesis-driven tests generate hundreds of adversarial inputs per run against URL normalization, the SSRF IP-safety classification (every IPv4/IPv6 address, not just a fixed list), and every extractor that runs on attacker-controlled page content — asserting they never crash and the SSRF logic never lets a dangerous address through. This found and fixed two real bugs: a crafted `url=[` query string could trigger an unhandled 500, and the embedded-credentials check (`user:pass@host`) could be bypassed by omitting the URL scheme.
> - **Real-World Accuracy Benchmark**: `benchmarks/bench_accuracy.py` runs the real pipeline against a hand-curated, independently-verified sample of 29 live URLs across ecommerce/news/blogs/SaaS/SPA/WordPress/multilingual/small/bot-protected sites — see `benchmarks/README_ACCURACY.md` for methodology and honest limitations. The first real run scored 61%: Brotli-compressed responses (common on modern CDN-fronted sites) were silently passed through undecoded and force-decoded as UTF-8, with **no error raised anywhere** — `app/fetcher/client.py` advertised `Accept-Encoding: br` but the decoder package wasn't installed. Adding `brotli` to `requirements.txt` fixed it with no other code change; the same 29-URL run now scores 100%, 0 unexpected errors.

---

## 🎯 What This API Is — And Isn't — For

This API turns **a URL into structured knowledge about that page**: SEO/OpenGraph metadata, public contact signals, social profiles, tech stack, Schema.org/product data, graded security headers, link classification, and clean Markdown — consolidated into one fast HTTP request. It's a metadata/intelligence layer over ordinary server-rendered HTML, not a general-purpose scraping tool or a browser-automation replacement. Keep that framing in mind when deciding whether it fits your use case.

**✅ Good fit:**

- **Company/website analysis** — pull tech stack, CMS, socials, contact signals, and SEO health for a given site in one call.
- **Input for a sales/outreach workflow** — `/api/v1/contacts` finds public emails/phones/social links present on a page; it's a raw signal you feed into a lead-gen process you build (company identification, role verification, CRM enrichment), not a lead-enrichment product by itself — see "Honest Limitations" below.
- **Automated SEO audits** — the 13-point on-page score, structured `seo_checks` breakdown, and graded security-header audit are built for exactly this.
- **Competitive/tech-stack monitoring** — compare tech stack, metadata, or product data across a known set of URLs over time. You supply and re-check the URL list; there's no built-in crawler (see below).
- **AI agents / RAG pipelines** — `markdown_content` and the structured JSON fields are designed as clean LLM input, not raw HTML soup.
- **E-commerce data extraction** — product name/price/currency/availability/brand/SKU/reviews where a site exposes Schema.org JSON-LD, OpenGraph product tags, or Microdata, cross-checked with a per-field confidence score. Product responses use a short 3-minute cache specifically because price data goes stale faster than everything else.
- **Link previews** — title, description, image, favicon for chat apps, social cards, and bookmarking tools.

**❌ Not a good fit:**

- **Complex/interactive scraping** — logins, multi-step forms, button clicks, infinite scroll, CAPTCHA-gated content. This API issues one HTTP GET and parses the HTML it gets back; it does not drive a browser or simulate user interaction.
- **Heavily JS-rendered sites** — if the meaningful content only exists after client-side hydration, this API sees close to the same empty shell a plain HTTP client would. The adaptive byte limit improves coverage of what the server already sent; it doesn't execute JavaScript.
- **Mass or distributed crawling** — there's no queue, frontier, or "give me a domain and I'll find its pages" mode. It's one URL in, one page's data out, by design — kept stateless and fast rather than growing into a crawler.
- **Penetration testing or vulnerability scanning** — the security-header audit grades the *presence and quality* of headers like HSTS, CSP, and X-Frame-Options. It does not probe for vulnerabilities, scan for misconfigurations beyond those headers, or constitute a security assessment. A high `security_score` means "this page sends good security headers," not "this site is secure."
- **"Extract anything from any site" scraping** — this is a fixed set of well-defined extractors (SEO, contacts, socials, tech, product, links, Markdown), not a programmable scraper for arbitrary custom fields or page structures.

For the technical reasoning behind these boundaries — why JS execution, crawling, and bot-protection bypass are out of scope, and what the confidence/quality scores do and don't mean — see "Honest Limitations" below.

---

## ⚠️ Honest Limitations

This API fetches raw HTTP responses and parses HTML — it is **not a browser**. That's a deliberate trade-off for speed (no browser startup, no JS execution wait, minimal memory per request), and it comes with real ceilings that no amount of additional regex or extractors can fully remove:

- **No JavaScript execution.** Content that only exists after client-side rendering (many SPAs, some login-gated pages, content behind "load more" interactions) will be missing or incomplete. A static/SSR page (most blogs, e-commerce product pages, marketing sites, GitHub, Wikipedia) works great; a client-rendered single-page app whose initial HTML is just `<div id="root"></div>` will return mostly empty results — the API cannot execute the JS that would fill it in.
- **Detecting a JS framework doesn't mean the JS problem is solved.** The adaptive byte limit (see below) expanding to 256 KB when React/Next.js/Vue/etc. signatures are spotted improves *coverage* of the initial HTML — it does not run a browser, execute hydration, or wait for client-side API calls. `Next.js -> more bytes -> a bigger parse` is not `Next.js -> Chromium -> JS execution -> hydration -> final DOM`. Treat it as "we tried harder to read what the server already sent," not "we solved SPAs."
- **Bot-protection / CAPTCHAs are detected, not bypassed.** `bot_protection_detected` (see above) tells you *that* Cloudflare/Akamai/PerimeterX/a CAPTCHA blocked the request — it does not solve the challenge. There is no workaround for this short of running a real browser.
- **Extraction is heuristic evidence, not ground truth — including when it looks confident.** Technology detection, contact info, social links, and product data are pattern/signature-based. A tech signature match (e.g. one CDN hostname in an image URL) proves the string was present somewhere the fetcher looked, not that the technology is meaningfully *in use* — it could be dead code, a shared/third-party asset, a transitive dependency, or an accidental substring. `technology_details.confidence` reflects how many independent signals agreed, not a probability that the detection is correct. See the live GitHub example above, where `"Contentful"` is detected at `0.75` confidence from a single CDN hostname in an `og:image` URL — plausible evidence, not proof GitHub runs on Contentful.
- **A `quality.score` near 1.0 means the *evidence available to this API* was internally consistent — not that the data is verified accurate.** When JSON-LD, OpenGraph, and Microdata all report the same price, that's three *encodings*, not necessarily three *independent* sources — a site frequently generates all three from the same underlying product record, so agreement can mean "one data source, expressed three ways" rather than three independently-verified facts. Read `confidence: 0.98` as "nothing on the page contradicts this," not "there's a 98% chance this is correct."
- **The adaptive 64/256 KB byte limit is a real trade-off, not just a performance knob.** It's what keeps typical requests fast, but it means content positioned late in a large page — JSON-LD placed near the closing `</body>`, a product block far down a long CMS-generated page — can be missed purely because of *where* it sits in the HTML, independent of how "complex" the page seems. Larger/more script-heavy pages are paradoxically more likely to have relevant data pushed past the cutoff. Always check `content_truncated` before treating a missing field as "this page doesn't have it" rather than "this API didn't read that far."
- **Markdown conversion is not semantic understanding.** `markdown_content` is a reasonably clean HTML→Markdown conversion, not a "read and understand what's actually the article" model — it doesn't reliably distinguish primary content from navigation, related-content widgets, paywalled teasers, or boilerplate on every layout.
- **The cache trades freshness for speed, and that trade-off matters more for some fields than others.** A 15-minute-stale `<title>` is harmless; a 15-minute-stale price is not — which is why product-bearing responses get a separate, much shorter TTL (`PRODUCT_CACHE_TTL_SECONDS`, 3 minutes by default) rather than sharing the general 15-minute cache. Everything else still follows the general TTL: don't build a real-time price-monitoring product directly on the general cache path without accounting for that window.
- **Arbitrary URL fetching is inherently unreliable**, independent of this API: pages can be slow, redirect repeatedly, be enormous, block automated clients, have TLS quirks, serve different content by geography/User-Agent, be temporarily down, or return unexpected status codes. SSRF protections, timeouts, redirect limits, byte caps, and the circuit breaker (see above) bound the damage but can't make an unreliable target reliable.
- **"~150–300ms" describes the live-fetch network leg, not a ceiling on total response time.** Server-side processing genuinely is single-digit milliseconds (see the benchmark methodology in `benchmarks/`), but the *live* end-to-end time is dominated by however long the target site takes to respond — if the target takes 2.5s, so does your request. Don't read the headline numbers as "this API responds in 200ms regardless of target."
- **There is no crawler.** The unit of work is one URL in, one page's data out — not "give me a domain and I'll discover/prioritize/crawl its pages for you." `/api/v1/links` classifies up to 100 hyperlinks *on the page you gave it*; it doesn't follow them. Analyzing a whole site (homepage + `/about` + `/pricing` + `/blog`, deduplicated, prioritized, crawled) is something you'd orchestrate externally, one `/extract` call per URL — this project deliberately doesn't grow a queue/worker/crawl-frontier system into what's meant to stay a fast, stateless per-request API.
- **`/api/v1/contacts` finds public contact *signals*, not company or people intelligence.** It returns emails/phones/social links it found in the page's HTML — it does not identify who those belong to, their role, or verify anything. Turning `website -> public contact signals` into real lead enrichment (`domain -> company identification -> people -> roles -> verification -> confidence`) is out of scope here; the endpoint is intentionally named/tagged "Contact Discovery," not "Lead Enrichment," to avoid implying more than it does.
- **Prefer the specific endpoint over `/api/v1/extract` — or use `fields=`.** `/extract` without `fields` runs the complete pipeline. `/extract?fields=detected_technologies` now runs exactly the same narrow extraction as `GET /api/v1/tech-stack` (and shares its cache entry) — `fields` genuinely skips unneeded work rather than computing everything and filtering afterward.
- **This project's API surface is still evolving.** New fields ship frequently (`quality`, `product_field_confidence`, `bot_protection_detected`, and others were all added recently) — additive changes only, existing fields never change type (see the versioning notes below), but if you're integrating deeply, treat the live `/openapi.json` schema as the source of truth over any single README snippet, which can lag by a commit or two.

None of this means the underlying approach is flawed for its intended job (fast metadata/SEO/contact/tech extraction from ordinary web pages) — it means "extract everything from any URL via one HTTP request" has a ceiling that only browser automation (Playwright/Puppeteer) can raise, at the cost of the speed and low resource footprint that make this API fast in the first place.

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

> [!NOTE]
> This is **real, live output** from `GET /api/v1/extract?url=https://github.com`, captured 2026-08-10 — not a hand-edited illustration. It's deliberately left un-prettified, including the parts that aren't flattering: `detected_technologies` includes `"Contentful"` on a page that almost certainly isn't Contentful-powered (see `technology_details` below — the evidence is one CDN hostname in an `og:image` URL, hence only `0.75` confidence, not `0.98`), and `markdown_content`/`word_count` come back empty because GitHub's homepage is a JS-heavy shell whose initial HTML has no `<article>`-like content for this API to find. Both are the "Honest Limitations" section below in action, not this example glossing over them.

```json
{
  "url": "https://github.com",
  "final_url": "https://github.com",
  "status_code": 200,
  "execution_time_ms": 481.95,
  "bot_protection_detected": false,
  "metadata": {
    "title": "GitHub · Change is constant. GitHub keeps you ahead. · GitHub",
    "description": "Join the world's most widely adopted, AI-powered developer platform where millions of developers, businesses, and the largest open source community build software that advances humanity.",
    "og_image": "https://images.ctfassets.net/8aevphvgewt8/4pe4eOtUJ0ARpZRE4fNekf/f52b1f9c52f059a33170229883731ed0/GH-Homepage-Universe-img.png",
    "og_type": "object",
    "canonical_url": "https://github.com",
    "language": "en",
    "favicon": "https://github.githubassets.com/favicons/favicon.svg",
    "theme_color": "#1e2327",
    "hreflang_tags": [
      {"lang": "en-us", "url": "https://github.com"},
      {"lang": "es-419", "url": "https://github.com?locale=es-419"}
    ],
    "h1_tags": [],
    "links_count": 52,
    "content_length_bytes": 110509
  },
  "social_links": { "github": "https://github.com/features/copilot", "twitter": null, "linkedin": null, "...": "17 more platforms, all null here" },
  "contacts": { "emails": [], "phones": [] },
  "detected_technologies": ["Contentful"],
  "technology_details": [
    { "name": "Contentful", "confidence": 0.75, "evidence": ["ctfassets.net"], "category": "cms" }
  ],
  "product_data": null,
  "quality": {
    "score": 0.85,
    "rendered": false,
    "sources_used": ["meta"],
    "warnings": [{ "field": null, "type": "CONTENT_TRUNCATED" }]
  },
  "rss_feeds": ["https://github.com/opensearch.xml"],
  "json_ld_schemas": [],
  "security_score_percentage": 64.2,
  "seo_score_percentage": 75.0,
  "seo_passed_checks": ["Title tag present with optimal length (10-70 chars)", "Canonical link tag present", "Favicon icon present", "HTTPS secure protocol active"],
  "seo_warnings": ["Meta description present but sub-optimal length (186 chars)", "Missing <h1> primary heading", "No structured data (JSON-LD) found"],
  "internal_links": ["https://github.com/", "https://github.com/login", "https://github.com/features/copilot"],
  "total_internal_count": 50,
  "total_external_count": 9,
  "word_count": 0,
  "reading_time_minutes": 0.0,
  "markdown_content": "",
  "content_truncated": true,
  "bytes_downloaded": 146437
}
```

> Since v4.0.0, `metadata` also includes `viewport`, `twitter_card`, and `h1_count`; `/api/v1/tech-stack` additionally returns `technology_details` (confidence score, matched evidence, category per technology); and `product_data` (when present) includes `sku`, `mpn`, `gtin`/`isbn`, `seller`, `condition`, and price-range fields. All additions are purely additive — no existing field was removed or changed type. Fields that were previously untyped `Dict`/`List[Dict]` blobs (`metadata`, `technology_details`, `seo_checks`, `phone_details`) now have documented Pydantic models in the OpenAPI schema — with `product_data`, previously missing from `/api/v1/extract` despite being shown here, now actually returned. Also new: `product_field_confidence` and a top-level `quality` object — e.g. for a page where JSON-LD says €39.99 and OpenGraph says €29.99: `"product_field_confidence": {"price": {"value": "39.99", "confidence": 0.5, "source": "json_ld", "agreement": ["json_ld", "microdata", "opengraph"]}}` and `"quality": {"score": 0.9, "rendered": false, "sources_used": ["json_ld", "microdata", "opengraph", "meta"], "warnings": [{"field": "product.price", "type": "SOURCE_CONFLICT", "values": {"json_ld": "39.99", "microdata": "39.99", "opengraph": "29.99"}, "chosen_source": "json_ld", "chosen_value": "39.99"}]}`.

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
| `/api/v1/seo-audit` | `GET` | **Automated SEO diagnostic** — 13-point audit score with warnings list plus structured `checks` (severity/evidence per check). |
| `/api/v1/links` | `GET` | **Link classifier** — internal vs external hyperlinks (up to 100 per page). |
| `/health` | `GET` | **Health check** — status, version, protection mode. |
| `/health/details` | `GET` | **Operational health** — Redis mode/status, trust-proxy config. Requires `X-Health-Secret` if `HEALTH_DETAILS_SECRET` is set. |
| `/health/ready` | `GET` | **Readiness probe** — 200 once the HTTP client is initialized, 503 during startup. |
| `/metrics` | `GET` | **Prometheus scrape target** — request/cache/SSRF/circuit-breaker/rate-limit counters and latency histograms. Open by default (protect at the network/proxy level, standard Prometheus practice) — set `METRICS_SECRET` to require an `X-Metrics-Secret` header instead, if you're self-hosting with the port reachable from the internet and no network-level control in front of it. Hidden from the public OpenAPI schema. |

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

# 3. Fixture-based test suite (SSRF matrix, circuit breaker, single-flight, rate-limit atomicity, ...)
pip install pytest
pytest tests/ -q

# 3b. Live-network smoke suite (14 SSRF vectors + 12 global domains)
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

## 🤝 Built With

This API was built and iterated on in collaboration with AI coding assistants — Google's **Gemini 3.6 Flash** and Anthropic's **Claude Sonnet 5** — alongside human design, review, and testing decisions throughout.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
