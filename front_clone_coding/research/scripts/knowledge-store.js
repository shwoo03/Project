import fs from 'fs/promises';
import path from 'path';
import { randomUUID } from 'crypto';

export const DEFAULT_COLLECTIONS = [
  'papers',
  'learning-notes',
  'code-links',
  'experiments',
];

export const DEFAULT_TAXONOMY = {
  topics: [
    'anti-bot',
    'api-capture',
    'asset-rewrite',
    'browser-automation',
    'change-detection',
    'content-extraction',
    'crawl-budget',
    'crawl-scope',
    'distributed-crawling',
    'dom-rewrite',
    'dynamic-rendering',
    'form-analysis',
    'graphql',
    'link-classification',
    'login-gated-detection',
    'network-observability',
    'output-scaffolding',
    'queue-prioritization',
    'replay-fidelity',
    'session-management',
    'url-normalization',
    'visual-analysis',
    'websocket-capture',
  ],
  evidence: [
    'benchmark',
    'design-note',
    'incident',
    'manual-test',
    'paper',
    'production-run',
    'prototype',
    'regression-test',
  ],
  sourceTypes: [
    'blog-post',
    'conference-talk',
    'internal-note',
    'paper',
    'postmortem',
    'reference-doc',
    'repo',
    'test-result',
  ],
  statuses: [
    'adopted',
    'draft',
    'planned',
    'rejected',
    'researched',
    'tested',
  ],
  priorities: [
    'high',
    'medium',
    'low',
  ],
};

export const DEFAULT_MODULE_CATALOG = [
  'src/crawler/page-crawler.js',
  'src/crawler/site-crawler.js',
  'src/crawler/network-interceptor.js',
  'src/processor/html-processor.js',
  'src/processor/js-processor.js',
  'src/processor/api-processor.js',
  'web/server.js',
];

export function getResearchRoot(rootDir = process.cwd()) {
  return path.join(rootDir, 'research');
}

export function getCollectionPath(rootDir, collection) {
  return path.join(getResearchRoot(rootDir), 'data', `${collection}.jsonl`);
}

export function getNotesRoot(rootDir = process.cwd()) {
  return path.join(getResearchRoot(rootDir), 'notes');
}

export function getTaxonomyPath(rootDir = process.cwd()) {
  return path.join(getResearchRoot(rootDir), 'config', 'taxonomy.json');
}

export function getModuleCatalogPath(rootDir = process.cwd()) {
  return path.join(getResearchRoot(rootDir), 'config', 'module-catalog.json');
}

export async function bootstrapResearchSystem(rootDir = process.cwd()) {
  const researchRoot = getResearchRoot(rootDir);
  const dirs = [
    researchRoot,
    path.join(researchRoot, 'config'),
    path.join(researchRoot, 'data'),
    path.join(researchRoot, 'notes'),
    path.join(researchRoot, 'notes', 'modules'),
    path.join(researchRoot, 'notes', 'topics'),
    path.join(researchRoot, 'notes', 'decisions'),
    path.join(researchRoot, 'schema'),
    path.join(researchRoot, 'scripts'),
    path.join(researchRoot, 'templates'),
  ];

  await Promise.all(dirs.map((dir) => fs.mkdir(dir, { recursive: true })));

  for (const collection of DEFAULT_COLLECTIONS) {
    const filePath = getCollectionPath(rootDir, collection);
    try {
      await fs.access(filePath);
    } catch {
      await fs.writeFile(filePath, '', 'utf8');
    }
  }

  const moduleCatalogPath = getModuleCatalogPath(rootDir);
  try {
    await fs.access(moduleCatalogPath);
  } catch {
    await fs.writeFile(
      moduleCatalogPath,
      `${JSON.stringify(DEFAULT_MODULE_CATALOG.map((moduleRef) => ({ moduleRef })), null, 2)}\n`,
      'utf8',
    );
  }

  const taxonomyPath = getTaxonomyPath(rootDir);
  try {
    await fs.access(taxonomyPath);
  } catch {
    await fs.writeFile(taxonomyPath, `${JSON.stringify(DEFAULT_TAXONOMY, null, 2)}\n`, 'utf8');
  }
}

