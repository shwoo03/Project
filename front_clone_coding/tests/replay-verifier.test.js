import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';

import { runReplayVerification } from '../src/verifier/replay-verifier.js';
import { ensureDir, saveFile } from '../src/utils/file-utils.js';
import { normalizeCrawlUrl } from '../src/utils/url-utils.js';

test('runReplayVerification writes empty artifacts when no representative pages exist', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-'));
  try {
    const result = await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [],
      apiArtifacts: {},
      sampleSize: 0,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));
    const markdownReport = await fs.readFile(path.join(tempRoot, 'server', 'docs', 'replay-verification.md'), 'utf-8');

    assert.deepEqual(result.verificationWarnings, []);
    assert.equal(jsonReport.pagesVerified, 0);
    assert.match(markdownReport, /No representative pages were available/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification can boot its replay server and verify a simple page', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-live-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'index.html'),
      '<!DOCTYPE html><html><head><title>Replay</title></head><body><main><h1>Hello replay</h1></main></body></html>',
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'),
      '[]',
    );

    const result = await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [{
        url: 'https://example.com',
        finalUrl: 'https://example.com',
        savedPath: 'index.html',
        title: 'Replay',
        qa: { rawTextLength: 'Hello replay'.length },
        classification: { shouldRunReplayValidation: true },
        bootstrapSignals: {
          hasInlineBootstrapState: true,
          hasFrameworkBootstrap: true,
          hasRenderableStateFallback: true,
          bootstrapEvidenceLevel: 'strong',
          bootstrapSignalCount: 3,
          frameworkKinds: ['next-pages-router'],
        },
      }],
      apiArtifacts: {},
      sampleSize: 1,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));

    assert.equal(result.verificationWarnings.length, 0);
    assert.equal(jsonReport.pagesVerified, 1);
    assert.equal(jsonReport.pages[0].routeReached, true);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification resolves nested host-aware saved paths', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-hosted-'));
  try {
    await ensureDir(path.join(tempRoot, 'views', 'news.naver.com'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'news.naver.com', 'index.html'),
      '<!DOCTYPE html><html><head><title>News</title></head><body><main><h1>Naver News</h1></main></body></html>',
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'),
      '[]',
    );

    const result = await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://www.naver.com',
      pages: [{
        url: 'https://news.naver.com',
        finalUrl: 'https://news.naver.com',
        savedPath: 'news.naver.com/index.html',
        title: 'News',
        processedHtml: '<!DOCTYPE html><html><head><title>News</title></head><body><main><h1>Naver News</h1></main></body></html>',
        qa: { rawTextLength: 'Naver News'.length },
        classification: { shouldRunReplayValidation: true },
      }],
      apiArtifacts: {},
      sampleSize: 1,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));

    assert.equal(result.verificationWarnings.length, 0);
    assert.equal(jsonReport.pages[0].verificationUrl.endsWith('/news.naver.com'), true);
    assert.equal(jsonReport.pages[0].routeReached, true);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification classifies blocked external requests by replay importance', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-external-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'index.html'),
      [
        '<!DOCTYPE html><html><head><title>Replay</title>',
        '<link rel="preload" as="font" href="https://occ.a.nflxso.net/art/font.woff2" crossorigin>',
        '<script src="https://www.google.com/recaptcha/api.js"></script>',
        '<script src="https://www.netflix.com/log?event=impression"></script>',
        '</head><body><main><img src="https://assets.nflxext.com/ffe/siteui/acquisition/hero.jpg" alt="hero"><h1>Hello replay</h1></main></body></html>',
      ].join(''),
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'),
      '[]',
    );

    await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [{
        url: 'https://example.com',
        finalUrl: 'https://example.com',
        savedPath: 'index.html',
        title: 'Replay',
        processedHtml: '<!DOCTYPE html><html><head><title>Replay</title></head><body><main><h1>Hello replay</h1></main></body></html>',
        qa: { rawTextLength: 'Hello replay'.length },
        classification: { shouldRunReplayValidation: true },
      }],
      apiArtifacts: {},
      sampleSize: 1,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));

    assert.equal(jsonReport.externalRequests.length >= 3, true);
    assert.equal(jsonReport.externalRequestSummary['render-critical-asset'] >= 2, true);
    assert.equal(jsonReport.externalRequestSummary['anti-abuse'] >= 1, true);
    assert.equal(jsonReport.externalRequestSummary['non-critical-runtime'] >= 1, true);
    assert.equal(jsonReport.externalRequestDetails.some((entry) => entry.category === 'render-critical-asset' && entry.resourceHint === 'font'), true);
    assert.equal(jsonReport.externalRequestDetails.some((entry) => entry.category === 'anti-abuse'), true);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification records mock API hits per page rather than cumulatively', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-mock-delta-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'first.html'),
      '<!DOCTYPE html><html><head><title>First</title></head><body><main><h1>First</h1><script>fetch("/api/bootstrap");</script></main></body></html>',
    );
    await saveFile(
      path.join(tempRoot, 'views', 'second.html'),
      '<!DOCTYPE html><html><head><title>Second</title></head><body><main><h1>Second</h1></main></body></html>',
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'bootstrap.json'),
      JSON.stringify({ ok: true }),
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'),
      JSON.stringify([{
        method: 'GET',
        path: '/bootstrap',
        search: '',
        bodyHash: 'no-body',
        status: 200,
        responseMimeType: 'application/json',
        bodyFile: 'mocks/bootstrap.json',
      }], null, 2),
    );

    await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [
        {
          url: 'https://example.com/first',
          finalUrl: 'https://example.com/first',
          savedPath: 'first.html',
          title: 'First',
          processedHtml: '<!DOCTYPE html><html><head><title>First</title></head><body><main><h1>First</h1></main></body></html>',
          qa: { rawTextLength: 'First'.length },
          classification: { shouldRunReplayValidation: true },
        },
        {
          url: 'https://example.com/second',
          finalUrl: 'https://example.com/second',
          savedPath: 'second.html',
          title: 'Second',
          processedHtml: '<!DOCTYPE html><html><head><title>Second</title></head><body><main><h1>Second</h1></main></body></html>',
          qa: { rawTextLength: 'Second'.length },
          classification: { shouldRunReplayValidation: true },
        },
      ],
      apiArtifacts: {},
      sampleSize: 2,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));

    assert.equal(jsonReport.pages[0].mockApiHitsObserved >= 1, true);
    assert.equal(jsonReport.pages[1].mockApiHitsObserved, 0);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification explains render-critical requests that were not triggered or missed rewrite', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-render-critical-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'first.html'),
      '<!DOCTYPE html><html><head><title>First</title></head><body><main><h1>First</h1><script>fetch("https://example.com/bootstrap");</script></main></body></html>',
    );
    await saveFile(
      path.join(tempRoot, 'views', 'second.html'),
      '<!DOCTYPE html><html><head><title>Second</title></head><body><main><h1>Second</h1></main></body></html>',
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'),
      JSON.stringify([{
        method: 'GET',
        path: '/bootstrap',
        search: '',
        normalizedSearch: '',
        bodyHash: 'no-body',
        replayRole: 'render-critical',
        bodyFile: 'mocks/bootstrap.json',
      }], null, 2),
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'bootstrap.json'),
      JSON.stringify({ ok: true }),
    );

    await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [
        {
          url: 'https://example.com/first',
          finalUrl: 'https://example.com/first',
          savedPath: 'first.html',
          title: 'First',
          processedHtml: '<!DOCTYPE html><html><head><title>First</title></head><body><main><h1>First</h1></main></body></html>',
          qa: { rawTextLength: 'First'.length },
          classification: { shouldRunReplayValidation: true },
        },
        {
          url: 'https://example.com/second',
          finalUrl: 'https://example.com/second',
          savedPath: 'second.html',
          title: 'Second',
          processedHtml: '<!DOCTYPE html><html><head><title>Second</title></head><body><main><h1>Second</h1></main></body></html>',
          qa: { rawTextLength: 'Second'.length },
          classification: { shouldRunReplayValidation: true },
        },
      ],
      apiArtifacts: {
        httpManifest: [{
          method: 'GET',
          path: '/bootstrap',
          search: '',
          normalizedSearch: '',
          bodyHash: 'no-body',
          replayRole: 'render-critical',
          bodyFile: 'mocks/bootstrap.json',
        }],
        renderCriticalCandidates: [
          {
            pageUrl: 'https://example.com/first',
            normalizedPageUrl: 'https://example.com/first',
            url: 'https://example.com/bootstrap',
            method: 'GET',
            path: '/bootstrap',
            search: '',
            replayPath: '/api/bootstrap',
            renderCriticalKind: 'render-critical-bootstrap',
            operationName: null,
            variablesHash: 'no-body',
            documentHash: 'no-body',
            graphQL: false,
          },
          {
            pageUrl: 'https://example.com/second',
            normalizedPageUrl: 'https://example.com/second',
            url: 'https://example.com/bootstrap',
            method: 'GET',
            path: '/bootstrap',
            search: '',
            replayPath: '/api/bootstrap',
            renderCriticalKind: 'render-critical-bootstrap',
            operationName: null,
            variablesHash: 'no-body',
            documentHash: 'no-body',
            graphQL: false,
          },
        ],
      },
      sampleSize: 2,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));

    assert.equal(jsonReport.pages[0].renderCriticalCandidatesExpected.length, 1);
    assert.equal(jsonReport.pages[0].renderCriticalRequestsTriggered.length, 0);
    assert.equal(jsonReport.pages[0].renderCriticalRequestsMissed[0].reason, 'rewrite-missed');
    assert.equal(jsonReport.pages[1].renderCriticalRequestsMissed[0].reason, 'not-triggered');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification keeps supporting replay candidates informational instead of warning-producing', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-supporting-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'index.html'),
      '<!DOCTYPE html><html><head><title>Replay</title></head><body><main><h1>Hello replay</h1></main></body></html>',
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'),
      '[]',
    );

    const result = await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [{
        url: 'https://example.com',
        finalUrl: 'https://example.com',
        savedPath: 'index.html',
        title: 'Replay',
        qa: { rawTextLength: 'Hello replay'.length },
        classification: { shouldRunReplayValidation: true },
        bootstrapSignals: {
          hasInlineBootstrapState: true,
          hasFrameworkBootstrap: true,
          hasRenderableStateFallback: true,
          bootstrapEvidenceLevel: 'strong',
          bootstrapSignalCount: 3,
          frameworkKinds: ['next-pages-router'],
        },
      }],
      apiArtifacts: {
        renderCriticalCandidates: [{
          pageUrl: 'https://example.com',
          normalizedPageUrl: normalizeCrawlUrl('https://example.com'),
          url: 'https://example.com/graphql',
          method: 'POST',
          path: '/graphql',
          search: '',
          replayPath: '/api/graphql',
          renderCriticalKind: 'render-supporting-runtime',
          replayRole: 'render-supporting',
          expectedForReplay: false,
          firstPaintDependency: 'supporting',
          classificationReason: 'bootstrap-backed-state-refresh',
          dependencyEvidence: ['bootstrap:strong', 'graphql-state-refresh'],
          operationName: 'MembershipStatus',
          variablesHash: 'bf21a9e8fbc5',
          documentHash: 'no-body',
          graphQL: true,
        }],
      },
      sampleSize: 1,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));

    assert.equal(result.verificationWarnings.includes('index.html: render-critical-not-triggered'), false);
    assert.equal(jsonReport.pages[0].renderCriticalCandidatesExpected.length, 0);
    assert.equal(jsonReport.pages[0].renderSupportingCandidatesObserved.length, 1);
    assert.equal(jsonReport.pages[0].renderSupportingRequestsSkipped[0].reason, 'not-triggered');
    assert.equal(jsonReport.pages[0].renderSupportingRequestsSkipped[0].classificationReason, 'bootstrap-backed-state-refresh');
    assert.equal(jsonReport.pages[0].bootstrapEvidenceLevel, 'strong');
    assert.equal(jsonReport.pages[0].replayDataAssessment, 'bootstrap-backed-supporting-refresh-skipped');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification does not emit strict warnings when no expected replay candidates remain', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-no-strict-candidates-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'index.html'),
      '<!DOCTYPE html><html><head><title>Replay</title></head><body><main><h1>Hello replay</h1></main></body></html>',
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'),
      '[]',
    );

    const result = await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [{
        url: 'https://example.com',
        finalUrl: 'https://example.com',
        savedPath: 'index.html',
        title: 'Replay',
        qa: { rawTextLength: 'Hello replay'.length },
        classification: { shouldRunReplayValidation: true },
      }],
      apiArtifacts: {
        renderCriticalCandidates: [],
      },
      sampleSize: 1,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));

    assert.equal(result.verificationWarnings.includes('index.html: render-critical-not-triggered'), false);
    assert.equal(jsonReport.pages[0].renderCriticalCandidatesExpected.length, 0);
    assert.equal(jsonReport.pages[0].warnings.includes('render-critical-not-triggered'), false);
    assert.equal(jsonReport.pages[0].replayDataAssessment, 'html-shell-only');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification surfaces encoding diagnostics without turning them into false replay failures', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-encoding-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'index.html'),
      '<!DOCTYPE html><html><head><title>Replay</title></head><body><main><h1>Hello replay</h1></main></body></html>',
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'),
      '[]',
    );

    await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [{
        url: 'https://example.com',
        finalUrl: 'https://example.com',
        savedPath: 'index.html',
        title: 'Replay',
        qa: { rawTextLength: 'Hello replay'.length },
        classification: { shouldRunReplayValidation: true },
        encodingDiagnostics: {
          encoding: 'euc-kr',
          encodingSource: 'meta-charset',
          decodeConfidence: 'medium',
          suspectedEncodingMismatch: true,
          encodingEvidence: {
            headerEncoding: 'utf-8',
            metaCharsetEncoding: 'euc-kr',
          },
        },
      }],
      apiArtifacts: {
        renderCriticalCandidates: [],
      },
      sampleSize: 1,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));

    assert.equal(jsonReport.pages[0].encodingObserved, 'euc-kr');
    assert.equal(jsonReport.pages[0].decodeConfidence, 'medium');
    assert.equal(jsonReport.pages[0].encodingMismatchLikely, true);
    assert.equal(jsonReport.pages[0].warnings.includes('render-critical-not-triggered'), false);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification downgrades boilerplate-heavy comparisons into comparison noise when main content still overlaps', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-comparison-noise-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'index.html'),
      [
        '<!DOCTYPE html>',
        '<html><head><title>Portal Home</title><script src="/__front_clone_runtime_guard__.js" data-front-clone-guard="true"></script></head><body>',
        '<header><nav>민원 안내 구청 소개 참여 광장 알림 마당 개인정보 처리방침 이용약관 쿠키 설정 사이트맵</nav></header>',
        '<main><h1>Project Update Notice</h1><p>Important planning summary for residents and visitors.</p></main>',
        '<footer>개인정보 처리방침 이용약관 쿠키 설정 사이트맵 연락처</footer>',
        '</body></html>',
      ].join(''),
    );
    await saveFile(
      path.join(tempRoot, 'public', '__front_clone_runtime_guard__.js'),
      'window.__FRONT_CLONE_RUNTIME__ = { guardActive: true, exceptions: [], resourceErrors: [] };',
    );
    await saveFile(path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'), '[]');

    const expectedHtml = [
      '<!DOCTYPE html><html><head><title>Portal Home</title></head><body>',
      '<header><nav>민원 안내 구청 소개 참여 광장 알림 마당 개인정보 처리방침 이용약관 쿠키 설정 사이트맵 민원 안내 구청 소개 참여 광장 알림 마당 개인정보 처리방침 이용약관 쿠키 설정 사이트맵</nav></header>',
      '<main><h1>Project Update Notice</h1><p>Important planning summary for residents and visitors.</p></main>',
      '<footer>개인정보 처리방침 이용약관 쿠키 설정 사이트맵 연락처 개인정보 처리방침 이용약관 쿠키 설정 사이트맵 연락처</footer>',
      '</body></html>',
    ].join('');

    await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [{
        url: 'https://example.com',
        finalUrl: 'https://example.com',
        savedPath: 'index.html',
        title: 'Portal Home',
        processedHtml: expectedHtml,
        qa: { rawTextLength: 420 },
        classification: { shouldRunReplayValidation: true },
      }],
      apiArtifacts: {
        renderCriticalCandidates: [],
      },
      sampleSize: 1,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));
    const page = jsonReport.pages[0];

    assert.equal(page.contentDriftAssessment, 'comparison-noise-likely');
    assert.equal(page.contentComparisonConfidence, 'medium');
    assert.equal(page.boilerplateDominanceLikely, true);
    assert.equal(page.warnings.includes('comparison-noise-likely'), true);
    assert.equal(page.warnings.includes('content-drift'), false);
    assert.equal(page.markerExtractionProfile.overlap.main >= 0.5, true);
    assert.equal(page.markerExtractionProfile.sourcesUsed.includes('main-content'), true);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification treats mojibake-like title mismatches as low-confidence noise', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-title-noise-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'index.html'),
      '<!DOCTYPE html><html><head><title>醫낅줈援ъ껍</title><script src="/__front_clone_runtime_guard__.js" data-front-clone-guard="true"></script></head><body><main><h1>Hello replay</h1></main></body></html>',
    );
    await saveFile(
      path.join(tempRoot, 'public', '__front_clone_runtime_guard__.js'),
      'window.__FRONT_CLONE_RUNTIME__ = { guardActive: true, exceptions: [], resourceErrors: [] };',
    );
    await saveFile(path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'), '[]');

    await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [{
        url: 'https://example.com',
        finalUrl: 'https://example.com',
        savedPath: 'index.html',
        title: '醫낅줈援ъ껌',
        qa: { rawTextLength: 'Hello replay'.length },
        classification: { shouldRunReplayValidation: true },
      }],
      apiArtifacts: {
        renderCriticalCandidates: [],
      },
      sampleSize: 1,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));
    const page = jsonReport.pages[0];

    assert.equal(page.titleComparisonConfidence, 'low');
    assert.equal(page.titleMismatchLikelyEncodingNoise, true);
    assert.equal(page.warnings.includes('title-comparison-low-confidence'), true);
    assert.equal(page.warnings.includes('title-drift'), false);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification keeps strong title-drift warnings for meaningful title mismatches', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-title-drift-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'index.html'),
      '<!DOCTYPE html><html><head><title>Different Portal Title</title><script src="/__front_clone_runtime_guard__.js" data-front-clone-guard="true"></script></head><body><main><h1>Hello replay</h1></main></body></html>',
    );
    await saveFile(
      path.join(tempRoot, 'public', '__front_clone_runtime_guard__.js'),
      'window.__FRONT_CLONE_RUNTIME__ = { guardActive: true, exceptions: [], resourceErrors: [] };',
    );
    await saveFile(path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'), '[]');

    await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [{
        url: 'https://example.com',
        finalUrl: 'https://example.com',
        savedPath: 'index.html',
        title: 'Replay Title',
        qa: { rawTextLength: 'Hello replay'.length },
        classification: { shouldRunReplayValidation: true },
      }],
      apiArtifacts: {
        renderCriticalCandidates: [],
      },
      sampleSize: 1,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));
    const page = jsonReport.pages[0];

    assert.equal(page.titleComparisonConfidence, 'high');
    assert.equal(page.titleMismatchLikelyEncodingNoise, false);
    assert.equal(page.warnings.includes('title-drift'), true);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification captures runtime console errors, exceptions, and failed script loads', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-runtime-errors-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'index.html'),
      [
        '<!DOCTYPE html>',
        '<html><head><title>Replay</title><script src="/__front_clone_runtime_guard__.js" data-front-clone-guard="true"></script></head><body>',
        '<main><h1>Hello replay</h1></main>',
        '<script>console.error("Hydration exploded"); setTimeout(() => { throw new Error("Chunk bootstrap failed"); }, 0);</script>',
        '<script src="/missing-chunk.js"></script>',
        '</body></html>',
      ].join(''),
    );
    await saveFile(
      path.join(tempRoot, 'public', '__front_clone_runtime_guard__.js'),
      'window.__FRONT_CLONE_RUNTIME__ = { guardActive: true, exceptions: [], resourceErrors: [] };',
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'),
      '[]',
    );

    await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [{
        url: 'https://example.com',
        finalUrl: 'https://example.com',
        savedPath: 'index.html',
        title: 'Replay',
        qa: { rawTextLength: 'Hello replay'.length },
        classification: { shouldRunReplayValidation: true },
      }],
      apiArtifacts: {
        renderCriticalCandidates: [],
      },
      sampleSize: 1,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));
    const page = jsonReport.pages[0];

    assert.equal(page.runtimeConsoleErrors.length >= 1, true);
    assert.equal(page.runtimeExceptions.length >= 1, true);
    assert.equal(page.failedRuntimeRequests.some((entry) => entry.url.endsWith('/missing-chunk.js')), true);
    assert.equal(page.runtimeErrorSummary.consoleErrors >= 1, true);
    assert.equal(page.runtimeErrorSummary.runtimeExceptions >= 1, true);
    assert.equal(page.runtimeErrorSummary.failedRuntimeRequests >= 1, true);
    assert.equal(page.warnings.includes('runtime-console-error'), true);
    assert.equal(page.warnings.includes('runtime-exception'), true);
    assert.equal(page.warnings.includes('runtime-script-failed'), true);
    assert.equal(page.runtimeGuardObserved, true);
    assert.equal(page.runtimeFailureClasses['runtime-script-failed'] >= 1, true);
    assert.equal(page.runtimeFailureAssessment, 'runtime-script-degraded');
    assert.equal(page.runtimeFailureSeverity, 'high');
    assert.equal(page.runtimeFailureScope, 'page');
    assert.equal(jsonReport.runtimeErrorSummary.pagesWithRuntimeErrors, 1);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('runReplayVerification classifies same-origin DOM assumptions and soft resource misses separately', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-verify-runtime-soft-miss-'));
  try {
    await ensureDir(path.join(tempRoot, 'views'));
    await ensureDir(path.join(tempRoot, 'public'));
    await ensureDir(path.join(tempRoot, 'server', 'mocks'));
    await saveFile(
      path.join(tempRoot, 'views', 'index.html'),
      [
        '<!DOCTYPE html>',
        '<html><head><title>Replay</title><script src="/__front_clone_runtime_guard__.js" data-front-clone-guard="true"></script></head><body>',
        '<main><h1>Hello replay</h1></main>',
        '<script>window.addEventListener("DOMContentLoaded", () => { document.querySelector("#missing").src = "/fallback.png"; fetch("/missing-file.txt"); });</script>',
        '<script>fetch("/missing-file.txt");</script>',
        '</body></html>',
      ].join(''),
    );
    await saveFile(
      path.join(tempRoot, 'public', '__front_clone_runtime_guard__.js'),
      [
        'window.__FRONT_CLONE_RUNTIME__ = {',
        '  guardActive: true,',
        '  exceptions: [],',
        '  resourceErrors: []',
        '};',
        'window.addEventListener("error", (event) => {',
        '  const target = event.target;',
        '  if (target && target !== window) {',
        '    window.__FRONT_CLONE_RUNTIME__.resourceErrors.push({',
        '      url: target.src || target.href || "",',
        '      sameOrigin: true,',
        '      resourceType: "resource",',
        '      failureClass: "runtime-resource-missing"',
        '    });',
        '    return;',
        '  }',
        '  window.__FRONT_CLONE_RUNTIME__.exceptions.push({',
        '    name: event.error?.name || "Error",',
        '    message: event.error?.message || event.message || "runtime error",',
        '    source: "window-error",',
        '    sameOrigin: true,',
        '    failureClass: "runtime-dom-assumption"',
        '  });',
        '});',
        'const originalAddEventListener = EventTarget.prototype.addEventListener;',
        'EventTarget.prototype.addEventListener = function (type, listener, options) {',
        '  if (typeof listener !== "function") return originalAddEventListener.call(this, type, listener, options);',
        '  return originalAddEventListener.call(this, type, function (...args) {',
        '    try { return listener.apply(this, args); } catch (error) {',
        '      window.__FRONT_CLONE_RUNTIME__.exceptions.push({',
        '        name: error?.name || "Error",',
        '        message: error?.message || String(error),',
        '        source: "event:" + type,',
        '        sameOrigin: true,',
        '        failureClass: "runtime-dom-assumption"',
        '      });',
        '      return undefined;',
        '    }',
        '  }, options);',
        '};',
      ].join('\n'),
    );
    await saveFile(
      path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'),
      '[]',
    );

    await runReplayVerification({
      outputDir: tempRoot,
      startUrl: 'https://example.com',
      pages: [{
        url: 'https://example.com',
        finalUrl: 'https://example.com',
        savedPath: 'index.html',
        title: 'Replay',
        qa: { rawTextLength: 'Hello replay'.length },
        classification: { shouldRunReplayValidation: true },
      }],
      apiArtifacts: {
        renderCriticalCandidates: [],
      },
      sampleSize: 1,
    });

    const jsonReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'replay-verification.json'), 'utf-8'));
    const page = jsonReport.pages[0];

    assert.equal(page.runtimeGuardObserved, true);
    assert.equal(page.runtimeFailureClasses['runtime-dom-assumption'] >= 1, true);
    // fetch 404s are now classified as runtime-data-miss (finer than runtime-resource-missing)
    assert.equal(page.runtimeFailureClasses['runtime-data-miss'] >= 1, true);
    assert.equal(page.sameOriginRuntimeMisses.some((entry) => entry.failureClass === 'runtime-data-miss'), true);
    assert.equal(page.warnings.includes('runtime-script-failed'), false);
    assert.equal(page.warnings.includes('runtime-exception'), false);
    // When content matches and shell is intact, soft-fail goes to notes instead of warnings
    assert.equal((page.notes || []).includes('runtime-widget-soft-fail'), true);
    assert.equal(page.runtimeFailureAssessment, 'runtime-widget-soft-fail');
    assert.equal(page.runtimeFailureSeverity, 'soft');
    assert.equal(page.runtimeFailureScope, 'widget');
    assert.equal(page.suspectedFailureChain, 'data-or-asset-led-dom-assumption');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
