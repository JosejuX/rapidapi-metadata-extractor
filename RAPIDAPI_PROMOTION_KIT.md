# 🚀 RapidAPI Promotion & Sales Strategy Kit

This document contains step-by-step strategy and copy-paste ready marketing assets to promote the **Web Metadata, OpenGraph & Contact Extractor API** on RapidAPI, developer communities, and social platforms.

---

## 📌 1. RapidAPI Marketplace Listing Optimization

To maximize organic search traffic inside RapidAPI's marketplace search engine, configure your API fields as follows:

### 🔹 Core Info
- **API Name**: `Web Metadata, OpenGraph & Contact Extractor`
- **Short Description**: `Ultra-fast (<200ms) REST API to extract OpenGraph SEO metadata, contact emails, phone numbers, social media profiles, and CMS tech stacks from any URL.`
- **Category**: `Data` / `Tools` / `Web Search` / `SEO`
- **Tags**: `metadata`, `opengraph`, `email-scraper`, `contact-extractor`, `social-links`, `tech-stack`, `link-preview`, `lead-generation`

---

### 🔹 Recommended Pricing Tiers

Configure the **Pricing** tab in RapidAPI using this proven tier structure to maximize free-to-paid conversion:

| Tier | Price / Month | Included Requests | Rate Limit | Primary Audience |
| :--- | :--- | :--- | :--- | :--- |
| **BASIC (Free)** | $0.00 | 100 requests / mo | 5 requests / min | Developer testing & evaluation |
| **PRO** | **$9.00** | 10,000 requests / mo | 60 requests / min | Small startups & indie projects |
| **ULTRA** | **$29.00** | 50,000 requests / mo | 300 requests / min | Production web applications |
| **MEGA** | **$79.00** | 200,000 requests / mo | 1,000 requests / min | Enterprise B2B & high-volume scrapers |

> 💡 **Conversion Tip**: Set a reasonable overage fee (e.g. `$0.002` per extra request) on paid tiers to capture upside revenue without hard-blocking active users.

---

## 📝 2. Article Templates for Dev.to / Medium / Hashnode

Publishing hands-on technical tutorials solves real developer problems and drives high-intent API subscribers.

### 📰 Article 1: Link Previews
**Title**: *How to Build a High-Performance Link Preview Component (Like WhatsApp) in Python/JS*

**Article Content**:
```markdown
Have you ever wondered how apps like WhatsApp, Slack, or Telegram generate instant rich card previews when you share a link?

Instead of spending hours writing complex HTML scrapers and handling edge cases, you can build a lightweight link preview generator in under 2 minutes.

### The Solution: Web Metadata API

We'll use the ultra-fast **Web Metadata Extractor API** on RapidAPI.

#### 1. JavaScript / Node.js Implementation

```javascript
async function getLinkPreview(targetUrl) {
  const endpoint = `https://web-metadata-and-contact-extractor-p.rapidapi.com/api/v1/link-preview?url=${encodeURIComponent(targetUrl)}`;
  
  const response = await fetch(endpoint, {
    headers: {
      'X-RapidAPI-Key': 'YOUR_RAPIDAPI_KEY',
      'X-RapidAPI-Host': 'web-metadata-and-contact-extractor-p.rapidapi.com'
    }
  });

  const preview = await response.json();
  return {
    title: preview.title,
    description: preview.description,
    image: preview.og_image,
    icon: preview.favicon
  };
}

// Example usage
getLinkPreview('https://github.com').then(console.log);
```

#### Why use this API?
- ⚡ **Sub-200ms Response Times** (powered by C-Lexbor HTML parsing)
- 🚀 **Built-in In-Memory Cache** (sub-0.1ms repeat requests)
- 🔑 **Get 100 free requests/month on RapidAPI**

👉 [Get your free API key on RapidAPI here](https://rapidapi.com/)
```

---

### 📰 Article 2: Lead Generation & Contact Enrichment
**Title**: *Automating B2B Prospecting: Extract Public Emails and Social Handles from Any Domain*

