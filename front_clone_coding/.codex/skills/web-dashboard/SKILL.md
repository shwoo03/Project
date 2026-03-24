---
name: web-dashboard
description: >
  Express dashboard, API endpoints, SSE log streaming, job status handling,
  output browsing, and browser-facing error recovery work.
---

# Web Dashboard Skill

Use this skill when changing the dashboard server in `web/`, the browser UI, or the clone job lifecycle exposed to users.

## Core Files

- `web/server.js`
- `web/public/index.html`
- `web/public/script.js`
- `web/public/style.css`
- `bin/cli.js`
- `src/utils/error-utils.js`
- `src/utils/logger.js`
- `src/utils/constants.js`

## Current API Contract

- `POST /api/clone` - start a clone job
- `GET /api/jobs/:jobId` - fetch job status
- `GET /api/jobs/active/current` - inspect the currently active job
- `POST /api/jobs/:jobId/cancel` - cancel a queued/running job
- `GET /api/logs?jobId=<id>` - SSE log stream
- `GET /api/output?path=<relative>` - browse or download generated output

## Current Implementation Anchors

- The UI server defaults to `PORT=4000` locally and uses `PORT=20000` in Docker via environment.
- Jobs are single-active-job only; `activeJobId` gates concurrent execution.
- Logger events are fanned out into per-job SSE logs and pruned with retention limits from `src/utils/constants.js`.
- Structured Playwright runtime errors are surfaced through job status and SSE hint logs.
- The static dashboard already supports job submission, active-job restore, polling, SSE connection, and output browsing.

## Rules

- Keep the API endpoints and request/response shape consistent with `tests/web-ui.test.js`.
- Preserve SSE heartbeat behavior and clean up listeners/clients when jobs finish or the server closes.
- Keep structured runtime recovery hints user-visible for browser/runtime mismatch failures.
- Validate incoming target URLs with `validateUrlSafety()` before starting a job.
- Preserve the single-active-job contract unless tests and UI flow are intentionally redesigned together.
- If you change polling, cancellation, or output browsing, update both server and browser-side code in the same task.
- Do not drift Docker port behavior from the documented `20000` container default without syncing docs and compose config.

## Validation

- Run `npm test`
- Pay special attention to:
  - `tests/web-ui.test.js`
  - `tests/playwright-runtime.test.js`
- Smoke test with `node bin/cli.js ui`
