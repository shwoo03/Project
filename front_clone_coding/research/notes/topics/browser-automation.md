# browser-automation

## Current Behavior

- Playwright remains the primary capture engine for DOM, network, storage, and screenshots.
- Crawl profiles now separate `accurate`, `balanced`, `lightweight`, and `authenticated` operation.

## Known Weaknesses

- Representative QA is still manifest-oriented and does not yet run a full replay screenshot comparison loop.

## Experiment Backlog

- Validate profile-dependent wait budgets against SPA-heavy fixtures.
- Add deeper replay validation once a local replay QA runner exists.

## Accepted Heuristics

- Keep `serviceWorkers: 'block'` and storage-state reuse as baseline behavior.
