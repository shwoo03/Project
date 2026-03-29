import crypto from 'crypto';
import fs from 'fs/promises';
import net from 'net';
import path from 'path';

import express from 'express';
import { chromium } from 'playwright';

import { cloneFrontend, getOutputDomainRoot } from '../index.js';
import { ensureDir, pathExists, saveFile } from '../utils/file-utils.js';

export const NETFLIX_PUBLIC_START_URL = 'https://www.netflix.com/';
export const NETFLIX_PUBLIC_EVAL_OPTIONS = Object.freeze({
  waitTime: 5000,
  viewport: '1440x900',
  screenshot: true,
  scrollCount: 4,
  recursive: true,
  maxPages: 6,
  maxDepth: 1,
  concurrency: 1,
  followLoginGated: false,
  crawlProfile: 'balanced',
  networkPosture: 'sensitive-site',
  enableRepresentativeQA: true,
  headful: false,
  scaffold: true,
  domainScope: 'registrable-domain',
  resumeManifest: null,
  updateExisting: false,
  visualAnalysis: 'docs',
});

const DEFAULT_VIEWPORT = { width: 1440, height: 900 };
const MARKER_LIMIT = 24;
const LINK_LIMIT = 3;
const NETFLIX_KEY_PHRASES = [
  'netflix',
  'sign in',
  'get started',
  'faq',
  'questions',
  'email address',
];

export async function runNetflixPublicSiteEvaluation(options = {}) {
  const startUrl = options.startUrl || NETFLIX_PUBLIC_START_URL;
  const outputDir = options.outputDir || path.resolve('output', getOutputDomainRoot(startUrl));
  let cloneResult = {
    outputDir,
    entryPagePath: null,
  };

  if (!options.skipClone) {
    const cloneOptions = {
      ...NETFLIX_PUBLIC_EVAL_OPTIONS,
      ...options,
      url: startUrl,
    };
    cloneResult = await cloneFrontend(cloneOptions);
  }

  const docsDir = path.join(outputDir, 'server', 'docs');
  const specDir = path.join(outputDir, 'server', 'spec');
  await ensureDir(docsDir);
  await ensureDir(specDir);

  const crawlManifest = await readJson(path.join(outputDir, 'server', 'spec', 'manifest', 'crawl-manifest.json'), {});
  const entryPath = cloneResult.entryPagePath || inferEntryPath(startUrl, crawlManifest) || 'index.html';
  const artifactSummary = await loadArtifactSummary(outputDir);
  const replayRuntime = await startReplayServerFromOutput(outputDir, options.localPort || 3300);
  const browser = await chromium.launch({ headless: true });

  try {
    const liveProfile = await capturePageProfile(browser, startUrl, {
      label: 'live',
      screenshotPath: path.join(docsDir, 'netflix-public-live.png'),
    });
    const localEntryUrl = buildLocalReplayUrl(replayRuntime.port, entryPath);
    const localProfile = await capturePageProfile(browser, localEntryUrl, {
      label: 'local',
      blockExternalToOrigin: replayRuntime.origin,
      screenshotPath: path.join(docsDir, 'netflix-public-replay.png'),
    });
    const localNavigation = await inspectLocalReplayNavigation(browser, localEntryUrl, replayRuntime.origin);

    const report = buildNetflixPublicEvaluationReport({
      startUrl,
      outputDir,
      entryPath,
      liveProfile,
      localProfile,
      localNavigation,
      artifactSummary,
    });

    await saveFile(
      path.join(specDir, 'netflix-public-evaluation.json'),
      JSON.stringify(report, null, 2),
    );
    await saveFile(
      path.join(docsDir, 'netflix-public-evaluation.md'),
      renderNetflixPublicEvaluationMarkdown(report),
    );

    return {
      ...report,
      artifacts: {
        json: 'server/spec/netflix-public-evaluation.json',
        markdown: 'server/docs/netflix-public-evaluation.md',
        liveScreenshot: 'server/docs/netflix-public-live.png',
        replayScreenshot: 'server/docs/netflix-public-replay.png',
      },
    };
  } finally {
    await browser.close().catch(() => {});
    await replayRuntime.close().catch(() => {});
  }
}

