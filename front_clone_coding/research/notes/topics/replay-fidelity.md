# replay-fidelity

## Current Behavior

- Recursive crawls now save multi-host pages under host-aware HTML paths such as `views/www.naver.com/index.html` and `views/news.naver.com/index.html`.
- Replay verification now resolves nested saved paths, serves host-aware HTML reliably, and uses structural replay signals such as route reachability, title parity, and marker overlap.
- Failed critical assets can be retried through a `recovery` capture lane instead of being treated as terminal loss.
- Charset metadata and decoded text are preserved in network capture so title and body comparisons are less likely to drift from encoding mistakes.
- Same-site logging endpoints are now classified as non-critical before generic same-site runtime fallback logic is applied.
- Same-site POST requests with explicit consolidated logging-envelope payloads are also classified as non-critical, even when the pathname itself does not resemble a logging endpoint.
- JS runtime filtering now handles simple concatenated and static template-string logging URLs in addition to plain string literals.
- Replay candidates are now split into strict `render-critical` and informational `render-supporting` groups so cache-backed state refresh requests do not inflate replay-failure warnings.
- Inline bootstrap presence such as embedded user or membership models can downgrade same-site state-refresh GraphQL calls out of the strict replay-expected set.
- SPA or CLCS-style serialized navigation models should use the same local-first rewrite policy as rendered anchors, because hydration can otherwise restore live same-site destinations after HTML rewrite.
- Same-scope URLs with volatile query state can safely collapse to a captured local page when a unique host-plus-pathname mapping exists; if not, they should degrade to disabled navigation rather than escaping to the live site.
- Charset-aware replay diagnostics should preserve the full `Content-Type` header, BOM, and in-document declarations together; passing only a bare mime type into decode heuristics hides transport charset evidence and makes portal-style text drift harder to interpret.
- Server-rendered legacy portal pages should not automatically treat every same-site JSON widget endpoint as first-paint critical; when the HTML already supplies the title, navigation, landmarks, and dense visible shell, ticket or queue-style widget refreshes belong in a supporting bucket unless stronger dependency evidence exists.
- Replay verification should separate runtime exceptions and same-origin failed script/resource loads from route misses and blocked external noise; otherwise portal pages can look like generic drift when the real blocker is a local script assumption or a missing same-origin runtime file.
- Replay-only runtime guards are a better first response to portal-style same-origin JavaScript failures than function-level patches, because wrapped callbacks and global error collection can preserve the rendered shell while classifying failures into reusable buckets such as `runtime-dom-assumption`, `runtime-script-failed`, and `runtime-resource-missing`.
- Fidelity comparison on boilerplate-heavy public pages should use separate heading, main-content, and body-text profiles; whole-body length drift and flat token overlap alone can understate good replays or overstate failures when repeated navigation, footer, and legal text dominate the page.

## Known Weaknesses

- Render-critical runtime APIs are still under-mocked on portal-style sites, so `mockApiHits` can remain zero even when the page shell renders correctly.
- Some same-site bootstrap endpoints such as help or consent support calls can still be marked strict even when the landing page renders without them, so candidate downgrading work is not finished.
- Replay verification still reports many blocked external requests for adtech, telemetry, remote frames, and widget runtimes that are intentionally not replayed.
- Marker overlap improved, but content drift on high-churn pages like `www.naver.com` remains materially above zero because personalization and remote widgets are excluded.
- Some same-site POST endpoints with opaque JSON bodies may still need payload-shape inspection before they can be safely downgraded out of the strict replay set on other sites.
- Some legacy portal JSON endpoints that populate boards or feeds can still blur the line between primary content and secondary widgets, so strict/supporting calibration on list-style APIs is not finished yet.
- Some portal pages still reach the correct local route while throwing same-origin runtime exceptions, so route and asset success alone is not enough to call a replay stable.
- Some public pages still need better low-confidence handling for title or text comparisons when the replay preserves the visible shell but the source page is dominated by repeated boilerplate or legacy encoding noise.

## Experiment Backlog

- Split render-critical bootstrap and feed endpoints more aggressively from telemetry and ad traffic in replay runtime handling.
- Refine strict vs supporting bootstrap classification so auxiliary support endpoints are not treated like first-paint blockers on marketing pages.
- Add richer portal fixtures to compare marker overlap, blocked requests, and visible widget fill rate after mock improvements.
- Promote recovery-lane results into a separate quality summary so missing critical assets and recovered critical assets are easy to compare.

## Accepted Heuristics

- Prioritize replay fidelity over crawl breadth when a site spans many subdomains and dynamic widgets.
- Keep adtech, telemetry, and personalization dependencies blocked or no-op unless they are required for first paint.
- Treat host-aware view storage as the default contract for recursive registrable-domain crawls.
- Treat same-site state-refresh queries with inline fallback data as supporting replay candidates unless visible first-paint sections prove otherwise.
- Treat same-site POST transports with explicit logging-envelope semantics as non-critical, even if pathname heuristics alone would be ambiguous.
- Treat same-site ticket, queue, calendar, reservation, and similar structured widget APIs as supporting when a server-rendered shell is already present and the endpoint behaves like a secondary module refresh rather than a route bootstrap.
- Treat charset confidence and encoding mismatch signals as replay diagnostics, not rendering failures by themselves; low-confidence text comparison should point toward decode investigation before strict runtime patching.
- Treat page-level console errors, uncaught exceptions, and failed same-origin runtime requests as first-class replay evidence so remaining fidelity gaps can be triaged without guessing from drift scores alone.
- Treat replay-only runtime guards as a stability layer, not as application logic overrides: they should absorb same-origin DOM assumption failures and preserve diagnostics, but they should not special-case individual site functions or invent missing content.
- Treat `comparison-noise-likely` as a separate outcome from real content drift when heading and main-content overlap remain strong; boilerplate-heavy body text should lower comparison confidence before it creates a high-severity fidelity warning.