**Article Content**:
```markdown
When building B2B lead enrichment pipelines, gathering public emails, telephone numbers, and official social media profiles from company websites is a critical step.

Here is how you can automate domain contact extraction using Python:

```python
import requests

def extract_domain_contacts(domain_url):
    api_url = "https://web-metadata-and-contact-extractor-p.rapidapi.com/api/v1/contacts"
    headers = {
        "X-RapidAPI-Key": "YOUR_RAPIDAPI_KEY",
        "X-RapidAPI-Host": "web-metadata-and-contact-extractor-p.rapidapi.com"
    }
    response = requests.get(api_url, headers=headers, params={"url": domain_url})
    return response.json()

data = extract_domain_contacts("https://stripe.com")
print("Emails found:", data["emails"])
print("Social Profiles:", data["social_links"])
```

Features:
- Automatic script/style DOM cleaning to eliminate false positive email matches.
- Multi-platform social detection: Twitter/X, LinkedIn, Facebook, Instagram, GitHub, YouTube, Telegram, TikTok.

👉 [Try the Lead Contacts Extractor API on RapidAPI](https://rapidapi.com/)
```

---

## 💬 3. Social Media & Community Launch Posts

### 🔴 Reddit Post - `r/SideProject` / `r/webdev`
**Title**: *I built an ultra-fast (<200ms) Web Metadata & Contact Extractor API in FastAPI (Selectolax + HTTP/2)*

**Post Body**:
> Hi everyone! 👋
> 
> I recently published a lightweight API designed to extract OpenGraph SEO metadata, public emails/phones, social links, and tech stack signatures from any webpage.
> 
> **Why I built it**: Most existing scrapers are either bloat-heavy (Selenium/Puppeteer) or too slow. I built this using FastAPI, Selectolax (C-Lexbor parser), and HTTP/2 multiplexed streaming to hit **<200ms average response times** and **<0.1ms cache responses**.
> 
> **Endpoints available**:
> - `/api/v1/link-preview` - Lightweight payload for rich preview cards.
> - `/api/v1/contacts` - B2B lead enrichment (emails, phones, socials).
> - `/api/v1/tech-stack` - CMS & framework detection (WordPress, Shopify, React, Next.js, etc.).
> - `/api/v1/extract` - Full extraction payload.
> 
> Feel free to test it with a free tier on RapidAPI: [Link]
> 
> Would love your feedback!

---

### 🐦 Twitter / X Post
> ⚡ Build rich WhatsApp-style link previews or extract domain contact emails in 1 line of code.
> 
> Introducing the Web Metadata & Contact Extractor API on @Rapid_API!
> 
> 🚀 <200ms execution
> 📦 Built-in caching
> 🔑 Free tier available
> 
> 🔗 Try it out: https://rapidapi.com/
> 
> #buildinpublic #python #fastapi #indiehackers

---

## ⚡ 4. Low-Code / No-Code Integration Setup (n8n / Make / Bubble)

Many API subscribers build automated workflows using No-Code platforms.

### 🔷 n8n HTTP Request Node Setup
- **Method**: `GET`
- **URL**: `https://web-metadata-and-contact-extractor-p.rapidapi.com/api/v1/extract`
- **Query Parameters**: `url` = `{{ $json.website_url }}`
- **Headers**:
  - `X-RapidAPI-Key`: `YOUR_RAPIDAPI_KEY`
  - `X-RapidAPI-Host`: `web-metadata-and-contact-extractor-p.rapidapi.com`

---

## 📈 5. Weekly Promotional Checklist

- [ ] Publish the API listing with the 4 categorized sub-endpoints on RapidAPI.
- [ ] Publish 1 technical article on **Dev.to** (Link Preview Tutorial).
- [ ] Post 1 launch showcase on **Reddit** (`r/SideProject`).
- [ ] Share on Twitter/X with `#buildinpublic` and `#api` hashtags.
- [ ] Submit to **Indie Hackers** under the *Products* section.
