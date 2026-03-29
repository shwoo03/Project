# crawl-accuracy

## Current Behavior

- Page classification now marks high-value pages, route-heavy pages, form-heavy pages, and representative QA candidates.
- Site traversal can limit enqueue budgets based on page classification and crawl profile.
- Frontier ranking now prefers representative same-host or same-domain content links over help, utility, legal, and query-heavy variants.
- Recursive multi-host crawls now preserve host-aware saved paths, which improves downstream replay accuracy instead of just crawl coverage.
- Canonical dedupe now collapses trailing-slash variants into a single replay HTML target before manifests and replay verification are emitted.
- Replay accuracy work now favors static removal of non-critical external runtime over broader crawl expansion when the goal is local replay fidelity.
- Auto-scroll and screenshot preparation now use body-null-safe scroll-root measurement so lazy-load helpers do not abort the crawl on shell-like or partially constructed documents.
- Replay candidate classification now uses page-level bootstrap signals so same-site GraphQL refresh queries with inline fallback data can be treated as supporting rather than strict first-paint requirements.

## Known Weaknesses

- Replay fidelity is approximated through manifest quality signals, not a full browser replay diff.
- Some auth and account utility links still appear in high-scoring frontier candidates on portal homepages.
- Some sites may still use nested custom scroll containers, which the current generic scroll-root fallback does not yet fully optimize for.

## Experiment Backlog

- Compare text drift and resource-count signals against actual replay breakage.
- Expand fixture coverage for CDN-heavy and route-heavy sites.
- Validate frontier weights on portal, marketing, docs, and SPA fixtures with live replay outcomes, not only queue ordering.

## Accepted Heuristics

- Favor smaller accurate crawls over broader but incomplete replays.
- Prefer representative route selection and replayable saved paths before increasing page count.
- Prefer stripping clearly non-critical external runtime from generated replay output before widening crawl scope to chase parity indirectly.
- Prefer page-level bootstrap evidence over request-name heuristics when deciding whether a captured API call is truly replay-critical.
