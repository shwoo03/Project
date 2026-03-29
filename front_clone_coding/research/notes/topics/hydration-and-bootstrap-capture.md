# hydration-and-bootstrap-capture

## Current Relevance

- Replay quality increasingly depends on distinguishing inline bootstrap data from runtime fetches that only refresh or extend already-renderable state.
- Next.js official docs show a clear split between Pages Router style inline `__NEXT_DATA__` payloads and App Router style server-side fetches, streamed route segments, and Data Cache behavior.
- This matters directly for `render-critical` classification, because a request observed during capture may already be covered by bootstrap data that survives into replay.

## Code Implications

- [html-processor.js](C:/Users/dntmd/OneDrive/Desktop/개인/Project/front_clone_coding/src/processor/html-processor.js) should keep preserving inline bootstrap blobs and known framework state containers before assuming later runtime requests are mandatory.
- [js-processor.js](C:/Users/dntmd/OneDrive/Desktop/개인/Project/front_clone_coding/src/processor/js-processor.js) should prefer rewriting framework runtime endpoints without stripping the triggers that hydrate visible sections.
- [api-processor.js](C:/Users/dntmd/OneDrive/Desktop/개인/Project/front_clone_coding/src/processor/api-processor.js) and [replay-verifier.js](C:/Users/dntmd/OneDrive/Desktop/개인/Project/front_clone_coding/src/verifier/replay-verifier.js) should use page-level bootstrap evidence when deciding whether a request is strict replay-critical or only supporting runtime.

## Accepted Heuristics

- Treat Pages Router style inline JSON as strong bootstrap evidence before labeling later same-site requests as first-paint blockers.
- Treat App Router pages as mixed bootstrap and streaming surfaces; do not assume the absence of `__NEXT_DATA__` means bootstrap is absent.
- Prefer preserving existing hydration payloads and request triggers over inventing synthetic bootstrap data during replay.

## Open Questions

- What stable heuristics best identify App Router streamed payloads in captured HTML and script chunks without framework-specific hacks?
- How should replay verification score pages that render first paint from inline bootstrap but defer meaningful sections to post-hydration client fetches?
- When a framework relies on server-side request memoization, what evidence is sufficient to prove a captured browser request was not first-paint critical?

## Sources

- Next.js Large Page Data error guide: https://nextjs.org/docs/messages/large-page-data
- Next.js App Router data fetching guide: https://nextjs.org/docs/app/getting-started/fetching-data
- Next.js App Router caching deep dive: https://nextjs.org/docs/app/deep-dive/caching
