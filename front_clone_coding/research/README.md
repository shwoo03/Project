# Research Knowledge System

This workspace is designed for solo local development and implementation knowledge capture. It is intentionally file-first: JSONL stores the append-only machine history, and Markdown stores curated summaries that are easy to review in Git.

## Principles

- Capture first, structure second, automate third, database last.
- Keep day-to-day operation file-based and repo-local.
- Link knowledge to crawler modules, not just to sources.
- Promote stable learnings into curated notes once they become durable.

## Source Of Truth

- `data/*.jsonl` is the canonical machine-readable store.
- `notes/**/*.md` is the canonical human-readable synthesis layer.
- `schema/postgres.sql` is migration scaffolding for future scale, not an operational dependency.

## Layout

- `config/taxonomy.json` - Shared tags, evidence labels, priorities, and statuses.
- `config/module-catalog.json` - Seed module catalog for the crawler architecture.
- `data/*.jsonl` - Append-only records.
- `notes/modules/` - Curated knowledge by code module.
- `notes/topics/` - Curated cross-cutting topics.
- `notes/decisions/` - Longer-lived decisions, accepted patterns, and rejections.
- `scripts/knowledge-store.js` - Storage, aggregation, and note rendering helpers.
- `scripts/knowledge-cli.js` - Capture and review commands.

## Record Lifecycle

1. `learning note` - something new was observed
2. `code link` - it was tied to a module
3. `experiment` - it was tested
4. `decision note` - it became durable knowledge

Every new record must include:

- `title`
- `summary`
- at least one module reference or tag
- one evidence type

Experiments must also reference at least one motivating learning note or code link via `linkedRecordIds`.

## Default Workflow

```bash
npm run knowledge:init
node research/scripts/knowledge-cli.js add-learning --title "Login gate false positive" --summary "Help page copy triggered the login heuristic without an auth form." --module src/crawler/site-crawler.js --tag login-gated-detection --evidence manual-test
node research/scripts/knowledge-cli.js link-module --title "Refine login gate signal" --summary "Require a stronger password-form signal before suppressing link queueing." --module src/crawler/site-crawler.js --tag login-gated-detection --source internal-note --learningNoteId <learning-note-id>
node research/scripts/knowledge-cli.js add-experiment --title "Login heuristic v2" --summary "Test the stronger auth-form signal on mixed auth and help pages." --hypothesis "A stronger form signal reduces false positives." --module src/crawler/site-crawler.js --tag login-gated-detection --evidence prototype --linkedRecordId <code-link-id>
node research/scripts/knowledge-cli.js promote-note --kind module --target src/crawler/site-crawler.js
npm run knowledge:report
```

## Capture And Review Commands

- `bootstrap` - Prepare the local research workspace.
- `add-learning` - Capture a new observation.
- `link-module` - Tie a learning to a concrete code module.
- `add-experiment` - Record a test or validation attempt.
- `list-module --module <path>` - Show all knowledge tied to one module.
- `list-tag --tag <name>` - Review a topic thread.
- `promote-note --kind <module|topic|decision> --target <value>` - Generate or update a curated Markdown summary.
- `report` - Show counts, hot spots, open work, and missing links.

## What The Report Answers

- Which modules accumulate the most knowledge?
- Which topics keep showing up?
- Which learning notes still have no code link?
- Which code links still have no experiment?
- Which experiments are still open?

## Database Readiness

`schema/postgres.sql` stays in the repo so the system can be promoted later, but PostgreSQL is not part of normal operation.

Promote to DB-backed storage only when at least one of these becomes true:

- the knowledge base grows to hundreds or thousands of records
- multiple contributors need concurrent editing
- semantic search over section-level content becomes necessary
- a UI/dashboard needs joined queries across sources, links, and experiments

Until then, keep the system simple and file-first.