export async function loadArtifactSummary(outputDir) {
  const crawlManifest = await readJson(path.join(outputDir, 'server', 'spec', 'manifest', 'crawl-manifest.json'), {});
  const resourceManifest = await readJson(path.join(outputDir, 'server', 'spec', 'resource-manifest.json'), []);
  const pageQualityReport = await readJson(path.join(outputDir, 'server', 'spec', 'page-quality-report.json'), []);
  const replayVerification = await readJson(path.join(outputDir, 'server', 'spec', 'replay-verification.json'), {});
  const missingBehaviors = await readText(path.join(outputDir, 'server', 'docs', 'missing-behaviors.md'), '');

  return summarizeCapturedArtifacts({
    crawlManifest,
    resourceManifest,
    pageQualityReport,
    replayVerification,
    missingBehaviors,
  });
}

export function summarizeCapturedArtifacts({
  crawlManifest = {},
  resourceManifest = [],
  pageQualityReport = [],
  replayVerification = {},
  missingBehaviors = '',
}) {
  const pages = Array.isArray(crawlManifest.pages) ? crawlManifest.pages : [];
  const criticalAssets = resourceManifest.filter((item) => item.replayCriticality === 'high');
  const missingBehaviorItems = String(missingBehaviors)
    .split(/\r?\n/)
    .filter((line) => line.trim().startsWith('- '))
    .map((line) => line.replace(/^- /, '').trim());

  return {
    capturedPages: pages.length,
    skippedPages: pages.filter((page) => page.skippedReason).length,
    loginGatedPages: pages.filter((page) => page.loginGated).length,
    representativePages: Array.isArray(replayVerification.pages) ? replayVerification.pages.length : 0,
    criticalAssetCount: criticalAssets.length,
    criticalAssetSavedCount: criticalAssets.filter((item) => Boolean(item.savedPath)).length,
    highTextDriftPages: pageQualityReport
      .filter((page) => typeof page.textDriftRatio === 'number' && page.textDriftRatio > 0.35)
      .map((page) => ({
        pageUrl: page.pageUrl,
        savedPath: page.savedPath,
        textDriftRatio: page.textDriftRatio,
      })),
    replayMissingCriticalAssets: replayVerification.missingCriticalAssets || [],
    replayExternalRequests: replayVerification.externalRequests || [],
    replayWarnings: collectReplayWarnings(replayVerification),
    missingBehaviors: missingBehaviorItems,
  };
}

export function buildNetflixPublicEvaluationReport({
  startUrl,
  outputDir,
  entryPath,
  liveProfile,
  localProfile,
  localNavigation,
  artifactSummary,
}) {
  const markerParity = compareTextMarkers(liveProfile.keyMarkers, localProfile.keyMarkers);
  const keyPhraseCoverage = compareTextMarkers(
    NETFLIX_KEY_PHRASES,
    localProfile.keyMarkers,
  );

  const risks = [];
  if (artifactSummary.replayExternalRequests.length > 0 || localProfile.externalRequests.length > 0) {
    risks.push('Replay still attempts external requests on the public landing surface.');
  }
  if (artifactSummary.replayMissingCriticalAssets.length > 0 || localProfile.network.failedCount > 0) {
    risks.push('Critical assets or page requests are missing in the local replay.');
  }
  if (artifactSummary.highTextDriftPages.length > 0) {
    risks.push('Some captured pages show elevated text drift versus the original snapshot.');
  }
  if (localNavigation.blockedLinkCount > 0) {
    risks.push('Some visible public links remain intentionally disabled because they were not cloned.');
  }
  if (localProfile.consoleErrors.length > 0) {
    risks.push('The local replay still emits console errors on first load.');
  }

  return {
    generatedAt: new Date().toISOString(),
    startUrl,
    outputDir,
    entryPath,
    captureSummary: artifactSummary,
    visualParity: {
      overlapRatio: markerParity.overlapRatio,
      sharedMarkers: markerParity.shared,
      liveOnlyMarkers: markerParity.referenceOnly,
      localOnlyMarkers: markerParity.candidateOnly,
      liveStructure: liveProfile.structure,
      localStructure: localProfile.structure,
    },
    assetParity: {
      criticalAssetCount: artifactSummary.criticalAssetCount,
      criticalAssetSavedCount: artifactSummary.criticalAssetSavedCount,
      replayMissingCriticalAssets: artifactSummary.replayMissingCriticalAssets,
      liveNetwork: liveProfile.network,
      localNetwork: localProfile.network,
    },
    behaviorParity: {
      localNavigation,
      localConsoleErrors: localProfile.consoleErrors,
      liveConsoleErrors: liveProfile.consoleErrors,
      localExternalRequests: localProfile.externalRequests,
      keyPhraseCoverage,
    },
    fidelityRisks: risks,
    profiles: {
      live: liveProfile,
      local: localProfile,
    },
  };
}

