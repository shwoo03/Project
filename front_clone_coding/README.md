# Front Clone Coding

Playwright-based tooling for turning a live site into an offline replay package with captured assets, HTML snapshots, API specs, mocks, and an Express adapter.

## Features

- Browser-driven crawling for static and SPA-style pages
- Recursive same-domain crawling with depth and page limits
- Asset capture and URL rewriting for offline-friendly client output
- API capture for XHR, fetch, GraphQL, and WebSocket traffic
- OpenAPI-style documentation and mock response generation
- Visual analysis docs for layout, components, and missing behaviors
- Optional generated Express scaffold for local backend handoff

## Install

```bash
npm ci
npx playwright install chromium
```

## Docker

This project expects the Playwright Docker image version to match the installed Playwright package version.

```bash
docker compose up -d --build
```

If Playwright is upgraded, rebuild the container image before starting the UI again. The current required image is `mcr.microsoft.com/playwright:v1.58.2-noble`.
The Playwright base image already includes the matching browser runtime, so the Docker build only installs Node dependencies from `package-lock.json`.
The Compose setup also enables `init: true` and `ipc: host`, which are the recommended defaults for Playwright containers.

Quick commands:

```bash
npm run docker:rebuild
# or, for a full cleanup:
npm run docker:reset
```

## CLI usage

```bash
node bin/cli.js https://example.com

node bin/cli.js https://example.com \
  --wait 5000 \
  --viewport 1440x900 \
  --screenshot \
  --recursive \
  --max-pages 10
```

## Key options

| Option | Description | Default |
| --- | --- | --- |
| `-w, --wait <ms>` | Extra wait time after page load. | `3000` |
| `-r, --recursive` | Enable recursive crawl within the selected domain scope. | `false` |
| `--max-pages <n>` | Maximum number of pages to crawl. | `20` |
| `--max-depth <n>` | Maximum crawl depth. | `3` |
| `-c, --concurrency <n>` | Number of concurrent page workers. | `3` |
| `--crawl-profile <mode>` | `accurate`, `balanced`, `lightweight`, or `authenticated`. | `accurate` |
| `--network-posture <mode>` | `default`, `authenticated`, `sensitive-site`, or `manual-review`. | `default` |
| `--representative-qa` | Emit representative page QA summaries in crawl manifests. | `false` |
| `--domain-scope <mode>` | `registrable-domain` or `hostname`. | `registrable-domain` |
| `--update-existing` | Merge new generated output into an existing target directory. | `false` |
| `--no-scaffold` | Skip generated backend scaffold files. | scaffold enabled |

## Architecture Notes

Implementation research and migration notes live under `docs/`.

The main orchestrator (`src/index.js`) delegates to focused pipeline modules:

- `src/pipeline/page-dedup.js` - page deduplication and canonical URL resolution
- `src/pipeline/page-route-manifest.js` - route manifest, route index, and locale-aware fallback maps
- `src/pipeline/replay-signals.js` - bootstrap and hydration signal extraction
- `src/pipeline/output-finalize.js` - staging-to-output finalization with filesystem retry logic

## Replay Fidelity Notes

