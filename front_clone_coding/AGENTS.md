# Front Clone Coding - Agent Guide

## Why

This project captures live websites through Playwright, rewrites the captured frontend into an offline-friendly package, and generates backend handoff artifacts so the result can be replayed and extended locally.

## Current Mission

The current project phase is not broad product expansion. The active mission is:

1. Pick real public websites and crawl them narrowly.
2. Run the generated local replay and compare it against the live site.
3. Find the most important fidelity gaps, crawl noise, replay failures, and runtime mismatches.
4. Improve the shared pipeline so the same fix helps many sites, not just one target.
5. Record durable findings in `research/` so future work starts from evidence instead of memory.

Everything agents do should support this crawl -> replay -> compare -> improve loop.

## Generic-First Principle

The most important engineering rule in this repository is:

- fixes must target reusable failure patterns, not just one website's current symptoms

When a real site reveals a bug, agents should first describe the issue in generic terms such as:

- host-aware path resolution
- same-scope runtime navigation rewrite
- charset preservation
- render-critical vs non-critical runtime classification
- asset-path duplication
- replay route resolution

Only then should they change code. Do not patch by domain name, host name, product name, or page slug unless all generic approaches have clearly failed and the limitation is documented.

## Out Of Scope By Default

- Do not invent unrelated product ideas, dashboards, or workflows that do not improve crawl fidelity, replay fidelity, verification quality, or research traceability.
- Do not optimize for broader crawl coverage if replay accuracy is the real bottleneck.
- Do not add site-specific hacks unless a generic solution is clearly impossible and the limitation is documented.
- Do not spend time on cosmetic refactors that do not improve debugging, correctness, or repeatability for live-site validation.
- Do not treat noisy third-party failures as priority bugs unless they measurably harm rendered replay output or verification outcomes.

## What

- `bin/cli.js` - CLI entrypoint. The literal `ui` argument boots `web/server.js`.
- `src/index.js` - main orchestration for staging, capture, rewriting, artifact generation, and final output merge/update flows. Delegates to pipeline submodules.
- `src/pipeline/page-dedup.js` - page deduplication, canonical URL resolution, and site map merging.
- `src/pipeline/page-route-manifest.js` - route manifest generation, route index building, and locale-aware fallback maps.
- `src/pipeline/replay-signals.js` - bootstrap and hydration signal extraction from captured HTML.
- `src/pipeline/output-finalize.js` - staging-to-output finalization with filesystem retry logic and numbered directory allocation.
- `src/crawler/page-crawler.js` - single-page Playwright capture with HAR recording, route tracking, storage snapshots, screenshots, and DOM extraction.
- `src/crawler/site-crawler.js` - recursive crawl queue, registrable-domain or hostname scope enforcement, login-gate heuristics, and destructive-link filtering.
- `src/crawler/network-interceptor.js` - request/response capture for assets, XHR/fetch, and WebSocket events.
- `src/downloader/asset-downloader.js` - persists intercepted assets into `public/`.
- `src/processor/html-processor.js` - Cheerio-based HTML rewrite for `href`, `src`, `action`, inline styles, and captured metadata.
- `src/processor/css-processor.js` - PostCSS + `postcss-url` rewrite for CSS imports and asset URLs.
- `src/processor/js-processor.js` - Babel/es-module-lexer-based JS rewrite for imports, static asset references, and runtime endpoint references.
- `src/processor/api-processor.js` - generates OpenAPI 3.1.0, AsyncAPI 3.0.0, GraphQL summaries, and HTTP mock manifests.
- `src/scaffolder/project-scaffolder.js` - emits generated replay runtime files under `server/`, plus root `server.js`, `package.json`, and replay README. Templates are externalized in `src/scaffolder/templates/`.
- `src/verifier/content-comparison.js` - content marker extraction, token overlap, drift assessment, title comparison (split from replay-verifier).
- `src/verifier/runtime-diagnostics.js` - runtime error classification, failure assessment, diagnostics building (split from replay-verifier).
- `src/utils/url-utils.js` - domain root calculation, scope checks, URL normalization, asset/view path mapping, and public URL safety validation.
- `src/utils/playwright-runtime.js` - runtime mismatch detection and recovery hints tied to the pinned Playwright image.
- `web/server.js` - Express dashboard API, job lifecycle, SSE log streaming, output browser, and structured job errors.
- `web/public/` - static dashboard UI assets.
- `src/utils/mock-sanitizer.js` - heuristic-based sanitization of user-specific fields in render-supporting API mock responses.
- `src/utils/concurrency-utils.js` - semaphore-style `batchParallel` worker pool for bounded parallel processing across the pipeline.
- `tests/` - Node.js built-in test runner coverage (200 tests) organized per module: css-processor, html-processor, js-processor, api-processor, mock-sanitizer, concurrency-utils, network-interceptor, asset-downloader, frontier-utils, page-route-manifest, replay-verifier, verifier-unit, crawl-quality, web-ui, and supporting utilities.
- `.codex/skills/` - project-specific Codex skills for common workstreams in this repository.

