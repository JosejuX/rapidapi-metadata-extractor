import os
import re
import time
import urllib.parse
from typing import Optional, List, Dict, Any
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(
    title="Web Metadata & Contact Extractor API",
    description="API de alto rendimiento para extraer metadatos OpenGraph, enlaces a redes sociales, correos de contacto, teléfonos y tecnologías de cualquier sitio web.",
    version="1.0.0"
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

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

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
        "version": "1.0.0",
        "rapidapi_protected": bool(RAPIDAPI_PROXY_SECRET)
    }


@app.get("/api/v1/extract", response_model=MetadataResponse, tags=["Extractor"])
def extract_metadata(
    url: str = Query(..., description="La URL de la página web a analizar (ej: https://ejemplo.com)"),
    user_agent: Optional[str] = Query(None, description="User-Agent personalizado opcional"),
    dependencies: None = Depends(verify_rapidapi_secret)
):
    """
    Extrae de forma automática:
    - **Metadatos SEO**: Título, descripción, canonical, og:image, favicon, idioma, autor.
    - **Contactos**: Correos electrónicos y números de teléfono detectados en el HTML.
    - **Redes Sociales**: Enlaces a Twitter/X, LinkedIn, Instagram, Facebook, GitHub, YouTube, Telegram, TikTok.
    - **Tecnologías**: Detección de CMS y frameworks (WordPress, Shopify, React, Next.js, Tailwind, etc.).
    """
    start_time = time.time()
    
    # Asegurar esquema HTTP/HTTPS
    parsed_url = urllib.parse.urlparse(url)
    if not parsed_url.scheme:
        url = "https://" + url
        parsed_url = urllib.parse.urlparse(url)
        
    headers = {
        "User-Agent": user_agent or USER_AGENTS[0],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo acceder a la URL especificada: {str(e)}"
        )
        
    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Extracción de Metadatos
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    
    def get_meta(property_or_name: str) -> Optional[str]:
        tag = soup.find('meta', attrs={'property': property_or_name}) or soup.find('meta', attrs={'name': property_or_name})
        return tag.get('content', '').strip() if tag and tag.get('content') else None

    description = get_meta('description') or get_meta('og:description') or get_meta('twitter:description')
    og_image = get_meta('og:image') or get_meta('twitter:image')
    keywords = get_meta('keywords')
    author = get_meta('author') or get_meta('article:author')
    site_name = get_meta('og:site_name')
    language = soup.html.get('lang') if soup.html and soup.html.get('lang') else None
    
    # Favicon
    favicon = None
    icon_tag = soup.find('link', attrs={'rel': re.compile(r'^(shortcut )?icon$', re.I)})
    if icon_tag and icon_tag.get('href'):
        favicon = urllib.parse.urljoin(url, icon_tag['href'])
    else:
        favicon = urllib.parse.urljoin(url, "/favicon.ico")

    # 2. Extracción de Redes Sociales
    social_domains = {
        'twitter': r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[a-zA-Z0-9_]+',
        'facebook': r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+',
        'instagram': r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._-]+',
        'linkedin': r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9._-]+',
        'github': r'https?://(?:www\.)?github\.com/[a-zA-Z0-9._-]+',
        'youtube': r'https?://(?:www\.)?youtube\.com/(?:c/|channel/|@)?[a-zA-Z0-9._-]+',
        'telegram': r'https?://(?:t\.me|telegram\.me)/[a-zA-Z0-9._-]+',
        'tiktok': r'https?://(?:www\.)?tiktok\.com/@[a-zA-Z0-9._-]+'
    }
    
    social_links: Dict[str, Optional[str]] = {}
    all_links = [a.get('href') for a in soup.find_all('a', href=True)]
    
    for platform, pattern in social_domains.items():
        found = None
        for link in all_links:
            if re.match(pattern, link, re.I):
                found = link
                break
        social_links[platform] = found

    # 3. Extracción de Contactos (Emails y Teléfonos)
    emails = list(set(re.findall(EMAIL_REGEX, html_content)))
    emails = [e for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))]
    
    for a in soup.find_all('a', href=re.compile(r'^mailto:', re.I)):
        mail = a['href'].replace('mailto:', '').split('?')[0].strip()
        if mail and mail not in emails:
            emails.append(mail)
            
    phones = []
    for a in soup.find_all('a', href=re.compile(r'^tel:', re.I)):
        phone = a['href'].replace('tel:', '').strip()
        if phone and phone not in phones:
            phones.append(phone)

    # 4. Detección de Tecnologías
    detected_tech = []
    html_lower = html_content.lower()
    
    tech_signatures = {
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
    
    for tech, sigs in tech_signatures.items():
        if any(sig in html_lower for sig in sigs):
            detected_tech.append(tech)
            
    execution_time = round((time.time() - start_time) * 1000, 2)
    
    return MetadataResponse(
        url=url,
        status_code=response.status_code,
        execution_time_ms=execution_time,
        metadata={
            "title": title,
            "description": description,
            "og_image": og_image,
            "keywords": keywords,
            "author": author,
            "site_name": site_name,
            "language": language,
            "favicon": favicon
        },
        social_links=social_links,
        contacts={
            "emails": emails[:10],
            "phones": phones[:5]
        },
        detected_technologies=detected_tech
    )