- Recursive multi-host crawls now save HTML under host-aware view paths such as `views/www.example.com/index.html`, which avoids subdomain root-page collisions during replay.
- Canonical page dedupe now merges trailing-slash variants into one representative HTML file before manifests and verification are generated.
- Replay HTML and JS now apply static external-runtime filtering in `Minimal` mode for non-critical `recaptcha`, adtech, telemetry, logging, pixel, and conversion endpoints.
- Filtered runtime calls are rewritten to the local inert endpoint `/__front_clone_noop__`, while visible consent or functional DOM is preserved by default.
- Same-site logging and telemetry URLs are now classified before the generic same-site runtime fallback, so they stay removable instead of being promoted to replay-critical runtime.
- Replay verification classifies blocked external requests into `render-critical-asset`, `render-critical-runtime`, `non-critical-runtime`, and `anti-abuse` so residual fidelity gaps are easier to diagnose.
- Replay verification page summaries now report mock API hits as page-level deltas instead of cumulative session totals.
- Replay API candidates are now split into strict `render-critical` and informational `render-supporting` groups, so cache-backed state refresh queries do not create false replay-failure warnings.
- Inline bootstrap signals such as embedded user or membership state are now recorded at the page level and used to downgrade same-site state-refresh GraphQL calls when first paint already has equivalent fallback data.
- Same-site POST requests that carry explicit logging-envelope payloads are now treated as `non-critical` even when their pathname does not look like `/log`, so strict replay candidates stay aligned with visible first-paint dependencies instead of hidden client logging transports.
- Hidden navigation sources such as `onclick`, `location.href`, `window.open`, `javascript:` URLs, and serialized same-site destinations now follow the same local-first replay contract as visible anchors when they can be resolved safely.
- Query-addressed legacy pages can now receive distinct replay routes when the same host and pathname diverge by meaningful query state, which helps government and CMS portals avoid collapsing different pages into one HTML file.
- Charset diagnostics now preserve transport metadata, decode confidence, and mismatch hints so replay reports can separate rendering gaps from text-decoding mistakes on legacy portals.
- CSS recovery now records discovered, recovered, failed, and canonicalized assets, and unrecoverable CSS-linked resources fail soft instead of turning into live leakage by default.
- Replay verification now records runtime console errors, uncaught exceptions, and failed same-origin runtime requests separately from route misses and blocked external traffic.
- Output finalize now retries bounded `EBUSY` and `EPERM` style conflicts and emits structured guidance when a sync client, file explorer, or running replay server is holding the target directory open.
- Replay-only runtime guards now absorb same-origin DOM assumption failures into reusable runtime failure classes instead of treating every portal script exception like a page-level hard blocker.
- Replay verification now compares heading, main-content, and whole-body text separately, so boilerplate-heavy pages can be classified as comparison noise instead of false content failures.
- Title comparison now reports confidence and encoding-noise hints, which reduces false `title-drift` warnings on legacy or mojibake-prone pages.
- Same-origin runtime request failures are now classified into `runtime-data-miss` (API/JSON), `runtime-asset-miss` (image/font), `runtime-script-failed`, and `runtime-style-failed` for finer severity assessment.
- Widget soft-fail warnings are now downgraded to informational `notes` when page content matches and the page shell is intact, reducing false-positive warning noise.
- Content comparison now separates `runtime-induced-partial-match` from `partial-content-match` when runtime failures accompany the content gap, so operators can distinguish crawl-sourcing issues from runtime replay issues.
- Hidden navigation detection now recognizes `fn*`, `nav*`, and `jump*` wrapper function patterns and `select[onchange]` handlers that navigate via `this.options[this.selectedIndex].value`.
- Hidden navigation now supports partial literal matching for mixed literal+variable concatenation patterns such as `location.href = '/board/list.do?menuNo=' + menuNo`, using the fallbackMap hostname+pathname uniqueness guarantee to safely resolve the target.
- Form GET actions with `<input type="hidden">` children are now automatically reconstructed into full GET URLs and matched against the pageRouteIndex, enabling localization of query-parameter-driven navigation forms.
- Crawl cancellation via AbortSignal now propagates from the Web UI through SiteCrawler workers to PageCrawler checkpoints, allowing crawls to stop within 2-3 seconds of a cancel request.
- SiteCrawler workers now enforce a per-page timeout (3x PAGE_LOAD_TIMEOUT) and record timed-out pages as `crawlState: 'timeout'` instead of blocking indefinitely.
- Render-supporting API mock responses (classified as `bootstrap-backed-state-refresh`) are now automatically sanitized to replace user-specific fields (emails, JWTs, UUIDs, session tokens, user IDs) with generic placeholders, using a 3-tier key heuristic and value-type pattern matching that never touches render-critical content.
- The HTTP mock manifest now includes `sanitized` and `sanitizedFields` metadata per entry, and the replay verifier reclassifies `runtime-induced-partial-match` to `mock-driven-sanitized-replay` when sanitized mocks are present for the page.
- Hidden navigation now supports variable-prefix + literal-suffix concatenation patterns such as `location.href = baseUrl + '/page.do'`, extracting the trailing literal suffix for fallbackMap pathname matching.
- Template literal navigation expressions such as `` location.href = `${baseUrl}/page.do` `` are now recognized, with the static suffix after the last `${}` expression extracted and matched against the fallbackMap.
- The `directNavigationPatterns` callback now guards against misprocessing backtick strings that contain `${...}` template expressions, preventing false disabling of template literal navigation targets.
- Asset download, CSS processing, JS processing, and HTML page processing are now fully parallelized using a shared `batchParallel` semaphore-style worker pool, with configurable concurrency limits per pipeline stage (10/6/8/4 respectively).
- JSP-style semicolon path parameters (e.g., `;CUSTOM_SESSION=...`, `;JSESSIONID=...`) are now stripped from URL pathnames before generating filesystem paths, fixing complete CSS breakage on JSP-based subdomains like `culture.jongno.go.kr`.
- ESLint configuration now includes test-file globals (`global`, `Response`, `Headers`, `TextDecoder`), and all source/test warnings (unused variables, useless assignments, useless escapes) have been resolved, achieving 0 errors and 0 warnings.
- Generated output README now includes dynamic sections for crawl summary (pages, CSS recovery rate), hidden navigation stats, API mock breakdown (render-critical/supporting/non-critical, sanitized count), and known limitations, all conditionally rendered based on available data.
- Scaffolder template literals (Express adapter 285 lines, runtime guard 141 lines) have been extracted to standalone files under `src/scaffolder/templates/`, reducing `project-scaffolder.js` from 577 to 248 lines.
- The Web UI now displays a real-time progress bar with stage labels (Crawling/Downloading), page counters, and current URL detail during crawl and asset download phases, powered by structured `progress` events via SSE.
- The replay verifier has been split into three focused modules: `content-comparison.js` (187 lines) for text marker and drift analysis, `runtime-diagnostics.js` (303 lines) for failure classification, and the orchestration core in `replay-verifier.js` (reduced from 1,408 to 940 lines), with re-exports preserving backwards compatibility.

