"""
Clean Markdown / AI-reader extraction (Plan section 25) plus the lightweight
NLP summary-snippet & top-keywords heuristic (Plan sections 26/27).
No LLM in the hot path, per Plan §25/§118.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from selectolax.parser import HTMLParser

MULTI_NEWLINE_REGEX = re.compile(r'\n{3,}')

# Competitive-differentiator #2: readability metrics. Simple regex heuristics
# on already-extracted text (clean_text or markdown_content) — no NLP
# dependency, matching this module's existing no-LLM-in-the-hot-path stance.
SENTENCE_SPLIT_REGEX = re.compile(r'(?<=[.!?])\s+')
PARAGRAPH_SPLIT_REGEX = re.compile(r'\n\s*\n+')

# §26: Unicode-aware word tokenizer. The old `[a-zA-Z]{3,15}` regex silently
# dropped every accented/non-Latin word, which for Spanish/French/German/etc
# content meant top_keywords was often empty or built only from stray English
# fragments (menu labels, boilerplate). `[^\W\d_]` matches any Unicode letter
# (letters minus digits/underscore) via Python's default Unicode-aware `\w`,
# so this covers Latin-with-diacritics, Cyrillic, Greek, Hebrew, Arabic, etc.
# CJK scripts don't segment on whitespace/word-boundaries the same way and
# are a known limitation (Plan §26/§28 note this explicitly) — full CJK
# segmentation needs a real tokenizer, which is out of scope for a
# regex-based, no-heavy-NLP-dependency approach.
WORD_REGEX = re.compile(r'\b[^\W\d_]{3,15}\b', re.UNICODE)

# §26: stopwords across the languages the plan explicitly calls out
# (es/en/fr/de/it/pt/nl) — compact, common-function-word lists, not
# exhaustive linguistic resources.
STOPWORDS = {
    # English
    'the', 'is', 'at', 'which', 'on', 'and', 'a', 'to', 'in', 'for', 'of', 'with', 'an', 'by',
    'as', 'from', 'that', 'it', 'are', 'this', 'be', 'or', 'we', 'you', 'your', 'our', 'us',
    'was', 'were', 'been', 'have', 'has', 'had', 'not', 'but', 'all', 'can', 'will', 'their',
    'its', 'his', 'her', 'they', 'them', 'about', 'into', 'than', 'more', 'also', 'when',
    # Spanish
    'de', 'la', 'el', 'en', 'un', 'una', 'que', 'los', 'las', 'por', 'con', 'para', 'del',
    'como', 'más', 'pero', 'sus', 'les', 'este', 'esta', 'estos', 'estas', 'una', 'uno',
    'ser', 'son', 'fue', 'han', 'está', 'muy', 'sin', 'sobre', 'entre', 'nos', 'ese', 'esa',
    # French
    'le', 'les', 'des', 'une', 'dans', 'sur', 'pour', 'avec', 'est', 'sont', 'que', 'qui',
    'pas', 'plus', 'mais', 'nous', 'vous', 'ils', 'elles', 'ces', 'leur', 'aux', 'être',
    # German
    'der', 'die', 'das', 'und', 'ist', 'sind', 'mit', 'auf', 'für', 'nicht', 'sich', 'auch',
    'eine', 'einen', 'einer', 'werden', 'wird', 'wurde', 'aber', 'oder', 'wie', 'nur',
    # Italian
    'il', 'lo', 'gli', 'delle', 'degli', 'nella', 'nel', 'per', 'con', 'che', 'sono', 'non',
    'più', 'anche', 'come', 'questo', 'questa', 'suo', 'loro',
    # Portuguese
    'do', 'da', 'dos', 'das', 'em', 'um', 'uma', 'para', 'com', 'não', 'mais', 'como', 'seu',
    'sua', 'ao', 'à', 'pelo', 'pela', 'este', 'esta', 'isso', 'são', 'foi',
    # Dutch
    'het', 'een', 'van', 'voor', 'met', 'niet', 'ook', 'zijn', 'wordt', 'werd', 'deze', 'dit',
    'aan', 'bij', 'uit', 'over', 'naar',
    # Generic web boilerplate tokens worth suppressing regardless of language
    'com', 'org', 'net', 'http', 'https', 'www',
}


def html_to_markdown_clean(tree: HTMLParser, base_url: str) -> Tuple[str, int, float]:
    """
    Converts an already-parsed HTMLParser tree to clean Markdown for AI/LLM consumption.
    Receives the existing tree to avoid a redundant re-parse.
    NOTE: strip_tags() mutates the tree — call this function LAST after all other
    tree-based extraction (metadata, links, jsonld, etc.) has already run.
    """
    target_node = (
        tree.css_first('article') or
        tree.css_first('main') or
        tree.css_first('[role="main"]') or
        tree.css_first('.post-content') or
        tree.css_first('.article-body') or
        tree.css_first('body') or
        tree.root
    )

    if not target_node:
        return "", 0, 0.0

    target_node.strip_tags([
        "nav", "header", "footer", "aside", "script", "style",
        "noscript", "svg", "iframe", "form", "button", "input"
    ])

    lines = []

    for element in target_node.css('h1, h2, h3, h4, h5, h6, p, li, blockquote, pre'):
        tag = element.tag
        raw_txt = element.text(deep=True, separator=' ')
        txt = raw_txt.strip() if raw_txt else ""
        if not txt:
            continue

        if tag == 'h1':
            lines.append(f"\n# {txt}\n")
        elif tag == 'h2':
            lines.append(f"\n## {txt}\n")
        elif tag == 'h3':
            lines.append(f"\n### {txt}\n")
        elif tag == 'h4':
            lines.append(f"\n#### {txt}\n")
        elif tag == 'h5':
            lines.append(f"\n##### {txt}\n")
        elif tag == 'h6':
            lines.append(f"\n###### {txt}\n")
        elif tag == 'p':
            lines.append(f"{txt}\n")
        elif tag == 'li':
            lines.append(f"* {txt}")
        elif tag == 'blockquote':
            lines.append(f"> {txt}\n")
        elif tag == 'pre':
            lines.append(f"\n```\n{txt}\n```\n")

    markdown_str = "\n".join(lines).strip()
    markdown_str = MULTI_NEWLINE_REGEX.sub("\n\n", markdown_str)

    words = markdown_str.split()
    word_count = len(words)
    reading_time = round(word_count / 200.0, 1) if word_count > 0 else 0.0

    return markdown_str, word_count, reading_time


def extract_summary_and_keywords(clean_text: str, description: Optional[str]) -> Tuple[str, List[str]]:
    words_all = [w.lower() for w in WORD_REGEX.findall(clean_text)]
    words_filtered = [w for w in words_all if w not in STOPWORDS]
    word_freq = {}
    for w in words_filtered:
        word_freq[w] = word_freq.get(w, 0) + 1
    top_keywords = sorted(word_freq, key=word_freq.get, reverse=True)[:5]

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_text) if len(s.strip()) > 20]
    summary_snippet = " ".join(sentences[:2]) if sentences else (description or "")

    return summary_snippet, top_keywords


def compute_readability_metrics(text: str) -> Dict[str, Any]:
    """Sentence count, paragraph count, and average words/sentence (Plan
    competitive-differentiator #2) from already-extracted text — simple
    regex splitting, no new NLP dependency.

    Works against either text source the pipeline has on hand:
    - clean_text (the stripped-tags second parse used by contacts/summary
      extraction): has no paragraph structure (body.text(separator=' ')
      collapses everything to single-space-joined text), so paragraph_count
      degrades to a single block there — a known heuristic limitation, same
      spirit as this module's documented CJK-tokenization caveat above.
    - markdown_content (html_to_markdown_clean()'s output): has real '\\n\\n'
      paragraph boundaries from its per-<p>/<hN> line synthesis, so this is
      the materially better source when it's already being computed anyway
      (the "markdown" extraction group).
    """
    stripped = text.strip() if text else ""
    if not stripped:
        return {"sentence_count": 0, "paragraph_count": 0, "avg_words_per_sentence": 0.0}

    sentences = [s for s in SENTENCE_SPLIT_REGEX.split(stripped) if s.strip()]
    sentence_count = len(sentences) if sentences else 1

    paragraphs = [p for p in PARAGRAPH_SPLIT_REGEX.split(stripped) if p.strip()]
    paragraph_count = len(paragraphs) if paragraphs else 1

    word_count = len(stripped.split())
    avg_words_per_sentence = round(word_count / sentence_count, 2) if sentence_count > 0 else 0.0

    return {
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "avg_words_per_sentence": avg_words_per_sentence,
    }
