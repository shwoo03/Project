---
name: test-suite
description: >
  Test creation, test maintenance, and verification follow-up for the Node.js
  built-in test runner used in this repository.
---

# Test Suite Skill

Use this skill when adding coverage, tightening assertions, or validating behavior after code changes.

## Mission Focus

Tests in this phase should protect the live-site validation loop. Favor regressions that lock down replay fidelity, crawl safety, output contracts, and the specific failure class that motivated a fix.

The test strategy should reinforce the repository's generic-first rule:

- convert site-discovered failures into reusable fixtures
- name tests after the failure pattern, not the site brand, unless the brand is part of a documented research case

## Core Files

- `tests/crawler-utils.test.js`
- `tests/crawl-quality.test.js`
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
- Add a regression whenever a real-site crawl exposed a reusable bug, even if the original site cannot be used directly in tests.
- Prefer narrow deterministic fixtures that simulate the real failure over broad snapshot tests.
- If a fix only passes with a site-specific fixture and cannot be described as a broader failure class, the implementation likely needs another design pass.
- Prioritize regressions around:
  - same-site logging vs replay-critical classification
  - canonical dedupe and host-aware saved paths
  - static external runtime filtering
  - replay verifier per-page metrics
  - route-localization and disabled-link contracts

## Validation

- Run `npm test`
- If Web UI behavior changed, also run `node bin/cli.js ui`
- If generated scaffold or Docker/runtime text changed, add or update targeted regression tests
- When possible, mention which live-site issue the new test is intended to guard against
- If a live-site rerun still disagrees with the deterministic tests, tighten the fixture before adding more one-off manual checks
