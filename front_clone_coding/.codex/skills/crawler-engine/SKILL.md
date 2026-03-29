---
name: crawler-engine
description: >
  Playwright crawling engine work for recursive traversal, network interception,
  domain-scope calculation, login-gated handling, and browser context behavior.
---

# Crawler Engine Skill

Use this skill when changing crawl behavior, scope rules, Playwright context setup, request capture, or page discovery heuristics.

## Mission Focus

This repository is currently in a live-site validation phase. Use this skill to improve reproducible crawl behavior for real websites and to turn concrete crawl failures into generic pipeline fixes.

Do:

- reproduce narrow real-site failures when needed
- improve shared crawl heuristics, observability, and safety
- keep findings aligned with replay fidelity, not just page-count growth
- translate site-specific crawl failures into reusable scope, queue, interaction, or capture rules before editing code

Do not:

- widen crawl scope just to collect more pages when replay quality is the real issue
- add one-off site hacks before exhausting generic queue, scope, or capture improvements
- treat noisy `requestfailed` traffic as a bug unless it harms replay output or validation
- patch a crawler decision by matching one domain or route shape when a broader signal can express the same fix

## Core Files

- `src/crawler/page-crawler.js`
- `src/crawler/site-crawler.js`
- `src/crawler/network-interceptor.js`
- `src/utils/url-utils.js`
- `src/utils/playwright-runtime.js`
- `src/utils/constants.js`
- `src/index.js`

## Current Implementation Anchors

- `PageCrawler.crawl()` launches Chromium, creates a context with `serviceWorkers: 'block'`, and records HAR files when `captureDir` is provided.
- `context.addInitScript()` tracks SPA route changes via `pushState`, `replaceState`, and `popstate`.
- The crawler captures HTML, computed styles, image URLs, structured link candidates, forms, interactive elements, storage state, and session storage state.
- `SiteCrawler` defaults to `registrable-domain` scope and uses `getDomainRoot()` / `isInDomainScope()` from `src/utils/url-utils.js`.
- Recursive crawling filters tracker hosts, destructive URLs, static binary extensions, and login-gated follow-up pages unless `followLoginGated` is enabled.
- `ensurePlaywrightRuntimeReady()` returns structured mismatch guidance tied to the pinned Docker image.
- Frontier selection is now ranked and explainable rather than purely first-seen.
- Safe interaction discovery can expose additional replay-relevant routes without blindly widening crawl scope.
- Failed requests are retained for later recovery analysis rather than being treated as log-only noise.

## Rules

- Keep `serviceWorkers: 'block'` in the Playwright context unless the runtime contract changes everywhere.
- Preserve HAR recording behavior for capture/debug runs. If you change capture-dir semantics, update docs and tests together.
- Keep route tracking in `addInitScript()` so SPA-discovered URLs remain visible to recursive crawl logic.
- Continue capturing request, response, requestfinished, and requestfailed data through the network interceptor.
- Preserve `storageState()` capture and separate session storage JSON output when `captureDir` is enabled.
- Use `tldts`-backed registrable-domain scope for the default multi-page crawl contract.
- Allow subdomains inside the same registrable domain when scope is `registrable-domain`; exclude unrelated domains.
- Do not weaken destructive-link, tracker, or login-gate heuristics without explicit test updates.
- Prefer changing shared URL utilities instead of re-implementing domain checks inside crawler classes.
- Prefer ranked, explainable frontier behavior over first-seen queue growth.
- Treat crawl-noise and replay-critical failures differently. A failed request is only a priority bug when it harms replay output, route discovery, or first paint.
- Preserve host-aware saved-path expectations for recursive multi-host crawls.
- When you learn something durable from a live run, add or update a `research/` record instead of leaving it undocumented.
- Describe the failure class in generic terms before implementing a fix, for example path normalization, query-family explosion, login-gated false positive, or safe-interaction under-capture.

## Validation

- Run `npm test`
- Pay special attention to:
  - `tests/crawler-utils.test.js`
  - `tests/playwright-runtime.test.js`
- If behavior touches the UI job flow, also run `node bin/cli.js ui`
- Prefer automated verification over live-site crawls; if a manual crawl is needed, keep it narrow and non-destructive
- For live runs, record what site was tested, what failed, whether the failure was crawl-noise or replay-critical, and whether the fix generalized
- When crawl behavior changes queue selection or interaction discovery, verify both automated regressions and one narrow live replay outcome
