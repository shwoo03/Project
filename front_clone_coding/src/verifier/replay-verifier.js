import fs from 'fs/promises';
import path from 'path';

import express from 'express';
import { chromium } from 'playwright';
import { load as loadHtml } from 'cheerio';

import { ensureDir, pathExists, saveFile } from '../utils/file-utils.js';
import logger from '../utils/logger.js';
import {
  extractTextMarkers,
  looksLikeEncodingNoise,
  normalizeComparisonText,
} from '../utils/encoding-utils.js';
import { classifyExternalRuntime, isNonCriticalRuntime } from '../utils/external-runtime-utils.js';
import {
  CONTENT_GAP_CEILING,
  PARTIAL_MATCH_CEILING,
  BOILERPLATE_DOMINANCE_RATIO,
  HEADING_MAIN_OVERLAP_FLOOR,
  LENGTH_DRIFT_FLOOR,
} from '../utils/constants.js';
import {
  buildSearch,
  findHttpMockMatch,
  hashValue,
  normalizeAbsoluteRequestUrl,
  normalizeSearch,
} from '../utils/replay-mock-utils.js';
import {
  buildReplayRouteFromSavedPath,
  normalizeCrawlUrl,
} from '../utils/url-utils.js';

export async function runReplayVerification({
  outputDir,
  startUrl,
  pages = [],
  apiArtifacts = {},
  sampleSize = 0,
}) {
  const warnings = [];
  const pageSamples = selectRepresentativePages(pages, sampleSize);
  if (pageSamples.length === 0) {
    const report = buildEmptyReport(startUrl);
    await writeReplayVerificationArtifacts(outputDir, report);
    return {
      verificationWarnings: [],
      report,
      artifacts: {
        replayVerificationReport: 'server/docs/replay-verification.md',
        replayVerificationJson: 'server/spec/replay-verification.json',
      },
    };
  }

  logger.start('Running replay verification');

  const serverState = {
    mockHits: 0,
    missingCriticalAssets: new Set(),
    externalRequests: new Set(),
    externalRequestDetails: new Map(),
  };
  const pageRouteManifest = await readJson(path.join(outputDir, 'server', 'spec', 'page-route-manifest.json'), { routes: [] });
  const pageRouteLookup = buildPageRouteLookup(pageRouteManifest);

  const runtime = await startReplayServer(outputDir, serverState, pageRouteLookup);
  let browser = null;

  try {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      serviceWorkers: 'block',
      locale: 'en-US',
      timezoneId: 'UTC',
      viewport: { width: 1440, height: 900 },
    });

    await context.addInitScript(() => {
      window.__FRONT_CLONE_VERIFY__ = {
        routes: [location.href],
        consoleErrors: [],
        serviceWorkerAttempts: [],
      };

      const remember = () => {
        window.__FRONT_CLONE_VERIFY__.routes.push(location.href);
      };

      for (const name of ['pushState', 'replaceState']) {
        const original = history[name];
        history[name] = function (...args) {
          const result = original.apply(this, args);
          remember();
          return result;
        };
      }

      window.addEventListener('popstate', remember);
      const originalRegister = navigator.serviceWorker?.register?.bind(navigator.serviceWorker);
      if (originalRegister) {
        navigator.serviceWorker.register = async (...args) => {
          window.__FRONT_CLONE_VERIFY__.serviceWorkerAttempts.push(String(args[0] || ''));
          return originalRegister(...args);
        };
      }
    });

    await context.route('**/*', async (route) => {
      const requestUrl = route.request().url();
      if (requestUrl.startsWith(runtime.origin)) {
        await route.continue();
        return;
      }

      serverState.externalRequests.add(requestUrl);
      if (!serverState.externalRequestDetails.has(requestUrl)) {
        serverState.externalRequestDetails.set(requestUrl, classifyExternalRequest(requestUrl));
      }
      await route.abort();
    });

    const pageResults = [];
    const manifest = apiArtifacts.httpManifest || [];
    for (const pageInfo of pageSamples) {
      const page = await context.newPage();
      const mockHitsBeforePage = serverState.mockHits;
      const pageApiRequests = [];
      const pageExternalRequests = [];
      const pageConsoleErrors = [];
      const pageRuntimeExceptions = [];
      const pageFailedRuntimeRequests = [];
      const requestListener = (request) => {
        const requestUrl = request.url();
        if (requestUrl.startsWith(`${runtime.origin}/api`)) {
          pageApiRequests.push(buildObservedApiRequest(request));
          return;
        }
        if (!requestUrl.startsWith(runtime.origin)) {
          pageExternalRequests.push(requestUrl);
        }
      };
      const consoleListener = (msg) => {
        if (msg.type() !== 'error') return;
        const text = String(msg.text() || '').trim();
        if (!text) return;
        const location = msg.location?.() || {};
        const classification = classifyRuntimeConsoleMessage(text, runtime.origin);
        pageConsoleErrors.push({
          text,
          url: location.url || '',
          lineNumber: location.lineNumber ?? null,
          columnNumber: location.columnNumber ?? null,
          category: classification.category,
          warningEligible: classification.warningEligible,
        });
      };
      const pageErrorListener = (error) => {
        const message = String(error?.message || error || '').trim();
        if (!message) return;
        pageRuntimeExceptions.push({
          message,
          name: error?.name || 'Error',
          stack: String(error?.stack || '').split('\n').slice(0, 5).join('\n'),
        });
      };
      const responseListener = (response) => {
        const status = Number(response.status?.() || 0);
        if (status < 400) return;
        const request = response.request();
        const resourceType = request.resourceType();
        if (!['script', 'stylesheet', 'fetch', 'xhr'].includes(resourceType)) return;
        const requestUrl = request.url();
        if (!requestUrl.startsWith(runtime.origin)) return;
        pageFailedRuntimeRequests.push({
          url: requestUrl,
          status,
          resourceType,
          failureText: '',
        });
      };
      const requestFailedListener = (request) => {
        const resourceType = request.resourceType();
        if (!['script', 'stylesheet', 'fetch', 'xhr'].includes(resourceType)) return;
        const requestUrl = request.url();
        if (!requestUrl.startsWith(runtime.origin)) return;
        pageFailedRuntimeRequests.push({
          url: requestUrl,
          status: null,
          resourceType,
          failureText: request.failure()?.errorText || 'requestfailed',
        });
      };
      page.on('request', requestListener);
      page.on('console', consoleListener);
      page.on('pageerror', pageErrorListener);
      page.on('response', responseListener);
      page.on('requestfailed', requestFailedListener);
      const verificationRoute = pageInfo.replayRoute || toVerificationRoute(pageInfo.savedPath);
      const verificationUrl = `${runtime.origin}${verificationRoute}`;
      const response = await page.goto(verificationUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForLoadState('domcontentloaded', { timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(400);

      const actualTitle = await page.title();
      const criticalLocatorPresent = await page.locator('main, body').first().isVisible().catch(() => false);
      const contentProfile = await page.evaluate(() => {
        const selectLongestText = (selectors = []) => {
          const candidates = selectors
            .flatMap((selector) => [...document.querySelectorAll(selector)])
            .map((node) => node.innerText || node.textContent || '')
            .map((text) => text.replace(/\s+/g, ' ').trim())
            .filter(Boolean)
            .sort((left, right) => right.length - left.length);
          return candidates[0] || '';
        };

        const collectText = (selectors = [], limit = 6) => selectors
          .flatMap((selector) => [...document.querySelectorAll(selector)].slice(0, limit))
          .map((node) => node.innerText || node.textContent || '')
          .map((text) => text.replace(/\s+/g, ' ').trim())
          .filter(Boolean)
          .join(' ');

        const bodyText = (document.body?.innerText || '').replace(/\s+/g, ' ').trim();
        const headingText = collectText(['h1', 'h2', 'h3'], 8);
        const mainText = selectLongestText(['main', '[role="main"]', 'article', 'section']);
        const navText = collectText(['header nav', 'nav', '[role="navigation"]'], 12);
        const footerText = collectText(['footer', '[role="contentinfo"]'], 12);

        return {
          bodyText,
          bodyTextLength: bodyText.length,
          headingText,
          mainText,
          navTextLength: navText.length,
          footerTextLength: footerText.length,
        };
      });
      const replayTextLength = contentProfile.bodyTextLength || 0;
      const bodyText = contentProfile.bodyText || '';
      const verificationMeta = await page.evaluate(() => {
        const routes = window.__FRONT_CLONE_VERIFY__?.routes || [];
        const serviceWorkerAttempts = window.__FRONT_CLONE_VERIFY__?.serviceWorkerAttempts || [];
        const runtimeState = window.__FRONT_CLONE_RUNTIME__ || null;
        const roleCounts = {};
        const errorSignals = {
          heading: document.querySelector('h1, title')?.textContent || '',
          bodyTextSample: (document.body?.innerText || '').slice(0, 300),
        };
        for (const el of document.querySelectorAll('[role], main, nav, header, footer, form, button, a')) {
          const role = el.getAttribute('role') || el.tagName.toLowerCase();
          roleCounts[role] = (roleCounts[role] || 0) + 1;
        }
        return {
          routes,
          serviceWorkerAttempts,
          runtimeGuardObserved: Boolean(runtimeState?.guardActive),
          runtimeState: runtimeState ? {
            guardActive: Boolean(runtimeState.guardActive),
            exceptions: Array.isArray(runtimeState.exceptions) ? runtimeState.exceptions : [],
            resourceErrors: Array.isArray(runtimeState.resourceErrors) ? runtimeState.resourceErrors : [],
          } : null,
          ariaSummary: roleCounts,
          errorSignals,
        };
      });
      page.off('request', requestListener);
      page.off('console', consoleListener);
      page.off('pageerror', pageErrorListener);
      page.off('response', responseListener);
      page.off('requestfailed', requestFailedListener);
      const expectedRenderCritical = getExpectedRenderCriticalCandidates(pageInfo, apiArtifacts);
      const supportingReplayCandidates = getSupportingReplayCandidates(pageInfo, apiArtifacts);
      const bootstrapSignalsObserved = getBootstrapSignalsForPage(pageInfo);
      const renderCriticalDiagnostics = analyzeReplayCandidates({
        candidates: expectedRenderCritical,
        observedApiRequests: pageApiRequests,
        externalRequests: pageExternalRequests,
        manifest,
      });
      const supportingDiagnostics = analyzeReplayCandidates({
        candidates: supportingReplayCandidates,
        observedApiRequests: pageApiRequests,
        externalRequests: pageExternalRequests,
        manifest,
      });

      const routeAnalysis = analyzeReplayRoute({
        responseStatus: response?.status() || 0,
        actualTitle,
        bodyText,
        criticalLocatorPresent,
        routesObserved: verificationMeta.routes,
        expectedRoute: verificationRoute,
      });
      const contentComparison = assessContentComparison(pageInfo, {
        title: actualTitle,
        bodyText,
        mainText: contentProfile.mainText,
        headingText: contentProfile.headingText,
        navTextLength: contentProfile.navTextLength,
        footerTextLength: contentProfile.footerTextLength,
      });
      const markerOverlap = contentComparison.markerOverlapRatio;
      const textDriftRatio = pageInfo.qa?.rawTextLength > 0
        ? Math.abs(replayTextLength - pageInfo.qa.rawTextLength) / pageInfo.qa.rawTextLength
        : Number((1 - markerOverlap).toFixed(4));
      const runtimeDiagnostics = buildRuntimeDiagnostics({
        consoleErrors: pageConsoleErrors,
        runtimeExceptions: pageRuntimeExceptions,
        failedRuntimeRequests: pageFailedRuntimeRequests,
        runtimeGuardState: verificationMeta.runtimeState,
        runtimeOrigin: runtime.origin,
      });
      const runtimeFailureProfile = assessRuntimeFailureState({
        routeReached: routeAnalysis.routeReached,
        criticalLocatorPresent,
        expectedRenderCritical,
        runtimeDiagnostics,
      });

      // When runtime failures are present, separate runtime-induced gaps from true content sourcing gaps.
      const hasRuntimeDegrade = runtimeFailureProfile.severity !== 'none' && runtimeFailureProfile.severity !== 'low';
      if (hasRuntimeDegrade && contentComparison.contentDriftAssessment === 'partial-content-match') {
        contentComparison.contentDriftAssessment = 'runtime-induced-partial-match';
      } else if (hasRuntimeDegrade && contentComparison.contentDriftAssessment === 'high-confidence-content-gap' && runtimeFailureProfile.assessment === 'runtime-script-degraded') {
        contentComparison.contentDriftAssessment = 'runtime-induced-content-gap';
      }

      // Determine whether soft runtime failures should be notes (informational) or warnings (actionable).
      // When the page shell is intact and content comparison is positive, soft failures are notes.
      const contentIsGood = contentComparison.contentDriftAssessment === 'content-match'
        || contentComparison.contentDriftAssessment === 'comparison-noise-likely';
      const shellIsIntact = routeAnalysis.routeReached && criticalLocatorPresent;
      const softFailIsNote = shellIsIntact && contentIsGood && runtimeFailureProfile.severity === 'soft';

      const runtimeImpactAssessment = softFailIsNote ? 'note' : (runtimeFailureProfile.severity === 'none' ? 'clean' : 'warning');

      const pageWarningSet = [];
      const pageNoteSet = [];
      if (!routeAnalysis.routeReached) pageWarningSet.push(routeAnalysis.warningCode);
      if (!criticalLocatorPresent) pageWarningSet.push('critical-locator-missing');
      if (contentComparison.contentDriftAssessment === 'high-confidence-content-gap') pageWarningSet.push('content-drift');
      if (contentComparison.contentDriftAssessment === 'runtime-induced-content-gap') pageWarningSet.push('runtime-induced-content-gap');
      if (contentComparison.contentDriftAssessment === 'runtime-induced-partial-match') pageNoteSet.push('runtime-induced-partial-match');
      if (contentComparison.contentDriftAssessment === 'comparison-noise-likely') pageWarningSet.push('comparison-noise-likely');
      if (verificationMeta.serviceWorkerAttempts.length > 0) pageWarningSet.push('service-worker-attempted');
      if (contentComparison.titleComparison.shouldWarn) pageWarningSet.push('title-drift');
      if (contentComparison.titleComparison.mismatchLikelyEncodingNoise) pageWarningSet.push('title-comparison-low-confidence');
      if (expectedRenderCritical.length > 0 && renderCriticalDiagnostics.triggered.length === 0) {
        pageWarningSet.push('render-critical-not-triggered');
      }
      if (renderCriticalDiagnostics.missed.some((item) => item.reason === 'mock-miss')) {
        pageWarningSet.push('render-critical-mock-miss');
      }
      for (const warning of runtimeDiagnostics.warningCodes) {
        if (runtimeFailureProfile.severity === 'soft' && warning === 'runtime-exception') {
          continue;
        }
        if (runtimeFailureProfile.severity === 'soft' && warning === 'runtime-request-failed') {
          continue;
        }
        pageWarningSet.push(warning);
      }
      if (runtimeFailureProfile.assessment === 'runtime-widget-soft-fail') {
        (softFailIsNote ? pageNoteSet : pageWarningSet).push('runtime-widget-soft-fail');
      }
      if (runtimeFailureProfile.assessment === 'runtime-resource-soft-miss') {
        (softFailIsNote ? pageNoteSet : pageWarningSet).push('runtime-resource-soft-miss');
      }

      pageResults.push({
        pageUrl: pageInfo.finalUrl || pageInfo.url,
        savedPath: pageInfo.savedPath,
        verificationUrl,
        routeReached: routeAnalysis.routeReached,
        responseStatus: response?.status() || null,
        criticalLocatorPresent,
        mockApiHitsObserved: serverState.mockHits - mockHitsBeforePage,
        textDriftRatio: Number(textDriftRatio.toFixed(4)),
        markerOverlapRatio: Number(markerOverlap.toFixed(4)),
        contentDriftAssessment: contentComparison.contentDriftAssessment,
        contentComparisonConfidence: contentComparison.contentComparisonConfidence,
        boilerplateDominanceLikely: contentComparison.boilerplateDominanceLikely,
        markerExtractionProfile: contentComparison.markerExtractionProfile,
        bootstrapSignalsObserved,
        bootstrapEvidenceLevel: bootstrapSignalsObserved.bootstrapEvidenceLevel || 'none',
        encodingObserved: pageInfo.encodingDiagnostics?.encoding || pageInfo.documentEncoding || null,
        encodingSource: pageInfo.encodingDiagnostics?.encodingSource || 'unknown',
        encodingMismatchLikely: Boolean(pageInfo.encodingDiagnostics?.suspectedEncodingMismatch),
        decodeConfidence: pageInfo.encodingDiagnostics?.decodeConfidence || 'low',
        replayDataAssessment: assessReplayDataState({
          bootstrapSignals: bootstrapSignalsObserved,
          expectedRenderCritical,
          renderCriticalDiagnostics,
          supportingReplayCandidates,
          supportingDiagnostics,
        }),
        renderCriticalCandidatesExpected: expectedRenderCritical,
        renderCriticalRequestsTriggered: renderCriticalDiagnostics.triggered,
        renderCriticalRequestsMissed: renderCriticalDiagnostics.missed,
        renderSupportingCandidatesObserved: supportingReplayCandidates,
        renderSupportingRequestsTriggered: supportingDiagnostics.triggered,
        renderSupportingRequestsSkipped: supportingDiagnostics.missed,
        titleExpected: pageInfo.title || '',
        titleActual: actualTitle || '',
        titleComparisonConfidence: contentComparison.titleComparison.confidence,
        titleMismatchLikelyEncodingNoise: contentComparison.titleComparison.mismatchLikelyEncodingNoise,
        ariaSummary: verificationMeta.ariaSummary,
        routesObserved: verificationMeta.routes,
        runtimeConsoleErrors: runtimeDiagnostics.consoleErrors,
        runtimeExceptions: runtimeDiagnostics.runtimeExceptions,
        failedRuntimeRequests: runtimeDiagnostics.failedRuntimeRequests,
        runtimeErrorSummary: runtimeDiagnostics.summary,
        runtimeGuardObserved: verificationMeta.runtimeGuardObserved,
        runtimeFailureClasses: runtimeDiagnostics.failureClasses,
        sameOriginRuntimeExceptions: runtimeDiagnostics.sameOriginRuntimeExceptions,
        sameOriginRuntimeMisses: runtimeDiagnostics.sameOriginRuntimeMisses,
        runtimeFailureAssessment: runtimeFailureProfile.assessment,
        runtimeFailureScope: runtimeFailureProfile.scope,
        runtimeFailureSeverity: runtimeFailureProfile.severity,
        runtimeImpactAssessment,
        suspectedFailureChain: runtimeFailureProfile.suspectedFailureChain,
        warnings: pageWarningSet,
        notes: pageNoteSet,
      });

      await page.close().catch(() => {});
    }

    if (serverState.externalRequests.size > 0) {
      warnings.push(`Replay attempted ${serverState.externalRequests.size} external request(s).`);
    }
    if (serverState.missingCriticalAssets.size > 0) {
      warnings.push(`Replay missed ${serverState.missingCriticalAssets.size} critical asset(s).`);
    }
    for (const pageResult of pageResults) {
      for (const item of pageResult.warnings) {
        warnings.push(`${pageResult.savedPath}: ${item}`);
      }
    }

    const report = {
      generatedAt: new Date().toISOString(),
      startUrl,
      runtimeOrigin: runtime.origin,
      pagesVerified: pageResults.length,
      mockApiHits: serverState.mockHits,
      missingCriticalAssets: [...serverState.missingCriticalAssets],
      externalRequests: [...serverState.externalRequests],
      externalRequestDetails: [...serverState.externalRequestDetails.values()],
      externalRequestSummary: summarizeExternalRequests(serverState.externalRequestDetails),
      runtimeErrorSummary: summarizeRuntimeErrors(pageResults),
      pages: pageResults,
    };

    await writeReplayVerificationArtifacts(outputDir, report);
    logger.succeed('Replay verification completed');
    return {
      verificationWarnings: warnings,
      report,
      artifacts: {
        replayVerificationReport: 'server/docs/replay-verification.md',
        replayVerificationJson: 'server/spec/replay-verification.json',
      },
    };
  } catch (error) {
    logger.warn(`Replay verification skipped: ${error.message}`);
    const report = {
      ...buildEmptyReport(startUrl),
      error: error.message,
    };
    await writeReplayVerificationArtifacts(outputDir, report);
    return {
      verificationWarnings: [`Replay verification skipped: ${error.message}`],
      report,
      artifacts: {
        replayVerificationReport: 'server/docs/replay-verification.md',
        replayVerificationJson: 'server/spec/replay-verification.json',
      },
    };
  } finally {
    await browser?.close().catch(() => {});
    await runtime.close();
  }
}

function selectRepresentativePages(pages, sampleSize) {
  const preferred = pages.filter((page) => page.classification?.shouldRunReplayValidation);
  const source = preferred.length > 0 ? preferred : pages.slice(0, 1);
  return source.slice(0, Math.max(sampleSize, source.length > 0 ? 1 : 0));
}

function buildEmptyReport(startUrl) {
  return {
    generatedAt: new Date().toISOString(),
    startUrl,
    runtimeOrigin: null,
    pagesVerified: 0,
    mockApiHits: 0,
    missingCriticalAssets: [],
    externalRequests: [],
    externalRequestDetails: [],
    externalRequestSummary: {},
    runtimeErrorSummary: {
      consoleErrors: 0,
      runtimeExceptions: 0,
      failedRuntimeRequests: 0,
      pagesWithRuntimeErrors: 0,
      pagesWithSoftRuntimeDegrade: 0,
      total: 0,
      failureClasses: {},
    },
    pages: [],
  };
}

async function writeReplayVerificationArtifacts(outputDir, report) {
  await ensureDir(path.join(outputDir, 'server', 'spec'));
  await ensureDir(path.join(outputDir, 'server', 'docs'));
  await saveFile(path.join(outputDir, 'server', 'spec', 'replay-verification.json'), JSON.stringify(report, null, 2));
  await saveFile(path.join(outputDir, 'server', 'docs', 'replay-verification.md'), renderReplayVerificationMarkdown(report));
}

function renderReplayVerificationMarkdown(report) {
  const lines = [
    '# Replay Verification',
    '',
    `- Generated at: ${report.generatedAt}`,
    `- Pages verified: ${report.pagesVerified || 0}`,
    `- Mock API hits: ${report.mockApiHits || 0}`,
    `- Missing critical assets: ${(report.missingCriticalAssets || []).length}`,
    `- External requests blocked: ${(report.externalRequests || []).length}`,
    `- Runtime console errors: ${report.runtimeErrorSummary?.consoleErrors || 0}`,
    `- Runtime exceptions: ${report.runtimeErrorSummary?.runtimeExceptions || 0}`,
    `- Failed runtime requests: ${report.runtimeErrorSummary?.failedRuntimeRequests || 0}`,
    `- Pages with soft runtime degrade: ${report.runtimeErrorSummary?.pagesWithSoftRuntimeDegrade || 0}`,
    '',
  ];

  if (report.error) {
    lines.push(`- Verification error: ${report.error}`, '');
  }

  if ((report.pages || []).length === 0) {
    lines.push('No representative pages were available for replay verification.');
    return lines.join('\n');
  }

  const summaryEntries = Object.entries(report.externalRequestSummary || {}).filter(([, count]) => count > 0);
  if (summaryEntries.length > 0) {
    lines.push('## External Request Categories');
    for (const [category, count] of summaryEntries) {
      lines.push(`- ${category}: ${count}`);
    }
    lines.push('');
  }

  const runtimeClassEntries = Object.entries(report.runtimeErrorSummary?.failureClasses || {}).filter(([, count]) => count > 0);
  if (runtimeClassEntries.length > 0) {
    lines.push('## Runtime Failure Classes');
    for (const [failureClass, count] of runtimeClassEntries) {
      lines.push(`- ${failureClass}: ${count}`);
    }
    lines.push('');
  }

  lines.push('## Pages');
  for (const page of report.pages) {
    lines.push(`- ${page.savedPath}: routeReached=${page.routeReached}, criticalLocatorPresent=${page.criticalLocatorPresent}, textDriftRatio=${page.textDriftRatio}, markerOverlapRatio=${page.markerOverlapRatio}, contentDriftAssessment=${page.contentDriftAssessment || 'unknown'}, contentComparisonConfidence=${page.contentComparisonConfidence || 'unknown'}, mockApiHitsObserved=${page.mockApiHitsObserved}, bootstrapEvidenceLevel=${page.bootstrapEvidenceLevel || 'none'}, replayDataAssessment=${page.replayDataAssessment || 'unknown'}, encodingObserved=${page.encodingObserved || 'unknown'}, decodeConfidence=${page.decodeConfidence || 'low'}, renderCriticalExpected=${(page.renderCriticalCandidatesExpected || []).length}, renderCriticalTriggered=${(page.renderCriticalRequestsTriggered || []).length}, renderSupportingObserved=${(page.renderSupportingCandidatesObserved || []).length}`);
    if (page.warnings.length > 0) {
      lines.push(`  warnings: ${page.warnings.join(', ')}`);
    }
    if ((page.notes || []).length > 0) {
      lines.push(`  notes: ${page.notes.join(', ')}`);
    }
    if (page.titleComparisonConfidence || page.titleMismatchLikelyEncodingNoise) {
      lines.push(`  title: comparisonConfidence=${page.titleComparisonConfidence || 'unknown'}, encodingNoiseLikely=${Boolean(page.titleMismatchLikelyEncodingNoise)}`);
    }
    if (page.runtimeErrorSummary?.total > 0) {
      lines.push(`  runtime: consoleErrors=${page.runtimeErrorSummary.consoleErrors}, exceptions=${page.runtimeErrorSummary.runtimeExceptions}, failedRequests=${page.runtimeErrorSummary.failedRuntimeRequests}`);
      lines.push(`  runtime-assessment: ${page.runtimeFailureAssessment || 'none'}, severity=${page.runtimeFailureSeverity || 'unknown'}, scope=${page.runtimeFailureScope || 'unknown'}, guardObserved=${Boolean(page.runtimeGuardObserved)}`);
    }
  }
  return lines.join('\n');
}

async function startReplayServer(outputDir, serverState, pageRouteLookup = new Map()) {
  const app = express();
  const manifest = await readJson(path.join(outputDir, 'server', 'mocks', 'http-manifest.json'), []);

  app.use(express.json({ limit: '20mb' }));
  app.use(express.urlencoded({ extended: true }));
  app.all('/__front_clone_noop__', (_req, res) => res.status(204).end());
  app.use('/public', express.static(path.join(outputDir, 'public'), { index: false }));
  app.use(express.static(path.join(outputDir, 'public'), { index: false }));

  app.use('/api', async (req, res, next) => {
    try {
      const pathname = req.path.replace(/^\/api/, '') || '/';
      const search = buildSearch(req.query || {});
      const bodyHash = hashValue(req.body);
      const operationName = typeof req.body?.operationName === 'string' ? req.body.operationName : null;
      const documentHash = hashValue(typeof req.body?.query === 'string' ? req.body.query : null);
      const variablesHash = hashValue(req.body?.variables ?? null);
      const extensionsHash = hashValue(req.body?.extensions ?? null);

      const match = findHttpMockMatch(manifest, {
        method: req.method,
        path: pathname,
        search,
        bodyHash,
        operationName,
        documentHash,
        variablesHash,
        extensionsHash,
      }) || manifest.find((item) => item.method === req.method && item.path === pathname);

      if (!match) return next();

      serverState.mockHits += 1;
      const body = await readJson(path.join(outputDir, 'server', match.bodyFile), null);
      res.type(match.responseMimeType || match.responseContentType || 'application/json');
      res.status(match.status || match.httpStatus || 200);
      return res.send(body);
    } catch (error) {
      return next(error);
    }
  });

  app.use('/api', (req, res, next) => {
    if (isNonCriticalApiRequest(req.path)) {
      return res.status(204).end();
    }
    return next();
  });

  app.use(async (req, res, next) => {
    for (const viewFile of resolveViewCandidates(outputDir, req.path, pageRouteLookup)) {
      if (await pathExists(viewFile)) {
        try {
          const html = await fs.readFile(viewFile, 'utf-8');
          res.type('html');
          return res.send(html);
        } catch (error) {
          logger.debug(`Replay verifier failed to serve HTML candidate: ${viewFile} - ${error.message}`);
        }
      }
    }
    return next();
  });

  app.use((req, res) => {
    if (isCriticalAssetRequest(req.path)) {
      serverState.missingCriticalAssets.add(req.path);
    }
    res.status(404).send('Not Found');
  });

  const server = await new Promise((resolve) => {
    const instance = app.listen(0, () => resolve(instance));
  });
  const address = server.address();
  const port = typeof address === 'object' && address ? address.port : 3000;

  return {
    origin: `http://127.0.0.1:${port}`,
    close: () => new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    }),
  };
}

