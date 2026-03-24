---
name: asset-rewriter
description: >
  HTML, CSS, JS, and asset rewrite work. Use for Cheerio HTML transforms,
  PostCSS URL rewriting, Babel AST module rewrites, and downloaded-asset path fixes.
---

# Asset Rewriter Skill

Use this skill when changing how captured frontend files are normalized into the generated `public/` and `views/` output.

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
- JS rewriting uses `@babel/parser`, `@babel/traverse`, `@babel/generator`, and `es-module-lexer` to rewrite imports, `new URL(...)`, `fetch`, `axios`, `WebSocket`, and `EventSource` string literals when mapped locally.
- `src/utils/url-utils.js` is the shared source of truth for path generation, relative path computation, and in-scope vs external asset placement.
- `src/utils/image-utils.js` handles extra live image downloads and reinjection into processed HTML.

## Rules

- Keep HTML rewriting in `src/processor/html-processor.js`; do not add ad hoc string replacement elsewhere if the DOM layer can own it cleanly.
- Keep CSS URL rewriting on the PostCSS pipeline and preserve support for `@import`, `url(...)`, and image-set style asset references.
- Keep JS rewrite behavior AST-based; do not replace it with brittle regex-only rewrites for module/runtime references.
- Asset URLs that are captured locally should continue to resolve under generated `public/` paths.
- External assets that are actually referenced and intercepted should still be persisted locally when the existing pipeline supports it.
- Inline style URLs and inline `<style>` blocks must stay in scope for rewriting.
- If some external behavior cannot be replayed locally, capture that gap in generated docs rather than silently dropping the reference.

## Validation

- Run `npm test`
- Pay special attention to:
  - `tests/output-processors.test.js`
- For larger output-shape changes, generate a narrow smoke output and confirm local references resolve under `public/` and `views/`
