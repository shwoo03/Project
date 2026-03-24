# Front Clone Coding - Agent Guide

## Why

This project captures live websites through Playwright, rewrites the captured frontend into an offline-friendly package, and generates backend handoff artifacts so the result can be replayed and extended locally.

## What

- `bin/cli.js` - CLI entrypoint. The literal `ui` argument boots `web/server.js`.
- `src/index.js` - main orchestration for staging, capture, rewriting, artifact generation, and final output merge/update flows.
- `src/crawler/page-crawler.js` - single-page Playwright capture with HAR recording, route tracking, storage snapshots, screenshots, and DOM extraction.
- `src/crawler/site-crawler.js` - recursive crawl queue, registrable-domain or hostname scope enforcement, login-gate heuristics, and destructive-link filtering.
- `src/crawler/network-interceptor.js` - request/response capture for assets, XHR/fetch, and WebSocket events.
- `src/downloader/asset-downloader.js` - persists intercepted assets into `public/`.
- `src/processor/html-processor.js` - Cheerio-based HTML rewrite for `href`, `src`, `action`, inline styles, and captured metadata.
- `src/processor/css-processor.js` - PostCSS + `postcss-url` rewrite for CSS imports and asset URLs.
- `src/processor/js-processor.js` - Babel/es-module-lexer-based JS rewrite for imports, static asset references, and runtime endpoint references.
- `src/processor/api-processor.js` - generates OpenAPI 3.1.0, AsyncAPI 3.0.0, GraphQL summaries, and HTTP mock manifests.
- `src/scaffolder/project-scaffolder.js` - emits generated replay runtime files under `server/`, plus root `server.js`, `package.json`, and replay README.
- `src/utils/url-utils.js` - domain root calculation, scope checks, URL normalization, asset/view path mapping, and public URL safety validation.
- `src/utils/playwright-runtime.js` - runtime mismatch detection and recovery hints tied to the pinned Playwright image.
- `web/server.js` - Express dashboard API, job lifecycle, SSE log streaming, output browser, and structured job errors.
- `web/public/` - static dashboard UI assets.
- `tests/` - Node.js built-in test runner coverage for crawler behavior, processor rewrites, runtime errors, and Web UI flows.
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

## Validation

- Default verification: `npm test`
- Web UI changes: `node bin/cli.js ui`
- Docker/runtime changes: `docker compose up -d --build`
- Crawl/runtime changes: prefer automated tests first; keep live-site manual runs minimal and non-destructive

## Skill Routing

- Crawler, Playwright runtime, scope logic, HAR capture, request interception: `$crawler-engine`
- HTML, CSS, JS, asset persistence, URL rewriting: `$asset-rewriter`
- Hyperlink classification, in-scope vs out-of-scope behavior, disabled-link UX: `$link-handler`
- OpenAPI/AsyncAPI/GraphQL docs, mocks, replay scaffold, generated package output: `$spec-generator`
- Dashboard API, SSE logs, job polling/cancellation, output browser, UI behavior: `$web-dashboard`
- Docker image sync, Compose flow, runtime packaging, container UX: `$docker-infra`
- New tests, regression coverage, verification follow-up: `$test-suite`
