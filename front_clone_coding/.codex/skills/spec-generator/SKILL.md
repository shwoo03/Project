---
name: spec-generator
description: >
  API specs, mock artifacts, generated docs, and replay scaffold work.
  Use for OpenAPI, AsyncAPI, GraphQL summaries, manifest output, and Express replay runtime changes.
---

# Spec Generator Skill

Use this skill when changing generated server artifacts or the backend handoff package emitted under `output/<domain>/`.

## Core Files

- `src/processor/api-processor.js`
- `src/processor/integration-doc-generator.js`
- `src/analyzer/visual-analyzer.js`
- `src/scaffolder/project-scaffolder.js`
- `src/utils/manifest-writer.js`
- `src/index.js`

## Output Contract

- `server/spec/openapi.json`
- `server/spec/asyncapi.json`
- `server/spec/graphql/operations.json`
- `server/spec/request-log.json`
- `server/spec/manifest/crawl-manifest.json`
- `server/mocks/http-manifest.json`
- `server/mocks/http/*.json`
- `server/mocks/ws/frames.json`
- `server/adapters/express/app.js`
- `server/docs/**`
- root `README.md`
- root `package.json`
- root `server.js`

## Current Implementation Anchors

- HTTP request capture is filtered to same-scope, non-static endpoints before spec generation.
- OpenAPI output is currently `3.1.0`; AsyncAPI output is currently `3.0.0`.
- GraphQL reporting groups by `operationName` plus variable hash and writes to `server/spec/graphql/operations.json`.
- HTTP mocks are keyed by method/path/search/body or GraphQL variant information and materialized under `server/mocks/http/`.
- The generated Express replay runtime serves `public/`, resolves `views/*.html`, and replays `/api/*` responses from `server/mocks/http-manifest.json`.
- Missing behavior notes are emitted under `server/docs/missing-behaviors.md`.

## Rules

- Treat `server/spec/` and `server/mocks/` as source-of-truth generated artifacts. `server/adapters/express/` is derived runtime code.
- Keep OpenAPI output compliant with `3.1.0` unless the entire contract is intentionally upgraded.
- Preserve GraphQL grouping by endpoint behavior and operation metadata.
- Preserve the replay adapter contract: `npm start` in the generated package should boot the local Express runtime.
- Keep replay routes aligned with generated `views/` paths and static asset serving aligned with `public/`.
- If some runtime behavior is missing or lossy, record it in `server/docs/missing-behaviors.md` instead of hiding the gap.
- Changes to generated output shape must stay aligned with `README.md` and any relevant tests/docs.

## Validation

- Run `npm test`
- For scaffold/output changes, inspect a generated sample under `output-smoke/` or a fresh output directory
- If replay runtime behavior changes, boot the generated server or smoke test the local UI flow that produces it
