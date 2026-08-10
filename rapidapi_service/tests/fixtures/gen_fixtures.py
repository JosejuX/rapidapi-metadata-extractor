"""
Generates deterministic local HTML fixtures for offline benchmarking/testing.
Plan sections 47 (fixtures) and 56 (benchmark suite): tests/fixtures/html/*.html
"""
import os
import json

OUT = "/sessions/admiring-eloquent-goodall/mnt/rapidapi-metadata-extractor/rapidapi_service/tests/fixtures/html"
os.makedirs(OUT, exist_ok=True)


def write(name, content: str):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"{name}: {len(content.encode('utf-8'))} bytes")


HEAD_COMMON = """
<meta charset="UTF-8">
<meta name="description" content="A concise, optimally-sized meta description for SEO testing purposes here.">
<meta name="keywords" content="testing, fixtures, benchmark, extraction">
<meta name="author" content="Fixture Author">
<meta property="og:title" content="Fixture Page">
<meta property="og:description" content="OG description for fixture page.">
<meta property="og:image" content="https://example.com/og.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Fixture Site">
<link rel="canonical" href="https://example.com/basic">
<link rel="icon" href="/favicon.ico">
"""

# --- basic.html : small representative page ---
write("basic.html", f"""<!DOCTYPE html>
<html lang="en">
<head><title>Basic Fixture Page</title>{HEAD_COMMON}</head>
<body>
<h1>Welcome to the Basic Fixture</h1>
<p>Contact us at info@fixture-example.com or call +1 555-123-4567.</p>
<p>Follow us on <a href="https://twitter.com/fixtureco">Twitter</a> and
<a href="https://github.com/fixtureco">GitHub</a>.</p>
<a href="/about">About</a>
<a href="https://external-example.org/partner">Partner</a>
<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@type": "Organization", "name": "Fixture Co"})}</script>
</body>
</html>
""")

# --- malformed.html : broken tags, unclosed elements ---
write("malformed.html", """<!DOCTYPE html>
<html lang="en">
<head><title>Malformed <b>Page
<meta name="description" content="Unclosed and broken markup test page">
<body>
<h1>Broken H1
<p>Paragraph without closing tag
<div><span>Nested unclosed
<a href="/no-close">Link without closing anchor
<script>var x = 1;
</html>
""")

# --- unicode.html : multi-language content ---
write("unicode.html", f"""<!DOCTYPE html>
<html lang="es">
<head><title>Página de Prueba — 中文 日本語 العربية</title>{HEAD_COMMON}</head>
<body>
<h1>Bienvenido a la página de prueba</h1>
<p>Contacto: soporte@ejemplo.es — ¡Gracias por visitarnos! 🚀</p>
<p>这是一个测试页面。请联系 info@ejemplo.jp</p>
<p>مرحبًا بكم في صفحة الاختبار</p>
</body>
</html>
""")

# --- redirect.html : content that would sit behind a redirect (used with mock 301) ---
write("redirect_target.html", """<!DOCTYPE html>
<html><head><title>Redirect Target</title></head>
<body><h1>You have been redirected here</h1></body></html>
""")

# --- spa.html : Next.js-like SPA shell that should trigger byte-limit expansion ---
write("spa.html", """<!DOCTYPE html>
<html>
<head><title>SPA Shell</title>
<script src="/_next/static/chunks/main.js"></script>
</head>
<body>
<div id="__next" data-reactroot=""></div>
<script>window.__NEXT_DATA__ = {"props": {}};</script>
</body>
</html>
""")

# --- many_links.html : 500 internal + external links (link extraction stress) ---
links_body = "\n".join(
    f'<a href="/internal/page-{i}">Internal {i}</a>' for i in range(300)
) + "\n" + "\n".join(
    f'<a href="https://partner-{i}.example.org/page">External {i}</a>' for i in range(300)
)
write("many_links.html", f"""<!DOCTYPE html>
<html><head><title>Many Links Fixture</title>{HEAD_COMMON}</head>
<body>
<h1>Link-heavy page</h1>
{links_body}
</body></html>
""")

# --- heavy_jsonld.html : many JSON-LD blocks (structured data stress) ---
jsonld_blocks = "\n".join(
    f'<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": f"Article {i}", "author": {"@type": "Person", "name": f"Author {i}"}})}</script>'
    for i in range(50)
)
write("heavy_jsonld.html", f"""<!DOCTYPE html>
<html><head><title>Heavy JSON-LD Fixture</title>{HEAD_COMMON}</head>
<body>
<h1>Structured data heavy page</h1>
<p>Some body text for context.</p>
{jsonld_blocks}
</body></html>
""")

# --- many_scripts.html : many script/style tags (tech-signature scanning stress) ---
scripts_body = "\n".join(f'<script src="/assets/vendor-{i}.js"></script>' for i in range(200))
write("many_scripts.html", f"""<!DOCTYPE html>
<html><head><title>Many Scripts Fixture</title>{HEAD_COMMON}
{scripts_body}
</head>
<body><h1>Script-heavy page</h1><p>Body text.</p></body></html>
""")


def padded_paragraphs(target_bytes: int) -> str:
    paras = []
    filler = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor "
              "incididunt ut labore et dolore magna aliqua. ")
    i = 0
    size = 0
    while size < target_bytes:
        p = f"<p>Paragraph {i}: {filler}</p>\n"
        paras.append(p)
        size += len(p.encode("utf-8"))
        i += 1
    return "".join(paras)


# --- large_64kb.html : ~70KB page (crosses STREAM_SOFT_LIMIT) ---
write("large_64kb.html", f"""<!DOCTYPE html>
<html><head><title>Large 64KB Fixture</title>{HEAD_COMMON}</head>
<body>
<h1>Large content page (~70KB)</h1>
{padded_paragraphs(70 * 1024)}
</body></html>
""")

# --- large_256kb.html : ~280KB page (crosses STREAM_HARD_LIMIT) ---
write("large_256kb.html", f"""<!DOCTYPE html>
<html><head><title>Large 256KB Fixture</title>{HEAD_COMMON}</head>
<body>
<h1>Large content page (~280KB)</h1>
{padded_paragraphs(280 * 1024)}
</body></html>
""")

print("\nAll fixtures generated.")
