---
name: link-handler
description: >
  Hyperlink rewrite and disablement work. Use for internal route mapping,
  out-of-scope link disabling, and generated replay navigation behavior.
---

# Link Handler Skill

Use this skill when changing hyperlink behavior in generated HTML, forms, image maps, or runtime navigation references.

## Core Files

- `src/processor/html-processor.js`
- `src/utils/url-utils.js`
- `src/index.js`
- `src/crawler/site-crawler.js`
- `tests/output-processors.test.js`

## Current Implementation Anchors

- Today, `HtmlProcessor._replaceAttr()` rewrites `href`, `src`, and `action` only when a mapped local target exists in `urlMap`.
- Scope classification already exists through `isInDomainScope()` and `getDomainRoot()` in `src/utils/url-utils.js`.
- Recursive crawl output already produces a page manifest via `buildPageManifest()` in `src/index.js`, which can be used to distinguish cloned vs not-cloned pages.
- There is not yet a dedicated disabled-link styling/data-attribute layer in the current pipeline, so changes here should be treated as a new contract and covered by tests.

## Rules

- Use registrable-domain scope by default when classifying links, unless the run explicitly uses hostname scope.
- Subdomains inside the same registrable domain count as in-scope; unrelated domains do not.
- Preserve protocol-only exceptions such as `#anchor`, `mailto:`, `tel:`, `data:`, `blob:`, and `javascript:` according to their current safe handling.
- For generated replay navigation:
  - In-scope and cloned targets should resolve to the local replay route.
  - In-scope but not-cloned targets should be disabled intentionally, not left as broken live links.
  - Out-of-scope targets should be disabled intentionally, not left as live links.
- If you add disabled-link behavior, apply it consistently to `<a>`, `<area>`, and `form[action]` where appropriate.
- If you add visual disabled styling or `data-disabled-reason`, keep the generated HTML contract and tests aligned.
- Do not guess scope with hostname substring checks; always go through shared URL utilities.

## Validation

- Run `npm test`
- Add or update processor tests for:
  - cloned internal links
  - in-scope but not-cloned links
  - external-domain links
- If the change affects replay UX materially, generate a small output sample and click through the local routes manually
