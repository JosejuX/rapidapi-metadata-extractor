"""Technology / CMS / framework signature detection (Plan section 20)."""
import re
from typing import Any, Dict, List

TECH_SIGNATURES = {
    "WordPress": [r'wp-content', r'wp-includes', r'generator" content="wordpress'],
    "Shopify": [r'cdn\.shopify\.com', r'shopify\.theme', r'myshopify\.com'],
    "WooCommerce": [r'woocommerce', r'wc-ajax'],
    "Wix": [r'wix\.com', r'_wix', r'wix-code'],
    "Squarespace": [r'squarespace\.com', r'sqsp\.net'],
    "Webflow": [r'uploads-ssl\.webflow\.com', r'webflow\.js', r'html class="w-mod-'],
    "Framer": [r'framerusercontent\.com', r'framer\.com'],
    "Ghost": [r'ghost\.io', r'ghost-sdk', r'generator" content="ghost'],
    "Drupal": [r'drupal\.js', r'sites/default/files', r'generator" content="drupal'],
    "Joomla": [r'/components/com_', r'generator" content="joomla'],
    "Magento": [r'skin/frontend', r'mage/cookies\.js'],
    "PrestaShop": [r'prestashop', r'_ps_version'],
    "BigCommerce": [r'cdn11\.bigcommerce\.com', r'stencil'],
    "Contentful": [r'contentful\.com', r'ctfassets\.net'],
    "Strapi": [r'strapi'],
    "Sanity": [r'cdn\.sanity\.io'],

    "React": [r'data-reactroot', r'_reactListening', r'react-dom'],
    "Next.js": [r'_next/static', r'__next', r'__next_f'],
    "Vue.js": [r'data-v-', r'vue\.js', r'vue\.min\.js'],
    "Nuxt.js": [r'_nuxt', r'__nuxt'],
    "Angular": [r'ng-version', r'angular\.js', r'ng-app'],
    "Svelte": [r'svelte-', r'svelte\.js'],
    "SvelteKit": [r'_app/immutable', r'__sveltekit'],
    "Astro": [r'astro-island', r'data-astro-cid'],
    "Gatsby": [r'___gatsby', r'gatsby-static'],
    "Remix": [r'__remix', r'remix-run'],
    "Alpine.js": [r'x-data', r'alpine\.js', r'x-init'],
    "HTMX": [r'hx-get', r'hx-post', r'htmx\.js'],
    "jQuery": [r'jquery\.min\.js', r'jquery\.js'],
    "Bootstrap": [r'bootstrap\.min\.css', r'bootstrap\.bundle'],
    "TailwindCSS": [r'cdn\.tailwindcss\.com', r'tailwind'],

    "Google Analytics 4": [r'googletagmanager\.com/gtag/js', r'ga4'],
    "Google Tag Manager": [r'googletagmanager\.com/gtm\.js'],
    "Hotjar": [r'static\.hotjar\.com', r'hjid:'],
    "Segment": [r'cdn\.segment\.com/analytics\.js'],
    "Plausible Analytics": [r'plausible\.io/js/script\.js'],
    "PostHog": [r'posthog\.com/static/array\.js'],
    "Stripe": [r'js\.stripe\.com'],
    "PayPal": [r'paypal\.com/sdk/js'],
    "Vercel": [r'_vercel', r'vercel\.app'],
    "Netlify": [r'netlify\.app'],
    "Cloudflare": [r'cf-beacon', r'cloudflare\.com'],
    "Fastly": [r'fastly\.net']
}

# Plan §61: cheap prefilter before expensive regex. Every pattern above is a
# plain literal string with only `\.` as a regex metacharacter (verified: no
# `|`, `(`, `[`, `*`, `+`, `?`, `^`, `$`, `{` anywhere in TECH_SIGNATURES) —
# so `\.` -> `.` recovers the exact literal each pattern matches. A `str in`
# check against a once-lowercased copy of the document is a CPython-optimized
# substring search, cheaper than running re.search (even for a literal
# pattern) — and it turns "~90 regex scans of the whole document" into
# "~90 substring checks, with a regex re-run only for the rare actual hits".
# If TECH_SIGNATURES ever gains a real regex pattern (alternation, classes,
# quantifiers), its literal-derived prefilter would stop matching correctly —
# there is no runtime guard for that here, so any future non-literal pattern
# must get its own prefilter or be excluded from this optimization.
COMPILED_TECH_SIGS = {
    tech: [
        (re.compile(pattern, re.I), pattern.replace(r'\.', '.').lower())
        for pattern in patterns
    ]
    for tech, patterns in TECH_SIGNATURES.items()
}

