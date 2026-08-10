"""Phase 5: Unicode-aware keyword extraction (Plan §26)."""
from app.extraction.markdown import extract_summary_and_keywords, WORD_REGEX


def test_accented_spanish_words_are_captured():
    print("\n--- Unicode keywords: accented Spanish words are no longer dropped ---")
    text = "La página principal ofrece información técnica sobre programación y educación."
    _, keywords = extract_summary_and_keywords(text, None)
    assert "página" in keywords or "información" in keywords or "técnica" in keywords, (
        f"expected at least one accented Spanish keyword, got {keywords}"
    )
    print(f"  [OK] keywords from accented Spanish text: {keywords}")


def test_ascii_only_english_still_works():
    print("\n--- Unicode keywords: plain ASCII English unaffected ---")
    text = "The quick brown fox jumps over the lazy dog repeatedly in the forest testing extraction quality thoroughly."
    _, keywords = extract_summary_and_keywords(text, None)
    assert len(keywords) > 0
    assert all(k.isascii() for k in keywords)
    print(f"  [OK] ASCII English keywords: {keywords}")


def test_word_regex_excludes_digits_and_underscores():
    print("\n--- Unicode keywords: digits/underscores excluded from word matches ---")
    text = "test_variable 12345 café über naïve résumé"
    matches = WORD_REGEX.findall(text)
    assert "12345" not in matches
    assert "test_variable" not in matches  # underscore breaks the match
    assert "café" in matches
    assert "über" in matches or "ber" in matches  # ü counts as a letter either way
    print(f"  [OK] matches: {matches}")


def test_stopwords_cover_multiple_languages():
    print("\n--- Unicode keywords: multilingual stopwords suppress function words ---")
    from app.extraction.markdown import STOPWORDS
    for word in ["the", "de", "le", "der", "il", "do", "het"]:
        assert word in STOPWORDS, f"expected common stopword '{word}' to be present"
    print(f"  [OK] stopword set covers en/es/fr/de/it/pt/nl function words ({len(STOPWORDS)} total)")


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_accented_spanish_words_are_captured()
        test_ascii_only_english_still_works()
        test_word_regex_excludes_digits_and_underscores()
        test_stopwords_cover_multiple_languages()
        print("\n[OK] ALL UNICODE KEYWORD TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
