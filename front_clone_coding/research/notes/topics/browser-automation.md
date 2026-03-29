# browser-automation

## Current Behavior

- Playwright remains the primary capture engine for DOM, network, storage, and screenshots.
- Crawl profiles now separate `accurate`, `balanced`, `lightweight`, and `authenticated` operation.
- Failed browser requests are now retained for recovery analysis, and some same-site critical assets can be retried after the browser lane aborts them.

## Known Weaknesses

- Representative QA is still manifest-oriented and does not yet run a full replay screenshot comparison loop.
- Browser-level `requestfailed` events are noisy on adtech-heavy and lazy-image-heavy pages, especially on portal sites.

## Experiment Backlog

- Validate profile-dependent wait budgets against SPA-heavy fixtures.
- Add deeper replay validation once a local replay QA runner exists.
- Classify `requestfailed` noise versus replay-critical failures before surfacing them directly to users.

## Accepted Heuristics

- Keep `serviceWorkers: 'block'` and storage-state reuse as baseline behavior.
- Treat many `ERR_ABORTED` events as browser cancellation signals, not immediate proof of crawl failure.
