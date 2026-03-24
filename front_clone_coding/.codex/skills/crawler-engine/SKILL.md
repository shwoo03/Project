---
name: crawler-engine
description: >
  Playwright crawling engine work for recursive traversal, network interception,
  domain-scope calculation, login-gated handling, and browser context behavior.
---

# Crawler Engine Skill

Use this skill when changing crawl behavior, scope rules, Playwright context setup, request capture, or page discovery heuristics.

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
- The crawler captures HTML, computed styles, image URLs, internal links, forms, interactive elements, storage state, and session storage state.
- `SiteCrawler` defaults to `registrable-domain` scope and uses `getDomainRoot()` / `isInDomainScope()` from `src/utils/url-utils.js`.
- Recursive crawling filters tracker hosts, destructive URLs, static binary extensions, and login-gated follow-up pages unless `followLoginGated` is enabled.
- `ensurePlaywrightRuntimeReady()` returns structured mismatch guidance tied to the pinned Docker image.

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

## Validation

- Run `npm test`
- Pay special attention to:
  - `tests/crawler-utils.test.js`
  - `tests/playwright-runtime.test.js`
- If behavior touches the UI job flow, also run `node bin/cli.js ui`
- Prefer automated verification over live-site crawls; if a manual crawl is needed, keep it narrow and non-destructive
