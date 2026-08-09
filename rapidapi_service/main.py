import os
import re
import time
import urllib.parse
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import httpx
from selectolax.parser import HTMLParser
from cachetools import TTLCache
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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
        timeout=httpx.Timeout(6.0, connect=2.5, read=4.0),
        limits=httpx.Limits(max_keepalive_connections=100, max_connections=500),
        follow_redirects=True
    )
    yield
    if http_client:
        await http_client.aclose()

# ------------------------------------------------------------------------------
# FastAPI App Config
# ------------------------------------------------------------------------------
app = FastAPI(
    title="Web Metadata & Contact Extractor API",
    description="API de ultra-alto rendimiento para extraer metadatos OpenGraph, enlaces a redes sociales, correos de contacto, teléfonos y tecnologías de cualquier sitio web.",
    version="1.2.0",
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

# Pre-compiled regular expressions for maximum performance
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
FAVICON_REL_REGEX = re.compile(r'^(shortcut )?icon$', re.I)
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
    "WordPress": ["wp-content", "wp-includes"],
    "Shopify": ["cdn.shopify.com", "shopify.theme"],
    "WooCommerce": ["woocommerce"],
    "Wix": ["wix.com", "_wix"],
    "Squarespace": ["squarespace.com"],
    "React": ["data-reactroot", "react-dom"],
    "Next.js": ["_next/static", "__next"],
    "Vue.js": ["data-v-", "vue.js"],
    "Nuxt.js": ["_nuxt"],
    "TailwindCSS": ["tailwind"],
    "Bootstrap": ["bootstrap.min.css", "bootstrap.bundle"]
}

class MetadataResponse(BaseModel):
    url: str
    status_code: int
    execution_time_ms: float
    metadata: Dict[str, Any]
    social_links: Dict[str, Optional[str]]
    contacts: Dict[str, List[str]]
    detected_technologies: List[str]

