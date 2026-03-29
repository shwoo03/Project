# network-observability

## Current Behavior

- `requestfailed` events are captured and logged during crawl, and failed requests are retained for later recovery analysis.
- Recovery fetches now target only same-site critical assets such as images, CSS, fonts, and script chunks.
- Replay verification blocks non-local requests and records the blocked destinations for parity analysis.
- Replay verification now classifies blocked destinations as `render-critical-asset`, `render-critical-runtime`, `non-critical-runtime`, or `anti-abuse`.
- Static replay filtering removes many adtech, anti-abuse, and telemetry calls before verification, so blocked-request reports are now more focused on residual misses.
- Same-site logging endpoints are now classified as non-critical before generic same-site fallback logic is applied.

## Known Weaknesses

- Debug logs still mix high-noise `ERR_ABORTED` traffic with more meaningful missing-asset failures.
- Portal and media pages generate many adtech and thumbnail cancellations, which can obscure the smaller set of replay-critical failures.

## Experiment Backlog

- Classify failed requests into noise, recovery-eligible, and critical buckets before logging them at the same verbosity.
- Add summary output by host and resource type so live runs show which failures are dominant without reading raw logs.
- Connect failed-request summaries to replay verification warnings so users can see which blocked or aborted resources actually affected fidelity.

## Accepted Heuristics

- Treat most adtech, telemetry, and lazy thumbnail `ERR_ABORTED` requests as noise unless they are first-paint critical.
- Preserve failed-request metadata even when the raw log line is noisy, because recovery and later diagnosis depend on it.
- Use replay verification external-request blocking as a parity signal, not as proof that the original crawl failed.
- Use static HTML and JS filtering as the first defense for non-critical runtime, then let replay blocking highlight only what the static pass missed.
- Treat page-level verifier counters as deltas so multi-page reports remain interpretable.
