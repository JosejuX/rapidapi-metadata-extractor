"""
Real-world extraction accuracy benchmark (Plan §105 "precision/data-quality
benchmark", raised again in external review feedback: "I'd want to see this
before calling the API excellent").

Runs the ACTUAL extraction pipeline (fetch_and_extract_raw — real network,
real SSRF validation, real everything, no mocking) against a small,
hand-curated set of real URLs (benchmarks/accuracy_dataset.json) with
independently-verified ground truth, and reports:

  - title / JSON-LD detection accuracy (overall and per category)
  - technology-detection recall where a known signature was confirmed
  - error/timeout rate, and specifically whether a known-to-block site
    (w3schools.com) is at least classified as a clean error rather than
    silently returning wrong data
  - latency percentiles (this is a live-network run, not the stubbed-
    transport methodology in bench_extraction.py, so figures here can't be
    compared directly to that file's numbers)

This is NOT the 1000-URL production benchmark a mature project would
eventually want (see accuracy_dataset.json's _methodology note and
README_ACCURACY.md for what's intentionally out of scope for this pass).
It's small enough to hand-verify and rerun cheaply, and big enough to catch
a real regression across categories this project cares about.
"""
import asyncio
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.errors import AppError  # noqa: E402
from app.extraction.pipeline import fetch_and_extract_raw  # noqa: E402

DATASET_PATH = os.path.join(os.path.dirname(__file__), "accuracy_dataset.json")
OUT_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "accuracy_report.json")


async def run_one(entry):
    url = entry["url"]
    t0 = time.perf_counter()
    result = {"url": url, "category": entry["category"], "checks": {}, "error": None}
    try:
        data = await fetch_and_extract_raw(url)
        result["duration_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        if entry.get("expect_blocked"):
            # Reaching here means it did NOT block us this run -- not a
            # failure of this API, just means the target's behavior changed
            # (bot-blocking is inherently non-deterministic over time).
            result["checks"]["expected_block_but_succeeded"] = True
            return result

        if "title_contains" in entry:
            title = (data.get("metadata") or {}).get("title") or ""
            result["checks"]["title_match"] = entry["title_contains"].lower() in title.lower()
            result["title_found"] = title

        if "has_json_ld" in entry:
            has_json_ld = bool(data.get("json_ld_schemas"))
            result["checks"]["json_ld_match"] = has_json_ld == entry["has_json_ld"]
            result["json_ld_found"] = has_json_ld

        if "expected_technologies" in entry:
            detected = set(data.get("detected_technologies") or [])
            expected = set(entry["expected_technologies"])
            result["checks"]["tech_match"] = bool(detected & expected)
            result["technologies_found"] = sorted(detected)

        result["bot_protection_detected"] = data.get("bot_protection_detected", False)
        result["content_truncated"] = data.get("content_truncated", False)

    except AppError as e:
        result["duration_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        result["error"] = {"code": e.code, "detail": e.detail}
        if entry.get("expect_blocked"):
            result["checks"]["expected_block_confirmed"] = True
    except Exception as e:
        result["duration_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        result["error"] = {"code": "UNEXPECTED_EXCEPTION", "detail": f"{type(e).__name__}: {e}"}

    return result


async def main():
    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)

    results = []
    for entry in dataset["urls"]:
        print(f"  probing {entry['url']} ...", flush=True)
        results.append(await run_one(entry))

    # --- aggregate ---
    by_category = {}
    for r in results:
        by_category.setdefault(r["category"], []).append(r)

    def pct(numerator, denominator):
        return round(100.0 * numerator / denominator, 1) if denominator else None

    overall_checks = [c for r in results for c in r["checks"].values() if isinstance(c, bool)]
    unexpected_errors = [r for r in results if r["error"] and not r["checks"].get("expected_block_confirmed")]
    latencies = [r["duration_ms"] for r in results if "duration_ms" in r]

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_urls": len(results),
        "unexpected_errors": len(unexpected_errors),
        "unexpected_error_rate_pct": pct(len(unexpected_errors), len(results)),
        "overall_check_pass_rate_pct": pct(sum(overall_checks), len(overall_checks)),
        "latency_ms": {
            "p50": round(statistics.median(latencies), 1) if latencies else None,
            "p95": round(sorted(latencies)[int(len(latencies) * 0.95)], 1) if latencies else None,
            "max": round(max(latencies), 1) if latencies else None,
            "mean": round(statistics.mean(latencies), 1) if latencies else None,
        },
        "by_category": {},
    }

    for cat, entries in sorted(by_category.items()):
        checks = [c for r in entries for c in r["checks"].values() if isinstance(c, bool)]
        errors = [r for r in entries if r["error"] and not r["checks"].get("expected_block_confirmed")]
        summary["by_category"][cat] = {
            "n": len(entries),
            "check_pass_rate_pct": pct(sum(checks), len(checks)),
            "unexpected_errors": len(errors),
        }

    report = {"summary": summary, "results": results}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print("\n========== ACCURACY BENCHMARK SUMMARY ==========")
    print(f"URLs tested:              {summary['total_urls']}")
    print(f"Unexpected errors:        {summary['unexpected_errors']} ({summary['unexpected_error_rate_pct']}%)")
    print(f"Overall check pass rate:  {summary['overall_check_pass_rate_pct']}%")
    print(f"Latency p50/p95/max (ms): {summary['latency_ms']['p50']} / {summary['latency_ms']['p95']} / {summary['latency_ms']['max']}")
    print("\nBy category:")
    for cat, s in summary["by_category"].items():
        print(f"  {cat:<15} n={s['n']:<3} pass_rate={s['check_pass_rate_pct']}%  unexpected_errors={s['unexpected_errors']}")
    print(f"\nFull report written to {OUT_PATH}")

    if unexpected_errors:
        print("\nUnexpected errors:")
        for r in unexpected_errors:
            print(f"  - {r['url']}: {r['error']}")


if __name__ == "__main__":
    asyncio.run(main())
