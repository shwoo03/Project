# static-asset-placement

## Current Behavior

- Browser-observed assets remain the source of truth.
- Direct downloads are limited to discovered safe static assets such as extra images.
- Resource manifests now track capture lane, class, and replay criticality.
- Recovery-lane downloads can now rescue failed same-site critical assets that the browser lane aborted.
- Non-critical external runtime URLs are now handled separately from static asset placement: replay HTML and JS can remove them entirely or rewrite them to `/__front_clone_noop__`.
- First-paint asset debugging is clearer because telemetry, adtech, and anti-abuse runtime noise is no longer mixed into the same placement path by default.
- CSS processing now has a late-binding final pass so fonts or images saved after an early CSS rewrite can still be rebound to local paths before replay output is finalized.
- CSS-discovered assets are now registered into the shared resource manifest instead of existing only on disk.
- Legacy portal CSS recovery now preserves already-local relative references during finalization, canonicalizes malformed same-origin asset URLs, and emits a dedicated `css-recovery-summary.json` so unresolved first-paint assets can be inspected by reason instead of silently leaking live URLs.

## Known Weaknesses

- Direct lane coverage is still narrow and intentionally avoids speculative fetching.
- Some owned CDN fonts still depend on bounded retry timing; very slow responses can still miss the direct CSS fetch window.
- Page-level CSS recovery is only as accurate as the page ownership signal on the source CSS or fetched asset response. Shared stylesheets can still blur which page truly needed a missing background image first.

## Experiment Backlog

- Extend direct-lane support to more passive-static resources without widening crawl scope.
- Validate path stability and dedupe behavior under CDN-heavy asset graphs.
- Measure when recovery-lane success materially improves replay marker overlap or visible widget completion.
- Separate true runtime/data gaps from CSS asset gaps on legacy portals where marker overlap stays low even after most first-paint assets are recovered.

## Accepted Heuristics

- Keep final placement deterministic and scope-safe before HTML rewriting begins.
- Recover only clearly scoped, replay-relevant assets and keep adtech or tracker resources out of the recovery lane.
