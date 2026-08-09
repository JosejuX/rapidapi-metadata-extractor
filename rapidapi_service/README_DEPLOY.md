# 🚀 Deployment and Monetization Guide for RapidAPI

This step-by-step guide explains how to deploy your **Web Metadata & Contact Extractor API** for $0 cost and connect it to **RapidAPI** to start earning passive income.

---

## STEP 1: Test the API Locally

You can test the API on your machine immediately:

```bash
cd rapidapi_service
python -m pip install -r requirements.txt
python test_api.py
```

To launch the interactive dev server:
```bash
python -m uvicorn main:app --reload --port 8000
```
Open `http://localhost:8000/docs` in your browser to view the interactive OpenAPI / Swagger UI.

---

## STEP 2: Free 24/7 Hosting (Choose One Option)

To connect your API to RapidAPI, you need a 24/7 publicly accessible HTTPS URL.

### Option A: Free Cloud Hosting (Render.com / Fly.io) - RECOMMENDED
No reliance on local hardware or home Wi-Fi:
1. Create a free account at **[Render.com](https://render.com)**.
2. Push this repository to GitHub.
3. In Render, create a **Web Service**, connect your GitHub repo, and configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Render will provide a free HTTPS URL like `https://web-metadata-extractor-api.onrender.com`.

### Option B: Android Device / Local Tunnel (Termux + Cloudflare)
1. Copy the `rapidapi_service` folder to Termux.
2. Install dependencies: `pip install -r requirements.txt`.
3. Start the server: `uvicorn main:app --host 0.0.0.0 --port 8000`.
4. Use a free tunnel tool like **Cloudflare Tunnel (`cloudflared`)** or **ngrok** to get a public HTTPS URL:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
   *(Cloudflare generates a public URL like `https://your-subdomain.trycloudflare.com`)*.

---

## STEP 3: Publish and Monetize on RapidAPI.com

1. **Create a Developer Account**:
   - Register at **[RapidAPI.com](https://rapidapi.com)**.
   - Go to **My APIs** -> **Add New API**.

2. **Configure API Details**:
   - **API Name**: `Web Metadata, OpenGraph & Contact Extractor`
   - **Category**: `Data` / `SEO` / `Tools`
   - **Base URL**: Enter your public server URL (e.g. `https://web-metadata-extractor-api.onrender.com`).

3. **Configure Security (Prevent Unpaid Usage)**:
   - On RapidAPI, enable the **Secret Header** setting. RapidAPI will generate a token like `sec_abc123...`.
   - Set the environment variable `RAPIDAPI_PROXY_SECRET=sec_abc123...` on your deployment host (e.g., Render Environment Variables).
   - Your API will automatically reject any request not routed through paying RapidAPI clients.

4. **Set Up Pricing Plans (Monetization)**:
   On the **Monetization** tab in RapidAPI, define your 4-tier pricing structure designed for maximum conversion:
   - **FREE ($0 / mo)**: 500 requests / month (~16/day) - Hard cap (honest evaluation & side-projects).
   - **STARTER ($5 / mo)**: 5,000 requests / month + $0.0015 per extra req (indie hackers & personal live apps).
   - **GROWTH ($19 / mo)**: 30,000 requests / month + $0.0012 per extra req (startups & production SaaS).
   - **SCALE ($59 / mo)**: 120,000 requests / month + $0.0008 per extra req (business platforms & high volume).


5. **Publish**:
   Click **Publish to Hub**.

---

## 💰 Receiving Payouts

RapidAPI charges end-user credit cards and automatically transfers your earnings to your **PayPal** or **Bank Account (Stripe Payouts)** at the end of each billing cycle.
