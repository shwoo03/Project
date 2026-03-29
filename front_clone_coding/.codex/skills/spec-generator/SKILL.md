---
name: spec-generator
description: >
  API specs, mock artifacts, generated docs, and replay scaffold work.
  Use for OpenAPI, AsyncAPI, GraphQL summaries, manifest output, and Express replay runtime changes.
---

# Spec Generator Skill

Use this skill when changing generated server artifacts or the backend handoff package emitted under `output/<domain>/`.

## Mission Focus

The generated runtime is currently part of the fidelity validation loop, not just a docs artifact. Use this skill to improve replay serving, mock usefulness, manifest diagnostics, and generated explanations for real-site clone gaps.

Do:

- make replay server behavior line up with generated `views/` and `public/`
- improve manifest usefulness for debugging real-site parity issues
- separate render-critical mock behavior from telemetry or adtech noise where possible
- encode live-site findings as generic output/runtime contracts, not target-site-only manifest quirks

Do not:

- expand generated artifacts that do not help replay verification, debugging, or backend handoff
- change output contracts casually during site-validation work
- ship generated runtime behavior that depends on one domain or one captured site's route names when a normalized contract can express the same behavior

## Core Files

- `src/processor/api-processor.js`
- `src/processor/integration-doc-generator.js`
- `src/analyzer/visual-analyzer.js`
- `src/scaffolder/project-scaffolder.js`
- `src/utils/manifest-writer.js`
- `src/index.js`
- `src/verifier/replay-verifier.js`

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
- Replay verification emits `server/spec/replay-verification.json` and `server/docs/replay-verification.md`, including external request category summaries and page-level replay signals.
- Generated runtimes can expose inert local fallback routes such as `/__front_clone_noop__` for stripped non-critical runtime calls.

## Rules

- Treat `server/spec/` and `server/mocks/` as source-of-truth generated artifacts. `server/adapters/express/` is derived runtime code.
- Keep OpenAPI output compliant with `3.1.0` unless the entire contract is intentionally upgraded.
- Preserve GraphQL grouping by endpoint behavior and operation metadata.
- Preserve the replay adapter contract: `npm start` in the generated package should boot the local Express runtime.
- Keep replay routes aligned with generated `views/` paths and static asset serving aligned with `public/`.
- Keep generated replay-verification artifacts aligned with the current replay runtime contract, especially route resolution, external-request categorization, and page-level mock metrics.
- If some runtime behavior is missing or lossy, record it in `server/docs/missing-behaviors.md` instead of hiding the gap.
- Changes to generated output shape must stay aligned with `README.md` and any relevant tests/docs.
- Prefer manifests and docs that explain why replay differs from the live site, not only what files were generated.
- Treat telemetry, adtech, and anti-abuse runtime as noise unless it is replay-critical; make that distinction visible in generated diagnostics.
- If a replay issue comes from one site's package, first look for the shared output contract that should have prevented it, then fix that contract and add regression coverage there.

## Validation

- Run `npm test`
- For scaffold/output changes, inspect a generated sample under `output-smoke/` or a fresh output directory
- If replay runtime behavior changes, boot the generated server or smoke test the local UI flow that produces it
- If the change came from a live-site issue, inspect the regenerated `crawl-manifest`, `resource-manifest`, and `replay-verification` artifacts after the rerun
- For replay-verification changes, confirm page-level metrics remain interpretable on multi-page samples and not just single-page runs
