# Front Clone Coding

Playwright-based tooling for turning a live site into an offline replay package with captured assets, HTML snapshots, API specs, mocks, and an Express adapter.

## Features

- Browser-driven crawling for static and SPA-style pages
- Recursive same-domain crawling with depth and page limits
- Asset capture and URL rewriting for offline-friendly client output
- API capture for XHR, fetch, GraphQL, and WebSocket traffic
- OpenAPI-style documentation and mock response generation
- Visual analysis docs for layout, components, and missing behaviors
- Optional generated Express scaffold for local backend handoff

## Install

```bash
npm ci
npx playwright install chromium
```

## Docker

This project expects the Playwright Docker image version to match the installed Playwright package version.

```bash
docker compose up -d --build
```

If Playwright is upgraded, rebuild the container image before starting the UI again. The current required image is `mcr.microsoft.com/playwright:v1.58.2-noble`.
The Playwright base image already includes the matching browser runtime, so the Docker build only installs Node dependencies from `package-lock.json`.
The Compose setup also enables `init: true` and `ipc: host`, which are the recommended defaults for Playwright containers.

Quick commands:

```bash
npm run docker:rebuild
# or, for a full cleanup:
npm run docker:reset
```

## CLI usage

```bash
node bin/cli.js https://example.com

node bin/cli.js https://example.com \
  --wait 5000 \
  --viewport 1440x900 \
  --screenshot \
  --recursive \
  --max-pages 10
```

## Key options

| Option | Description | Default |
| --- | --- | --- |
| `-w, --wait <ms>` | Extra wait time after page load. | `3000` |
| `-r, --recursive` | Enable recursive crawl within the selected domain scope. | `false` |
| `--max-pages <n>` | Maximum number of pages to crawl. | `20` |
| `--max-depth <n>` | Maximum crawl depth. | `3` |
| `-c, --concurrency <n>` | Number of concurrent page workers. | `3` |
| `--crawl-profile <mode>` | `accurate`, `balanced`, `lightweight`, or `authenticated`. | `accurate` |
| `--network-posture <mode>` | `default`, `authenticated`, `sensitive-site`, or `manual-review`. | `default` |
| `--representative-qa` | Emit representative page QA summaries in crawl manifests. | `false` |
| `--domain-scope <mode>` | `registrable-domain` or `hostname`. | `registrable-domain` |
| `--update-existing` | Merge new generated output into an existing target directory. | `false` |
| `--no-scaffold` | Skip generated backend scaffold files. | scaffold enabled |

## Architecture Notes

Implementation research and migration notes live under `docs/`.

## Output structure

Generated packages are always written under `output/<main-domain>/`.
The folder name uses the registrable domain such as `netflix.com` or `example.co.uk`, even when crawl scope is set to `hostname`.

```text
output/example.com/
  public/                 Captured CSS, JS, images, fonts, media, misc assets
  views/                  Route-based HTML snapshots
  server/
    spec/                 OpenAPI, AsyncAPI, GraphQL reports, crawl manifest
                          resource-manifest, page-quality-report, crawl-profile
    mocks/                HTTP payloads, HTTP manifest, WebSocket frames
    adapters/express/     Replay adapter runtime
    docs/                 Visual, crawl, integration, and missing-behavior reports
  README.md               Generated replay package guide
  package.json            Generated runtime package
  server.js               Generated server entrypoint shim
```

## Web UI

```bash
node bin/cli.js ui
```

This starts a local dashboard at `http://localhost:4000` by default.

If you run the provided Docker Compose setup, the UI is exposed at `http://localhost:20000` because the container sets `PORT=20000`.

The dashboard provides:

- job-based clone execution
- live SSE logs
- status polling for the active run

If the browser runtime is missing, the job status API returns a structured error with a recovery hint, and the terminal panel keeps the raw launch details.

## Test

```bash
npm test
```

The test suite covers utility behavior, crawler heuristics, API capture shaping, and CLI/web smoke flows that do not require mutating tracked source files.

## Research Knowledge System

The repo includes a file-first `research/` workspace for implementation learnings, code-linked insights, and experiments.

```bash
npm run knowledge:init
npm run knowledge:report
```

Use `research/data/*.jsonl` as the canonical machine store and `research/notes/**/*.md` as the curated review layer. `research/schema/postgres.sql` is only a future migration path when the file-first workflow no longer scales.

## License

MIT
