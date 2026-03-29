---
name: asset-rewriter
description: >
  HTML, CSS, JS, and asset rewrite work. Use for Cheerio HTML transforms,
  PostCSS URL rewriting, Babel AST module rewrites, and downloaded-asset path fixes.
---

# Asset Rewriter Skill

Use this skill when changing how captured frontend files are normalized into the generated `public/` and `views/` output.

## Mission Focus

This skill exists to improve local replay fidelity for real crawled sites. Changes should make local HTML, CSS, JS, images, fonts, and route references behave more like the live site while staying scope-safe and deterministic.

Do:

- prioritize fixes that improve first paint, local navigation, and asset completeness
- prefer generic runtime URL, asset-path, and malformed-asset handling improvements
- preserve evidence of unsupported behavior in generated docs
- keep cloned routes local and uncloned or out-of-scope routes intentionally disabled
- express replay fixes in terms of shared rewrite or classification rules, not one site's exact HTML or CDN strings

Do not:

- add cosmetic rewrites that do not change replay quality
- hide missing behavior silently when it should be documented
- hardcode one site's exact asset paths unless the pattern is provably generic
- leave live-site navigation fallbacks in generated replay HTML when a local or disabled target is expected
- add host-name or product-name based rewrite branches if the same behavior can be detected from path shape, payload semantics, DOM context, or scope metadata

## Core Files

- `src/processor/html-processor.js`
- `src/processor/css-processor.js`
- `src/processor/js-processor.js`
- `src/downloader/asset-downloader.js`
- `src/utils/url-utils.js`
- `src/utils/image-utils.js`
- `src/index.js`

## Current Implementation Anchors

- HTML rewriting is Cheerio-based and currently rewrites `src`, `href`, `action`, `srcset`, inline `style`, `<style>` blocks, and several lazy-load data attributes.
- CSS rewriting uses PostCSS plus `postcss-url`, including `@import` chain handling and opportunistic saving of additional intercepted assets.
- JS rewriting uses `@babel/parser`, `@babel/traverse`, `@babel/generator`, and `es-module-lexer` to rewrite imports, `new URL(...)`, and runtime endpoints, including non-critical external runtime no-op rewrites.
- `src/utils/url-utils.js` is the shared source of truth for path generation, relative path computation, and in-scope vs external asset placement.
- `src/utils/image-utils.js` handles extra live image downloads and reinjection into processed HTML.
- Link disablement, `data-disabled-reason`, and local replay navigation contracts now live in the same HTML rewrite layer as asset and route rewriting.

## Rules

- Keep HTML rewriting in `src/processor/html-processor.js`; do not add ad hoc string replacement elsewhere if the DOM layer can own it cleanly.
- Keep CSS URL rewriting on the PostCSS pipeline and preserve support for `@import`, `url(...)`, and image-set style asset references.
- Keep JS rewrite behavior AST-based; do not replace it with brittle regex-only rewrites for module/runtime references.
- Asset URLs that are captured locally should continue to resolve under generated `public/` paths.
- External assets that are actually referenced and intercepted should still be persisted locally when the existing pipeline supports it.
- Inline style URLs and inline `<style>` blocks must stay in scope for rewriting.
- Keep hyperlink and form-action rewriting aligned with local replay routing:
  - cloned targets resolve locally
  - uncloned in-scope targets are intentionally disabled
  - out-of-scope targets are intentionally disabled
- Preserve the generated disabled-link contract for `<a>`, `<area>`, and `form[action]`, including `data-disabled-reason` and local no-fallback behavior.
- If some external behavior cannot be replayed locally, capture that gap in generated docs rather than silently dropping the reference.
- Fail soft when third-party assets are malformed if a bounded fallback can preserve useful replay behavior.
- Keep host-aware and scope-aware path handling aligned with the replay server contract.
- Keep static external-runtime filtering generic:
  - classify same-site logging before same-site fallback promotion
  - rewrite non-critical runtime to `/__front_clone_noop__` or inert image targets
  - prefer owned-CDN localization for first-paint assets
- When a live site exposes a broken rewrite, promote the underlying pattern into a shared rule and add a deterministic regression instead of shipping a one-off exception.

## Validation

- Run `npm test`
- Pay special attention to:
  - `tests/output-processors.test.js`
- Pay extra attention to regressions around:
  - disabled local navigation
  - same-site logging misclassification
  - canonical replay path dedupe
  - static external runtime filtering
- For larger output-shape changes, generate a narrow smoke output and confirm local references resolve under `public/` and `views/`
- If a live-site regression motivated the change, re-run a narrow clone and confirm the same class of asset or rewrite failure is gone