## Current Status

As of `2026-03-30`, the project is strongest on:

- replayable local route generation for pages that were actually saved
- CSS and first-paint asset recovery for public and legacy portal sites
- strict vs supporting runtime classification for cache-backed or secondary async modules
- replay verification that distinguishes route issues, external noise, encoding diagnostics, and runtime errors
- **fine-grained runtime failure classification** (`runtime-data-miss`, `runtime-asset-miss`, `runtime-script-failed`, `runtime-style-failed`) for precise severity assessment
- **runtime-induced content gap separation** from true content sourcing gaps (`runtime-induced-partial-match`, `runtime-induced-content-gap`)
- **abort signal propagation** allowing immediate crawl cancellation from the Web UI
- **comprehensive hidden navigation coverage** including literal prefix, variable prefix + literal suffix, template literals, and form GET reconstruction
- **automatic mock sanitization** of render-supporting API responses to replace user-specific fields with generic placeholders
- **parallel pipeline processing** via `batchParallel` for asset downloads, CSS/JS/HTML processing (50-80% faster)
- **JSP semicolon path parameter stripping** for correct CSS serving on JSP-based portals
- **clean ESLint** with 0 errors and 0 warnings across all source and test files
- **enriched output README** with crawl statistics, CSS recovery rates, API mock summaries, and known limitations
- **real-time progress UI** with stage-based progress bar, page counters, and asset download tracking in the Web dashboard
- **modular verifier** with content-comparison and runtime-diagnostics split into focused submodules
- **modular codebase** with index.js reduced to 794 lines, scaffolder templates externalized, and 200 automated tests

The project is still not a perfect one-click clone for all sites. The main remaining gaps are:

- legacy portal widget scripts that still degrade into `runtime-widget-soft-fail` (now classified as `note` when content matches)
- pure-variable hidden navigation patterns with no literal component (e.g., `goPage(baseUrl + menuNo)`) cannot be statically resolved
- personalized page mock sanitization only covers generic field patterns; site-specific non-standard keys (e.g., `mbrNo`, `loginHash`) may pass through unsanitized

