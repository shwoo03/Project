import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';

import {
  appendJsonlRecord,
  bootstrapResearchSystem,
  buildCodeLinkRecord,
  buildExperimentRecord,
  buildLearningNoteRecord,
  buildResearchReport,
  listKnowledgeForModule,
  loadTaxonomy,
  promoteCuratedNote,
  readJsonlCollection,
} from '../research/scripts/knowledge-store.js';

test('knowledge store bootstrap creates research data and notes directories', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-knowledge-'));
  try {
    await bootstrapResearchSystem(tempRoot);

    const researchRoot = path.join(tempRoot, 'research');
    const files = await fs.readdir(path.join(researchRoot, 'data'));
    const notesEntries = await fs.readdir(path.join(researchRoot, 'notes'));
    const moduleCatalog = JSON.parse(
      await fs.readFile(path.join(researchRoot, 'config', 'module-catalog.json'), 'utf8'),
    );

    assert.deepEqual(
      files.sort(),
      ['code-links.jsonl', 'experiments.jsonl', 'learning-notes.jsonl', 'papers.jsonl'],
    );
    assert.deepEqual(notesEntries.sort(), ['decisions', 'modules', 'topics']);
    assert.equal(moduleCatalog.length >= 7, true);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('knowledge store validates required evidence and tag-or-module capture', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-knowledge-'));
  try {
    await bootstrapResearchSystem(tempRoot);
    const taxonomy = await loadTaxonomy(tempRoot);

    assert.throws(() => buildLearningNoteRecord({
      title: 'Missing index target',
      summary: 'This should fail because nothing indexes it.',
      evidence: 'manual-test',
    }, { taxonomy }), /at least one module reference or tag/);

    assert.throws(() => buildLearningNoteRecord({
      title: 'Bad evidence',
      summary: 'This should fail because evidence is unknown.',
      moduleRefs: ['src/crawler/site-crawler.js'],
      evidence: 'unknown-evidence',
    }, { taxonomy }), /Unknown evidence/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('knowledge store records knowledge and builds unresolved report sections', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-knowledge-'));
  try {
    await bootstrapResearchSystem(tempRoot);
    const taxonomy = await loadTaxonomy(tempRoot);

    const learningNote = buildLearningNoteRecord({
      title: 'Login page false positives',
      summary: 'Need a stronger auth form signal before skipping queue expansion.',
      moduleRefs: ['src/crawler/site-crawler.js'],
      tags: ['login-gated-detection'],
      evidence: 'manual-test',
    }, { taxonomy });
    const linkedLearningNote = buildLearningNoteRecord({
      title: 'GraphQL response variant drift',
      summary: 'Operation grouping may miss a replay-relevant variant.',
      moduleRefs: ['src/processor/api-processor.js'],
      tags: ['graphql'],
      evidence: 'design-note',
    }, { taxonomy });
    const codeLink = buildCodeLinkRecord({
      title: 'GraphQL dedupe review',
      summary: 'Potential improvement for operation grouping.',
      moduleRef: 'src/processor/api-processor.js',
      tags: ['graphql'],
      evidence: 'design-note',
      learningNoteId: linkedLearningNote.id,
    }, { taxonomy });
    const experiment = buildExperimentRecord({
      title: 'Login detection heuristic v2',
      summary: 'Test a stronger auth-form signal on mixed auth and help pages.',
      hypothesis: 'Adding form semantics reduces false positives.',
      moduleRefs: ['src/crawler/site-crawler.js'],
      tags: ['login-gated-detection'],
      evidence: 'prototype',
      linkedRecordIds: [learningNote.id],
      metricBefore: { precision: 0.71 },
      metricAfter: { precision: 0.84 },
    }, { taxonomy });

    await appendJsonlRecord(tempRoot, 'learning-notes', learningNote);
    await appendJsonlRecord(tempRoot, 'learning-notes', linkedLearningNote);
    await appendJsonlRecord(tempRoot, 'code-links', codeLink);
    await appendJsonlRecord(tempRoot, 'experiments', experiment);

    const notes = await readJsonlCollection(tempRoot, 'learning-notes');
    const report = await buildResearchReport(tempRoot);

    assert.equal(notes.length, 2);
    assert.equal(report.counts.learningNotes, 2);
    assert.equal(report.counts.codeLinks, 1);
    assert.equal(report.counts.experiments, 1);
    assert.deepEqual(report.topModules[0], {
      value: 'src/crawler/site-crawler.js',
      count: 2,
    });
    assert.deepEqual(report.topTags[0], {
      value: 'graphql',
      count: 2,
    });
    assert.deepEqual(report.unresolvedLearningNotes, [
      {
        id: learningNote.id,
        title: 'Login page false positives',
      },
    ]);
    assert.deepEqual(report.unresolvedCodeLinks, [
      {
        id: codeLink.id,
        title: 'GraphQL dedupe review',
      },
    ]);
    assert.deepEqual(report.openExperiments, [
      {
        id: experiment.id,
        title: 'Login detection heuristic v2',
        decision: 'planned',
      },
    ]);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('knowledge store lists module knowledge across record types', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-knowledge-'));
  try {
    await bootstrapResearchSystem(tempRoot);
    const taxonomy = await loadTaxonomy(tempRoot);

    const learningNote = buildLearningNoteRecord({
      title: 'Scope edge case',
      summary: 'Hostname mode needs extra redirect validation.',
      moduleRefs: ['src/crawler/site-crawler.js'],
      tags: ['crawl-scope'],
      evidence: 'manual-test',
    }, { taxonomy });
    const codeLink = buildCodeLinkRecord({
      title: 'Hostname redirect guard',
      summary: 'Guard scope after final URL normalization.',
      moduleRef: 'src/crawler/site-crawler.js',
      tags: ['crawl-scope'],
      learningNoteId: learningNote.id,
    }, { taxonomy });
    const experiment = buildExperimentRecord({
      title: 'Hostname redirect validation',
      summary: 'Check redirect handling in hostname-only scope.',
      hypothesis: 'Final URL checks reduce out-of-scope captures.',
      moduleRefs: ['src/crawler/site-crawler.js'],
      tags: ['crawl-scope'],
      evidence: 'prototype',
      linkedRecordIds: [codeLink.id],
    }, { taxonomy });

    await appendJsonlRecord(tempRoot, 'learning-notes', learningNote);
    await appendJsonlRecord(tempRoot, 'code-links', codeLink);
    await appendJsonlRecord(tempRoot, 'experiments', experiment);

    const payload = await listKnowledgeForModule(tempRoot, 'src/crawler/site-crawler.js');

    assert.equal(payload.learningNotes.length, 1);
    assert.equal(payload.codeLinks.length, 1);
    assert.equal(payload.experiments.length, 1);
    assert.equal(payload.moduleRef, 'src/crawler/site-crawler.js');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('knowledge store promotes deterministic module notes', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-knowledge-'));
  try {
    await bootstrapResearchSystem(tempRoot);
    const taxonomy = await loadTaxonomy(tempRoot);

    const learningNote = buildLearningNoteRecord({
      title: 'Login gate false positive',
      summary: 'Marketing help copy matched login copy without auth fields.',
      moduleRefs: ['src/crawler/site-crawler.js'],
      tags: ['login-gated-detection'],
      evidence: 'manual-test',
      nextAction: 'Require a stronger password-form signal.',
    }, { taxonomy });
    const codeLink = buildCodeLinkRecord({
      title: 'Auth-form heuristic',
      summary: 'A password-form plus login copy is the current accepted baseline.',
      moduleRef: 'src/crawler/site-crawler.js',
      tags: ['login-gated-detection'],
      status: 'adopted',
      learningNoteId: learningNote.id,
    }, { taxonomy });
    const experiment = buildExperimentRecord({
      title: 'Auth-form heuristic validation',
      summary: 'Re-test auth-form plus login copy against mixed help pages.',
      hypothesis: 'The combined signal reduces false positives.',
      moduleRefs: ['src/crawler/site-crawler.js'],
      tags: ['login-gated-detection'],
      evidence: 'prototype',
      linkedRecordIds: [codeLink.id],
      decision: 'adopted',
    }, { taxonomy });

    await appendJsonlRecord(tempRoot, 'learning-notes', learningNote);
    await appendJsonlRecord(tempRoot, 'code-links', codeLink);
    await appendJsonlRecord(tempRoot, 'experiments', experiment);

    const result = await promoteCuratedNote(tempRoot, {
      kind: 'module',
      target: 'src/crawler/site-crawler.js',
    });
    const saved = await fs.readFile(result.path, 'utf8');

    assert.match(saved, /^# src\/crawler\/site-crawler\.js/m);
    assert.match(saved, /## Current Behavior/);
    assert.match(saved, /Login gate false positive: Marketing help copy matched login copy without auth fields\./);
    assert.match(saved, /## Experiment Backlog/);
    assert.match(saved, /Auth-form heuristic validation: adopted \| Re-test auth-form plus login copy against mixed help pages\./);
    assert.match(saved, /## Accepted Heuristics/);
    assert.match(saved, /Auth-form heuristic: A password-form plus login copy is the current accepted baseline\./);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