export function compareTextMarkers(referenceMarkers = [], candidateMarkers = []) {
  const reference = dedupeNormalized(referenceMarkers);
  const candidate = dedupeNormalized(candidateMarkers);
  const shared = reference.filter((item) => candidate.includes(item));
  const referenceOnly = reference.filter((item) => !candidate.includes(item));
  const candidateOnly = candidate.filter((item) => !reference.includes(item));
  const denominator = Math.max(reference.length, 1);

  return {
    shared,
    referenceOnly,
    candidateOnly,
    overlapRatio: Number((shared.length / denominator).toFixed(4)),
  };
}

export function renderNetflixPublicEvaluationMarkdown(report) {
  const lines = [
    '# Netflix Public Replay Evaluation',
    '',
    `- Generated at: ${report.generatedAt}`,
    `- Source URL: ${report.startUrl}`,
    `- Output directory: ${report.outputDir}`,
    `- Entry path: ${report.entryPath}`,
    '',
    '## Capture Summary',
    `- Captured pages: ${report.captureSummary.capturedPages}`,
    `- Representative pages: ${report.captureSummary.representativePages}`,
    `- Skipped pages: ${report.captureSummary.skippedPages}`,
    `- Login-gated pages: ${report.captureSummary.loginGatedPages}`,
    `- Critical assets saved: ${report.assetParity.criticalAssetSavedCount}/${report.assetParity.criticalAssetCount}`,
    `- Replay external requests: ${report.captureSummary.replayExternalRequests.length}`,
    `- Replay missing critical assets: ${report.captureSummary.replayMissingCriticalAssets.length}`,
    '',
    '## Visual Parity',
    `- Marker overlap ratio: ${report.visualParity.overlapRatio}`,
    `- Shared markers: ${report.visualParity.sharedMarkers.slice(0, 10).join(', ') || 'none'}`,
    `- Live-only markers: ${report.visualParity.liveOnlyMarkers.slice(0, 10).join(', ') || 'none'}`,
    `- Replay-only markers: ${report.visualParity.localOnlyMarkers.slice(0, 10).join(', ') || 'none'}`,
    `- Live structure: headers=${report.visualParity.liveStructure.headerCount}, mains=${report.visualParity.liveStructure.mainCount}, footers=${report.visualParity.liveStructure.footerCount}, links=${report.visualParity.liveStructure.linkCount}`,
    `- Replay structure: headers=${report.visualParity.localStructure.headerCount}, mains=${report.visualParity.localStructure.mainCount}, footers=${report.visualParity.localStructure.footerCount}, links=${report.visualParity.localStructure.linkCount}`,
    '',
    '## Behavior Parity',
    `- Local navigation successes: ${report.behaviorParity.localNavigation.successCount}/${report.behaviorParity.localNavigation.attemptedCount}`,
    `- Visible blocked links: ${report.behaviorParity.localNavigation.blockedLinkCount}`,
    `- Local external requests blocked by browser guard: ${report.behaviorParity.localExternalRequests.length}`,
    `- Key phrase coverage in replay: ${report.behaviorParity.keyPhraseCoverage.shared.join(', ') || 'none'}`,
    '',
    '## Fidelity Risks',
  ];

  if (report.fidelityRisks.length === 0) {
    lines.push('- No major replay risks were detected for the sampled public landing surface.');
  } else {
    for (const risk of report.fidelityRisks) {
      lines.push(`- ${risk}`);
    }
  }

  if (report.captureSummary.missingBehaviors.length > 0) {
    lines.push('', '## Missing Behaviors');
    for (const item of report.captureSummary.missingBehaviors.slice(0, 12)) {
      lines.push(`- ${item}`);
    }
  }

  return lines.join('\n');
}

