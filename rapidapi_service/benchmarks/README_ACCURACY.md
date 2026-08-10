# Extraction Accuracy Benchmark

A real, but intentionally **small**, hand-curated accuracy benchmark — not
the 1000-URL production dataset a fully mature project would eventually
want, but enough to catch real regressions and give an honest signal beyond
"the README says it's fast and secure."

## Running it

```bash
cd rapidapi_service
python benchmarks/bench_accuracy.py [output_path.json]
```

This hits **real, live URLs** over the real network using the actual
extraction pipeline (`fetch_and_extract_raw` — no mocking). It is not part
of `pytest tests/` and does not run in CI: live sites change, go down, or
start rate-limiting/blocking, so this is a manually-run signal, not a
blocking gate.

## Methodology

- **Dataset**: `accuracy_dataset.json`, 29 real URLs across 9 categories
  (ecommerce, news, blogs, SaaS, SPA, WordPress, multilingual, small sites,
  and one deliberately bot-protected site).
- **Ground truth**: independently verified by fetching each URL with plain
  `curl` (not this API, not selectolax) and regex-matching the raw HTML,
  separately from any code in this repository, on 2026-08-10. Technology
  signatures were confirmed the same way (grepping raw HTML for literal
  strings like `cdn.shopify.com`, `_next/static`).
- **What's checked per URL**: title substring match, JSON-LD presence
  (skipped for pages large enough that adaptive-byte-limit truncation could
  legitimately cause a miss — see below), technology detection recall
  where a signature was independently confirmed, and whether the request
  errored unexpectedly.
- **What's NOT covered by this pass**: price/product accuracy across a
  large e-commerce sample, image accuracy, contact-info accuracy (most
  real sites don't have machine-checkable public contact info), and a
  large enough N to be statistically meaningful per category. These are
  real gaps, not oversights — building a properly labeled 1000-URL dataset
  is its own project.

## Known limitations of this methodology

- **content_truncated changes what "correct" means.** The two largest
  Wikipedia article pages in the sample (~240KB/~440KB) get legitimately
  truncated by the adaptive byte-limit before JSON-LD (positioned late in
  the page) is reached. That's the byte-limit working as designed, not an
  extraction bug — the API is honest about it via `content_truncated:
  true`. `has_json_ld` is intentionally not asserted for those two entries;
  don't read "JSON-LD not found on a 240KB Wikipedia page" as a miss
  without checking `content_truncated` first.
- **Live sites are moving targets.** A URL that redirects differently,
  gets a new bot-detection rule, or changes its markup between when this
  dataset was built and when you run it can cause a "failure" that's
  really just the target site changing — not a regression in this
  repository. Re-verify against the live site before treating a benchmark
  failure as a code bug.
- **The bot-protection check is soft.** `w3schools.com` returned a
  confirmed 403 "Access Denied" during dataset construction; if it doesn't
  block a later run, that's recorded as informational
  (`expected_block_but_succeeded`), not a failure — bot-blocking behavior
  is inherently non-deterministic over time and this project has no
  interest in provoking it more aggressively than a normal single request.

## What this benchmark actually found

The first real run of this benchmark (before any fix) scored **61% overall
pass rate**, with systematic `metadata.title = None` failures concentrated
on modern CDN-fronted sites (Vercel, WordPress.org, Next.js/Vue/Svelte/
Angular doc sites, ...). Root cause: `app/fetcher/client.py` advertises
`Accept-Encoding: gzip, deflate, br`, but the `brotli` decoder package
wasn't in `requirements.txt` — Brotli-compressed responses were silently
passed through undecoded and force-decoded as UTF-8, producing
garbage/empty extraction with **no error raised anywhere**. Adding `brotli`
to requirements.txt (see the main README's CHANGELOG-style feature notes)
fixed it with no other code change and brought the same 29-URL run to
**100% pass rate, 0 unexpected errors**. See `tests/test_brotli_decoding.py`
for the permanent regression test.
