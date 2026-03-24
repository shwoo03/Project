---
name: docker-infra
description: >
  Dockerfile, Docker Compose, runtime image synchronization, and container-first
  execution flow for the Web UI and Playwright runtime.
---

# Docker Infrastructure Skill

Use this skill when changing containerization, runtime install expectations, or scripts that rebuild/reset the container workflow.

## Core Files

- `Dockerfile`
- `docker-compose.yml`
- `package.json`
- `README.md`
- `src/utils/constants.js`
- `src/utils/playwright-runtime.js`
- `tests/playwright-runtime.test.js`

## Current Implementation Anchors

- The pinned Playwright package version is `1.58.2`.
- The matching Docker image is `mcr.microsoft.com/playwright:v1.58.2-noble`.
- The container starts the Web UI with `node bin/cli.js ui`.
- Compose keeps `init: true`, `ipc: host`, and maps `20000:20000`.
- Docker build installs Node dependencies with `npm ci --omit=dev`; browsers come from the Playwright base image.
- The project provides `npm run docker:rebuild` and `npm run docker:reset`.

## Rules

- Keep the Playwright npm version and Docker base image tag in sync.
- If the pinned version changes, update every user-facing/runtime-facing mention together:
  - `package.json`
  - `Dockerfile`
  - `README.md`
  - `src/utils/constants.js`
  - `src/utils/playwright-runtime.js`
  - related tests
- Preserve `init: true` and `ipc: host` unless there is a deliberate, tested platform decision.
- Keep `PORT`-driven UI startup intact so Docker can continue exposing `20000`.
- Do not add redundant browser installation steps to the Docker build when the base image already provides the runtime.
- `docker compose up -d --build` should remain the one-command bootstrap path.

## Validation

- Run `npm test`
- Rebuild with `docker compose up -d --build`
- If runtime mismatch guidance changes, verify the text still matches the pinned image and recovery steps