## Non-Negotiable Rules

- Keep Playwright versions synchronized across `package.json`, `Dockerfile`, `README.md`, `src/utils/constants.js`, `src/utils/playwright-runtime.js`, and related tests.
- Preserve URL safety and crawl safety behavior. Do not weaken public-URL validation, same-scope enforcement, destructive-link filtering, tracker filtering, or login-gated page handling without updating tests.
- Treat the generated output shape as a public contract: `public/`, `views/`, `server/spec/`, `server/mocks/`, `server/adapters/express/`, `server/docs/`, root `server.js`, root `package.json`, and generated `README.md`.
- Registrable-domain scope is the default contract. Subdomains belonging to the same registrable domain remain in scope; unrelated domains do not.
- `PageCrawler` must continue to use `serviceWorkers: 'block'`, HAR recording when `captureDir` is set, SPA route tracking through `addInitScript`, and storage/session capture for debug artifacts.
- Web UI contracts must stay consistent: `POST /api/clone`, `GET /api/jobs/:jobId`, `GET /api/jobs/active/current`, `POST /api/jobs/:jobId/cancel`, `GET /api/logs`, and `GET /api/output`.
- If you add or tighten link disabling behavior, keep it aligned with `src/processor/html-processor.js`, `src/utils/url-utils.js`, generated `views/`, and tests.
- Prefer extending the existing utilities and logger event flow instead of adding parallel helper stacks.
- `npm test` must pass after meaningful changes.
- When live-site validation reveals a durable finding, update `research/` with machine-readable records and curated notes instead of leaving the knowledge only in chat or memory.
- Prefer generic replay-fidelity improvements over target-site special casing. If a site-specific exception is unavoidable, document why the generic path failed.
- Do not key core behavior off a single site's domain, URL, or route shape when the same behavior can be driven by shared signals, payload semantics, DOM structure, or normalized path rules.
- Before implementing a live-site fix, write down the generic failure class it belongs to; if you cannot name a reusable class, pause and rethink the change.
- Every important live-site fix should leave behind one of the following:
  - a shared utility improvement
  - a broader rewrite/classification rule
  - a deterministic regression test
  - a documented limitation in `research/`

## Validation

- Default verification: `npm test` (200 tests) and `npm run lint`
- Web UI changes: `node bin/cli.js ui`
- Docker/runtime changes: `docker compose up -d --build` (HEALTHCHECK enabled, resource limits 4G/2CPU)
- Crawl/runtime changes: prefer automated tests first; keep live-site manual runs minimal and non-destructive
- For fidelity work, prefer this validation order: targeted tests -> narrow live crawl -> local replay check -> research note update

## Agent Workflow

- Complex fidelity gaps, multi-file refactors, and architectural changes should start with the `planner` agent.
- If the user explicitly asks for research or asks why a live site failed, begin with read-only exploration and evidence collection before changing code.
- After the plan is approved or locked, hand implementation work to GPT-5.3-Codex workers.
- Hand regression coverage and verification follow-up to the GPT-5.3-Codex `test_worker`.
- Prefer the explicit flow `Reproduce -> Research -> Plan -> Implement -> Test -> Re-run -> Record`.
- Planner outputs should be decision-complete and should call out public contract changes, assumptions, and required validation.
- In every plan and implementation summary, explicitly state why the proposed fix is generic and what other classes of sites it should help.

## Site Validation Priorities

When testing on a real site, prioritize these questions in order:

1. Does the clone complete?
2. Does the local replay open the correct page?
3. Are critical HTML, CSS, JS, fonts, and images served locally?
4. Do cloned links stay local and uncloned links stay disabled?
5. Are blocked external requests mostly harmless noise, or are they first-paint critical?
6. Is the fix generic enough to help other modern sites?
7. If the fix is not generic enough yet, what reusable failure class is still missing?

## Skill Routing

- Crawler, Playwright runtime, scope logic, HAR capture, request interception: `$crawler-engine`
- HTML, CSS, JS, asset persistence, URL rewriting, local route remapping, and disabled-link behavior: `$asset-rewriter`
- OpenAPI/AsyncAPI/GraphQL docs, mocks, replay scaffold, generated package output: `$spec-generator`
- Dashboard API, SSE logs, job polling/cancellation, output browser, UI behavior: `$web-dashboard`
- Docker image sync, Compose flow, runtime packaging, container UX: `$docker-infra`
- New tests, regression coverage, verification follow-up: `$test-suite`
