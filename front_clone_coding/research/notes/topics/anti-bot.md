# anti-bot

## Current Behavior

- The crawler uses a stable Playwright browser runtime with `serviceWorkers: 'block'`.
- Auth reuse is supported through storage state and cookie import.

## Known Weaknesses

- There is no crawl posture layer yet in historical runs, so all sites were previously treated with the same pacing.
- The project intentionally does not ship stealth-plugin style evasion.

## Experiment Backlog

- Compare `accurate` and `balanced` profiles on login-gated flows.
- Measure whether network posture changes reduce replay drift without hurting coverage.

## Accepted Heuristics

- Prefer realism-first browser identity and session reuse over aggressive fingerprint mutation.
