"""Phase 5: expanded SEO audit checks (Plan §23)."""
from app.extraction.seo import run_seo_audit


def _base_kwargs(**overrides):
    kwargs = dict(
        title="A well sized title for testing",
        description="A meta description that sits comfortably within the fifty to one hundred sixty character sweet spot for SEO purposes here.",
        canonical_url="https://example.com/",
        h1_tags=["Main heading"],
        og_image="https://example.com/og.png",
        favicon="https://example.com/favicon.ico",
        images_count=2,
        images_missing_alt_count=0,
        final_url="https://example.com/",
        language="en",
        viewport="width=device-width, initial-scale=1.0",
        robots_directive=None,
        h1_count=1,
        twitter_card="summary_large_image",
        has_structured_data=True,
    )
    kwargs.update(overrides)
    return kwargs


def test_perfect_page_scores_high_and_passes_new_checks():
    print("\n--- SEO quality: a page with everything present passes all new checks ---")
    passed, warnings, score, checks = run_seo_audit(**_base_kwargs())
    assert any("lang attribute" in p for p in passed)
    assert any("viewport" in p.lower() for p in passed)
    assert any("indexable" in p for p in passed)
    assert any("Twitter Card" in p for p in passed)
    assert any("structured data" in p for p in passed)
    assert warnings == [], f"expected no warnings on a fully-optimized page, got {warnings}"
    print(f"  [OK] score={score}, {len(passed)} checks passed, 0 warnings")


def test_missing_lang_and_viewport_warn():
    print("\n--- SEO quality: missing lang/viewport produce warnings ---")
    passed, warnings, score, checks = run_seo_audit(**_base_kwargs(language=None, viewport=None))
    assert any("lang attribute" in w for w in warnings)
    assert any("viewport" in w.lower() for w in warnings)
    print(f"  [OK] warnings: {warnings}")


def test_noindex_flagged_as_warning():
    print("\n--- SEO quality: noindex robots directive is flagged ---")
    passed, warnings, score, checks = run_seo_audit(**_base_kwargs(robots_directive="noindex, nofollow"))
    assert any("noindex" in w.lower() for w in warnings)
    assert not any("indexable" in p for p in passed)
    print(f"  [OK] noindex correctly flagged: {[w for w in warnings if 'noindex' in w.lower()]}")


def test_multiple_h1_warns():
    print("\n--- SEO quality: multiple H1 tags trigger a warning ---")
    passed, warnings, score, checks = run_seo_audit(**_base_kwargs(h1_count=3))
    assert any("Multiple" in w and "h1" in w.lower() for w in warnings)
    print(f"  [OK] multiple-H1 warning present: {[w for w in warnings if 'ultiple' in w]}")


def test_single_h1_does_not_warn():
    print("\n--- SEO quality: exactly one H1 does NOT trigger the multiple-H1 warning ---")
    passed, warnings, score, checks = run_seo_audit(**_base_kwargs(h1_count=1))
    assert not any("Multiple" in w for w in warnings)
    print("  [OK] no false positive for a single H1")


def test_missing_structured_data_and_twitter_card_warn():
    print("\n--- SEO quality: missing structured data / Twitter Card warn ---")
    passed, warnings, score, checks = run_seo_audit(**_base_kwargs(has_structured_data=False, twitter_card=None))
    assert any("structured data" in w.lower() for w in warnings)
    assert any("Twitter Card" in w for w in warnings)
    print(f"  [OK] warnings present: {[w for w in warnings if 'structured' in w.lower() or 'Twitter' in w]}")


def test_backward_compatible_defaults_when_new_params_omitted():
    """Callers that don't pass the new Plan §23 params (language, viewport,
    etc.) must still work — defaults must not crash or force spurious warnings
    that didn't exist before this phase for callers who can't supply them."""
    print("\n--- SEO quality: new params are optional, old-style calls still work ---")
    passed, warnings, score, checks = run_seo_audit(
        title="A title of reasonable length for the test",
        description="A description in the sweet spot range for SEO purposes, comfortably between fifty and one sixty characters long.",
        canonical_url="https://example.com/",
        h1_tags=["H1"],
        og_image="https://example.com/og.png",
        favicon="https://example.com/favicon.ico",
        images_count=0,
        images_missing_alt_count=0,
        final_url="https://example.com/",
    )
    assert isinstance(score, float)
    assert isinstance(passed, list) and isinstance(warnings, list)
    print(f"  [OK] old-style call (no new kwargs) still works, score={score}")


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_perfect_page_scores_high_and_passes_new_checks()
        test_missing_lang_and_viewport_warn()
        test_noindex_flagged_as_warning()
        test_multiple_h1_warns()
        test_single_h1_does_not_warn()
        test_missing_structured_data_and_twitter_card_warn()
        test_backward_compatible_defaults_when_new_params_omitted()
        print("\n[OK] ALL SEO AUDIT QUALITY TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
