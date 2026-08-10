# 🚀 Deployment & Monetization Guide — v2.6.0

This guide explains how to deploy the **Web Metadata & Contact Extractor API** at $0 cost and connect it to **RapidAPI** for passive income.

---

## STEP 1: Test the API Locally

```bash
cd rapidapi_service
pip install -r requirements.txt

# Run full test suite (14 SSRF vectors + 12 global domains)
python test_api.py

# Interactive dev server
uvicorn main:app --reload --port 8000
# → Open http://localhost:8000/docs for Swagger UI

# Optional: run the load test benchmark
python load_test.py
```

---

## STEP 2: Free 24/7 Hosting

### Option A: Render.com (Recommended)

1. Push this repo to GitHub.
2. Create a **Web Service** on [Render.com](https://render.com).
3. Connect your GitHub repo and configure:
   - **Build Command**: `pip install -r rapidapi_service/requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Root Directory**: `rapidapi_service`
4. Render provides a free HTTPS URL like `https://your-api.onrender.com`.

### Option B: Fly.io

```bash
cd rapidapi_service
fly launch --name web-metadata-api
fly deploy
```

### Option C: Local Tunnel (Termux + Cloudflare)

```bash
# In Termux
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# Expose publicly
cloudflared tunnel --url http://localhost:8000
```

---

## STEP 3: Critical Environment Variables

Set these in your hosting panel (**Render → Environment → Add Variable**):

| Variable | Required | Description |
|:---|:---|:---|
| `RAPIDAPI_PROXY_SECRET` | **YES** | Secret token from RapidAPI. Blocks all direct backend access without it. |
| `TRUST_PROXY` | No | Set `true` if behind Render/Fly.io reverse proxy to use real client IP in rate limiter. Default: `false`. |
| `WORKERS` | No | Number of Uvicorn workers. Default `1` (free tier). Set `4` on paid plans for higher throughput. |
| `ALLOWED_ORIGINS` | No | Comma-separated list of allowed CORS origins. Default `*` — safe for a public API keyed by header/API-key (no cookies). Set a fixed list only if you're self-hosting for a known set of frontends. |

**Verify protection is active:**
```bash
curl https://your-api.onrender.com/health
# Must return: "rapidapi_protected": true
```

### Advanced (optional) tuning

Everything below has a sane default and doesn't need to be set. All of it is
validated at startup via pydantic-settings — an invalid value (e.g. a
negative rate limit, or `STREAM_SOFT_LIMIT` set above `STREAM_HARD_LIMIT`)
fails immediately with a clear error instead of surfacing as a confusing
runtime bug later.

| Variable | Default | Description |
|:---|:---|:---|
| `RATE_LIMIT_PER_MINUTE` | `60` | Requests/minute per client IP. |
| `CACHE_TTL_SECONDS` | `900` | How long extraction results stay cached. |
| `PRODUCT_CACHE_TTL_SECONDS` | `180` | Shorter cache TTL specifically for responses whose `product_data` includes a price — a stale price is a worse problem than a stale `<title>`. |
| `CACHE_MAXSIZE` | `5000` | Max number of cached URLs (L1, in-process). |
| `MAX_REDIRECTS` | `5` | Redirect hops followed before giving up. |
| `STREAM_SOFT_LIMIT` / `STREAM_HARD_LIMIT` | `65536` / `262144` | Adaptive byte-fetch limits (bytes) — see the Adaptive SPA Byte Limit feature. |
| `MAX_CONCURRENT_REQUESTS_PER_HOST` | `6` | Outbound concurrency cap per target host. |
| `TRUSTED_PROXY_IPS` | *(empty)* | Comma-separated CIDRs allowed to set `X-Forwarded-For` when `TRUST_PROXY=true`. |
| `REDIS_URL` | *(unset)* | Enables distributed rate limiting across workers when set. |
| `METRICS_SECRET` | *(unset)* | If set, `/metrics` requires an `X-Metrics-Secret` header matching it. Leave unset if `/metrics` is only reachable on a private network — set it if the port is exposed to the internet with no proxy-level protection in front of it. |

---

## STEP 4: Publish & Monetize on RapidAPI

1. Go to **RapidAPI Hub** → **My APIs** → **Add New API**.
2. Set **Base URL** to your Render/Fly.io HTTPS URL.
3. On **Definition → Security**, enable **Transformation → Add Secret Header**:
   - **Header Name**: `X-RapidAPI-Proxy-Secret`
   - Copy the generated value into your `RAPIDAPI_PROXY_SECRET` environment variable.
4. Configure **Monetization** plans:
   - **FREE ($0/mo)**: 100 requests/month — honest evaluation limit.
   - **STARTER ($4.99/mo)**: 5,000 requests/month + $0.0015/extra req.
   - **GROWTH ($19.99/mo)**: 30,000 requests/month + $0.0012/extra req.
   - **SCALE ($59.99/mo)**: 120,000 requests/month + $0.0008/extra req.
5. Click **Publish to Hub**.

---

## STEP 5: Scaling Notes

| Scenario | Action |
|:---|:---|
| Free tier (0–1K req/day) | `WORKERS=1` — default, no changes needed. |
| Paid tier (1K–10K req/day) | `WORKERS=4` — set in Render environment. |
| Multi-instance (10K+ req/day) | Add **Redis** for shared cache across instances. |

---

## 💰 Payouts

RapidAPI charges end-users automatically and transfers your earnings to **PayPal** or **Stripe Payouts** at the end of each billing cycle.
