---
name: test-suite
description: >
  Test creation, test maintenance, and verification follow-up for the Node.js
  built-in test runner used in this repository.
---

# Test Suite Skill

Use this skill when adding coverage, tightening assertions, or validating behavior after code changes.

## Core Files

- `tests/crawler-utils.test.js`
- `tests/error-utils.test.js`
- `tests/output-processors.test.js`
- `tests/playwright-runtime.test.js`
- `tests/web-ui.test.js`

## Current Test Strategy

- The repo uses the Node.js built-in test runner via `node --test "tests/**/*.test.js"`.
- Existing coverage focuses on utility behavior, crawl/runtime behavior, processor rewrites, and Web UI job contracts.
- Tests are offline-friendly and avoid depending on live remote websites.
- Web UI tests boot the local Express server and exercise API behavior through `fetch`.

## Rules

- Keep tests deterministic and runnable offline.
- Prefer implementation fixes over weakening correct tests.
- Add tests alongside behavior changes, especially when changing public contracts or generated output shape.
- Cover both success paths and structured failure paths for UI-facing/server-facing behavior.
- For processor changes, assert on generated output content rather than only internal bookkeeping.
- For runtime contract changes, verify user-visible guidance text as well as error codes.

## Validation

- Run `npm test`
- If Web UI behavior changed, also run `node bin/cli.js ui`
- If generated scaffold or Docker/runtime text changed, add or update targeted regression tests
