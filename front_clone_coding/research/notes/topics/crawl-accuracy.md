# crawl-accuracy

## Current Behavior

- Page classification now marks high-value pages, route-heavy pages, form-heavy pages, and representative QA candidates.
- Site traversal can limit enqueue budgets based on page classification and crawl profile.

## Known Weaknesses

- Replay fidelity is approximated through manifest quality signals, not a full browser replay diff.

## Experiment Backlog

- Compare text drift and resource-count signals against actual replay breakage.
- Expand fixture coverage for CDN-heavy and route-heavy sites.

## Accepted Heuristics

- Favor smaller accurate crawls over broader but incomplete replays.
