# graphql-runtime-replay

## Current Relevance

- GraphQL replay quality now depends less on capturing every request and more on deciding which operations are strict first-paint dependencies versus supporting refresh traffic.
- Apollo documentation confirms two important behaviors for this repository: `cache-and-network` can trigger a network request even when cached or inline data is already sufficient, and APQ can omit the full GraphQL document entirely.
- Those behaviors explain why some replay candidates should be downgraded to supporting runtime and why mock matching cannot depend on `query` text alone.

## Code Implications

- [api-processor.js](C:/Users/dntmd/OneDrive/Desktop/개인/Project/front_clone_coding/src/processor/api-processor.js) should continue separating strict `render-critical` GraphQL from supporting runtime based on bootstrap fallback and visible-content dependence.
- [replay-mock-utils.js](C:/Users/dntmd/OneDrive/Desktop/개인/Project/front_clone_coding/src/utils/replay-mock-utils.js) should evolve toward matching GraphQL mocks using operation name, persisted query metadata, and variables shape or hash when full query text is missing.
- [replay-verifier.js](C:/Users/dntmd/OneDrive/Desktop/개인/Project/front_clone_coding/src/verifier/replay-verifier.js) should keep reporting strict misses separately from supporting requests that were never triggered.

## Accepted Heuristics

- Do not treat every observed GraphQL request as first-paint critical; prefer page bootstrap evidence over request-name heuristics alone.
- When `query` is absent, persisted query metadata and operation identity are still sufficient to build bounded replay candidate keys.
- Keep method and pathname strict even when GraphQL fallback matching becomes more flexible around operation metadata.

## Open Questions

- What minimal variables fingerprint is stable enough for persisted-query matching without overfitting to request noise?
- Which GraphQL operations on public landing pages commonly behave like optional state refresh rather than visible content fill?
- Should replay artifacts record persisted query hashes separately so later mock-debugging does not rely on raw request bodies alone?

## Sources

- Apollo fetch policy documentation: https://www.apollographql.com/docs/react/data/queries/#setting-a-fetch-policy
- Apollo Automatic Persisted Queries documentation: https://www.apollographql.com/docs/graphos/routing/operations/apq
