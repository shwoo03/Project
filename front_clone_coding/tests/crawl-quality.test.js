import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';

import AssetDownloader from '../src/downloader/asset-downloader.js';
import {
  buildOutputFinalizeError,
  dedupeCapturedPages,
  isRetriableFilesystemConflict,
  withFilesystemRetry,
} from '../src/index.js';
import { classifyPageSnapshot } from '../src/utils/crawl-config.js';
import { classifyExternalRuntime } from '../src/utils/external-runtime-utils.js';
import { getViewPathFromUrl, normalizeCrawlUrl } from '../src/utils/url-utils.js';
import {
  enrichLinkCandidate,
  prioritizeFrontierCandidates,
  scoreLinkCandidate,
} from '../src/utils/frontier-utils.js';
import { writeManifest } from '../src/utils/manifest-writer.js';

test('classifyPageSnapshot marks route-heavy pages for representative QA', () => {
  const classification = classifyPageSnapshot({
    routeCount: 3,
    scriptCount: 10,
    liveImageUrls: new Array(4).fill('https://example.com/image.png'),
    forms: [],
    interactiveElements: new Array(12).fill({}),
  }, 'https://example.com/app', {
    crawlProfile: 'accurate',
    enableRepresentativeQA: true,
    takeScreenshot: false,
  });

  assert.equal(classification.pageClass, 'spa-route-heavy');
  assert.equal(classification.shouldRunReplayValidation, true);
  assert.equal(classification.queueBudget >= 30, true);
  assert.equal(classification.flags.includes('spa-routes'), true);
});

