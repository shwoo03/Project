# static-asset-placement

## Current Behavior

- Browser-observed assets remain the source of truth.
- Direct downloads are limited to discovered safe static assets such as extra images.
- Resource manifests now track capture lane, class, and replay criticality.

## Known Weaknesses

- Direct lane coverage is still narrow and intentionally avoids speculative fetching.

## Experiment Backlog

- Extend direct-lane support to more passive-static resources without widening crawl scope.
- Validate path stability and dedupe behavior under CDN-heavy asset graphs.

## Accepted Heuristics

- Keep final placement deterministic and scope-safe before HTML rewriting begins.