export async function readJsonlCollection(rootDir, collection) {
  const filePath = getCollectionPath(rootDir, collection);
  try {
    const raw = await fs.readFile(filePath, 'utf8');
    return raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line));
  } catch (error) {
    if (error.code === 'ENOENT') {
      return [];
    }
    throw error;
  }
}

export async function appendJsonlRecord(rootDir, collection, record) {
  await bootstrapResearchSystem(rootDir);
  const filePath = getCollectionPath(rootDir, collection);
  const serialized = `${JSON.stringify(record)}\n`;
  await fs.appendFile(filePath, serialized, 'utf8');
  return record;
}

export async function loadTaxonomy(rootDir = process.cwd()) {
  try {
    const raw = await fs.readFile(getTaxonomyPath(rootDir), 'utf8');
    return JSON.parse(raw);
  } catch (error) {
    if (error.code === 'ENOENT') {
      return DEFAULT_TAXONOMY;
    }
    throw error;
  }
}

export async function loadModuleCatalog(rootDir = process.cwd()) {
  const raw = await fs.readFile(getModuleCatalogPath(rootDir), 'utf8');
  const parsed = JSON.parse(raw);
  return parsed
    .map((entry) => entry.moduleRef || entry)
    .filter(Boolean)
    .map((value) => normalizeModuleRef(value));
}

export function buildLearningNoteRecord(input, options = {}) {
  const title = normalizeRequiredString(input.title, 'title');
  const summary = normalizeRequiredString(input.summary, 'summary');
  const moduleRefs = normalizeModuleRefs(input.moduleRefs || input.moduleRef || input.module);
  const tags = normalizeStringArray(input.tags || input.tag);
  const customTags = normalizeStringArray(input.customTags || input.customTag);
  const evidence = normalizeRequiredString(input.evidence || 'design-note', 'evidence');

  validateKnowledgeTarget(moduleRefs, tags, customTags);
  validateTaxonomyValues(tags, options.taxonomy?.topics, 'tag');
  validateTaxonomyValue(evidence, options.taxonomy?.evidence, 'evidence');

  return {
    id: randomUUID(),
    type: 'learning-note',
    title,
    summary,
    moduleRefs,
    tags,
    customTags,
    evidence,
    nextAction: normalizeOptionalString(input.nextAction, ''),
    status: normalizeOptionalString(input.status, 'draft'),
    createdAt: new Date().toISOString(),
  };
}

export function buildCodeLinkRecord(input, options = {}) {
  const moduleRef = normalizeRequiredString(input.moduleRef || input.module, 'moduleRef');
  const tags = normalizeStringArray(input.tags || input.tag);
  const customTags = normalizeStringArray(input.customTags || input.customTag);
  const evidence = normalizeRequiredString(input.evidence || 'design-note', 'evidence');

  validateKnowledgeTarget([moduleRef], tags, customTags);
  validateTaxonomyValues(tags, options.taxonomy?.topics, 'tag');
  validateTaxonomyValue(evidence, options.taxonomy?.evidence, 'evidence');
  validateTaxonomyValue(
    normalizeOptionalString(input.sourceType || input.source, 'internal-note'),
    options.taxonomy?.sourceTypes,
    'sourceType',
  );
  validateTaxonomyValue(
    normalizeOptionalString(input.priority, 'medium'),
    options.taxonomy?.priorities,
    'priority',
  );
  validateTaxonomyValue(
    normalizeOptionalString(input.status, 'draft'),
    options.taxonomy?.statuses,
    'status',
  );

  return {
    id: randomUUID(),
    type: 'code-link',
    title: normalizeRequiredString(input.title, 'title'),
    summary: normalizeRequiredString(input.summary, 'summary'),
    moduleRef: normalizeModuleRef(moduleRef),
    evidence,
    sourceType: normalizeOptionalString(input.sourceType || input.source, 'internal-note'),
    tags,
    customTags,
    priority: normalizeOptionalString(input.priority, 'medium'),
    status: normalizeOptionalString(input.status, 'draft'),
    learningNoteId: normalizeOptionalString(input.learningNoteId, ''),
    createdAt: new Date().toISOString(),
  };
}