test('AssetDownloader records browser-lane resource metadata', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-assets-'));
  try {
    const downloader = new AssetDownloader(tempRoot, 'https://example.com');
    const interceptor = {
      getAssets() {
        return new Map([
          ['stylesheet https://example.com/app.css', {
            url: 'https://example.com/app.css',
            mimeType: 'text/css',
            type: 'stylesheet',
            body: Buffer.from('body { color: red; }'),
            bodyLength: 20,
            status: 200,
            pageUrl: 'https://example.com',
          }],
        ]);
      },
    };

    const urlMap = await downloader.downloadAll(interceptor);
    const resources = downloader.getResourceManifestEntries();

    assert.equal(urlMap.get('https://example.com/app.css').endsWith('.css'), true);
    assert.deepEqual(resources[0], {
      url: 'https://example.com/app.css',
      savedPath: urlMap.get('https://example.com/app.css'),
      mimeType: 'text/css',
      contentType: '',
      resourceType: 'stylesheet',
      captureLane: 'browser',
      status: 200,
      size: 20,
      pageUrl: 'https://example.com',
      resourceClass: 'critical-render',
      replayCriticality: 'high',
      encoding: null,
      encodingSource: 'unknown',
      decodeConfidence: 'low',
      suspectedEncodingMismatch: false,
      encodingEvidence: {},
    });
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('writeManifest emits crawl profile and page quality reports', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-manifest-'));
  try {
    await writeManifest(tempRoot, {
      generatedAt: '2026-03-23T00:00:00.000Z',
      startUrl: 'https://example.com',
      domainRoot: 'example.com',
      pages: [{
        url: 'https://example.com',
        finalUrl: 'https://example.com',
        savedPath: 'index.html',
        replayRoute: '/',
        replayable: true,
        linksSelected: 4,
        crawlState: 'completed',
        bootstrapSignals: {
          hasInlineBootstrapState: true,
          hasFrameworkBootstrap: true,
          hasStreamingHydrationHints: false,
          hasRenderableStateFallback: true,
          bootstrapEvidenceLevel: 'strong',
          bootstrapSignalCount: 3,
          frameworkKinds: ['next-pages-router'],
        },
        encodingSource: 'content-type',
        decodeConfidence: 'medium',
        suspectedEncodingMismatch: true,
        hiddenNavigationSummary: {
          localizedHiddenNavigationCount: 2,
          disabledHiddenNavigationCount: 1,
          nonReplayableTargetCount: 1,
          localizedHiddenNavigationClasses: {
            'page-route': 1,
            'value-driven-navigation': 1,
          },
          disabledHiddenNavigationClasses: {
            'uncloned-target': 1,
          },
        },
      }],
      assets: [{ url: 'https://example.com/app.css', savedPath: 'css/app.css' }],
      pageQualityReport: [{ pageUrl: 'https://example.com', textDriftRatio: 0.02 }],
      cssRecoverySummary: {
        cssAssetsDiscovered: 3,
        cssAssetsRecovered: 2,
        cssAssetsFailed: 1,
        cssAssetsSkipped: 0,
        cssAssetCanonicalizationApplied: 1,
        cssAssetFailureReasons: {
          timeout: 1,
        },
        pages: [{
          pageUrl: 'https://example.com',
          cssAssetsDiscovered: 3,
          cssAssetsRecovered: 2,
          cssAssetsFailed: 1,
          cssAssetsSkipped: 0,
          missingCriticalCssAssets: 1,
          cssRecoveryWarnings: ['timeout'],
          cssRecoveryStatus: 'missing-critical-assets',
        }],
      },
      crawlProfile: { name: 'accurate', networkPosture: 'default' },
      pageRoutes: {
        entryPagePath: 'index.html',
        entryReplayRoute: '/',
        routes: [{
          pageUrl: 'https://example.com',
          finalUrl: 'https://example.com',
          normalizedUrl: 'https://example.com',
          savedPath: 'index.html',
          replayRoute: '/',
          routeAliases: ['/index.html'],
          replayable: true,
        }],
      },
    });

    const resourceManifest = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'resource-manifest.json'), 'utf8'));
    const pageQuality = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'page-quality-report.json'), 'utf8'));
    const crawlProfile = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'crawl-profile.json'), 'utf8'));
    const crawlReport = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'docs', 'crawl', 'crawl-report.json'), 'utf8'));
    const pageRouteManifest = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'page-route-manifest.json'), 'utf8'));
    const bootstrapSummary = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'bootstrap-summary.json'), 'utf8'));
    const cssRecoverySummary = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'css-recovery-summary.json'), 'utf8'));

    assert.equal(resourceManifest.length, 1);
    assert.equal(pageQuality[0].pageUrl, 'https://example.com');
    assert.equal(crawlProfile.name, 'accurate');
    assert.equal(crawlReport.counts.linksSelected, 4);
    assert.equal(crawlReport.counts.pagesCompleted, 1);
    assert.equal(crawlReport.counts.pagesSaved, 1);
    assert.equal(crawlReport.counts.pagesReplayable, 1);
    assert.equal(crawlReport.counts.localizedHiddenNavigationCount, 2);
    assert.equal(crawlReport.counts.disabledHiddenNavigationCount, 1);
    assert.equal(crawlReport.counts.nonReplayableTargetCount, 1);
    assert.equal(crawlReport.counts.pagesWithSuspectedEncodingMismatch, 1);
    assert.equal(crawlReport.counts.pagesWithLowDecodeConfidence, 0);
    assert.equal(crawlReport.counts.cssAssetsDiscovered, 3);
    assert.equal(crawlReport.counts.cssAssetsRecovered, 2);
    assert.equal(crawlReport.counts.cssAssetsFailed, 1);
    assert.equal(crawlReport.counts.cssAssetCanonicalizationApplied, 1);
    assert.equal(pageRouteManifest.routes[0].replayRoute, '/');
    assert.equal(bootstrapSummary.counts.pagesWithFrameworkBootstrap, 1);
    assert.equal(bootstrapSummary.pages[0].bootstrapSignals.bootstrapEvidenceLevel, 'strong');
    assert.equal(cssRecoverySummary.cssAssetFailureReasons.timeout, 1);
    assert.equal(cssRecoverySummary.pages[0].cssRecoveryStatus, 'missing-critical-assets');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('getViewPathFromUrl can isolate recursive multi-host roots with host prefixes', () => {
  assert.equal(
    getViewPathFromUrl('https://www.naver.com/', { includeHostPrefix: true }),
    'www.naver.com/index.html',
  );
  assert.equal(
    getViewPathFromUrl('https://news.naver.com/', { includeHostPrefix: true }),
    'news.naver.com/index.html',
  );
  assert.equal(
    getViewPathFromUrl('https://news.naver.com/article/123', { includeHostPrefix: true }),
    'news.naver.com/article/123.html',
  );
});

test('withFilesystemRetry retries bounded filesystem lock conflicts before succeeding', async () => {
  let attempts = 0;
  const result = await withFilesystemRetry(async () => {
    attempts += 1;
    if (attempts < 3) {
      const error = new Error('busy');
      error.code = 'EBUSY';
      throw error;
    }
    return 'ok';
  }, {
    operation: 'move staging output into place',
    targetPath: 'C:/output/example.com',
  });

  assert.equal(result, 'ok');
  assert.equal(attempts, 3);
});

