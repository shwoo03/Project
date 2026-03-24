#!/usr/bin/env node

import path from 'path';
import {
  appendJsonlRecord,
  bootstrapResearchSystem,
  buildCodeLinkRecord,
  buildExperimentRecord,
  buildLearningNoteRecord,
  buildResearchReport,
  listKnowledgeForModule,
  listKnowledgeForTag,
  loadTaxonomy,
  promoteCuratedNote,
} from './knowledge-store.js';

const [, , command, ...rest] = process.argv;
const args = parseArgs(rest);
const rootDir = path.resolve(args.root || process.cwd());

try {
  const taxonomy = await loadTaxonomy(rootDir);

  switch (command) {
    case 'bootstrap':
      await bootstrapResearchSystem(rootDir);
      console.log(`Research knowledge system is ready at ${path.join(rootDir, 'research')}`);
      break;
    case 'add-learning': {
      const record = buildLearningNoteRecord({
        ...args,
        moduleRefs: args.module,
        tags: args.tag,
        customTags: args.customTag,
      }, { taxonomy });
      await appendJsonlRecord(rootDir, 'learning-notes', record);
      console.log(`Saved learning note: ${record.title}`);
      break;
    }
    case 'link-module': {
      const record = buildCodeLinkRecord({
        ...args,
        moduleRef: args.module,
        tags: args.tag,
        customTags: args.customTag,
      }, { taxonomy });
      await appendJsonlRecord(rootDir, 'code-links', record);
      console.log(`Saved code link: ${record.title}`);
      break;
    }
    case 'add-experiment': {
      const record = buildExperimentRecord({
        ...args,
        moduleRefs: args.module,
        tags: args.tag,
        customTags: args.customTag,
        metricBefore: parseJsonArg(args.metricBefore),
        metricAfter: parseJsonArg(args.metricAfter),
        linkedRecordIds: args.linkedRecordId || args.link,
      }, { taxonomy });
      await appendJsonlRecord(rootDir, 'experiments', record);
      console.log(`Saved experiment: ${record.title}`);
      break;
    }
    case 'promote-note': {
      const result = await promoteCuratedNote(rootDir, {
        kind: args.kind,
        target: args.target,
        summary: args.summary,
      });
      console.log(`Updated curated note: ${result.path}`);
      break;
    }
    case 'list-module': {
      const payload = await listKnowledgeForModule(rootDir, args.module);
      console.log(JSON.stringify(payload, null, 2));
      break;
    }
    case 'list-tag': {
      const payload = await listKnowledgeForTag(rootDir, args.tag);
      console.log(JSON.stringify(payload, null, 2));
      break;
    }
    case 'report': {
      const report = await buildResearchReport(rootDir);
      console.log(JSON.stringify(report, null, 2));
      break;
    }
    default:
      printUsage();
      process.exitCode = 1;
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) continue;
    const key = token.slice(2);
    const next = argv[index + 1];
    const value = next && !next.startsWith('--') ? next : true;
    if (value !== true) {
      index += 1;
    }

    if (parsed[key] === undefined) {
      parsed[key] = value;
    } else if (Array.isArray(parsed[key])) {
      parsed[key].push(value);
    } else {
      parsed[key] = [parsed[key], value];
    }
  }
  return parsed;
}

function parseJsonArg(value) {
  if (!value || value === true) return {};
  try {
    return JSON.parse(value);
  } catch {
    throw new Error(`Invalid JSON payload: ${value}`);
  }
}

function printUsage() {
  console.log([
    'Usage:',
    '  node research/scripts/knowledge-cli.js bootstrap',
    '  node research/scripts/knowledge-cli.js add-learning --title "..." --summary "..." --module src/crawler/site-crawler.js --tag login-gated-detection --evidence manual-test',
    '  node research/scripts/knowledge-cli.js link-module --title "..." --summary "..." --module src/processor/api-processor.js --source internal-note --tag graphql',
    '  node research/scripts/knowledge-cli.js add-experiment --title "..." --summary "..." --hypothesis "..." --module src/crawler/site-crawler.js --linkedRecordId <uuid> --metricBefore "{\\"precision\\":0.71}" --metricAfter "{\\"precision\\":0.84}"',
    '  node research/scripts/knowledge-cli.js list-module --module src/crawler/site-crawler.js',
    '  node research/scripts/knowledge-cli.js list-tag --tag login-gated-detection',
    '  node research/scripts/knowledge-cli.js promote-note --kind module --target src/crawler/site-crawler.js',
    '  node research/scripts/knowledge-cli.js report',
  ].join('\n'));
}
