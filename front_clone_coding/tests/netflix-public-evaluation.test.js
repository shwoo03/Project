import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildNetflixPublicEvaluationReport,
  compareTextMarkers,
  renderNetflixPublicEvaluationMarkdown,
  summarizeCapturedArtifacts,
} from '../src/evaluation/netflix-public-site-evaluator.js';

test('summarizeCapturedArtifacts extracts replay and manifest signals', () => {
  const summary = summarizeCapturedArtifacts({
    crawlManifest: {
      pages: [
        { loginGated: false, skippedReason: null },
        { loginGated: true, skippedReason: 'login-gated' },
        { loginGated: false, skippedReason: 'max-depth' },
      ],
    },
    resourceManifest: [
      { replayCriticality: 'high', savedPath: 'public/css/main.css' },
      { replayCriticality: 'high', savedPath: null },
      { replayCriticality: 'low', savedPath: 'public/img/poster.jpg' },
    ],
    pageQualityReport: [
      { pageUrl: 'https://www.netflix.com', savedPath: 'index.html', textDriftRatio: 0.12 },
      { pageUrl: 'https://www.netflix.com/faq', savedPath: 'faq.html', textDriftRatio: 0.44 },
    ],
    replayVerification: {
      missingCriticalAssets: ['/public/app.js'],
      externalRequests: ['https://assets.nflxext.com/x.js'],
      pages: [
        { savedPath: 'index.html', warnings: ['title-drift'] },
      ],
    },
    missingBehaviors: '# Missing Behaviors\n\n- Inline click handlers detected\n- sessionStorage was captured\n',
  });

  assert.equal(summary.capturedPages, 3);
  assert.equal(summary.skippedPages, 2);
  assert.equal(summary.loginGatedPages, 1);
  assert.equal(summary.criticalAssetCount, 2);
  assert.equal(summary.criticalAssetSavedCount, 1);
  assert.equal(summary.highTextDriftPages.length, 1);
  assert.deepEqual(summary.replayWarnings, ['index.html: title-drift']);
  assert.deepEqual(summary.missingBehaviors, ['Inline click handlers detected', 'sessionStorage was captured']);
});

test('compareTextMarkers computes overlap and deltas', () => {
  const result = compareTextMarkers(
    ['Netflix', 'Get Started', 'FAQ'],
    ['NETFLIX', 'faq', 'Sign In'],
  );

  assert.equal(result.overlapRatio, 0.6667);
  assert.deepEqual(result.shared, ['netflix', 'faq']);
  assert.deepEqual(result.referenceOnly, ['get started']);
  assert.deepEqual(result.candidateOnly, ['sign in']);
});

test('renderNetflixPublicEvaluationMarkdown prints compact report sections', () => {
  const report = buildNetflixPublicEvaluationReport({
    startUrl: 'https://www.netflix.com/',
    outputDir: 'output/netflix.com',
    entryPath: 'index.html',
    artifactSummary: {
      capturedPages: 3,
      skippedPages: 1,
      loginGatedPages: 0,
      representativePages: 2,
      criticalAssetCount: 5,
      criticalAssetSavedCount: 4,
      highTextDriftPages: [{ savedPath: 'faq.html', textDriftRatio: 0.5 }],
      replayMissingCriticalAssets: ['/public/app.js'],
      replayExternalRequests: ['https://cdn.example.com/live.js'],
      replayWarnings: ['index.html: title-drift'],
      missingBehaviors: ['Inline click handlers detected'],
    },
    liveProfile: {
      keyMarkers: ['Netflix', 'Get Started', 'FAQ'],
      structure: { headerCount: 1, mainCount: 1, footerCount: 1, linkCount: 8 },
      network: { requestCount: 20, failedCount: 0, status4xx5xx: 0 },
      consoleErrors: [],
      externalRequests: [],
    },
    localProfile: {
      keyMarkers: ['Netflix', 'FAQ', 'Sign In'],
      structure: { headerCount: 1, mainCount: 1, footerCount: 1, linkCount: 5 },
      network: { requestCount: 12, failedCount: 1, status4xx5xx: 1 },
      consoleErrors: ['Failed to load resource'],
      externalRequests: ['https://cdn.example.com/live.js'],
    },
    localNavigation: {
      attemptedCount: 2,
      successCount: 1,
      blockedLinkCount: 3,
      results: [],
      externalRequests: [],
    },
  });

  const markdown = renderNetflixPublicEvaluationMarkdown(report);

  assert.match(markdown, /# Netflix Public Replay Evaluation/);
  assert.match(markdown, /Captured pages: 3/);
  assert.match(markdown, /Marker overlap ratio: 0.6667/);
  assert.match(markdown, /Local navigation successes: 1\/2/);
  assert.match(markdown, /Replay still attempts external requests/);
  assert.match(markdown, /Inline click handlers detected/);
});
