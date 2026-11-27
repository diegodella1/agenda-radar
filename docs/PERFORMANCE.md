# Frontend performance

The application keeps server-rendered HTML and vanilla JavaScript. No frontend framework or bundler is required.

## Changes

- Help, onboarding and job polling load on demand. An active tour still resumes automatically. The criteria editor loads only on its page and builds closed sections on first expansion or full validation.
- Criteria dictionaries reconcile rows by key. Existing inputs and focus survive additions/removals. Draft changes invalidate preview immediately; status updates are grouped per animation frame. Diagnostic JSON serializes only when needed.
- Concurrent GETs share one pending promise; success and failure both release it. Completed results are not cached, so later requests see current data. Pending forms/buttons reject duplicate submissions. Job polling is shared by ID and backs off from 1.5 to 5 seconds, with a three-minute polling window.
- Static URLs use content hashes, including WOFF2 URLs inside CSS. Matching versions receive one-year immutable caching; unversioned or stale versions revalidate. Both static prefixes work without demo session creation. Private HTML/API responses remain `no-store`. Text resources use gzip when accepted.
- Local Fira Sans WOFF2 files preserve the full character set and OFL license. Fallback metrics reduce font shifts. The tiny external navigation initializer establishes mobile menu state before paint; remaining scripts are deferred or imported on demand.
- Editor loading space, result placeholders and notifications outside document flow prevent asynchronous content from pushing the page. No raster images are currently used in the application, so no WebP conversion applies; SVG stays vector.

## Measurements

Three cold/warm runs per route, at 390×950 and 1440×950. Chromium, CPU slowdown ×4, 80 ms network latency and 200 KB/s download. Measurements wait for `document.fonts.ready` and two animation frames. Data comes from an isolated offline fixture, with the tutorial inactive.

Mobile medians, transferred bytes (HTML and resources):

| Route | Before, cold | After, cold | After, warm |
| --- | ---: | ---: | ---: |
| `/home` | 655,314 | 213,807 | 2,294 |
| `/login` | 682,526 | 220,494 | 935 |
| `/demo/` | 788,844 | 227,806 | 7,901 |
| `/demo/admin/config` | 727,695 | 231,289 | 4,524 |

Radar cold transfer fell 71%; editor fell 68%. Font files fell from 638,872 to 207,656 bytes (67.5%). Warm demo transfers previously reloaded resources because its static responses inherited `no-store`.

Maximum CLS across all runs: radar mobile 0.4748 → 0.0001; editor mobile 0.6990 → 0; editor desktop 0.3517 → 0.0001. Every measured route remained below 0.003 after the change. These are lab measurements, not field Core Web Vitals. The shared host was under load; elapsed-time results should not be interpreted as a production speed guarantee.

Raw local reports: `artifacts/performance/before.json` and `after.json` (generated artifacts, not committed).

Validation completed: the 64-test Python suite initially passed 62 tests. After fixing demo login asset resolution and updating the font-family assertion, both failed cases plus static caching/security coverage passed in a 17-test rerun. Browser checks passed for the criteria editor, public pages, demo flows, seven-step onboarding and performance regressions; two job-polling tests passed. Ruff and whitespace checks passed.

## Reproduce

Use the existing Python development environment and Playwright with Chromium. Start `PYTHONPATH=src .venv/bin/python scripts/serve-performance.py`; wait for the server startup message. This creates only temporary synthetic data and ignores `.env`.

Run with `SMOKE_BASE_URL=http://127.0.0.1:8791` and, when Playwright is not installed locally, `PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs`:

```sh
node scripts/measure-performance.mjs
node scripts/smoke-performance.mjs
node scripts/smoke-criteria.mjs
node scripts/smoke-onboarding.mjs
node scripts/smoke-public.mjs
node scripts/smoke-demo.mjs
node --test scripts/test-jobs.mjs
.venv/bin/python -m pytest
```

Regenerate fonts with `uv run --with 'fonttools[woff]' scripts/build-fonts.py`. The script preserves source timestamps and updates CSS font hashes. Restart the server after changing assets so template versions match their contents. Include the new static modules and WOFF2 files in deployment; existing package-data globs cover them.