function resolveViewCandidates(outputDir, routePath, pageRouteLookup = new Map()) {
  const normalized = normalizeRoutePath(routePath);
  const mappedRoute = pageRouteLookup.get(normalized);
  if (mappedRoute?.savedPath) {
    return [path.join(outputDir, 'views', mappedRoute.savedPath)];
  }

  if (normalized === '/') return [path.join(outputDir, 'views', 'index.html')];
  const withoutLeadingSlash = normalized.replace(/^\//, '');
  return [
    path.join(outputDir, 'views', `${withoutLeadingSlash}.html`),
    path.join(outputDir, 'views', withoutLeadingSlash, 'index.html'),
  ];
}

function toVerificationRoute(savedPath = 'index.html') {
  return buildReplayRouteFromSavedPath(savedPath);
}

function analyzeReplayRoute({ responseStatus, actualTitle, bodyText, criticalLocatorPresent, routesObserved = [], expectedRoute = '/' }) {
  const lowerTitle = String(actualTitle || '').trim().toLowerCase();
  const lowerBody = String(bodyText || '').slice(0, 500).toLowerCase();
  const normalizedExpected = expectedRoute.replace(/\/+$/, '') || '/';
  const normalizedObserved = routesObserved.map((item) => {
    try {
      const url = new URL(item);
      return url.pathname.replace(/\/+$/, '') || '/';
    } catch {
      return String(item || '');
    }
  });

  if (responseStatus === 404 || lowerBody === 'not found' || lowerTitle === 'error') {
    return { routeReached: false, warningCode: 'file-not-found' };
  }
  if (!normalizedObserved.includes(normalizedExpected)) {
    return { routeReached: false, warningCode: 'route-mismatch' };
  }
  if (!criticalLocatorPresent || /not found|cannot get|runtime error|application error/.test(lowerBody)) {
    return { routeReached: false, warningCode: 'runtime-error' };
  }
  return { routeReached: true, warningCode: null };
}

function computeMarkerOverlap(pageInfo, bodyText) {
  const expectedMarkers = getExpectedMarkers(pageInfo);
  if (expectedMarkers.length === 0) return 1;

  const actualTokens = new Set(extractTextMarkers(bodyText, 120).map((token) => token.toLowerCase()));
  const hits = expectedMarkers.filter((token) => actualTokens.has(token.toLowerCase())).length;
  return hits / expectedMarkers.length;
}

function getExpectedMarkers(pageInfo) {
  const html = pageInfo.processedHtml || pageInfo.decodedDocumentHtml || pageInfo.html || '';
  if (!html) {
    return extractTextMarkers(pageInfo.title || '', 20);
  }

  const $ = loadHtml(html);
  $('script, style, noscript').remove();
  const text = $('body').text() || $.root().text() || '';
  return extractTextMarkers(`${pageInfo.title || ''} ${text}`, 80);
}

export function assessContentComparison(pageInfo, actualProfile = {}) {
  const expectedProfile = buildExpectedContentProfile(pageInfo);
  const actualMarkers = {
    heading: extractTextMarkers(actualProfile.headingText || '', 24),
    main: extractTextMarkers(actualProfile.mainText || actualProfile.bodyText || '', 80),
    body: extractTextMarkers(actualProfile.bodyText || '', 120),
  };
  const overlap = {
    heading: computeTokenOverlap(expectedProfile.markers.heading, actualMarkers.heading),
    main: computeTokenOverlap(expectedProfile.markers.main, actualMarkers.main),
    body: computeTokenOverlap(expectedProfile.markers.body, actualMarkers.body),
  };
  const markerOverlapRatio = computeWeightedOverlap(overlap, expectedProfile.markers);
  const expectedBodyLength = expectedProfile.lengths.body;
  const boilerplateBytes = (actualProfile.navTextLength || 0) + (actualProfile.footerTextLength || 0);
  const actualBodyLength = String(actualProfile.bodyText || '').length;
  const boilerplateDominanceLikely = actualBodyLength > 0
    && boilerplateBytes / actualBodyLength >= BOILERPLATE_DOMINANCE_RATIO
    && overlap.main >= CONTENT_GAP_CEILING;

  let contentDriftAssessment = 'content-match';
  if (
    boilerplateDominanceLikely
    && (overlap.heading >= HEADING_MAIN_OVERLAP_FLOOR || overlap.main >= HEADING_MAIN_OVERLAP_FLOOR)
    && (
      overlap.body + LENGTH_DRIFT_FLOOR < overlap.main
      || computeLengthDrift(expectedBodyLength, actualBodyLength) >= LENGTH_DRIFT_FLOOR
    )
  ) {
    contentDriftAssessment = 'comparison-noise-likely';
  } else if (markerOverlapRatio < CONTENT_GAP_CEILING && overlap.main < CONTENT_GAP_CEILING && overlap.heading < CONTENT_GAP_CEILING) {
    contentDriftAssessment = 'high-confidence-content-gap';
  } else if (markerOverlapRatio < PARTIAL_MATCH_CEILING) {
    contentDriftAssessment = 'partial-content-match';
  }

  const contentComparisonConfidence = boilerplateDominanceLikely
    ? 'medium'
    : (expectedProfile.markers.main.length === 0 && expectedProfile.markers.heading.length === 0)
      ? 'low'
      : 'high';
  const titleComparison = assessTitleComparison(pageInfo.title || '', actualProfile.title || '');

  return {
    markerOverlapRatio,
    contentDriftAssessment,
    contentComparisonConfidence,
    boilerplateDominanceLikely,
    titleComparison,
    markerExtractionProfile: {
      expected: {
        headingMarkers: expectedProfile.markers.heading.length,
        mainMarkers: expectedProfile.markers.main.length,
        bodyMarkers: expectedProfile.markers.body.length,
      },
      actual: {
        headingMarkers: actualMarkers.heading.length,
        mainMarkers: actualMarkers.main.length,
        bodyMarkers: actualMarkers.body.length,
      },
      overlap,
      sourcesUsed: buildMarkerSourceList(expectedProfile),
    },
  };
}

function buildExpectedContentProfile(pageInfo) {
  const html = pageInfo.processedHtml || pageInfo.decodedDocumentHtml || pageInfo.html || '';
  if (!html) {
    const title = pageInfo.title || '';
    return {
      markers: {
        heading: extractTextMarkers(title, 20),
        main: extractTextMarkers(title, 40),
        body: extractTextMarkers(title, 60),
      },
      lengths: {
        body: String(title).length,
      },
      sourcesUsed: ['title-fallback'],
    };
  }

  const $ = loadHtml(html, { decodeEntities: false });
  $('script, style, noscript').remove();
  const getTexts = (selectors, limit = 8) => selectors
    .flatMap((selector) => $(selector).slice(0, limit).toArray())
    .map((node) => $(node).text())
    .map((text) => text.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  const pickLongest = (selectors) => {
    const values = getTexts(selectors, 20).sort((left, right) => right.length - left.length);
    return values[0] || '';
  };

  const bodyText = ($('body').text() || $.root().text() || '').replace(/\s+/g, ' ').trim();
  const headingText = getTexts(['h1', 'h2', 'h3'], 8).join(' ');
  const mainText = pickLongest(['main', '[role="main"]', 'article', 'section']);

  return {
    markers: {
      heading: extractTextMarkers(`${pageInfo.title || ''} ${headingText}`, 24),
      main: extractTextMarkers(mainText || bodyText, 80),
      body: extractTextMarkers(`${pageInfo.title || ''} ${bodyText}`, 120),
    },
    lengths: {
      body: bodyText.length,
    },
    sourcesUsed: buildMarkerSourceList({
      headingText,
      mainText,
      bodyText,
    }),
  };
}

function buildMarkerSourceList(profile = {}) {
  const sources = [];
  if (profile.headingText || profile.markers?.heading?.length) sources.push('headings');
  if (profile.mainText || profile.markers?.main?.length) sources.push('main-content');
  if (profile.bodyText || profile.markers?.body?.length) sources.push('body-text');
  return sources.length > 0 ? sources : ['title-fallback'];
}

export function computeTokenOverlap(expected = [], actual = []) {
  if ((expected || []).length === 0) return 1;
  const actualSet = new Set((actual || []).map((token) => String(token).toLowerCase()));
  const hits = (expected || []).filter((token) => actualSet.has(String(token).toLowerCase())).length;
  return hits / expected.length;
}

function computeWeightedOverlap(overlap = {}, markers = {}) {
  const weights = [
    ['heading', 0.3],
    ['main', 0.5],
    ['body', 0.2],
  ];
  let totalWeight = 0;
  let score = 0;
  for (const [key, weight] of weights) {
    if ((markers[key] || []).length === 0) continue;
    totalWeight += weight;
    score += (overlap[key] || 0) * weight;
  }
  if (totalWeight === 0) return 1;
  return score / totalWeight;
}

function computeLengthDrift(expectedLength = 0, actualLength = 0) {
  if (!expectedLength) return 0;
  return Math.abs(actualLength - expectedLength) / expectedLength;
}

export function assessTitleComparison(expectedTitle = '', actualTitle = '') {
  const expectedNormalized = normalizeTitleForComparison(expectedTitle);
  const actualNormalized = normalizeTitleForComparison(actualTitle);
  const expectedNoise = looksLikeEncodingNoise(expectedTitle);
  const actualNoise = looksLikeEncodingNoise(actualTitle);
  const mismatchLikelyEncodingNoise = expectedNormalized !== actualNormalized && expectedNoise && actualNoise;

  return {
    normalizedExpected: expectedNormalized,
    normalizedActual: actualNormalized,
    confidence: mismatchLikelyEncodingNoise ? 'low' : (expectedNoise || actualNoise ? 'medium' : 'high'),
    mismatchLikelyEncodingNoise,
    shouldWarn: Boolean(expectedNormalized && actualNormalized && expectedNormalized !== actualNormalized && !mismatchLikelyEncodingNoise),
  };
}

function normalizeTitleForComparison(value = '') {
  return normalizeComparisonText(String(value || '')).toLowerCase();
}

function isCriticalAssetRequest(value) {
  return /\.(css|js|woff2?|ttf|svg|png|jpe?g|gif|webp)$/i.test(value || '');
}

function isNonCriticalApiRequest(value) {
  return isNonCriticalRuntime(value);
}

function classifyExternalRequest(value) {
  const url = safeParseUrl(value);
  const renderedUrl = url?.href || String(value || '');
  const host = url?.hostname || '';
  const classification = classifyExternalRuntime(renderedUrl);
  return {
    url: renderedUrl,
    host,
    category: classification.category,
    resourceHint: classification.resourceHint,
  };
}

function getExpectedRenderCriticalCandidates(pageInfo, apiArtifacts = {}) {
  return getReplayCandidatesForPage(pageInfo, apiArtifacts).filter((candidate) => candidate.expectedForReplay !== false);
}

function getSupportingReplayCandidates(pageInfo, apiArtifacts = {}) {
  return getReplayCandidatesForPage(pageInfo, apiArtifacts).filter((candidate) => candidate.expectedForReplay === false);
}

function getReplayCandidatesForPage(pageInfo, apiArtifacts = {}) {
  const pageKey = normalizeCrawlUrl(pageInfo.finalUrl || pageInfo.url);
  return (apiArtifacts.renderCriticalCandidates || []).filter((candidate) => candidate.normalizedPageUrl === pageKey);
}

function getBootstrapSignalsForPage(pageInfo = {}) {
  const signals = pageInfo.bootstrapSignals
    || pageInfo.replayBootstrapSignals
    || {};
  const hasRenderableStateFallback = Boolean(signals.hasRenderableStateFallback);
  const hasInlineBootstrapState = Boolean(signals.hasInlineBootstrapState);
  const hasFrameworkBootstrap = Boolean(signals.hasFrameworkBootstrap);
  const hasStreamingHydrationHints = Boolean(signals.hasStreamingHydrationHints);
  const bootstrapEvidenceLevel = signals.bootstrapEvidenceLevel
    || (
      hasRenderableStateFallback || hasInlineBootstrapState
        ? 'strong'
        : (hasFrameworkBootstrap || hasStreamingHydrationHints)
          ? 'partial'
          : 'none'
    );

  return {
    ...signals,
    hasRenderableStateFallback,
    hasInlineBootstrapState,
    hasFrameworkBootstrap,
    hasStreamingHydrationHints,
    bootstrapEvidenceLevel,
  };
}

function assessReplayDataState({
  bootstrapSignals = {},
  expectedRenderCritical = [],
  renderCriticalDiagnostics = { triggered: [], missed: [] },
  supportingReplayCandidates = [],
  supportingDiagnostics = { triggered: [], missed: [] },
}) {
  const hasBootstrapEvidence = bootstrapSignals.bootstrapEvidenceLevel === 'strong'
    || Boolean(bootstrapSignals.hasRenderableStateFallback || bootstrapSignals.hasInlineBootstrapState || bootstrapSignals.hasFrameworkBootstrap);

  if (expectedRenderCritical.length > 0 && renderCriticalDiagnostics.missed.length > 0) {
    return 'strict-runtime-missed';
  }

  if (hasBootstrapEvidence && supportingReplayCandidates.length > 0 && supportingDiagnostics.triggered.length === 0) {
    return 'bootstrap-backed-supporting-refresh-skipped';
  }

  if (hasBootstrapEvidence && expectedRenderCritical.length === 0) {
    return 'bootstrap-backed-first-paint';
  }

  if (!hasBootstrapEvidence && expectedRenderCritical.length > 0) {
    return 'strict-runtime-required';
  }

  return 'html-shell-only';
}

function analyzeReplayCandidates({ candidates, observedApiRequests, externalRequests, manifest }) {
  const triggered = [];
  const missed = [];
  const externalRequestSet = new Set((externalRequests || []).map((value) => normalizeAbsoluteRequestUrl(value)));

  for (const candidate of candidates || []) {
    const observedRequest = (observedApiRequests || []).find((request) => requestMatchesCandidate(request, candidate));
    if (observedRequest) {
      triggered.push({
        method: candidate.method,
        replayPath: candidate.replayPath,
        renderCriticalKind: candidate.renderCriticalKind,
        operationName: candidate.operationName,
        firstPaintDependency: candidate.firstPaintDependency || 'strict',
        classificationReason: candidate.classificationReason || 'unclassified',
        dependencyEvidence: candidate.dependencyEvidence || [],
      });

      if (!findHttpMockMatch(manifest, observedRequest)) {
        missed.push({
          method: candidate.method,
          replayPath: candidate.replayPath,
          renderCriticalKind: candidate.renderCriticalKind,
          operationName: candidate.operationName,
          firstPaintDependency: candidate.firstPaintDependency || 'strict',
          classificationReason: candidate.classificationReason || 'unclassified',
          dependencyEvidence: candidate.dependencyEvidence || [],
          reason: 'mock-miss',
        });
      }
      continue;
    }

    missed.push({
      method: candidate.method,
      replayPath: candidate.replayPath,
      renderCriticalKind: candidate.renderCriticalKind,
      operationName: candidate.operationName,
      firstPaintDependency: candidate.firstPaintDependency || 'strict',
      classificationReason: candidate.classificationReason || 'unclassified',
      dependencyEvidence: candidate.dependencyEvidence || [],
      reason: externalRequestSet.has(normalizeAbsoluteRequestUrl(candidate.url)) ? 'rewrite-missed' : 'not-triggered',
    });
  }

  return { triggered, missed };
}

function requestMatchesCandidate(request, candidate) {
  if (!request || !candidate) return false;
  if (request.method !== candidate.method) return false;
  if (request.path !== candidate.path) return false;
  if (normalizeSearch(request.search) !== normalizeSearch(candidate.search)) return false;
  if (!candidate.graphQL) return true;
  return (request.operationName || null) === (candidate.operationName || null)
    && (request.variablesHash || 'no-body') === (candidate.variablesHash || 'no-body');
}

function buildObservedApiRequest(request) {
  const url = new URL(request.url());
  const body = safeParseJson(request.postData());
  const pathname = url.pathname.replace(/^\/api/, '') || '/';

  return {
    method: request.method(),
    path: pathname,
    search: normalizeSearch(url.search),
    bodyHash: hashValue(body),
    operationName: typeof body?.operationName === 'string' ? body.operationName : null,
    documentHash: hashValue(typeof body?.query === 'string' ? body.query : null),
    variablesHash: hashValue(body?.variables ?? null),
    extensionsHash: hashValue(body?.extensions ?? null),
  };
}

function safeParseJson(value) {
  if (!value) return null;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function summarizeExternalRequests(detailMap) {
  const summary = {
    'render-critical-asset': 0,
    'render-critical-runtime': 0,
    'non-critical-runtime': 0,
    'anti-abuse': 0,
  };

  for (const detail of detailMap.values()) {
    summary[detail.category] = (summary[detail.category] || 0) + 1;
  }

  return summary;
}

function summarizeRuntimeErrors(pageResults = []) {
  return pageResults.reduce((summary, page) => {
    summary.consoleErrors += page.runtimeErrorSummary?.consoleErrors || 0;
    summary.runtimeExceptions += page.runtimeErrorSummary?.runtimeExceptions || 0;
    summary.failedRuntimeRequests += page.runtimeErrorSummary?.failedRuntimeRequests || 0;
    for (const [failureClass, count] of Object.entries(page.runtimeFailureClasses || {})) {
      summary.failureClasses[failureClass] = (summary.failureClasses[failureClass] || 0) + count;
    }
    if ((page.runtimeErrorSummary?.total || 0) > 0) {
      summary.pagesWithRuntimeErrors += 1;
    }
    if (page.runtimeFailureSeverity === 'soft') {
      summary.pagesWithSoftRuntimeDegrade += 1;
    }
    summary.total += page.runtimeErrorSummary?.total || 0;
    return summary;
  }, {
    consoleErrors: 0,
    runtimeExceptions: 0,
    failedRuntimeRequests: 0,
    pagesWithRuntimeErrors: 0,
    pagesWithSoftRuntimeDegrade: 0,
    total: 0,
    failureClasses: {},
  });
}

export function classifyRuntimeConsoleMessage(text, runtimeOrigin) {
  const normalized = String(text || '').trim();
  if (!normalized) {
    return { category: 'unknown', warningEligible: false };
  }

  const lower = normalized.toLowerCase();
  const hasExternalUrl = /https?:\/\//i.test(normalized) && !normalized.includes(runtimeOrigin);
  if ((/failed to load resource|net::err_|blocked by client|access to fetch/i.test(lower)) && hasExternalUrl) {
    return { category: 'external-runtime-noise', warningEligible: false };
  }

  if (/hydrat/i.test(lower)) {
    return { category: 'hydration-failure', warningEligible: true };
  }
  if (/chunk|loading chunk|importing a module script failed|module script/i.test(lower)) {
    return { category: 'chunk-load-failure', warningEligible: true };
  }

  return { category: 'runtime-console-error', warningEligible: true };
}

function buildRuntimeDiagnostics({
  consoleErrors = [],
  runtimeExceptions = [],
  failedRuntimeRequests = [],
  runtimeGuardState = null,
  runtimeOrigin = '',
}) {
  const sameOriginRuntimeExceptions = dedupeRuntimeExceptions([
    ...runtimeExceptions.map((entry) => ({
      ...entry,
      source: entry.source || 'pageerror',
      sameOrigin: true,
      failureClass: classifySameOriginRuntimeException(entry),
    })),
    ...((runtimeGuardState?.exceptions || []).map((entry) => ({
      ...entry,
      sameOrigin: entry.sameOrigin !== false,
      failureClass: entry.failureClass || classifySameOriginRuntimeException(entry),
    }))),
  ]);

  const sameOriginRuntimeMisses = dedupeRuntimeRequests([
    ...failedRuntimeRequests.map((entry) => classifyRuntimeRequestFailure(entry, runtimeOrigin)),
    ...((runtimeGuardState?.resourceErrors || []).map((entry) => classifyRuntimeRequestFailure(entry, runtimeOrigin))),
  ].filter((entry) => entry.sameOrigin));

  const failureClasses = summarizeRuntimeFailureClasses(sameOriginRuntimeExceptions, sameOriginRuntimeMisses);
  const summary = {
    consoleErrors: consoleErrors.length,
    runtimeExceptions: sameOriginRuntimeExceptions.length,
    failedRuntimeRequests: sameOriginRuntimeMisses.length,
    total: consoleErrors.length + sameOriginRuntimeExceptions.length + sameOriginRuntimeMisses.length,
  };
  const warningCodes = [];

  if (consoleErrors.some((entry) => entry.warningEligible !== false)) {
    warningCodes.push('runtime-console-error');
  }
  if (sameOriginRuntimeExceptions.length > 0) {
    warningCodes.push('runtime-exception');
  }
  if (sameOriginRuntimeMisses.some((entry) => entry.failureClass === 'runtime-script-failed')) {
    warningCodes.push('runtime-script-failed');
  } else if (sameOriginRuntimeMisses.some((entry) => entry.failureClass === 'runtime-style-failed')) {
    warningCodes.push('runtime-style-failed');
  } else if (sameOriginRuntimeMisses.some((entry) => entry.failureClass !== 'runtime-resource-missing')) {
    warningCodes.push('runtime-request-failed');
  }

  return {
    consoleErrors,
    runtimeExceptions: sameOriginRuntimeExceptions,
    failedRuntimeRequests: sameOriginRuntimeMisses,
    sameOriginRuntimeExceptions,
    sameOriginRuntimeMisses,
    failureClasses,
    summary,
    warningCodes,
  };
}

export function classifySameOriginRuntimeException(entry = {}) {
  const lower = String(entry?.message || '').toLowerCase();
  if (/(cannot (set|read) properties of null|cannot (set|read) properties of undefined|null is not an object|undefined is not an object|appendchild|removechild|insertbefore|queryselector)/.test(lower)) {
    return 'runtime-dom-assumption';
  }
  if (/chunk|module script|loading chunk|importing a module script failed/.test(lower)) {
    return 'runtime-script-failed';
  }
  return 'runtime-exception';
}

export function classifyRuntimeRequestFailure(entry = {}, runtimeOrigin = '') {
  const url = String(entry.url || '');
  const parsed = safeParseUrl(url);
  const sameOrigin = entry.sameOrigin ?? Boolean(parsed && parsed.origin === runtimeOrigin);
  const resourceType = String(entry.resourceType || '').toLowerCase();
  const mimeHint = String(entry.mimeType || entry.responseMimeType || '').toLowerCase();
  const pathLower = parsed ? parsed.pathname.toLowerCase() : '';

  let failureClass = entry.failureClass || 'runtime-resource-missing';
  if (sameOrigin) {
    if (resourceType === 'script' || resourceType === 'module') {
      failureClass = 'runtime-script-failed';
    } else if (resourceType === 'stylesheet' || resourceType === 'style') {
      failureClass = 'runtime-style-failed';
    } else if (resourceType === 'fetch' || resourceType === 'xhr' || mimeHint.includes('json') || mimeHint.includes('xml') || /\.(json|xml|api)\b/.test(pathLower)) {
      failureClass = 'runtime-data-miss';
    } else if (resourceType === 'image' || resourceType === 'font' || /\.(png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|otf)\b/.test(pathLower)) {
      failureClass = 'runtime-asset-miss';
    } else if (!entry.failureClass) {
      failureClass = 'runtime-resource-missing';
    }
  }

  return {
    ...entry,
    url,
    sameOrigin,
    resourceType: resourceType || 'resource',
    failureClass,
  };
}

function summarizeRuntimeFailureClasses(runtimeExceptions = [], runtimeMisses = []) {
  const summary = {};
  for (const entry of [...runtimeExceptions, ...runtimeMisses]) {
    const failureClass = String(entry.failureClass || '').trim();
    if (!failureClass) continue;
    summary[failureClass] = (summary[failureClass] || 0) + 1;
  }
  return summary;
}

function dedupeRuntimeRequests(requests = []) {
  const seen = new Set();
  const deduped = [];
  for (const request of requests) {
    const key = `${request.resourceType || ''}|${request.status || ''}|${request.url || ''}|${request.failureText || ''}|${request.failureClass || ''}|${request.sameOrigin ? 'same' : 'cross'}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(request);
  }
  return deduped;
}

function dedupeRuntimeExceptions(exceptions = []) {
  const seen = new Set();
  const deduped = [];
  for (const entry of exceptions) {
    const key = `${entry.name || ''}|${entry.message || ''}|${entry.source || ''}|${entry.failureClass || ''}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(entry);
  }
  return deduped;
}

export function assessRuntimeFailureState({
  routeReached = false,
  criticalLocatorPresent = false,
  expectedRenderCritical = [],
  runtimeDiagnostics = {},
}) {
  const hasStrictDependencies = (expectedRenderCritical || []).length > 0;
  const exceptionClasses = new Set((runtimeDiagnostics.sameOriginRuntimeExceptions || []).map((entry) => entry.failureClass));
  const missClasses = new Set((runtimeDiagnostics.sameOriginRuntimeMisses || []).map((entry) => entry.failureClass));
  const hasDomAssumption = exceptionClasses.has('runtime-dom-assumption');
  const hasScriptFailure = exceptionClasses.has('runtime-script-failed') || missClasses.has('runtime-script-failed');
  const hasStyleFailure = missClasses.has('runtime-style-failed');
  const hasResourceMiss = missClasses.has('runtime-resource-missing');
  const hasDataMiss = missClasses.has('runtime-data-miss');
  const hasAssetMiss = missClasses.has('runtime-asset-miss');
  const hasOnlySoftMisses = !hasResourceMiss && !hasScriptFailure && !hasStyleFailure && (hasDataMiss || hasAssetMiss);

  if (!routeReached) {
    return {
      assessment: 'route-failed',
      severity: 'high',
      scope: 'page',
      suspectedFailureChain: 'route-unreachable',
    };
  }

  if (hasScriptFailure) {
    return {
      assessment: 'runtime-script-degraded',
      severity: 'high',
      scope: 'page',
      suspectedFailureChain: hasDomAssumption ? 'script-led-runtime-failure' : 'script-runtime-failure',
    };
  }

  if (hasStyleFailure) {
    return {
      assessment: 'runtime-style-degraded',
      severity: criticalLocatorPresent ? 'medium' : 'high',
      scope: criticalLocatorPresent ? 'widget' : 'page',
      suspectedFailureChain: 'style-runtime-failure',
    };
  }

  if (hasDomAssumption) {
    const softEligible = criticalLocatorPresent && !hasStrictDependencies;
    const dataOrAssetLed = hasOnlySoftMisses && !hasResourceMiss;
    return {
      assessment: softEligible ? 'runtime-widget-soft-fail' : 'runtime-page-degraded',
      severity: softEligible ? 'soft' : 'high',
      scope: softEligible ? 'widget' : 'page',
      suspectedFailureChain: hasResourceMiss
        ? 'resource-led-dom-assumption'
        : dataOrAssetLed
          ? 'data-or-asset-led-dom-assumption'
          : 'isolated-dom-assumption',
    };
  }

  if (hasResourceMiss) {
    return {
      assessment: 'runtime-resource-soft-miss',
      severity: 'soft',
      scope: 'widget',
      suspectedFailureChain: 'resource-soft-miss',
    };
  }

  if (hasDataMiss || hasAssetMiss) {
    return {
      assessment: 'runtime-resource-soft-miss',
      severity: 'soft',
      scope: 'widget',
      suspectedFailureChain: hasDataMiss ? 'data-soft-miss' : 'asset-soft-miss',
    };
  }

  if ((runtimeDiagnostics.summary?.total || 0) > 0) {
    return {
      assessment: 'runtime-warning-only',
      severity: 'low',
      scope: 'unknown',
      suspectedFailureChain: 'warning-only',
    };
  }

  return {
    assessment: 'runtime-clean',
    severity: 'none',
    scope: 'none',
    suspectedFailureChain: 'none',
  };
}

function buildPageRouteLookup(pageRouteManifest = { routes: [] }) {
  const lookup = new Map();

  for (const route of pageRouteManifest.routes || []) {
    if (!route.replayable || !route.savedPath) continue;
    for (const routePath of [route.replayRoute, ...(route.routeAliases || [])]) {
      const normalizedRoute = normalizeRoutePath(routePath);
      if (!normalizedRoute) continue;
      lookup.set(normalizedRoute, route);
    }
  }

  return lookup;
}

function normalizeRoutePath(value) {
  const normalized = String(value || '/').replace(/\\/g, '/').replace(/\/+$/, '');
  return normalized || '/';
}

function safeParseUrl(value) {
  try {
    return new URL(value);
  } catch {
    return null;
  }
}

async function readJson(filePath, fallback) {
  try {
    const raw = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}
