"""
Embedded playground UI (Plan section 68: separate UI from API — moved out of
main.py into its own module as a first step; still served inline rather than
from static files/CDN, which is a later follow-up).
"""

HOME_HTML = """
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

            function clearChildren(el) {
                while (el.firstChild) el.removeChild(el.firstChild);
            }

            function mutedSpan(text) {
                const span = document.createElement('span');
                span.style.color = '#64748b';
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

                    // Socials — data comes from an arbitrary scraped page, so it's
                    // treated as untrusted: build DOM nodes via textContent/setAttribute
                    // rather than innerHTML, and only assign hrefs with a safe scheme.
                    const socialsDiv = document.getElementById('socialsContainer');
                    clearChildren(socialsDiv);
                    let foundSocials = false;
                    for (const [net, link] of Object.entries(data.social_links)) {
                        if (link) {
                            foundSocials = true;
                            const a = document.createElement('a');
                            if (isSafeHttpUrl(link)) a.setAttribute('href', link);
                            a.target = '_blank';
                            a.rel = 'noopener noreferrer';
                            a.className = 'social-tag';
                            a.textContent = net.toUpperCase();
                            socialsDiv.appendChild(a);
                        }
                    }
                    if (!foundSocials) socialsDiv.appendChild(mutedSpan('No social links found'));

                    // Emails — also untrusted, scraped from the target page.
                    const emailsDiv = document.getElementById('emailsContainer');
                    clearChildren(emailsDiv);
                    if (data.contacts.emails && data.contacts.emails.length > 0) {
                        data.contacts.emails.forEach((e, i) => {
                            if (i > 0) emailsDiv.appendChild(document.createTextNode(', '));
                            const span = document.createElement('span');
                            span.style.color = '#38bdf8';
                            span.textContent = e;
                            emailsDiv.appendChild(span);
                        });
                    } else {
                        emailsDiv.appendChild(mutedSpan('No public emails on main page'));
                    }

                    // Tech Stack — names come from our own fixed signature list
                    // server-side, but rendered the same safe way for consistency.
                    const techDiv = document.getElementById('techContainer');
                    clearChildren(techDiv);
                    if (data.detected_technologies && data.detected_technologies.length > 0) {
                        data.detected_technologies.forEach(t => {
                            const span = document.createElement('span');
                            span.className = 'tech-tag';
                            span.textContent = t;
                            techDiv.appendChild(span);
                        });
                    } else {
                        techDiv.appendChild(mutedSpan('Standard HTML / No known CMS signatures'));
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