export function buildExperimentRecord(input, options = {}) {
  const moduleRefs = normalizeModuleRefs(input.moduleRefs || input.moduleRef || input.module);
  const tags = normalizeStringArray(input.tags || input.tag);
  const customTags = normalizeStringArray(input.customTags || input.customTag);
  const evidence = normalizeRequiredString(input.evidence || 'prototype', 'evidence');
  const linkedRecordIds = normalizeStringArray(input.linkedRecordIds || input.linkedRecordId || input.link);

  validateKnowledgeTarget(moduleRefs, tags, customTags);
  validateTaxonomyValues(tags, options.taxonomy?.topics, 'tag');
  validateTaxonomyValue(evidence, options.taxonomy?.evidence, 'evidence');
  validateTaxonomyValue(
    normalizeOptionalString(input.decision, 'planned'),
    options.taxonomy?.statuses,
    'decision',
  );
  if (linkedRecordIds.length === 0) {
    throw new Error('Experiments must reference at least one linked record id');
  }

  return {
    id: randomUUID(),
    type: 'experiment',
    title: normalizeRequiredString(input.title, 'title'),
    summary: normalizeRequiredString(input.summary || input.hypothesis, 'summary'),
    hypothesis: normalizeRequiredString(input.hypothesis, 'hypothesis'),
    moduleRefs,
    tags,
    customTags,
    evidence,
    linkedRecordIds,
    dataset: normalizeOptionalString(input.dataset, ''),
    metricBefore: normalizeObject(input.metricBefore),
    metricAfter: normalizeObject(input.metricAfter),
    decision: normalizeOptionalString(input.decision, 'planned'),
    notes: normalizeOptionalString(input.notes, ''),
    createdAt: new Date().toISOString(),
  };
}

export async function buildResearchSnapshot(rootDir = process.cwd()) {
  const [papers, learningNotes, codeLinks, experiments, moduleCatalog] = await Promise.all([
    readJsonlCollection(rootDir, 'papers'),
    readJsonlCollection(rootDir, 'learning-notes'),
    readJsonlCollection(rootDir, 'code-links'),
    readJsonlCollection(rootDir, 'experiments'),
    loadModuleCatalog(rootDir),
  ]);

  const allRecords = { papers, learningNotes, codeLinks, experiments };
  const modules = new Map();
  const tags = new Map();
  const linkIds = new Set(codeLinks.map((link) => link.id).filter(Boolean));
  const noteIds = new Set(learningNotes.map((note) => note.id).filter(Boolean));

  const noteIdsWithLinks = new Set(
    codeLinks
      .map((link) => link.learningNoteId)
      .filter(Boolean),
  );
  const linkedRecordIdsWithExperiments = new Set(
    experiments.flatMap((experiment) => experiment.linkedRecordIds || []).filter(Boolean),
  );

  for (const record of [...learningNotes, ...codeLinks, ...experiments]) {
    for (const moduleRef of collectModuleRefs(record)) {
      modules.set(moduleRef, (modules.get(moduleRef) || 0) + 1);
    }
    for (const tag of collectAllTags(record)) {
      tags.set(tag, (tags.get(tag) || 0) + 1);
    }
  }

  const unresolvedLearningNotes = learningNotes
    .filter((note) => !noteIdsWithLinks.has(note.id))
    .map((note) => ({ id: note.id, title: note.title }));
  const unresolvedCodeLinks = codeLinks
    .filter((link) => !linkedRecordIdsWithExperiments.has(link.id))
    .map((link) => ({ id: link.id, title: link.title }));
  const openExperiments = experiments
    .filter((experiment) => !['adopted', 'rejected'].includes(experiment.decision))
    .map((experiment) => ({ id: experiment.id, title: experiment.title, decision: experiment.decision }));

  return {
    records: allRecords,
    moduleCatalog,
    topModules: toSortedCountList(modules),
    topTags: toSortedCountList(tags),
    unresolvedLearningNotes,
    unresolvedCodeLinks,
    openExperiments,
    knownRecordIds: new Set([...noteIds, ...linkIds]),
  };
}