# Plan §20: category metadata for the richer technology_details field.
TECH_CATEGORIES: Dict[str, str] = {
    "WordPress": "cms", "Wix": "cms", "Squarespace": "cms", "Webflow": "cms",
    "Framer": "cms", "Ghost": "cms", "Drupal": "cms", "Joomla": "cms",
    "Contentful": "cms", "Strapi": "cms", "Sanity": "cms",

    "Shopify": "ecommerce", "WooCommerce": "ecommerce", "Magento": "ecommerce",
    "PrestaShop": "ecommerce", "BigCommerce": "ecommerce",

    "React": "framework", "Next.js": "framework", "Vue.js": "framework",
    "Nuxt.js": "framework", "Angular": "framework", "Svelte": "framework",
    "SvelteKit": "framework", "Astro": "framework", "Gatsby": "framework",
    "Remix": "framework", "Alpine.js": "framework", "HTMX": "framework",

    "jQuery": "library", "Bootstrap": "css", "TailwindCSS": "css",

    "Google Analytics 4": "analytics", "Google Tag Manager": "analytics",
    "Hotjar": "analytics", "Segment": "analytics", "Plausible Analytics": "analytics",
    "PostHog": "analytics",

    "Stripe": "payment", "PayPal": "payment",

    "Vercel": "hosting", "Netlify": "hosting", "Cloudflare": "hosting", "Fastly": "hosting",
}


def detect_technologies(html_content: str) -> List[str]:
    html_lower = html_content.lower()
    detected = []
    for tech, patterns in COMPILED_TECH_SIGS.items():
        if any(literal in html_lower and pattern.search(html_content) for pattern, literal in patterns):
            detected.append(tech)
    return detected


def names_in_signature_order(detailed: List[Dict[str, Any]]) -> List[str]:
    """Given detect_technologies_detailed()'s output, returns just the names
    in the original TECH_SIGNATURES insertion order (matching what
    detect_technologies() would have returned) — lets pipeline.py get both
    the flat list AND the detailed list from a SINGLE regex pass instead of
    running detect_technologies() and detect_technologies_detailed()
    separately, which doubled tech-detection cost for no reason."""
    names = {d["name"] for d in detailed}
    return [tech for tech in TECH_SIGNATURES if tech in names]


def detect_technologies_detailed(html_content: str) -> List[Dict[str, Any]]:
    """
    Richer detection alongside the plain detected_technologies list (Plan
    §20): each match reports which specific patterns fired (evidence) and a
    confidence score based on how many independent signals agreed — a single
    matched pattern is weaker evidence than two or three matching
    simultaneously. `detect_technologies()` (and the public
    `detected_technologies` field) is untouched by this — this is a purely
    additive, separate pass reusing the same compiled patterns so there's no
    extra regex compilation cost.
    """
    html_lower = html_content.lower()
    results: List[Dict[str, Any]] = []
    for tech, patterns in COMPILED_TECH_SIGS.items():
        evidence: List[str] = []
        for pattern, literal in patterns:
            if literal not in html_lower:
                continue
            match = pattern.search(html_content)
            if match:
                evidence.append(match.group(0))
        if not evidence:
            continue
        # 1 signal -> 0.75, 2 -> 0.9, 3+ -> 0.98. Never a flat 1.0: a regex
        # match on raw HTML is still a heuristic, not certainty.
        confidence = min(0.98, 0.75 + 0.15 * (len(evidence) - 1))
        results.append({
            "name": tech,
            "confidence": round(confidence, 2),
            "evidence": evidence[:5],
            "category": TECH_CATEGORIES.get(tech, "other"),
        })
    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results