async function capturePageProfile(browser, url, options = {}) {
  const context = await browser.newContext({
    serviceWorkers: 'block',
    locale: 'en-US',
    timezoneId: 'UTC',
    viewport: DEFAULT_VIEWPORT,
  });

  const consoleErrors = [];
  const externalRequests = new Set();
  const network = {
    requestCount: 0,
    failedCount: 0,
    status4xx5xx: 0,
    cssRequests: 0,
    jsRequests: 0,
    fontRequests: 0,
    imageRequests: 0,
    documentRequests: 0,
  };

  await context.route('**/*', async (route) => {
    const requestUrl = route.request().url();
    if (options.blockExternalToOrigin && !requestUrl.startsWith(options.blockExternalToOrigin)) {
      externalRequests.add(requestUrl);
      await route.abort();
      return;
    }
    await route.continue();
  });

  const page = await context.newPage();
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });
  page.on('request', (request) => {
    network.requestCount += 1;
    const type = request.resourceType();
    if (type === 'stylesheet') network.cssRequests += 1;
    if (type === 'script') network.jsRequests += 1;
    if (type === 'font') network.fontRequests += 1;
    if (type === 'image') network.imageRequests += 1;
    if (type === 'document') network.documentRequests += 1;
  });
  page.on('requestfailed', () => {
    network.failedCount += 1;
  });
  page.on('response', (response) => {
    if (response.status() >= 400) {
      network.status4xx5xx += 1;
    }
  });

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForLoadState('domcontentloaded', { timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(2000);

  const profile = await page.evaluate(({ markerLimit }) => {
    const isVisible = (el) => {
      if (!(el instanceof HTMLElement)) return false;
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.display !== 'none'
        && style.visibility !== 'hidden'
        && rect.width > 0
        && rect.height > 0;
    };

    const normalize = (value) => String(value || '').replace(/\s+/g, ' ').trim();
    const markerSet = new Set();
    for (const el of document.querySelectorAll('h1, h2, h3, button, a, [role="button"], [data-uia]')) {
      if (!isVisible(el)) continue;
      const text = normalize(el.textContent || el.getAttribute('aria-label') || '');
      if (text.length < 3 || text.length > 80) continue;
      markerSet.add(text);
      if (markerSet.size >= markerLimit) break;
    }

    const hrefs = [];
    for (const el of document.querySelectorAll('a[href]')) {
      const href = el.getAttribute('href') || '';
      const text = normalize(el.textContent || '');
      if (!href || href.startsWith('#')) continue;
      hrefs.push({
        href,
        text: text.slice(0, 120),
        disabled: el.getAttribute('data-disabled-link') === 'true',
        reason: el.getAttribute('data-disabled-reason') || null,
      });
      if (hrefs.length >= 20) break;
    }

    return {
      finalUrl: location.href,
      title: document.title || '',
      textLength: normalize(document.body?.innerText || '').length,
      keyMarkers: [...markerSet],
      structure: {
        headerCount: document.querySelectorAll('header').length,
        mainCount: document.querySelectorAll('main').length,
        footerCount: document.querySelectorAll('footer').length,
        sectionCount: document.querySelectorAll('section').length,
        linkCount: document.querySelectorAll('a[href]').length,
        buttonCount: document.querySelectorAll('button, [role="button"]').length,
        formCount: document.querySelectorAll('form').length,
        disabledLinkCount: document.querySelectorAll('[data-disabled-link="true"]').length,
      },
      hrefs,
    };
  }, { markerLimit: MARKER_LIMIT });

  if (options.screenshotPath) {
    await page.screenshot({ path: options.screenshotPath, fullPage: true }).catch(() => {});
  }

  await context.close().catch(() => {});
  return {
    label: options.label || 'page',
    ...profile,
    consoleErrors: consoleErrors.slice(0, 20),
    externalRequests: [...externalRequests].slice(0, 50),
    network,
  };
}

async function inspectLocalReplayNavigation(browser, entryUrl, localOrigin) {
  const context = await browser.newContext({
    serviceWorkers: 'block',
    locale: 'en-US',
    timezoneId: 'UTC',
    viewport: DEFAULT_VIEWPORT,
  });
  const page = await context.newPage();
  const externalRequests = new Set();

  await context.route('**/*', async (route) => {
    const requestUrl = route.request().url();
    if (!requestUrl.startsWith(localOrigin)) {
      externalRequests.add(requestUrl);
      await route.abort();
      return;
    }
    await route.continue();
  });

  await page.goto(entryUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(1000);

  const navigationCandidates = await page.evaluate(({ limit }) => {
    const normalize = (value) => String(value || '').replace(/\s+/g, ' ').trim();
    const items = [];
    for (const el of document.querySelectorAll('a[href]')) {
      const href = el.getAttribute('href') || '';
      if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) continue;
      if (el.getAttribute('data-disabled-link') === 'true') continue;
      const absolute = new URL(href, location.href).href;
      if (absolute === location.href) continue;
      items.push({
        href: absolute,
        text: normalize(el.textContent || '').slice(0, 120),
      });
      if (items.length >= limit) break;
    }
    return items;
  }, { limit: LINK_LIMIT });

  let successCount = 0;
  const results = [];
  for (const candidate of navigationCandidates) {
    try {
      const response = await page.goto(candidate.href, { waitUntil: 'domcontentloaded', timeout: 30000 });
      const ok = Boolean(response) && response.status() < 400 && page.url().startsWith(localOrigin);
      if (ok) successCount += 1;
      results.push({
        href: candidate.href,
        text: candidate.text,
        ok,
        finalUrl: page.url(),
      });
    } catch (error) {
      results.push({
        href: candidate.href,
        text: candidate.text,
        ok: false,
        finalUrl: page.url(),
        error: error.message,
      });
    }
  }

  const blockedLinkCount = await page.locator('[data-disabled-link="true"]').count().catch(() => 0);
  await context.close().catch(() => {});

  return {
    attemptedCount: navigationCandidates.length,
    successCount,
    blockedLinkCount,
    results,
    externalRequests: [...externalRequests].slice(0, 30),
  };
}

async function startReplayServerFromOutput(outputDir, preferredPort) {
  const app = express();
  const manifest = await readJson(path.join(outputDir, 'server', 'mocks', 'http-manifest.json'), []);
  const staticOptions = {
    index: false,
    etag: true,
    lastModified: true,
    maxAge: '1h',
    immutable: false,
    setHeaders(res) {
      res.setHeader('Cache-Control', 'public, max-age=3600');
    },
  };

  app.use(express.json({ limit: '20mb' }));
  app.use(express.urlencoded({ extended: true }));
  app.use(express.static(path.join(outputDir, 'public'), staticOptions));
  app.use('/public', express.static(path.join(outputDir, 'public'), staticOptions));

  app.use('/api', async (req, res, next) => {
    try {
      const pathname = req.path.replace(/^\/api/, '') || '/';
      const search = buildSearch(req.query || {});
      const bodyHash = hashValue(req.body);
      const graphQLBody = typeof req.body === 'object' && req.body ? req.body : {};
      const operationName = typeof graphQLBody.operationName === 'string' ? graphQLBody.operationName : null;
      const variablesHash = hashValue(graphQLBody.variables ?? null);
      const documentHash = hashValue(typeof graphQLBody.query === 'string' ? graphQLBody.query : null);
      const extensionsHash = hashValue(graphQLBody.extensions ?? null);

      const match = manifest.find((item) => {
        if (item.method !== req.method || item.path !== pathname || (item.search || '') !== search) {
          return false;
        }
        if (item.matchStrategy === 'graphql-operation' || item.graphQL) {
          const details = item.graphQLDetails || {};
          const persistedHash = hashValue(details.persistedOperationHint || null);
          return (details.operationName || item.graphQLOperationName || null) === operationName
            && (details.variablesHash || item.graphQLVariablesHash || 'no-body') === variablesHash
            && (
              (details.documentHash && details.documentHash !== 'no-body' && details.documentHash === documentHash)
              || (!(details.documentHash && details.documentHash !== 'no-body')
                && hashValue(details.extensions || null) === extensionsHash
                && hashValue(details.persistedOperationHint || null) === persistedHash)
            );
        }
        return (item.bodyHash || 'no-body') === bodyHash;
      }) || manifest.find((item) => item.method === req.method && item.path === pathname);

      if (!match) return next();

      const body = await readJson(path.join(outputDir, 'server', match.bodyFile), null);
      res.type(match.responseMimeType || 'application/json');
      res.status(match.status || 200);
      return res.send(body);
    } catch (error) {
      return next(error);
    }
  });

  app.use(async (req, res, next) => {
    try {
      const viewFile = resolveViewFile(outputDir, req.path);
      await fs.access(viewFile);
      res.setHeader('Cache-Control', 'no-cache');
      return res.sendFile(viewFile);
    } catch {
      return next();
    }
  });

  app.use((_req, res) => {
    res.status(404).send('Not Found');
  });

  const port = await findAvailablePort(preferredPort, preferredPort + 20);
  const server = await new Promise((resolve) => {
    const instance = app.listen(port, () => resolve(instance));
  });

  return {
    app,
    server,
    port,
    origin: `http://localhost:${port}`,
    close: () => new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    }),
  };
}

