"""Phase 5: tech detection confidence/evidence (Plan §20)."""
from app.extraction.tech import detect_technologies, detect_technologies_detailed


def test_backward_compatible_flat_list_unchanged():
    print("\n--- Tech detection: detected_technologies (flat list) unaffected by the new detailed pass ---")
    html = '<html><head><script src="/_next/static/chunks/main.js"></script></head><body data-reactroot=""></body></html>'
    flat = detect_technologies(html)
    assert "Next.js" in flat
    assert "React" in flat
    print(f"  [OK] flat list still works: {flat}")


def test_detailed_detection_includes_confidence_and_evidence():
    print("\n--- Tech detection: detailed pass reports confidence + evidence + category ---")
    html = '<html><head><script src="/_next/static/chunks/main.js"></script><meta name="next-head-count" content="1"></head><body id="__next" data-reactroot=""></body></html>'
    detailed = detect_technologies_detailed(html)
    names = {d["name"] for d in detailed}
    assert "Next.js" in names
    nextjs = next(d for d in detailed if d["name"] == "Next.js")
    assert 0.0 < nextjs["confidence"] <= 1.0
    assert len(nextjs["evidence"]) >= 1
    assert nextjs["category"] == "framework"
    print(f"  [OK] Next.js: confidence={nextjs['confidence']}, evidence={nextjs['evidence']}, category={nextjs['category']}")


def test_more_matching_patterns_yield_higher_confidence():
    print("\n--- Tech detection: more matched signals -> higher confidence ---")
    weak_html = '<html><body class="wp-content">x</body></html>'
    strong_html = '<html><head><meta name="generator" content="WordPress 6.4"></head><body class="wp-content"><script src="/wp-includes/js/x.js"></script></body></html>'

    weak = next(d for d in detect_technologies_detailed(weak_html) if d["name"] == "WordPress")
    strong = next(d for d in detect_technologies_detailed(strong_html) if d["name"] == "WordPress")

    assert strong["confidence"] > weak["confidence"], (
        f"expected more evidence to raise confidence: weak={weak['confidence']} strong={strong['confidence']}"
    )
    print(f"  [OK] weak evidence confidence={weak['confidence']}, strong evidence confidence={strong['confidence']}")


def test_confidence_never_reaches_absolute_certainty():
    print("\n--- Tech detection: confidence is capped below 1.0 (heuristic, not certainty) ---")
    html = '<html><head><script src="/wp-content/x.js"></script><script src="/wp-includes/y.js"></script><meta name="generator" content="WordPress"></head></html>'
    wp = next(d for d in detect_technologies_detailed(html) if d["name"] == "WordPress")
    assert wp["confidence"] < 1.0
    print(f"  [OK] confidence capped at {wp['confidence']} even with all 3 signals present")


def test_no_false_technology_when_no_signatures_match():
    print("\n--- Tech detection: plain page with no known signatures reports nothing ---")
    html = '<html><head><title>Plain</title></head><body><p>Hello</p></body></html>'
    detailed = detect_technologies_detailed(html)
    flat = detect_technologies(html)
    assert detailed == []
    assert flat == []
    print("  [OK] no spurious detections on a signature-free page")


if __name__ == "__main__":
    import sys
    import traceback
    try:
        test_backward_compatible_flat_list_unchanged()
        test_detailed_detection_includes_confidence_and_evidence()
        test_more_matching_patterns_yield_higher_confidence()
        test_confidence_never_reaches_absolute_certainty()
        test_no_false_technology_when_no_signatures_match()
        print("\n[OK] ALL TECH DETECTION QUALITY TESTS PASSED")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
