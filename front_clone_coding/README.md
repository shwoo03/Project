# Front Clone Coding

Playwright-based tooling for mirroring a public website into a frontend handoff package with captured assets, API docs, mock data, and an optional Express scaffold.

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
npm install
npx playwright install chromium
```

## CLI usage

```bash
node bin/cli.js https://example.com

node bin/cli.js https://example.com \
  --output ./my-clone \
  --wait 5000 \
  --viewport 1440x900 \
  --screenshot \
  --recursive \
  --max-pages 10
```

## Key options

| Option | Description | Default |
| --- | --- | --- |
| `-o, --output <dir>` | Output parent directory. Final output is written to `<dir>/<domain>`. | `./output` |
| `-w, --wait <ms>` | Extra wait time after page load. | `3000` |
| `-r, --recursive` | Enable recursive crawl within the selected domain scope. | `false` |
| `--max-pages <n>` | Maximum number of pages to crawl. | `20` |
| `--max-depth <n>` | Maximum crawl depth. | `3` |
| `-c, --concurrency <n>` | Number of concurrent page workers. | `3` |
| `--domain-scope <mode>` | `registrable-domain` or `hostname`. | `registrable-domain` |
| `--update-existing` | Merge new generated output into an existing target directory. | `false` |
| `--no-scaffold` | Skip generated backend scaffold files. | scaffold enabled |

## Output structure

```text
output/example.com/
  client/                 Mirrored HTML pages and captured assets
  docs/
    api/                  OpenAPI, request log, GraphQL, WebSocket docs
    crawl/                Crawl manifest and site map summary
    integration/          Forms, auth hints, frontend/backend mapping
    ui/                   Screenshots, design tokens, layout analysis
  manifest/               Normalized crawl manifest
  mocks/api/              Captured mock responses
  server/                 Generated Express routes/controllers/services
  README.md               Generated handoff guide
  package.json            Generated runtime package for the scaffold
  server.js               Generated local server entrypoint
```

## Web UI

```bash
node bin/cli.js ui
```

This starts a local dashboard at `http://localhost:4000` with:

- job-based clone execution
- live SSE logs
- status polling for the active run

## Test

```bash
npm test
```

The test suite covers utility behavior, crawler heuristics, API capture shaping, and CLI/web smoke flows that do not require mutating tracked source files.

## License

MIT