function buildLocalReplayUrl(port, entryPath) {
  const normalized = String(entryPath || 'index.html').replace(/\\/g, '/').replace(/\.html$/, '');
  const route = normalized === 'index' ? '' : `/${normalized}`;
  return `http://localhost:${port}${route || '/'}`;
}

function dedupeNormalized(values) {
  const output = [];
  const seen = new Set();
  for (const value of values || []) {
    const normalized = normalizeMarker(value);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    output.push(normalized);
  }
  return output;
}

function normalizeMarker(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

function collectReplayWarnings(replayVerification) {
  const items = [];
  for (const page of replayVerification.pages || []) {
    for (const warning of page.warnings || []) {
      items.push(`${page.savedPath}: ${warning}`);
    }
  }
  return items;
}

function inferEntryPath(startUrl, crawlManifest) {
  const pages = Array.isArray(crawlManifest?.pages) ? crawlManifest.pages : [];
  if (pages.length === 0) return null;

  const exact = pages.find((page) => page.url === startUrl || page.finalUrl === startUrl);
  if (exact?.savedPath) return exact.savedPath;

  const completed = pages.find((page) => page.savedPath && !page.skippedReason);
  return completed?.savedPath || null;
}

async function readJson(filePath, fallback) {
  try {
    const raw = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

async function readText(filePath, fallback) {
  if (!await pathExists(filePath)) return fallback;
  try {
    return await fs.readFile(filePath, 'utf-8');
  } catch {
    return fallback;
  }
}

function resolveViewFile(outputDir, routePath) {
  let normalized = routePath || '/';
  if (normalized === '/') return path.join(outputDir, 'views', 'index.html');
  normalized = normalized.replace(/\/+$/, '');
  return path.join(outputDir, 'views', normalized.replace(/^\//, '') + '.html');
}

function buildSearch(query) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query || {})) {
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, item);
    } else if (value !== undefined && value !== null) {
      params.append(key, String(value));
    }
  }
  const rendered = params.toString();
  return rendered ? `?${rendered}` : '';
}

function hashValue(value) {
  if (value === null || value === undefined || value === '' || (typeof value === 'object' && Object.keys(value || {}).length === 0)) {
    return 'no-body';
  }
  return crypto.createHash('sha1').update(stableSerialize(value)).digest('hex').slice(0, 12);
}

function stableSerialize(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return `[${value.map((item) => stableSerialize(item)).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => JSON.stringify(key) + ':' + stableSerialize(value[key])).join(',')}}`;
  }
  return JSON.stringify(value);
}

async function findAvailablePort(startPort, maxPort) {
  for (let current = startPort; current <= maxPort; current += 1) {
    const available = await canListenOnPort(current);
    if (available) return current;
  }
  throw new Error(`No available port found between ${startPort} and ${maxPort}`);
}

function canListenOnPort(port) {
  return new Promise((resolve) => {
    const tester = net.createServer();
    tester.once('error', () => resolve(false));
    tester.once('listening', () => {
      tester.close(() => resolve(true));
    });
    tester.listen(port);
  });
}