test('withFilesystemRetry surfaces structured lock guidance after exhausting retries', async () => {
  await assert.rejects(
    withFilesystemRetry(async () => {
      const error = new Error('permission denied');
      error.code = 'EPERM';
      throw error;
    }, {
      operation: 'replace output entry views',
      targetPath: 'C:/output/example.com/views',
    }),
    (error) => {
      assert.equal(error.code, 'OUTPUT_FINALIZE_LOCKED');
      assert.match(error.message, /replace output entry views/);
      assert.match(error.details, /C:\/output\/example\.com\/views/);
      assert.match(error.details, /EPERM/);
      assert.match(error.hint, /OneDrive sync lock|replay server|file explorer/i);
      return true;
    },
  );
});

test('buildOutputFinalizeError preserves non-retriable filesystem failure context', () => {
  const original = new Error('access denied');
  original.code = 'EACCES';
  const wrapped = buildOutputFinalizeError(original, {
    operation: 'remove output directory',
    targetPath: 'C:/output/example.com',
  });

  assert.equal(isRetriableFilesystemConflict(original), true);
  assert.equal(wrapped.code, 'OUTPUT_FINALIZE_LOCKED');
  assert.match(wrapped.message, /remove output directory/);
  assert.match(wrapped.details, /C:\/output\/example\.com/);
  assert.match(wrapped.details, /EACCES/);
  assert.match(wrapped.details, /access denied/);
  assert.equal(wrapped.cause, original);
});

test('frontier prioritization prefers same-host main content over help and footer links', () => {
  const candidates = [
    enrichLinkCandidate({
      url: 'https://www.naver.com/shopping',
      sourceKind: 'anchor',
      anchorText: 'Shopping',
      domOrder: 2,
      landmark: 'main',
      rel: '',
      isHashOnly: false,
      discoveredFromPageClass: 'document',
    }, {
      startUrl: 'https://www.naver.com/',
      currentPageUrl: 'https://www.naver.com/',
      domainScope: 'registrable-domain',
    }),
    enrichLinkCandidate({
      url: 'https://help.naver.com/service/5627/contents/9148?lang=ko&osType=COMMONOS',
      sourceKind: 'anchor',
      anchorText: 'Help',
      domOrder: 1,
      landmark: 'footer',
      rel: '',
      isHashOnly: false,
      discoveredFromPageClass: 'document',
    }, {
      startUrl: 'https://www.naver.com/',
      currentPageUrl: 'https://www.naver.com/',
      domainScope: 'registrable-domain',
    }),
    enrichLinkCandidate({
      url: 'https://www.naver.com/privacy',
      sourceKind: 'anchor',
      anchorText: 'Privacy',
      domOrder: 3,
      landmark: 'footer',
      rel: '',
      isHashOnly: false,
      discoveredFromPageClass: 'document',
    }, {
      startUrl: 'https://www.naver.com/',
      currentPageUrl: 'https://www.naver.com/',
      domainScope: 'registrable-domain',
    }),
  ].filter(Boolean);

  const prioritized = prioritizeFrontierCandidates(candidates, {
    startUrl: 'https://www.naver.com/',
    currentPageUrl: 'https://www.naver.com/',
    nextDepth: 1,
    queueBudget: 2,
    domainScope: 'registrable-domain',
  });

  assert.equal(prioritized.selectedCandidates[0].normalizedUrl, 'https://www.naver.com/shopping');
  assert.equal(prioritized.selectedCandidates.filter((candidate) => ['utility', 'docs'].includes(candidate.familyKey)).length, 1);
  assert.equal(prioritized.topCandidates[0].normalizedUrl, 'https://www.naver.com/shopping');
});

test('frontier prioritization limits query-heavy variants in the same path family', () => {
  const candidates = [
    'https://example.com/search?q=one&utm_source=newsletter',
    'https://example.com/search?q=two&utm_source=ad',
    'https://example.com/search?q=three&utm_source=social',
    'https://example.com/pricing',
  ].map((url, index) => enrichLinkCandidate({
    url,
    sourceKind: 'anchor',
    anchorText: index === 3 ? 'Pricing' : 'Search',
    domOrder: index,
    landmark: index === 3 ? 'main' : 'nav',
    rel: '',
    isHashOnly: false,
    discoveredFromPageClass: 'document',
  }, {
    startUrl: 'https://example.com/',
    currentPageUrl: 'https://example.com/',
    domainScope: 'registrable-domain',
  })).filter(Boolean);

  const prioritized = prioritizeFrontierCandidates(candidates, {
    startUrl: 'https://example.com/',
    currentPageUrl: 'https://example.com/',
    nextDepth: 1,
    queueBudget: 3,
    domainScope: 'registrable-domain',
  });

  const queryVariants = prioritized.selectedCandidates.filter((candidate) => candidate.pathname === '/search');
  assert.equal(queryVariants.length, 1);
  assert.equal(prioritized.selectedCandidates[0].normalizedUrl, 'https://example.com/pricing');
});