def verify_rapidapi_secret(x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    if RAPIDAPI_PROXY_SECRET and x_rapidapi_proxy_secret != RAPIDAPI_PROXY_SECRET:
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado: Cabecera X-RapidAPI-Proxy-Secret inválida o ausente."
        )

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home_ui():
    return """
    <!DOCTYPE html>
    <html lang="es">
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
                <p>Prueba en vivo de tu API monetizable para RapidAPI</p>
            </div>

            <div class="card">
                <div class="input-group">
                    <input type="url" id="urlInput" value="https://github.com" placeholder="Introduce cualquier URL (ej: https://ejemplo.com)">
                    <button onclick="analyzeUrl()">Analizar Web</button>
                </div>
                <div class="quick-links">
                    <span>Prueba rápida:</span>
                    <div class="chip" onclick="setUrl('https://github.com')">GitHub</div>
                    <div class="chip" onclick="setUrl('https://amazon.es')">Amazon</div>
                    <div class="chip" onclick="setUrl('https://wikipedia.org')">Wikipedia</div>
                </div>
            </div>

            <div id="loading">Analizando web y extrayendo metadatos en tiempo real...</div>

            <div id="results" class="card">
                <div class="res-header">
                    <div>
                        <span style="color: #94a3b8;">Resultado para:</span>
                        <strong id="resUrl" style="color: #fff; margin-left: 0.5rem;"></strong>
                    </div>
                    <div style="display: flex; gap: 1rem; align-items: center;">
                        <span id="resTime" style="color: #38bdf8; font-size: 0.9rem;"></span>
                        <span class="badge-status" id="resStatus">200 OK</span>
                    </div>
                </div>

                <div class="res-grid">
                    <div class="res-block" style="grid-column: 1 / -1;">
                        <h3>Metadatos SEO</h3>
                        <div class="data-item">
                            <span class="data-label">Título de la página</span>
                            <span class="data-val" id="metaTitle"></span>
                        </div>
                        <div class="data-item">
                            <span class="data-label">Descripción</span>
                            <span class="data-val" id="metaDesc"></span>
                        </div>
                    </div>

                    <div class="res-block">
                        <h3>Redes Sociales</h3>
                        <div id="socialsContainer"></div>
                    </div>

                    <div class="res-block">
                        <h3>Contactos e Idioma</h3>
                        <div class="data-item">
                            <span class="data-label">Correos Electrónicos</span>
                            <div id="emailsContainer" class="data-val"></div>
                        </div>
                        <div class="data-item">
                            <span class="data-label">Idioma detectado</span>
                            <span class="data-val" id="metaLang"></span>
                        </div>
                    </div>

                    <div class="res-block" style="grid-column: 1 / -1;">
                        <h3>Tecnologías Detectadas</h3>
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

                    document.getElementById('resUrl').innerText = data.url;
                    document.getElementById('resStatus').innerText = `${data.status_code} OK`;
                    document.getElementById('resTime').innerText = `⚡ ${data.execution_time_ms} ms`;

                    document.getElementById('metaTitle').innerText = data.metadata.title || 'No detectado';
                    document.getElementById('metaDesc').innerText = data.metadata.description || 'No detectada';
                    document.getElementById('metaLang').innerText = data.metadata.language || 'No especificado';

                    // Redes Sociales
                    const socialsDiv = document.getElementById('socialsContainer');
                    socialsDiv.innerHTML = '';
                    let foundSocials = false;
                    for (const [net, link] of Object.entries(data.social_links)) {
                        if (link) {
                            foundSocials = true;
                            socialsDiv.innerHTML += `<a href="${link}" target="_blank" class="social-tag">${net.toUpperCase()}</a>`;
                        }
                    }
                    if(!foundSocials) socialsDiv.innerHTML = '<span style="color: #64748b;">No se encontraron redes</span>';

                    // Emails
                    const emailsDiv = document.getElementById('emailsContainer');
                    if (data.contacts.emails && data.contacts.emails.length > 0) {
                        emailsDiv.innerHTML = data.contacts.emails.map(e => `<span style="color: #38bdf8;">${e}</span>`).join(', ');
                    } else {
                        emailsDiv.innerHTML = '<span style="color: #64748b;">Ningún email público en la portada</span>';
                    }

                    // Tecnologías
                    const techDiv = document.getElementById('techContainer');
                    techDiv.innerHTML = '';
                    if (data.detected_technologies && data.detected_technologies.length > 0) {
                        data.detected_technologies.forEach(t => {
                            techDiv.innerHTML += `<span class="tech-tag">${t}</span>`;
                        });
                    } else {
                        techDiv.innerHTML = '<span style="color: #64748b;">HTML estándar sin firmas de CMS conocidas</span>';
                    }

                } catch(err) {
                    document.getElementById('loading').innerText = 'Error al conectar con la API: ' + err.message;
                }
            }

            // Analizar GitHub por defecto al cargar
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
        "version": "1.2.0",
        "rapidapi_protected": bool(RAPIDAPI_PROXY_SECRET)
    }

@app.get("/api/v1/extract", response_model=MetadataResponse, tags=["Extractor"])
async def extract_metadata(
    url: str = Query(..., description="La URL de la página web a analizar (ej: https://ejemplo.com)"),
    user_agent: Optional[str] = Query(None, description="User-Agent personalizado opcional"),
    dependencies: None = Depends(verify_rapidapi_secret)
):
    """
    Extrae de forma hiper-rápida y ultra-optimizada (Selectolax C-Parser + HTTP/2 Streaming):
    - **Metadatos SEO**: Título, descripción, canonical, og:image, favicon, idioma, autor.
    - **Contactos**: Correos electrónicos y números de teléfono detectados en el HTML.
    - **Redes Sociales**: Enlaces a Twitter/X, LinkedIn, Instagram, Facebook, GitHub, YouTube, Telegram, TikTok.
    - **Tecnologías**: Detección de CMS y frameworks (WordPress, Shopify, React, Next.js, Tailwind, etc.).
    """
    start_time = time.time()
    
    # Normalizar User-Agent si viene como objeto Query
    ua_str = str(user_agent) if (user_agent and not hasattr(user_agent, 'default')) else None
    
    # Normalizar esquema URL
    parsed_url = urllib.parse.urlparse(url)
    if not parsed_url.scheme:
        url = "https://" + url
        parsed_url = urllib.parse.urlparse(url)

    # 0. Comprobar Caché en Memoria
    if url in cache:
        cached_data = cache[url].copy()
        cached_data["execution_time_ms"] = 0.05
        return MetadataResponse(**cached_data)

    headers = {
        "User-Agent": ua_str or USER_AGENTS[0],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br"
    }
    
    # Obtener o instanciar cliente HTTP/2 de alto rendimiento
    client = http_client
    should_close_client = False
    if client is None:
        client = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(6.0, connect=2.5, read=4.0),
            follow_redirects=True
        )
        should_close_client = True

    MAX_BYTES = 256 * 1024  # 256 KB Límite ultra-rápido por streaming
    content_chunks = []
    total_bytes = 0
    status_code = 200

    try:
        async with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            status_code = response.status_code
            
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
            detail=f"No se pudo acceder a la URL especificada: {str(e)}"
        )
    finally:
        if should_close_client:
            await client.aclose()

    # Parseo ultrarrápido con Selectolax (Parser C-Lexbor)
    tree = HTMLParser(html_content)
    
    # 1. Metadatos SEO
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
    
    # Favicon
    favicon = None
    for link in tree.css('link[rel]'):
        rel = link.attributes.get('rel', '')
        if FAVICON_REL_REGEX.search(rel):
            href = link.attributes.get('href')
            if href:
                favicon = urllib.parse.urljoin(url, href)
                break
    if not favicon:
        favicon = urllib.parse.urljoin(url, "/favicon.ico")

    # 2. Redes Sociales & Contactos (Single Pass de Elementos <a>)
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

    # 3. Limpieza previa del DOM y Extracción de Emails por Regex sobre Texto Limpio
    tree.strip_tags(["script", "style", "code", "noscript", "svg"])
    clean_text = tree.body.text(separator=' ') if tree.body else tree.text(separator=' ')
    emails = list(set(EMAIL_REGEX.findall(clean_text)))
    emails = [e for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))]
    
    for mail in mailto_emails:
        if mail not in emails:
            emails.append(mail)

    # 4. Detección de Tecnologías
    detected_tech = []
    html_lower = html_content.lower()
    
    for tech, sigs in TECH_SIGNATURES.items():
        if any(sig in html_lower for sig in sigs):
            detected_tech.append(tech)
            
    execution_time = round((time.time() - start_time) * 1000, 2)
    
    response_data = {
        "url": url,
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
        "detected_technologies": detected_tech
    }

    # Guardar en caché
    cache[url] = response_data

    return MetadataResponse(**response_data)
