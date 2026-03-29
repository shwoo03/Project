# service-worker-and-offline-replay

## Current Relevance

- `PageCrawler` still runs Playwright with `serviceWorkers: 'block'`, and that remains the right default while capture and replay depend on direct request visibility.
- MDN service worker and fetch-event documentation confirms that a registered worker can intercept document and subresource requests before the normal network path is visible to debugging tools.
- The current replay runtime already has explicit Express adapter routing, static file serving, and mock manifests. Adding a browser-managed worker too early would create two overlapping request-resolution layers.

## Code Implications

- [page-crawler.js](C:/Users/dntmd/OneDrive/Desktop/개인/Project/front_clone_coding/src/crawler/page-crawler.js) should keep blocking service workers during capture so HAR data, failed-request classification, and request accounting stay deterministic.
- [project-scaffolder.js](C:/Users/dntmd/OneDrive/Desktop/개인/Project/front_clone_coding/src/scaffolder/project-scaffolder.js) should not emit a replay service worker by default until the runtime can explain whether a request was served by static files, Express mocks, or a cache layer.
- [replay-verifier.js](C:/Users/dntmd/OneDrive/Desktop/개인/Project/front_clone_coding/src/verifier/replay-verifier.js) should continue judging replay from adapter-visible requests rather than browser cache hits that hide route-level evidence.

## Accepted Heuristics

- Prefer explicit replay adapter routing over service-worker interception while request attribution and debugging are still higher priorities than progressive offline polish.
- Treat service workers as an optional later optimization for generated replay, not as a baseline contract for fidelity validation.
- If service workers are explored later, require diagnostics that can distinguish `served-from-worker`, `served-from-mock`, and `served-from-static-file`.

## Open Questions

- Can a generated replay service worker help with static asset caching without obscuring mock-route visibility for API requests?
- Would a worker be useful only for asset caching while leaving `/api` requests entirely adapter-visible?
- How should replay verification surface worker-served responses so fidelity regressions remain explainable?

## Sources

- MDN Using Service Workers: https://developer.mozilla.org/docs/Web/API/Service_Worker_API/Using_Service_Workers
- MDN ServiceWorkerGlobalScope `fetch` event: https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerGlobalScope/fetch_event
- MDN Cache interface: https://developer.mozilla.org/en-US/docs/Web/API/Cache