export async function buildResearchReport(rootDir = process.cwd()) {
  const snapshot = await buildResearchSnapshot(rootDir);
  const { records, topModules, topTags, unresolvedLearningNotes, unresolvedCodeLinks, openExperiments } = snapshot;

  return {
    generatedAt: new Date().toISOString(),
    counts: {
      papers: records.papers.length,
      learningNotes: records.learningNotes.length,
      codeLinks: records.codeLinks.length,
      experiments: records.experiments.length,
    },
    topModules: topModules.slice(0, 10),
    topTags: topTags.slice(0, 10),
    unresolvedLearningNotes,
    unresolvedCodeLinks,
    openExperiments,
  };
}

export async function listKnowledgeForModule(rootDir, moduleRef) {
  const snapshot = await buildResearchSnapshot(rootDir);
  const normalizedModule = normalizeModuleRef(moduleRef);
  return {
    moduleRef: normalizedModule,
    learningNotes: snapshot.records.learningNotes.filter((note) => collectModuleRefs(note).includes(normalizedModule)),
    codeLinks: snapshot.records.codeLinks.filter((link) => collectModuleRefs(link).includes(normalizedModule)),
    experiments: snapshot.records.experiments.filter((experiment) => collectModuleRefs(experiment).includes(normalizedModule)),
  };
}

export async function listKnowledgeForTag(rootDir, tag) {
  const snapshot = await buildResearchSnapshot(rootDir);
  const normalizedTag = String(tag || '').trim();
  return {
    tag: normalizedTag,
    learningNotes: snapshot.records.learningNotes.filter((note) => collectAllTags(note).includes(normalizedTag)),
    codeLinks: snapshot.records.codeLinks.filter((link) => collectAllTags(link).includes(normalizedTag)),
    experiments: snapshot.records.experiments.filter((experiment) => collectAllTags(experiment).includes(normalizedTag)),
  };
}

export async function promoteCuratedNote(rootDir, input) {
  await bootstrapResearchSystem(rootDir);
  const kind = normalizeRequiredString(input.kind, 'kind');
  const target = normalizeRequiredString(input.target, 'target');

  if (!['module', 'topic', 'decision'].includes(kind)) {
    throw new Error(`Unsupported note kind: ${kind}`);
  }

  let notePath;
  let payload;
  if (kind === 'module') {
    const moduleRef = normalizeModuleRef(target);
    payload = await listKnowledgeForModule(rootDir, moduleRef);
    notePath = path.join(getNotesRoot(rootDir), 'modules', `${slugify(moduleRef)}.md`);
  } else if (kind === 'topic') {
    payload = await listKnowledgeForTag(rootDir, target);
    notePath = path.join(getNotesRoot(rootDir), 'topics', `${slugify(target)}.md`);
  } else {
    payload = input;
    notePath = path.join(getNotesRoot(rootDir), 'decisions', `${slugify(target)}.md`);
  }

  const markdown = renderCuratedNote(kind, target, payload, input.summary || '');
  await fs.writeFile(notePath, `${markdown}\n`, 'utf8');
  return { path: notePath, markdown };
}

function renderCuratedNote(kind, target, payload, summary) {
  const lines = [
    `# ${target}`,
    '',
    `- Kind: ${kind}`,
    `- Updated: ${new Date().toISOString()}`,
  ];

  if (summary) {
    lines.push(`- Summary: ${summary}`);
  }

  lines.push('', '## Current Behavior');
  lines.push(...renderRecordBullets(payload.learningNotes, 'No captured learning notes yet.'));

  lines.push('', '## Known Weaknesses');
  lines.push(...renderKnownWeaknessBullets(payload.learningNotes, payload.codeLinks));

  lines.push('', '## Experiment Backlog');
  lines.push(...renderExperimentBullets(payload.experiments));

  lines.push('', '## Accepted Heuristics');
  lines.push(...renderAcceptedHeuristics(payload.codeLinks, payload.experiments));

  return lines.join('\n');
}