test('frontier scoring relaxes docs penalties inside docs or help contexts', () => {
  const docsCandidate = enrichLinkCandidate({
    url: 'https://docs.example.com/guide/getting-started',
    sourceKind: 'anchor',
    anchorText: 'Getting started',
    domOrder: 0,
    landmark: 'main',
    rel: '',
    isHashOnly: false,
    discoveredFromPageClass: 'document',
  }, {
    startUrl: 'https://docs.example.com/',
    currentPageUrl: 'https://docs.example.com/reference',
    domainScope: 'registrable-domain',
  });

  const nonDocsScore = scoreLinkCandidate(docsCandidate, {
    currentPageUrl: 'https://example.com/',
    nextDepth: 1,
  });
  const docsScore = scoreLinkCandidate(docsCandidate, {
    currentPageUrl: 'https://docs.example.com/reference',
    nextDepth: 1,
  });

  assert.equal(docsScore.score > nonDocsScore.score, true);
});

test('AssetDownloader can recover failed critical assets into a recovery lane', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-recovery-'));
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (_url) => ({
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': 'image/png' }),
    async arrayBuffer() {
      return Uint8Array.from([137, 80, 78, 71]).buffer;
    },
  });

  try {
    const downloader = new AssetDownloader(tempRoot, 'https://www.naver.com/');
    const result = await downloader.recoverFailedAssets([{
      url: 'https://www.naver.com/static/logo.png',
      method: 'GET',
      resourceType: 'image',
      pageUrl: 'https://www.naver.com/',
      errorText: 'net::ERR_ABORTED',
    }]);

    const entries = downloader.getResourceManifestEntries();
    assert.equal(result.recovered, 1);
    assert.equal(entries[0].captureLane, 'recovery');
    assert.equal(entries[0].savedPath.endsWith('logo.png'), true);
  } finally {
    globalThis.fetch = originalFetch;
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('dedupeCapturedPages collapses trailing-slash canonical variants into one saved path', () => {
  const result = dedupeCapturedPages([
    {
      url: 'https://www.netflix.com/',
      finalUrl: 'https://www.netflix.com/kr-en/',
      html: '<html></html>',
      title: 'Netflix',
      linkCandidates: [],
      captureWarnings: [],
      graphqlArtifacts: [],
      qa: { rawTextLength: 10, observedResources: 1 },
    },
    {
      url: 'https://www.netflix.com/kr-en',
      finalUrl: 'https://www.netflix.com/kr-en',
      html: '<html></html>',
      title: 'Netflix',
      linkCandidates: [{ url: 'https://www.netflix.com/browse', sourceKind: 'anchor', domOrder: 1 }],
      captureWarnings: ['redirected'],
      graphqlArtifacts: [],
      qa: { rawTextLength: 12, observedResources: 2 },
    },
  ], [
    {
      url: 'https://www.netflix.com/',
      finalUrl: 'https://www.netflix.com/kr-en/',
      normalizedUrl: 'https://www.netflix.com/kr-en',
      depth: 0,
      status: 200,
      crawlState: 'completed',
    },
    {
      url: 'https://www.netflix.com/kr-en',
      finalUrl: 'https://www.netflix.com/kr-en',
      normalizedUrl: 'https://www.netflix.com/kr-en',
      depth: 1,
      status: 200,
      crawlState: 'completed',
    },
  ], { includeHostPrefix: true });

  assert.equal(result.pages.length, 1);
  assert.equal(result.pages[0].savedPath, 'www.netflix.com/kr-en/index.html');
  assert.equal(result.pageUrlMap.get('https://www.netflix.com/'), 'www.netflix.com/kr-en/index.html');
  assert.equal(result.pageUrlMap.get('https://www.netflix.com/kr-en'), 'www.netflix.com/kr-en/index.html');
  assert.equal(result.siteMap.length, 1);
});

test('dedupeCapturedPages isolates query-addressed pages when the same host and pathname diverge by normalized query', () => {
  const result = dedupeCapturedPages([
    {
      url: 'https://www.example.com/Main.do?menuNo=1003&utm_source=nav',
      finalUrl: 'https://www.example.com/Main.do?menuNo=1003&utm_source=nav',
      html: '<html></html>',
      title: 'One',
      linkCandidates: [],
      captureWarnings: [],
      graphqlArtifacts: [],
      qa: { rawTextLength: 10, observedResources: 1 },
    },
    {
      url: 'https://www.example.com/Main.do?menuNo=1200',
      finalUrl: 'https://www.example.com/Main.do?menuNo=1200',
      html: '<html></html>',
      title: 'Two',
      linkCandidates: [],
      captureWarnings: [],
      graphqlArtifacts: [],
      qa: { rawTextLength: 12, observedResources: 2 },
    },
  ], [
    {
      url: 'https://www.example.com/Main.do?menuNo=1003&utm_source=nav',
      finalUrl: 'https://www.example.com/Main.do?menuNo=1003&utm_source=nav',
      normalizedUrl: 'https://www.example.com/Main.do?menuNo=1003&utm_source=nav',
      depth: 0,
      status: 200,
      crawlState: 'completed',
    },
    {
      url: 'https://www.example.com/Main.do?menuNo=1200',
      finalUrl: 'https://www.example.com/Main.do?menuNo=1200',
      normalizedUrl: 'https://www.example.com/Main.do?menuNo=1200',
      depth: 1,
      status: 200,
      crawlState: 'completed',
    },
  ], { includeHostPrefix: true });

  assert.equal(result.pages.length, 2);
  assert.notEqual(result.pages[0].savedPath, result.pages[1].savedPath);
  assert.match(result.pages[0].savedPath, /Main\.do__q_menuNo-1003\.html/);
  assert.match(result.pages[1].savedPath, /Main\.do__q_menuNo-1200\.html/);
  assert.equal(result.pages.every((page) => page.replayRoute.startsWith('/www.example.com/Main.do__q_')), true);
});

test('AssetDownloader can recover external render-critical assets from owned cdn hosts', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-owned-recovery-'));
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': 'font/woff2' }),
    async arrayBuffer() {
      return Uint8Array.from([1, 2, 3, 4]).buffer;
    },
  });

  try {
    const downloader = new AssetDownloader(tempRoot, 'https://www.netflix.com/');
    const result = await downloader.recoverFailedAssets([{
      url: 'https://occ.a.nflxso.net/art/12345/font.woff2',
      method: 'GET',
      resourceType: 'font',
      pageUrl: 'https://www.netflix.com/kr-en/',
      errorText: 'net::ERR_ABORTED',
    }]);

    const entries = downloader.getResourceManifestEntries();
    assert.equal(result.recovered, 1);
    assert.equal(entries[0].captureLane, 'recovery');
    assert.equal(entries[0].savedPath.includes('/external/'), true);
    assert.equal(entries[0].savedPath.endsWith('.woff2'), true);
  } finally {
    globalThis.fetch = originalFetch;
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('classifyExternalRuntime separates anti-abuse, non-critical, render-critical runtime, and assets', () => {
  assert.deepEqual(
    classifyExternalRuntime('https://www.google.com/recaptcha/api.js'),
    { category: 'anti-abuse', resourceHint: 'script' },
  );
  assert.deepEqual(
    classifyExternalRuntime('https://logs.netflix.com/log/www/cl/2'),
    { category: 'non-critical-runtime', resourceHint: 'request' },
  );
  assert.deepEqual(
    classifyExternalRuntime('https://web.prod.cloud.netflix.com/graphql'),
    { category: 'render-critical-runtime', resourceHint: 'request' },
  );
  assert.deepEqual(
    classifyExternalRuntime('https://assets.nflxext.com/hero.jpg'),
    { category: 'render-critical-asset', resourceHint: 'image' },
  );
});

test('classifyExternalRuntime keeps same-site logging non-critical while same-site bootstrap stays render-critical', () => {
  assert.deepEqual(
    classifyExternalRuntime('https://www.netflix.com/log/www/cl/2', { targetUrl: 'https://www.netflix.com/kr-en/' }),
    { category: 'non-critical-runtime', resourceHint: 'request' },
  );
  assert.deepEqual(
    classifyExternalRuntime('https://www.netflix.com/bootstrap/runtime-data', { targetUrl: 'https://www.netflix.com/kr-en/' }),
    { category: 'render-critical-runtime', resourceHint: 'request' },
  );
});

test('normalizeCrawlUrl removes tracking query params and sorts remaining', () => {
  const withTracking = normalizeCrawlUrl('https://example.com/Main.do?menuNo=1003&utm_source=nav');
  const withoutTracking = normalizeCrawlUrl('https://example.com/Main.do?menuNo=1003');
  assert.equal(withTracking, withoutTracking);
});

test('normalizeCrawlUrl normalizes query parameter order', () => {
  const orderA = normalizeCrawlUrl('https://example.com/page?b=2&a=1');
  const orderB = normalizeCrawlUrl('https://example.com/page?a=1&b=2');
  assert.equal(orderA, orderB);
});
