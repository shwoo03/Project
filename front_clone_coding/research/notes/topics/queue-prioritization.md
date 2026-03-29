# queue-prioritization

## Current Behavior

- Frontier expansion now ranks structured link candidates instead of enqueueing links in first-seen order.
- Candidate scoring uses same-host preference, landmark context, anchor text quality, path cleanliness, and query penalties.
- Diversity caps prevent utility-heavy or query-only URL families from dominating a batch.

## Known Weaknesses

- Some same-domain auth or account utility routes can still score higher than desired on portal homepages.
- Ranked selection is strong for early depth representative crawls, but it still needs more fixtures for documentation-heavy and app-shell-heavy sites.

## Experiment Backlog

- Add penalties or stricter family handling for account-route and utility API entry points that appear as visible links.
- Expand fixture coverage across marketing, docs, SPA, and portal-style homepages to tune same-host and family diversity weights.
- Track selected-vs-skipped frontier families in output summaries so queue behavior is easier to audit after live crawls.

## Accepted Heuristics

- Deprioritize utility, legal, help, and query-heavy variants instead of hard-blocking them.
- Prefer same-host main-content routes early, then widen within the registrable domain only as budget allows.
- Keep query normalization non-destructive and solve duplicate pressure through scoring plus diversity caps.