function renderRecordBullets(records = [], emptyLine) {
  if (!records.length) return [emptyLine];
  return records
    .slice()
    .sort((a, b) => a.title.localeCompare(b.title))
    .map((record) => `- ${record.title}: ${record.summary}`);
}

function renderKnownWeaknessBullets(learningNotes = [], codeLinks = []) {
  const weaknesses = [
    ...learningNotes.filter((note) => note.nextAction || note.status !== 'adopted'),
    ...codeLinks.filter((link) => link.status !== 'adopted'),
  ];
  if (!weaknesses.length) return ['- No open weaknesses recorded yet.'];
  return weaknesses
    .slice()
    .sort((a, b) => a.title.localeCompare(b.title))
    .map((record) => `- ${record.title}: ${record.nextAction || record.summary}`);
}

function renderExperimentBullets(experiments = []) {
  if (!experiments.length) return ['- No experiments recorded yet.'];
  return experiments
    .slice()
    .sort((a, b) => a.title.localeCompare(b.title))
    .map((experiment) => `- ${experiment.title}: ${experiment.decision} | ${experiment.summary}`);
}

function renderAcceptedHeuristics(codeLinks = [], experiments = []) {
  const accepted = [
    ...codeLinks.filter((link) => link.status === 'adopted'),
    ...experiments.filter((experiment) => experiment.decision === 'adopted'),
  ];
  if (!accepted.length) return ['- No accepted heuristics captured yet.'];
  return accepted
    .slice()
    .sort((a, b) => a.title.localeCompare(b.title))
    .map((record) => `- ${record.title}: ${record.summary}`);
}

function collectModuleRefs(record) {
  if (!record) return [];
  if (Array.isArray(record.moduleRefs)) return record.moduleRefs.map((value) => normalizeModuleRef(value));
  if (record.moduleRef) return [normalizeModuleRef(record.moduleRef)];
  return [];
}

function collectAllTags(record) {
  return [...normalizeStringArray(record.tags), ...normalizeStringArray(record.customTags)];
}

function toSortedCountList(map) {
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count }));
}

function validateKnowledgeTarget(moduleRefs, tags, customTags) {
  if (moduleRefs.length === 0 && tags.length === 0 && customTags.length === 0) {
    throw new Error('Each record needs at least one module reference or tag');
  }
}

function validateTaxonomyValues(values, allowedValues, label) {
  if (!allowedValues || allowedValues.length === 0) return;
  for (const value of values) {
    validateTaxonomyValue(value, allowedValues, label);
  }
}

function validateTaxonomyValue(value, allowedValues, label) {
  if (!allowedValues || allowedValues.length === 0) return;
  if (!allowedValues.includes(value)) {
    throw new Error(`Unknown ${label}: ${value}`);
  }
}

function normalizeRequiredString(value, fieldName) {
  const normalized = normalizeOptionalString(value, '');
  if (!normalized) {
    throw new Error(`Missing required field: ${fieldName}`);
  }
  return normalized;
}

function normalizeOptionalString(value, fallback = '') {
  if (value === undefined || value === null || value === true) return fallback;
  return String(value).trim() || fallback;
}

function normalizeStringArray(value) {
  if (value === undefined || value === null || value === '' || value === true) return [];
  const raw = Array.isArray(value) ? value : [value];
  return [...new Set(
    raw
      .flatMap((item) => String(item).split(','))
      .map((item) => item.trim())
      .filter(Boolean),
  )];
}

function normalizeModuleRefs(value) {
  return normalizeStringArray(value).map((item) => normalizeModuleRef(item));
}

function normalizeModuleRef(value) {
  return String(value).trim().replace(/\\/g, '/').replace(/^\.\/+/, '');
}

function normalizeObject(value) {
  if (!value) return {};
  if (typeof value === 'object' && !Array.isArray(value)) return value;
  return {};
}

function slugify(value) {
  return String(value || 'note')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'note';
}
