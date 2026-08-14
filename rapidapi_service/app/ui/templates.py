"""
Embedded playground UI (Plan section 68: separate UI from API — moved out of
main.py into its own module as a first step; still served inline rather than
from static files/CDN, which is a later follow-up).

Calls /demo/extract (app/api/demo.py) — a same-origin route that runs the
real pipeline with no RapidAPI secret required, gated only by the shared
per-IP rate limiter. Every value rendered here comes from a live response,
not sample data.
"""

HOME_HTML = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Web Metadata & Contact Extractor API — Live Demo</title>
        <meta name="description" content="Turn any URL into structured data: SEO metadata, contacts, tech stack, security headers &amp; AI-ready Markdown in one fast REST call. Free tier, no card required.">
        <meta name="robots" content="index, follow">
        <meta name="google-site-verification" content="2u6zsBi7uQUAV0BGbX2PUiOpniskmBuRLoUdqkyx34I" />
        <link rel="canonical" href="https://rapidapi-metadata-extractor.onrender.com/">
        <link rel="icon" type="image/png" href="https://rapidapi-metadata-extractor.onrender.com/assets/logo.png">
        <link rel="apple-touch-icon" href="https://rapidapi-metadata-extractor.onrender.com/assets/logo.png">

        <meta property="og:type" content="website">
        <meta property="og:site_name" content="Web Metadata & Contact Extractor API">
        <meta property="og:url" content="https://rapidapi-metadata-extractor.onrender.com/">
        <meta property="og:title" content="Web Metadata & Contact Extractor API — Live Demo">
        <meta property="og:description" content="Turn any URL into structured data: SEO metadata, contacts, tech stack, security headers &amp; AI-ready Markdown in one fast REST call. Free tier, no card required.">
        <meta property="og:image" content="https://rapidapi-metadata-extractor.onrender.com/assets/logo.png">
        <meta property="og:image:width" content="500">
        <meta property="og:image:height" content="500">
        <meta property="og:image:type" content="image/png">
        <meta property="og:locale" content="en_US">

        <meta name="twitter:card" content="summary">
        <meta name="twitter:title" content="Web Metadata & Contact Extractor API — Live Demo">
        <meta name="twitter:description" content="Turn any URL into structured data: SEO metadata, contacts, tech stack, security headers & AI-ready Markdown in one fast REST call.">
        <meta name="twitter:image" content="https://rapidapi-metadata-extractor.onrender.com/assets/logo.png">

        <script type="application/ld+json" nonce="__CSP_NONCE__">
        {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "Web Metadata & Contact Extractor API",
            "description": "Turn any URL into structured data: SEO metadata, contacts, tech stack, security headers and AI-ready Markdown in one fast REST call.",
            "url": "https://rapidapi-metadata-extractor.onrender.com/",
            "applicationCategory": "DeveloperApplication",
            "operatingSystem": "Any (REST API)",
            "image": "https://rapidapi-metadata-extractor.onrender.com/assets/logo.png",
            "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "USD"
            },
            "author": {
                "@type": "Person",
                "name": "Juanjo Renau"
            },
            "sameAs": [
                "https://github.com/JosejuX/rapidapi-metadata-extractor",
                "https://rapidapi.com/josejuanjocoding/api/web-metadata-and-contact-extractor"
            ]
        }
        </script>
        <style nonce="__CSP_NONCE__">
            :root {
                --bg: #09080f;
                --bg-blob-a: rgba(167, 139, 250, 0.16);
                --bg-blob-b: rgba(34, 211, 238, 0.12);
                --surface: #14111f;
                --surface-2: #100d1a;
                --border: #2a2740;
                --text: #f2effa;
                --muted: #a79fc2;
                --muted-2: #726b8f;

                --violet: #a78bfa;
                --cyan: #22d3ee;
                --cyan-soft: #0e2b34;
                --amber: #fbbf24;
                --amber-soft: #2e2410;
                --pink: #f472b6;
                --pink-soft: #331b29;
                --emerald: #34d399;
                --emerald-soft: #0f2b22;

                --good: #34d399;
                --warn: #fbbf24;
                --bad: #fb7185;
                --bad-soft: #331820;

                --shadow: 0 1px 2px rgba(0, 0, 0, 0.4), 0 16px 40px -18px rgba(0, 0, 0, 0.7);
                --mono: ui-monospace, "SFMono-Regular", "JetBrains Mono", Consolas, "Liberation Mono", Menlo, monospace;
                --sans: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }
            * { box-sizing: border-box; }
            html, body { height: 100%; }
            body {
                margin: 0;
                background: var(--bg);
                color: var(--text);
                font-family: var(--sans);
                -webkit-font-smoothing: antialiased;
                line-height: 1.5;
                position: relative;
                overflow-x: hidden;
            }
            .bg-blob { position: fixed; width: 46vmax; height: 46vmax; border-radius: 50%; filter: blur(80px); z-index: 0; pointer-events: none; }
            .bg-blob.a { top: -18vmax; left: -14vmax; background: var(--bg-blob-a); }
            .bg-blob.b { bottom: -20vmax; right: -16vmax; background: var(--bg-blob-b); }

            .shell { position: relative; z-index: 1; max-width: 800px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }

            .eyebrow { display: inline-flex; align-items: center; gap: 0.45rem; font-family: var(--mono); font-size: 0.72rem; letter-spacing: 0.09em; text-transform: uppercase; color: var(--muted-2); margin: 0 0 0.75rem; }
            .pulse-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--good); box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.6); animation: pulse 2s ease-out infinite; }
            @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.55); } 70% { box-shadow: 0 0 0 7px rgba(52, 211, 153, 0); } 100% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); } }

            h1 {
                font-family: var(--mono); font-weight: 700; font-size: clamp(1.7rem, 5vw, 2.35rem); letter-spacing: -0.015em;
                margin: 0 0 0.6rem;
                background: linear-gradient(100deg, var(--violet) 0%, var(--cyan) 55%, var(--pink) 100%);
                -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
            }
            .sub { color: var(--muted); font-size: 1rem; max-width: 58ch; margin: 0; }

            .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; box-shadow: var(--shadow); }
            .input-card { margin-top: 1.6rem; padding: 1.15rem 1.15rem 1.3rem; }
            .input-row { display: flex; gap: 0.6rem; }
            .url-field { flex: 1; display: flex; align-items: center; gap: 0.55rem; background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px; padding: 0 0.9rem; min-width: 0; }
            .url-field svg { flex: none; color: var(--muted-2); }
            input#urlInput { flex: 1; border: none; background: transparent; outline: none; color: var(--text); font-family: var(--mono); font-size: 0.94rem; padding: 0.72rem 0; min-width: 0; }
            input#urlInput::placeholder { color: var(--muted-2); }

            button.analyze { font-family: var(--sans); font-weight: 700; font-size: 0.92rem; color: #0b0715; background: linear-gradient(120deg, var(--violet), var(--cyan)); border: none; border-radius: 10px; padding: 0 1.3rem; cursor: pointer; transition: filter 0.15s ease, transform 0.05s ease; }
            button.analyze:hover { filter: brightness(1.1); }
            button.analyze:active { transform: scale(0.97); }
            button.analyze:disabled { opacity: 0.6; cursor: progress; }
            button.analyze:focus-visible, .chip:focus-visible, .action-btn:focus-visible { outline: 2px solid var(--cyan); outline-offset: 2px; }

            .chips { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.85rem; }
            .chips .label { font-size: 0.78rem; color: var(--muted-2); align-self: center; margin-right: 0.15rem; }
            .chip { display: inline-flex; align-items: center; gap: 0.4rem; font-family: var(--mono); font-size: 0.8rem; background: var(--surface-2); color: var(--muted); border: 1px solid var(--border); border-radius: 999px; padding: 0.34rem 0.8rem 0.34rem 0.65rem; cursor: pointer; transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease; }
            .chip .dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
            .chip:hover { color: var(--text); border-color: var(--chip-color, var(--violet)); }

            #loading { display: none; align-items: center; gap: 0.65rem; padding: 1.1rem 1.15rem; color: var(--muted); font-family: var(--mono); font-size: 0.88rem; margin-top: 1.15rem; }
            .spinner { width: 15px; height: 15px; border-radius: 50%; border: 2px solid var(--border); border-top-color: var(--cyan); animation: spin 0.7s linear infinite; flex: none; }
            @keyframes spin { to { transform: rotate(360deg); } }

            #error { display: none; margin-top: 1.15rem; padding: 1rem 1.15rem; border-radius: 14px; background: var(--bad-soft); border: 1px solid color-mix(in srgb, var(--bad) 40%, var(--border)); color: var(--text); font-size: 0.9rem; }
            #error b { color: var(--bad); }

            #results { margin-top: 1.15rem; display: none; }
            .res-meta { display: flex; justify-content: space-between; align-items: center; padding: 0.9rem 1.15rem; border-bottom: 1px solid var(--border); gap: 0.75rem; flex-wrap: wrap; }
            .res-meta .final-url { font-family: var(--mono); font-size: 0.85rem; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
            .res-meta .right { display: flex; gap: 0.6rem; align-items: center; font-family: var(--mono); font-size: 0.8rem; }
            .status-ok { background: var(--emerald-soft); color: var(--good); border-radius: 6px; padding: 0.2rem 0.55rem; font-weight: 700; }
            .exec-time { color: var(--muted-2); }

            .score-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 1px; background: var(--border); }
            .score-card { background: var(--surface); padding: 1.05rem 1.05rem 1.1rem; display: flex; flex-direction: column; gap: 0.5rem; opacity: 0; transform: translateY(6px); animation: rise 0.4s ease forwards; }
            @keyframes rise { to { opacity: 1; transform: translateY(0); } }
            .score-card .k { font-size: 0.72rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted-2); }

            .ring-row { display: flex; align-items: center; gap: 0.85rem; }
            .ring-wrap { position: relative; width: 58px; height: 58px; flex: none; }
            .ring-wrap svg { width: 100%; height: 100%; transform: rotate(-90deg); }
            .ring-wrap .track { fill: none; stroke: var(--border); stroke-width: 9; }
            .ring-wrap .fill { fill: none; stroke-width: 9; stroke-linecap: round; transition: stroke-dashoffset 0.7s cubic-bezier(.2,.8,.2,1); }
            .ring-wrap .ring-num { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-family: var(--mono); font-weight: 700; font-size: 0.92rem; font-variant-numeric: tabular-nums; }
            .ring-caption { font-size: 0.8rem; color: var(--muted); }

            .tile-row { display: flex; align-items: center; gap: 0.85rem; }
            .tile-num { width: 58px; height: 58px; flex: none; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-family: var(--mono); font-weight: 700; font-size: 1.35rem; font-variant-numeric: tabular-nums; background: var(--tile-soft, var(--surface-2)); color: var(--tile-color, var(--text)); border: 1px solid color-mix(in srgb, var(--tile-color, var(--border)) 35%, var(--border)); }
            .tile-caption { font-size: 0.8rem; color: var(--muted); }

            .detail-block { padding: 1.15rem; border-top: 1px solid var(--border); }
            .detail-block h3 { font-family: var(--mono); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted-2); margin: 0 0 0.6rem; font-weight: 700; }
            .meta-title { font-weight: 700; font-size: 1.02rem; margin: 0 0 0.3rem; }
            .meta-desc { color: var(--muted); font-size: 0.9rem; margin: 0; }
            .block-caption { color: var(--muted); font-size: 0.85rem; margin: -0.3rem 0 0.85rem; }
            .block-caption code { font-family: var(--mono); background: var(--surface-2); border: 1px solid var(--border); border-radius: 4px; padding: 0.03rem 0.32rem; font-size: 0.82rem; color: var(--text); }

            .code-label { display: flex; justify-content: space-between; align-items: center; font-family: var(--mono); font-size: 0.7rem; color: var(--muted-2); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }

            .tag-row { display: flex; flex-wrap: wrap; gap: 0.45rem; }
            .tag { font-family: var(--mono); font-size: 0.78rem; border-radius: 7px; padding: 0.3rem 0.6rem; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); }
            .tag.muted { color: var(--muted-2); border-style: dashed; }
            .tag.conf { color: var(--muted-2); font-size: 0.7rem; margin-left: 0.35rem; }
            a.tag { text-decoration: none; }
            a.tag:hover { border-color: var(--cyan); color: var(--cyan); }

            .kv-list { display: flex; flex-direction: column; gap: 0.5rem; }
            .kv-row { display: flex; gap: 0.9rem; align-items: baseline; font-size: 0.87rem; }
            .kv-label { color: var(--muted-2); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; min-width: 108px; flex: none; }
            .kv-value { color: var(--text); word-break: break-word; }
            .kv-value.muted { color: var(--muted-2); }
            .kv-value a { color: var(--cyan); }

            .check-row { display: flex; gap: 0.6rem; align-items: flex-start; padding: 0.32rem 0; font-size: 0.85rem; border-bottom: 1px solid var(--border); }
            .check-row:last-child { border-bottom: none; }
            .check-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 0.45rem; flex: none; }
            .check-dot.good { background: var(--good); }
            .check-dot.warn { background: var(--warn); }
            .check-dot.bad { background: var(--bad); }
            .check-text { color: var(--text); flex: 1; }
            .check-sev { font-family: var(--mono); font-size: 0.66rem; color: var(--muted-2); text-transform: uppercase; white-space: nowrap; margin-top: 0.15rem; }

            .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 1.3rem; }
            .two-col > div { min-width: 0; }
            @media (max-width: 560px) { .two-col { grid-template-columns: 1fr; } }
            .link-list { display: flex; flex-direction: column; gap: 0.3rem; margin-top: 0.5rem; min-width: 0; }
            .link-item { display: block; max-width: 100%; min-width: 0; font-family: var(--mono); font-size: 0.78rem; color: var(--muted); text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
            .link-item:hover { color: var(--cyan); }

            .md-preview { font-family: var(--mono); font-size: 0.8rem; color: var(--muted); background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem; max-height: 280px; overflow: auto; overflow-wrap: break-word; white-space: pre-wrap; }

            .badge { display: inline-flex; align-items: center; gap: 0.35rem; font-family: var(--mono); font-size: 0.78rem; padding: 0.28rem 0.65rem; border-radius: 7px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); }
            .badge.good { color: var(--good); border-color: color-mix(in srgb, var(--good) 40%, var(--border)); }
            .badge.bad { color: var(--bad); border-color: color-mix(in srgb, var(--bad) 40%, var(--border)); }
            .badge.warn { color: var(--warn); border-color: color-mix(in srgb, var(--warn) 40%, var(--border)); }

            .actions { display: flex; gap: 0.6rem; padding: 1.05rem 1.15rem; border-top: 1px solid var(--border); flex-wrap: wrap; }
            .action-btn { font-family: var(--sans); font-size: 0.85rem; font-weight: 700; color: var(--text); background: var(--surface-2); border: 1px solid var(--border); border-radius: 9px; padding: 0.58rem 0.95rem; cursor: pointer; display: inline-flex; align-items: center; gap: 0.4rem; transition: border-color 0.15s ease, color 0.15s ease; }
            .action-btn:hover { border-color: var(--violet); color: var(--violet); }

            .json-panel { border-top: 1px solid var(--border); display: none; }
            .json-panel.open { display: block; }
            .json-panel pre { margin: 0; padding: 1.15rem; font-family: var(--mono); font-size: 0.78rem; line-height: 1.55; color: var(--text); background: var(--surface-2); overflow: auto; max-height: 420px; white-space: pre; }

            footer { margin-top: 1.85rem; font-size: 0.8rem; color: var(--muted-2); text-align: center; line-height: 1.6; }
            footer a { color: var(--cyan); }
            footer code { font-family: var(--mono); background: var(--surface-2); border: 1px solid var(--border); border-radius: 5px; padding: 0.05rem 0.35rem; }
            .footer-links { display: flex; align-items: center; justify-content: center; gap: 1.1rem; margin-top: 0.85rem; }
            .gh-link { display: inline-flex; align-items: center; gap: 0.4rem; color: var(--text) !important; }
            .gh-link:hover { color: var(--cyan) !important; }

            @media (max-width: 480px) { .input-row { flex-direction: column; } button.analyze { padding: 0.75rem; } }
        </style>
    </head>
    <body>
        <div class="bg-blob a"></div>
        <div class="bg-blob b"></div>

        <div class="shell">
            <p class="eyebrow"><span class="pulse-dot"></span>Live demo — no signup required</p>
            <h1>Turn any URL into structured intelligence.</h1>
            <p class="sub">Extract SEO, technologies, contacts, products, social profiles, security signals and AI-ready content from any public website — with one API call.</p>

            <div class="panel input-card">
                <div class="input-row">
                    <div class="url-field">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                        <input type="url" id="urlInput" value="https://buffer.com" placeholder="Enter a URL, e.g. https://example.com">
                    </div>
                    <button class="analyze" id="analyzeBtn" type="button">Analyze</button>
                </div>
                <div class="chips">
                    <span class="label">Quick presets:</span>
                    <button class="chip" type="button" style="--chip-color:#f472b6" data-url="https://buffer.com"><span class="dot" style="background:#f472b6"></span>buffer.com</button>
                    <button class="chip" type="button" style="--chip-color:#22d3ee" data-url="https://techcrunch.com"><span class="dot" style="background:#22d3ee"></span>techcrunch.com</button>
                    <button class="chip" type="button" style="--chip-color:#fbbf24" data-url="https://basecamp.com"><span class="dot" style="background:#fbbf24"></span>basecamp.com</button>
                </div>
            </div>

            <div id="loading"><span class="spinner"></span><span>Fetching and analyzing the page in real time…</span></div>
            <div id="error"></div>

            <div class="panel" id="results">
                <div class="res-meta">
                    <span class="final-url" id="resUrl"></span>
                    <span class="right">
                        <span class="status-ok" id="resStatus">200 OK</span>
                        <span class="exec-time" id="resTime"></span>
                    </span>
                </div>

                <div class="score-grid" id="scoreGrid"></div>

                <div class="detail-block">
                    <h3>Metadata</h3>
                    <p class="meta-title" id="metaTitle"></p>
                    <p class="meta-desc" id="metaDesc"></p>
                    <div class="kv-list" id="metaKv" style="margin-top: 0.75rem"></div>
                </div>

                <div class="detail-block">
                    <h3>SEO audit — 14-point check</h3>
                    <div id="seoChecks"></div>
                </div>

                <div class="detail-block">
                    <h3>Technologies</h3>
                    <div class="tag-row" id="techRow"></div>
                </div>

                <div class="detail-block">
                    <h3>Social profiles</h3>
                    <div class="tag-row" id="socialRow"></div>
                </div>

                <div class="detail-block">
                    <h3>Contacts</h3>
                    <div class="tag-row" id="contactsRow"></div>
                </div>

                <div class="detail-block">
                    <h3>Links on this page</h3>
                    <div class="two-col">
                        <div>
                            <div class="kv-row"><span class="kv-label">Internal</span><span class="kv-value" id="internalCount"></span></div>
                            <div class="link-list" id="internalLinks"></div>
                        </div>
                        <div>
                            <div class="kv-row"><span class="kv-label">External</span><span class="kv-value" id="externalCount"></span></div>
                            <div class="link-list" id="externalLinks"></div>
                        </div>
                    </div>
                </div>

                <div class="detail-block">
                    <h3>Structured data &amp; feeds</h3>
                    <div class="kv-list" id="structuredKv"></div>
                </div>

                <div class="detail-block">
                    <h3>AI-ready content</h3>
                    <p class="block-caption">This is <code>markdown_content</code> exactly as the API returns it — raw Markdown meant to be fed to an LLM or RAG pipeline, not rendered HTML. The <code>#</code>/<code>##</code> symbols are intentional.</p>
                    <div class="kv-list" id="aiKv" style="margin-bottom: 0.75rem"></div>
                    <div class="code-label"><span>markdown_content</span><span id="mdCharCount"></span></div>
                    <div class="md-preview" id="mdPreview"></div>
                </div>

                <div class="detail-block">
                    <h3>Data quality &amp; signals</h3>
                    <div class="tag-row" id="qualityRow"></div>
                </div>

                <div class="actions">
                    <button class="action-btn" id="viewJsonBtn" type="button">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
                        <span id="viewJsonLabel">View JSON</span>
                    </button>
                    <button class="action-btn" id="copyBtn" type="button">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                        <span id="copyLabel">Copy API request</span>
                    </button>
                </div>

                <div class="json-panel" id="jsonPanel"><pre id="jsonPre"></pre></div>
            </div>

            <footer>
                Live extraction — every result above is real, fetched when you click Analyze. No signup for this demo.<br>
                Production usage requires a RapidAPI key: <code>X-RapidAPI-Key</code> · <a href="https://rapidapi.com/josejuanjocoding/api/web-metadata-and-contact-extractor/pricing" target="_blank" rel="noopener noreferrer">get one free →</a>
                <div class="footer-links">
                    <a class="gh-link" href="https://github.com/JosejuX/rapidapi-metadata-extractor" target="_blank" rel="noopener noreferrer">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg>
                        <span>View source on GitHub</span>
                    </a>
                </div>
            </footer>
        </div>

        <script nonce="__CSP_NONCE__">
            let lastData = null;

            function clearChildren(el) { while (el.firstChild) el.removeChild(el.firstChild); }

            function mutedSpan(text) {
                const span = document.createElement('span');
                span.className = 'tag muted';
                span.textContent = text;
                return span;
            }

            // Only ever assign http(s) URLs to href — blocks javascript:/data:
            // and other script-executing schemes from a scraped page's links.
            function isSafeHttpUrl(value) {
                try {
                    const u = new URL(value, window.location.href);
                    return u.protocol === 'http:' || u.protocol === 'https:';
                } catch {
                    return false;
                }
            }

            function kvRow(container, label, value) {
                const row = document.createElement('div'); row.className = 'kv-row';
                const l = document.createElement('span'); l.className = 'kv-label'; l.textContent = label;
                const v = document.createElement('span'); v.className = 'kv-value'; v.textContent = value;
                row.appendChild(l); row.appendChild(v);
                container.appendChild(row);
            }

            function badge(text, tone) {
                const b = document.createElement('span');
                b.className = 'badge' + (tone ? ' ' + tone : '');
                b.textContent = text;
                return b;
            }

            function checkRow(check) {
                const row = document.createElement('div'); row.className = 'check-row';
                const dot = document.createElement('span');
                const tone = check.passed ? 'good' : (check.severity === 'critical' ? 'bad' : check.severity === 'important' ? 'warn' : 'bad');
                dot.className = 'check-dot ' + tone;
                const text = document.createElement('span'); text.className = 'check-text'; text.textContent = check.evidence;
                const sev = document.createElement('span'); sev.className = 'check-sev'; sev.textContent = check.severity;
                row.appendChild(dot); row.appendChild(text); row.appendChild(sev);
                return row;
            }

            // Link hrefs come straight from an arbitrary scraped page — same
            // safe-scheme allowlist as socials, never assigned unchecked.
            function buildLinkList(container, urls, max, { clear = true } = {}) {
                if (clear) clearChildren(container);
                (urls || []).slice(0, max).forEach((u) => {
                    const a = document.createElement('a');
                    a.className = 'link-item';
                    if (isSafeHttpUrl(u)) a.setAttribute('href', u);
                    a.target = '_blank';
                    a.rel = 'noopener noreferrer';
                    a.textContent = u;
                    container.appendChild(a);
                });
                if (!(urls || []).length) container.appendChild(mutedSpan('None found'));
            }

            function scoreTone(pct) {
                if (pct >= 80) return 'good';
                if (pct >= 50) return 'warn';
                return 'bad';
            }

            const RING_CIRC = 2 * Math.PI * 42;
            const TONE_COLOR = { good: 'var(--good)', warn: 'var(--warn)', bad: 'var(--bad)' };

            function ringCard(label, pct, caption) {
                const tone = scoreTone(pct);
                const color = TONE_COLOR[tone];
                const offset = RING_CIRC * (1 - pct / 100);

                const card = document.createElement('div');
                card.className = 'score-card';
                const k = document.createElement('div'); k.className = 'k'; k.textContent = label;

                const row = document.createElement('div'); row.className = 'ring-row';
                const wrap = document.createElement('div'); wrap.className = 'ring-wrap';
                const svgNS = 'http://www.w3.org/2000/svg';
                const svg = document.createElementNS(svgNS, 'svg');
                svg.setAttribute('viewBox', '0 0 100 100');
                const track = document.createElementNS(svgNS, 'circle');
                track.setAttribute('class', 'track'); track.setAttribute('cx', '50'); track.setAttribute('cy', '50'); track.setAttribute('r', '42');
                const fillC = document.createElementNS(svgNS, 'circle');
                fillC.setAttribute('class', 'fill'); fillC.setAttribute('cx', '50'); fillC.setAttribute('cy', '50'); fillC.setAttribute('r', '42');
                fillC.setAttribute('stroke', color);
                fillC.setAttribute('stroke-dasharray', RING_CIRC.toFixed(1));
                fillC.setAttribute('stroke-dashoffset', RING_CIRC.toFixed(1));
                svg.appendChild(track); svg.appendChild(fillC);
                const num = document.createElement('div'); num.className = 'ring-num'; num.style.color = color; num.textContent = Math.round(pct);
                wrap.appendChild(svg); wrap.appendChild(num);

                requestAnimationFrame(() => requestAnimationFrame(() => { fillC.setAttribute('stroke-dashoffset', offset.toFixed(1)); }));

                const capWrap = document.createElement('div');
                const cap = document.createElement('div'); cap.className = 'ring-caption'; cap.textContent = caption;
                capWrap.appendChild(cap);
                row.appendChild(wrap); row.appendChild(capWrap);
                card.appendChild(k); card.appendChild(row);
                return card;
            }

            function tileCard(label, value, colorVar, softVar, caption) {
                const card = document.createElement('div');
                card.className = 'score-card';
                const k = document.createElement('div'); k.className = 'k'; k.textContent = label;
                const row = document.createElement('div'); row.className = 'tile-row';
                const tile = document.createElement('div');
                tile.className = 'tile-num';
                tile.style.setProperty('--tile-color', colorVar);
                tile.style.setProperty('--tile-soft', softVar);
                tile.textContent = value;
                const capWrap = document.createElement('div');
                const cap = document.createElement('div'); cap.className = 'tile-caption'; cap.textContent = caption;
                capWrap.appendChild(cap);
                row.appendChild(tile); row.appendChild(capWrap);
                card.appendChild(k); card.appendChild(row);
                return card;
            }

            function setUrl(url) {
                document.getElementById('urlInput').value = url;
                analyzeUrl();
            }

            document.querySelectorAll('.chip').forEach((chip) => {
                chip.addEventListener('click', () => setUrl(chip.dataset.url));
            });
            document.getElementById('analyzeBtn').addEventListener('click', analyzeUrl);
            document.getElementById('urlInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') analyzeUrl(); });

            document.getElementById('viewJsonBtn').addEventListener('click', () => {
                const panel = document.getElementById('jsonPanel');
                const open = panel.classList.toggle('open');
                document.getElementById('viewJsonLabel').textContent = open ? 'Hide JSON' : 'View JSON';
            });

            document.getElementById('copyBtn').addEventListener('click', () => {
                if (!lastData) return;
                const host = (lastData.url || '').replace(/^https?:\\/\\//, '');
                const cmd = 'curl "https://web-metadata-and-contact-extractor.p.rapidapi.com/api/v1/extract?url=' + host + '" \\\\\\n' +
                    '  -H "X-RapidAPI-Key: YOUR_KEY" -H "X-RapidAPI-Host: web-metadata-and-contact-extractor.p.rapidapi.com"';
                const done = () => {
                    const label = document.getElementById('copyLabel');
                    label.textContent = 'Copied!';
                    setTimeout(() => { label.textContent = 'Copy API request'; }, 1500);
                };
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(cmd).then(done).catch(() => fallbackCopy(cmd, done));
                } else {
                    fallbackCopy(cmd, done);
                }
            });

            function fallbackCopy(text, done) {
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.select();
                try { document.execCommand('copy'); done(); } catch (e) {}
                document.body.removeChild(ta);
            }

            async function analyzeUrl() {
                const url = document.getElementById('urlInput').value;
                if (!url) return;

                document.getElementById('analyzeBtn').disabled = true;
                document.getElementById('loading').style.display = 'flex';
                document.getElementById('results').style.display = 'none';
                document.getElementById('error').style.display = 'none';

                try {
                    const res = await fetch(`/demo/extract?url=${encodeURIComponent(url)}`);
                    const data = await res.json();

                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('analyzeBtn').disabled = false;

                    if (!res.ok) {
                        const errBox = document.getElementById('error');
                        clearChildren(errBox);
                        const b = document.createElement('b'); b.textContent = `Request failed (${res.status}): `;
                        const span = document.createElement('span'); span.textContent = data.detail || 'Unknown error.';
                        errBox.appendChild(b); errBox.appendChild(span);
                        errBox.style.display = 'block';
                        return;
                    }

                    lastData = data;
                    document.getElementById('results').style.display = 'block';

                    document.getElementById('resUrl').textContent = data.final_url || data.url;
                    document.getElementById('resStatus').textContent = `${data.status_code} OK`;
                    document.getElementById('resTime').textContent = `⚡ ${data.execution_time_ms} ms`;

                    const techList = data.detected_technologies || [];
                    const socialEntries = Object.entries(data.social_links || {}).filter(([, v]) => v);
                    const contactsCount = (data.contacts.emails || []).length + (data.contacts.phones || []).length;
                    const hasProduct = !!data.product_data;
                    const seo = data.seo_score_percentage;
                    const sec = data.security_score_percentage;

                    const grid = document.getElementById('scoreGrid');
                    clearChildren(grid);
                    grid.appendChild(ringCard('SEO', seo, seo >= 80 ? 'Strong on-page SEO' : seo >= 50 ? 'Room to improve' : 'Weak on-page SEO'));
                    grid.appendChild(tileCard('Technologies', techList.length, 'var(--cyan)', 'var(--cyan-soft)', techList.length ? techList.slice(0, 2).join(', ') : 'None matched'));
                    grid.appendChild(tileCard('Product data', hasProduct ? '✓' : '—', hasProduct ? 'var(--emerald)' : 'var(--muted-2)', hasProduct ? 'var(--emerald-soft)' : 'var(--surface-2)', hasProduct ? 'Schema.org / OG product' : 'Not a product page'));
                    grid.appendChild(tileCard('Social', socialEntries.length, 'var(--pink)', 'var(--pink-soft)', socialEntries.length ? socialEntries.map(([n]) => n).slice(0, 3).join(', ') : 'No profiles linked'));
                    grid.appendChild(tileCard('Contacts', contactsCount, 'var(--amber)', 'var(--amber-soft)', contactsCount ? 'Public email/phone found' : 'None on this page'));
                    grid.appendChild(ringCard('Security', sec, sec >= 80 ? 'Strong headers' : sec >= 50 ? 'Some headers missing' : 'Weak security headers'));
                    Array.from(grid.querySelectorAll('.score-card')).forEach((card, i) => { card.style.animationDelay = (i * 45) + 'ms'; });

                    document.getElementById('metaTitle').textContent = data.metadata.title || 'Not detected';
                    document.getElementById('metaDesc').textContent = data.metadata.description || 'Not detected';
                    const metaKv = document.getElementById('metaKv');
                    clearChildren(metaKv);
                    kvRow(metaKv, 'Canonical', data.metadata.canonical_url || 'Not set');
                    kvRow(metaKv, 'Language', data.metadata.language || 'Not detected');
                    kvRow(metaKv, 'Robots', data.metadata.robots || 'Not set (defaults to index, follow)');
                    kvRow(metaKv, 'Viewport', data.metadata.viewport || 'Not set');
                    kvRow(metaKv, 'H1 headings', String(data.metadata.h1_count ?? 0));
                    kvRow(metaKv, 'Images', `${data.metadata.images_count ?? 0} total, ${data.metadata.images_missing_alt_count ?? 0} missing alt`);
                    kvRow(metaKv, 'Page size', `${(data.metadata.content_length_bytes ?? 0).toLocaleString()} bytes`);

                    // --- SEO audit: every check the score is built from ---
                    const seoChecksEl = document.getElementById('seoChecks');
                    clearChildren(seoChecksEl);
                    (data.seo_checks || []).forEach((c) => seoChecksEl.appendChild(checkRow(c)));
                    if (!(data.seo_checks || []).length) seoChecksEl.appendChild(mutedSpan('No checks available'));

                    // --- Technologies, socials, contacts, and internal/external
                    // links below all come from an arbitrary scraped page (tech
                    // names indirectly via our own fixed signature list; the rest
                    // directly), so every value is built via textContent/
                    // setAttribute rather than innerHTML, and hrefs only get
                    // assigned when they pass the http(s) scheme allowlist. ---
                    const techRow = document.getElementById('techRow');
                    clearChildren(techRow);
                    const techDetails = data.technology_details || [];
                    if (techDetails.length) {
                        techDetails.forEach((t) => {
                            const el = document.createElement('span'); el.className = 'tag';
                            el.textContent = t.name;
                            const conf = document.createElement('span'); conf.className = 'tag conf';
                            conf.textContent = Math.round((t.confidence || 0) * 100) + '%';
                            el.appendChild(conf);
                            techRow.appendChild(el);
                        });
                    } else if (techList.length) {
                        techList.forEach((t) => { const el = document.createElement('span'); el.className = 'tag'; el.textContent = t; techRow.appendChild(el); });
                    } else {
                        techRow.appendChild(mutedSpan('No known CMS/framework signatures matched'));
                    }

                    const socialRow = document.getElementById('socialRow');
                    clearChildren(socialRow);
                    socialEntries.forEach(([net, link]) => {
                        const a = document.createElement('a');
                        a.className = 'tag';
                        if (isSafeHttpUrl(link)) a.setAttribute('href', link);
                        a.target = '_blank';
                        a.rel = 'noopener noreferrer';
                        a.textContent = net.toUpperCase();
                        socialRow.appendChild(a);
                    });
                    if (!socialEntries.length) socialRow.appendChild(mutedSpan('No profiles linked on this page'));

                    const contactsRow = document.getElementById('contactsRow');
                    clearChildren(contactsRow);
                    (data.contacts.emails || []).forEach((e) => { const span = document.createElement('span'); span.className = 'tag'; span.textContent = e; contactsRow.appendChild(span); });
                    (data.contacts.phones || []).forEach((p) => { const span = document.createElement('span'); span.className = 'tag'; span.textContent = p; contactsRow.appendChild(span); });
                    if (!contactsCount) contactsRow.appendChild(mutedSpan('No public emails or phone numbers on this page'));

                    document.getElementById('internalCount').textContent = data.total_internal_count ?? 0;
                    document.getElementById('externalCount').textContent = data.total_external_count ?? 0;
                    buildLinkList(document.getElementById('internalLinks'), data.internal_links, 6);
                    buildLinkList(document.getElementById('externalLinks'), data.external_links, 6);

                    // --- Structured data & feeds ---
                    const structuredKv = document.getElementById('structuredKv');
                    clearChildren(structuredKv);
                    const schemas = data.json_ld_schemas || [];
                    const schemaTypes = [...new Set(schemas.map((s) => s['@type']).filter(Boolean))];
                    kvRow(structuredKv, 'JSON-LD schemas', schemas.length ? `${schemas.length} found (${schemaTypes.join(', ') || 'unnamed type'})` : 'None found');
                    kvRow(structuredKv, 'RSS / Atom feeds', (data.rss_feeds || []).length ? String(data.rss_feeds.length) + ' found' : 'None found');
                    buildLinkList(structuredKv, data.rss_feeds, 5, { clear: false });

                    // --- AI-ready content ---
                    const aiKv = document.getElementById('aiKv');
                    clearChildren(aiKv);
                    kvRow(aiKv, 'Word count', String(data.word_count ?? 0));
                    kvRow(aiKv, 'Reading time', `${data.reading_time_minutes ?? 0} min`);
                    const md = data.markdown_content || '';
                    document.getElementById('mdPreview').textContent = md || 'No article-like content extracted from this page.';
                    document.getElementById('mdCharCount').textContent = md ? `${md.length.toLocaleString()} chars` : '';

                    // --- Data quality & signals ---
                    const qualityRow = document.getElementById('qualityRow');
                    clearChildren(qualityRow);
                    const q = data.quality || {};
                    const qScore = q.score ?? 0;
                    qualityRow.appendChild(badge(`Quality score ${Math.round(qScore * 100)}%`, qScore >= 0.8 ? 'good' : qScore >= 0.5 ? 'warn' : 'bad'));
                    qualityRow.appendChild(badge(data.bot_protection_detected ? 'Bot protection detected' : 'No bot protection detected', data.bot_protection_detected ? 'warn' : 'good'));
                    (q.sources_used || []).forEach((s) => qualityRow.appendChild(badge('source: ' + s)));
                    (q.warnings || []).forEach((w) => qualityRow.appendChild(badge(w.type + (w.field ? ': ' + w.field : ''), 'warn')));
                    if (!(q.sources_used || []).length && !(q.warnings || []).length) qualityRow.appendChild(mutedSpan('No additional signals'));

                    document.getElementById('jsonPre').textContent = JSON.stringify(data, null, 2);
                    document.getElementById('jsonPanel').classList.remove('open');
                    document.getElementById('viewJsonLabel').textContent = 'View JSON';

                } catch (err) {
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('analyzeBtn').disabled = false;
                    const errBox = document.getElementById('error');
                    clearChildren(errBox);
                    const b = document.createElement('b'); b.textContent = 'Connection error: ';
                    const span = document.createElement('span'); span.textContent = err.message;
                    errBox.appendChild(b); errBox.appendChild(span);
                    errBox.style.display = 'block';
                }
            }

            window.onload = analyzeUrl;
        </script>
    </body>
    </html>
    """


def render_home(nonce: str) -> str:
    """Inject the per-request CSP nonce into the embedded <style>/<script>
    tags. A plain .replace() rather than .format()/f-string on the whole
    template deliberately avoids having to escape the large literal CSS
    block's own curly braces."""
    return HOME_HTML.replace("__CSP_NONCE__", nonce)
