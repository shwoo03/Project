# replay-fidelity-hardening

- Kind: decision
- Updated: 2026-03-27T00:00:00.000Z
- Summary: Replay fidelity work should focus on host-aware storage, encoding preservation, fail-soft asset handling, and verifier accuracy before expanding crawl breadth.

## Context

- Portal-style sites such as Naver exposed a structural weakness where recursive pages from multiple hosts collapsed into the same `views/index.html`.
- Replay verification was overstating failure because route resolution and HTML serving were not robust enough for nested saved paths.
- Malformed third-party CSS and aborted critical assets could stop or degrade a clone even when the main document was still recoverable.

## Decision

- Make host-aware HTML paths the default for recursive registrable-domain crawls.
- Preserve charset and decoded text during capture so replay analysis compares meaningful text rather than damaged UTF-8 fallbacks.
- Allow malformed CSS to fail soft and continue URL or import rewriting through a regex fallback instead of aborting the clone.
- Separate render-critical replay dependencies from telemetry, adtech, and personalization dependencies.

## Consequences

- Output structure becomes more stable for multi-host crawls and easier to inspect manually.
- Replay verification becomes more trustworthy, but blocked external requests will remain visible until more runtime dependencies are mocked or neutralized.
- The crawler can finish more live runs that previously died on malformed assets, at the cost of accepting a looser CSS rewrite fallback in edge cases.