In short: the pipeline now produces a stable, inspectable local replay package with precise fidelity diagnostics, but some sites still need more generic runtime-hardening work before they feel indistinguishable from the original.

Recent validation baseline:

- `jongno.go.kr` narrow public reruns now reach the correct local route with `routeReached=true` and `responseStatus=200`.
- CSS recovery on the Jongno baseline remains strong at `1649 / 1657` discovered CSS-linked assets recovered.
- The main remaining Jongno runtime issue is now a soft widget-level failure classified as a `note` (not a warning) when the page shell and content are intact.
- Content verification on the Jongno main page now reports high-confidence title parity and strong marker overlap, so remaining gaps are less likely to be verifier noise.

## Performance Notes

The default crawl settings prioritize replay fidelity over raw speed.

- Default CLI mode uses `accurate` crawl profile.
- Default `--wait` is `3000ms`, and `accurate` multiplies that wait by `1.3`.
- Default `--scroll-count` is `5`.
- Recursive crawls also pay for safe interaction discovery, asset recovery, spec generation, scaffold generation, and replay verification.

If you want faster iteration during development, prefer:

```bash
node bin/cli.js https://example.com \
  --recursive \
  --max-pages 8 \
  --max-depth 1 \
  --concurrency 4 \
  --wait 1200 \
  --scroll-count 1 \
  --crawl-profile balanced
```

Use `accurate` again for final validation runs.

## Output structure

Generated packages are always written under `output/<main-domain>/`.
The folder name uses the registrable domain such as `netflix.com` or `example.co.uk`, even when crawl scope is set to `hostname`.
If the canonical folder already exists and the run is not using `--update-existing`, a new sibling folder such as `output/netflix.com-2/` or `output/netflix.com-3/` is created instead of deleting the previous package.

```text
output/example.com/
  public/                 Captured CSS, JS, images, fonts, media, misc assets
  views/                  Route-based HTML snapshots
  server/
    spec/                 OpenAPI, AsyncAPI, GraphQL reports, crawl manifest
                          resource-manifest, page-quality-report, crawl-profile
    mocks/                HTTP payloads, HTTP manifest, WebSocket frames
    adapters/express/     Replay adapter runtime
    docs/                 Visual, crawl, integration, and missing-behavior reports
  README.md               Generated replay package guide
  package.json            Generated runtime package
  server.js               Generated server entrypoint shim
```

## Web UI

```bash
node bin/cli.js ui
```

This starts a local dashboard at `http://localhost:4000` by default.

If you run the provided Docker Compose setup, the UI is exposed at `http://localhost:20000` because the container sets `PORT=20000`.

The dashboard provides:

- job-based clone execution
- live SSE logs
- status polling for the active run

If the browser runtime is missing, the job status API returns a structured error with a recovery hint, and the terminal panel keeps the raw launch details.

## Test

```bash
npm test
```

The test suite (200 tests) covers utility behavior, crawler heuristics, API capture shaping, verifier pure-function logic, and CLI/web smoke flows that do not require mutating tracked source files. Tests are organized by module:

- `tests/css-processor.test.js` - CSS rewriting and asset recovery
- `tests/html-processor.test.js` - HTML rewriting and hidden navigation
- `tests/js-processor.test.js` - JS AST transforms and runtime filtering
- `tests/api-processor.test.js` - API artifact generation
- `tests/replay-verifier.test.js` - replay verification integration
- `tests/verifier-unit.test.js` - verifier pure function unit tests
- `tests/crawl-quality.test.js` - frontier scoring and crawl heuristics
- `tests/web-ui.test.js` - Web UI server and job lifecycle

Lint with:

```bash
npm run lint
```

## Research Knowledge System

The repo includes a file-first `research/` workspace for implementation learnings, code-linked insights, and experiments.

```bash
npm run knowledge:init
npm run knowledge:report
```

Use `research/data/*.jsonl` as the canonical machine store and `research/notes/**/*.md` as the curated review layer. `research/schema/postgres.sql` is only a future migration path when the file-first workflow no longer scales.

## License

MIT
