import path from 'path';
import * as cheerio from 'cheerio';

import PageCrawler from './crawler/page-crawler.js';
import SiteCrawler from './crawler/site-crawler.js';
import AssetDownloader from './downloader/asset-downloader.js';
import HtmlProcessor from './processor/html-processor.js';
import CssProcessor from './processor/css-processor.js';
import JsProcessor from './processor/js-processor.js';
import ComputedStyleExtractor from './processor/computed-style-extractor.js';
import ApiProcessor from './processor/api-processor.js';
import ProjectScaffolder from './scaffolder/project-scaffolder.js';
import VisualAnalyzer from './analyzer/visual-analyzer.js';
import IntegrationDocGenerator from './processor/integration-doc-generator.js';
import { runReplayVerification } from './verifier/replay-verifier.js';
import {
  ensureDir,
  removePath,
  saveFile,
} from './utils/file-utils.js';
import { downloadExternalImages, injectCapturedImages } from './utils/image-utils.js';
import { batchParallel } from './utils/concurrency-utils.js';
import { PAGE_PROCESSING_CONCURRENCY } from './utils/constants.js';
import {
  normalizeCrawlUrl,
} from './utils/url-utils.js';
import { hashContent, writeManifest } from './utils/manifest-writer.js';
import logger from './utils/logger.js';
import { ensurePlaywrightRuntimeReady } from './utils/playwright-runtime.js';
import {
  buildRenderCriticalRuntimeMap,
} from './utils/replay-mock-utils.js';
import { summarizeEncodingDiagnosis } from './utils/encoding-utils.js';
import {
  DEFAULT_CRAWL_PROFILE,
  DEFAULT_NETWORK_POSTURE,
  resolveCrawlProfile,
  resolveNetworkPosture,
} from './utils/crawl-config.js';
import {
  dedupeCapturedPages as _dedupeCapturedPages,
} from './pipeline/page-dedup.js';
import {
  buildPageRouteManifest as _buildPageRouteManifest,
  buildPageRouteIndex as _buildPageRouteIndex,
  buildPagePathFallbackMap as _buildPagePathFallbackMap,
  normalizeRouteLookupPath as _normalizeRouteLookupPath,
} from './pipeline/page-route-manifest.js';
import {
  buildPageReplaySignals as _buildPageReplaySignals,
  extractPageReplaySignals as _extractPageReplaySignals,
} from './pipeline/replay-signals.js';
import {
  finalizeOutput as _finalizeOutput,
  getOutputDomainRoot as _getOutputDomainRoot,
  resolveOutputDirForRun as _resolveOutputDirForRun,
  isRetriableFilesystemConflict as _isRetriableFilesystemConflict,
  withFilesystemRetry as _withFilesystemRetry,
  buildOutputFinalizeError as _buildOutputFinalizeError,
} from './pipeline/output-finalize.js';

const CANONICAL_OUTPUT_PARENT = path.resolve('./output');

function checkAborted(signal) {
  if (signal?.aborted) {
    throw new Error('Operation cancelled');
  }
}

export async function cloneFrontend(options) {
  const startTime = Date.now();
  const context = await createRunContext(options);

  console.log('');
  logger.info(`Target URL: ${context.options.url}`);
  logger.info(`Output directory: ${context.outputDir}`);
  logger.info(`Staging directory: ${context.stagingDir}`);
  logger.info(`Domain scope: ${context.domainScope}`);
  console.log('');

  const signal = options.signal || null;

  try {
    checkAborted(signal);
    await ensurePlaywrightRuntimeReady();

    checkAborted(signal);
    await prepareStagingArea(context);

    checkAborted(signal);
    const capture = await capturePages(context, signal);

    checkAborted(signal);
    const apiArtifacts = await prepareApiArtifacts(context, capture);

    checkAborted(signal);
    const transformed = await transformCapturedOutput(context, capture, apiArtifacts);

    checkAborted(signal);
    const artifacts = await generateArtifacts(context, capture, transformed, apiArtifacts);

    const qualitySummary = buildQualitySummary(capture, artifacts);

    checkAborted(signal);
    await finalizeOutput(context);

    const duration = ((Date.now() - startTime) / 1000).toFixed(1);
    logger.succeed(`Clone completed! (${duration}s)`);
    logger.info(`Saved output to: ${context.outputDir}`);

    return {
      outputDir: context.outputDir,
      pageCount: capture.pages.length,
      entryPagePath: transformed.entryPagePath,
      apiSummary: artifacts.apiArtifacts.apiSummary,
      verificationWarnings: artifacts.verificationWarnings,
      qualitySummary,
      artifacts: artifacts.artifactPaths,
    };
  } catch (err) {
    console.error('[Unexpected Error]');
    console.error(err.stack);
    if (err.details) {
      logger.error(err.details);
    }
    if (err.hint) {
      logger.warn(err.hint);
    }
    logger.error(`Operation failed: ${err.message}`);
    await removePath(context.stagingDir).catch(() => {});
    throw err;
  }
}

export const getOutputDomainRoot = _getOutputDomainRoot;

export const resolveOutputDirForRun = _resolveOutputDirForRun;

export const dedupeCapturedPages = _dedupeCapturedPages;

export const buildPagePathFallbackMap = _buildPagePathFallbackMap;

export const buildPageRouteManifest = _buildPageRouteManifest;

export const buildPageRouteIndex = _buildPageRouteIndex;

async function createRunContext(options) {
  const normalizedOptions = {
    ...options,
    output: options.output || './output',
    domainScope: options.domainScope || 'registrable-domain',
    visualAnalysis: options.visualAnalysis || 'docs',
    crawlProfile: options.crawlProfile || DEFAULT_CRAWL_PROFILE,
    networkPosture: options.networkPosture || DEFAULT_NETWORK_POSTURE,
    enableRepresentativeQA: Boolean(options.enableRepresentativeQA),
  };

  if (normalizedOptions.output && path.resolve(normalizedOptions.output) !== CANONICAL_OUTPUT_PARENT) {
    logger.warn('Custom output directories are ignored. Generated packages are always written under ./output/<main-domain>.');
  }

  const outputParent = CANONICAL_OUTPUT_PARENT;
  const domainRoot = getOutputDomainRoot(normalizedOptions.url);
  const shouldUpdate = Boolean(normalizedOptions.updateExisting);
  const outputResolution = await resolveOutputDirForRun(outputParent, domainRoot, {
    updateExisting: shouldUpdate,
  });
  const outputDir = outputResolution.outputDir;
  const stageRoot = path.join(outputParent, '.front-clone-tmp');
  const runId = `${outputResolution.outputLabel}-${Date.now()}-${process.pid}`;
  const stagingDir = path.join(stageRoot, runId);

  return {
    options: normalizedOptions,
    outputParent,
    outputDir,
    domainRoot,
    outputLabel: outputResolution.outputLabel,
    domainScope: normalizedOptions.domainScope,
    shouldUpdate,
    captureVisualDocs: normalizedOptions.visualAnalysis !== 'off',
    stagingDir,
    publicDir: path.join(stagingDir, 'public'),
    viewsDir: path.join(stagingDir, 'views'),
    serverDir: path.join(stagingDir, 'server'),
    captureDir: path.join(stagingDir, 'server', 'debug'),
  };
}

async function prepareStagingArea(context) {
  await ensureDir(context.outputParent);
  await ensureDir(path.dirname(context.stagingDir));
  await removePath(context.stagingDir);
  await ensureDir(context.stagingDir);
  await ensureDir(context.publicDir);
  await ensureDir(context.viewsDir);
  await ensureDir(context.serverDir);
  await ensureDir(context.captureDir);
}

async function capturePages(context, signal = null) {
  const { options, captureVisualDocs } = context;

  if (options.recursive) {
    const siteCrawler = new SiteCrawler({
      url: options.url,
      waitTime: options.waitTime,
      viewport: options.viewport,
      screenshot: options.screenshot || captureVisualDocs,
      scrollCount: options.scrollCount,
      maxPages: options.maxPages,
      maxDepth: options.maxDepth,
      concurrency: options.concurrency,
      followLoginGated: options.followLoginGated,
      storageState: options.storageState,
      cookieFile: options.cookieFile,
      headful: options.headful,
      domainScope: context.domainScope,
      captureDir: context.captureDir,
      crawlProfile: options.crawlProfile,
      networkPosture: options.networkPosture,
      enableRepresentativeQA: options.enableRepresentativeQA,
      interactionBudget: options.interactionBudget,
      enableGraphqlIntrospection: options.enableGraphqlIntrospection,
      signal,
    });

    const crawlResult = await siteCrawler.crawlAll();
    if (!crawlResult.results || crawlResult.results.length === 0) {
      const lastError = crawlResult.lastFailure || crawlResult.siteMap.find((item) => item.crawlState === 'failed')?.error;
      throw new Error(
        lastError
          ? `No page content could be captured. Last error: ${lastError}`
          : 'No page content could be captured.',
      );
    }

    return {
      pages: crawlResult.results,
      interceptor: crawlResult.interceptor,
      siteMap: crawlResult.siteMap,
    };
  }

  const pageCrawler = new PageCrawler({
    url: options.url,
    waitTime: options.waitTime,
    viewport: options.viewport,
    screenshot: options.screenshot || captureVisualDocs,
    scrollCount: options.scrollCount,
    storageState: options.storageState,
    cookieFile: options.cookieFile,
    headful: options.headful,
    captureDir: context.captureDir,
    crawlProfile: options.crawlProfile,
    networkPosture: options.networkPosture,
    enableRepresentativeQA: options.enableRepresentativeQA,
    interactionBudget: options.interactionBudget,
    enableGraphqlIntrospection: options.enableGraphqlIntrospection,
    signal,
  });

  const crawlResult = await pageCrawler.crawl();
  const finalUrl = crawlResult.finalUrl || options.url;

  return {
    pages: [
      {
        url: options.url,
        finalUrl,
        html: crawlResult.html,
        computedStyles: crawlResult.computedStyles,
        liveImageUrls: crawlResult.liveImageUrls,
        screenshot: crawlResult.screenshot,
        depth: 0,
        isLogin: false,
        forms: crawlResult.forms,
        interactiveElements: crawlResult.interactiveElements,
        title: crawlResult.title,
        documentEncoding: crawlResult.documentEncoding,
        classification: crawlResult.classification,
        crawlProfile: crawlResult.crawlProfile,
        networkPosture: crawlResult.networkPosture,
        qa: crawlResult.qa,
        status: crawlResult.status,
        storageState: crawlResult.storageState,
        sessionStorageState: crawlResult.sessionStorageState,
        graphqlArtifacts: crawlResult.graphqlArtifacts,
        captureWarnings: crawlResult.captureWarnings,
        linkCandidates: crawlResult.linkCandidates || [],
        discoveredFrom: null,
        skippedReason: null,
      },
    ],
    interceptor: crawlResult.interceptor,
    siteMap: [
      {
        url: options.url,
        finalUrl,
        normalizedUrl: normalizeCrawlUrl(finalUrl),
        depth: 0,
        status: crawlResult.status,
        discoveredFrom: null,
        title: crawlResult.title,
        documentEncoding: crawlResult.documentEncoding,
        loginGated: false,
        skippedReason: null,
        crawlState: 'completed',
        linksFound: crawlResult.internalLinks.length,
        linkCandidatesSeen: crawlResult.linkCandidates?.length || crawlResult.internalLinks.length,
        linksSelected: 0,
        frontierTopCandidates: [],
        selectionReasons: [],
      },
    ],
  };
}

async function transformCapturedOutput(context, capture, apiArtifacts) {
  const includeHostPrefix = Boolean(context.options.recursive) && context.domainScope === 'registrable-domain';
  const deduped = dedupeCapturedPages(capture.pages, capture.siteMap, { includeHostPrefix });
  capture.pages = deduped.pages;
  capture.siteMap = deduped.siteMap;
  const pageUrlMap = deduped.pageUrlMap;
  const pageRouteManifest = buildPageRouteManifest(capture.siteMap, capture.pages, capture.pages[0]?.savedPath || 'index.html');
  const pageRouteIndex = buildPageRouteIndex(pageRouteManifest);

  const downloader = new AssetDownloader(context.stagingDir, context.options.url);
  const fullUrlMap = await downloader.downloadAll(capture.interceptor);
  await downloader.recoverFailedAssets(capture.interceptor.getFailedRequests());
  for (const [url, localPath] of pageUrlMap) {
    fullUrlMap.set(url, localPath);
  }
  const renderCriticalRuntimeMap = buildRenderCriticalRuntimeMap(apiArtifacts.filteredRequests || []);

  const cssProcessor = new CssProcessor(context.stagingDir, context.options.url, fullUrlMap, capture.interceptor, {
    assetRegistry: downloader,
  });
  const jsProcessor = new JsProcessor(context.stagingDir, context.options.url, fullUrlMap, {
    renderCriticalRuntimeMap,
  });
  const [cssResult] = await Promise.all([cssProcessor.processAll(), jsProcessor.processAll()]);

  await batchParallel(capture.pages, PAGE_PROCESSING_CONCURRENCY, async (page) => {
    const pageHtmlProcessor = new HtmlProcessor(page.finalUrl || page.url, {
      useBaseHref: true,
      renderCriticalRuntimeMap,
      pageRouteIndex,
    });
    let processedHtml = pageHtmlProcessor.process(page.html, fullUrlMap, page.savedPath);

    if (page.computedStyles) {
      const $ = cheerio.load(processedHtml, { decodeEntities: false });
      ComputedStyleExtractor.injectIntoHtml($, page.computedStyles);
      processedHtml = $.html();
    }

    const extraImages = await downloadExternalImages(
      processedHtml,
      context.publicDir,
      fullUrlMap,
      capture.interceptor,
      page.liveImageUrls,
      context.options.url,
      downloader,
    );

    if (extraImages.savedCount > 0) {
      processedHtml = pageHtmlProcessor.process(processedHtml, fullUrlMap, page.savedPath);
    }

    processedHtml = injectCapturedImages(processedHtml, fullUrlMap);
    await saveFile(path.join(context.viewsDir, page.savedPath), processedHtml);
    page.processedHtml = processedHtml;

    logger.info(`Saved HTML: views/${page.savedPath}`);
  });

  const entryPagePath = capture.pages[0].savedPath;

  if (context.captureVisualDocs) {
    await persistScreenshots(context.stagingDir, capture.pages);
  }

  return {
    entryPagePath,
    entryReplayRoute: pageRouteManifest.entryReplayRoute,
    fullUrlMap,
    resourceManifestEntries: downloader.getResourceManifestEntries(),
    pageRouteManifest,
    cssRecoverySummary: cssResult.cssRecoverySummary,
  };
}

async function generateArtifacts(context, capture, transformed, apiArtifacts) {
  const websocketEvents = capture.interceptor.getWebsocketEvents();

  const integrationDocGenerator = new IntegrationDocGenerator(context.stagingDir);
  await integrationDocGenerator.generate({
    pages: capture.pages,
    requests: apiArtifacts.filteredRequests,
    websocketEvents,
  });

  if (context.captureVisualDocs) {
    const visualAnalyzer = new VisualAnalyzer(context.stagingDir);
    await visualAnalyzer.generate(capture.pages);
  }

  annotatePagesWithEncodingDiagnostics(capture.pages, capture.interceptor);
  const assetManifest = buildAssetManifest(capture.interceptor, transformed.fullUrlMap, transformed.resourceManifestEntries);
  annotatePagesWithRenderCriticalCandidates(capture.pages, apiArtifacts.renderCriticalCandidates || []);
  const pageManifest = buildPageManifest(capture.siteMap, capture.pages);
  const pageQualityReport = buildPageQualityReport(capture.pages, assetManifest, transformed.cssRecoverySummary);

  await writeManifest(context.stagingDir, {
    generatedAt: new Date().toISOString(),
    startUrl: context.options.url,
    domainRoot: context.domainRoot,
    domainScope: context.domainScope,
    resumeManifest: context.options.resumeManifest || null,
    updateExisting: context.shouldUpdate,
    pages: pageManifest,
    assets: assetManifest,
    pageQualityReport,
    cssRecoverySummary: transformed.cssRecoverySummary,
    crawlProfile: buildCrawlProfileManifest(context.options, capture.pages),
    pageRoutes: transformed.pageRouteManifest,
  });

  if (context.options.scaffold !== false) {
    const scaffolder = new ProjectScaffolder(context.stagingDir, new URL(context.options.url).hostname);
    await scaffolder.scaffold({
      entryPagePath: transformed.entryPagePath,
      entryReplayRoute: transformed.entryReplayRoute,
      apiSummary: apiArtifacts.apiSummary,
      siteMap: capture.siteMap,
      pages: capture.pages,
      cssRecoverySummary: transformed.cssRecoverySummary,
      httpManifest: apiArtifacts.httpManifest,
    });
  }

  const verifierResult = await runReplayVerification({
    outputDir: context.stagingDir,
    startUrl: context.options.url,
    pages: capture.pages,
    apiArtifacts,
    sampleSize: resolveCrawlProfile(context.options.crawlProfile).replayValidationSampleSize,
  });

  return {
    apiArtifacts,
    verificationWarnings: verifierResult.verificationWarnings,
    verificationReport: verifierResult.report,
    artifactPaths: {
      openApiSpec: 'server/spec/openapi.json',
      asyncApiSpec: 'server/spec/asyncapi.json',
      graphqlOperations: 'server/spec/graphql/operations.json',
      graphqlSchema: apiArtifacts.graphqlArtifacts?.length ? 'server/spec/graphql/schema.json' : null,
      replayVerificationReport: verifierResult.artifacts.replayVerificationReport,
      replayVerificationJson: verifierResult.artifacts.replayVerificationJson,
    },
  };
}

async function prepareApiArtifacts(context, capture) {
  const xhrRequests = capture.interceptor.getXhrRequests();
  const websocketEvents = capture.interceptor.getWebsocketEvents();
  const graphqlArtifacts = capture.pages.flatMap((page) => page.graphqlArtifacts || []);
  const pageReplaySignals = buildPageReplaySignals(capture.pages);

  const apiProcessor = new ApiProcessor(
    context.stagingDir,
    context.options.url,
    context.domainScope,
    pageReplaySignals,
  );
  return apiProcessor.generateArtifacts(xhrRequests, websocketEvents, graphqlArtifacts);
}

const buildPageReplaySignals = _buildPageReplaySignals;

export const extractPageReplaySignals = _extractPageReplaySignals;

const finalizeOutput = _finalizeOutput;
export const isRetriableFilesystemConflict = _isRetriableFilesystemConflict;
export const withFilesystemRetry = _withFilesystemRetry;
export const buildOutputFinalizeError = _buildOutputFinalizeError;

function buildPageManifest(siteMap, pages) {
  const pagesByUrl = new Map();
  for (const page of pages) {
    const key = normalizeCrawlUrl(page.finalUrl || page.url);
    pagesByUrl.set(key, page);
  }

  return siteMap.map((item) => {
    const page = pagesByUrl.get(item.normalizedUrl);
    const hiddenNavigationSummary = extractHiddenNavigationSummary(page?.processedHtml || page?.html || '');
    const encodingDiagnostics = summarizeEncodingDiagnosis(page?.encodingDiagnostics || {});
    return {
      url: item.url,
      finalUrl: item.finalUrl,
      normalizedUrl: item.normalizedUrl,
      savedPath: page?.savedPath || null,
      replayRoute: page?.replayRoute || null,
      routeAliases: page?.replayRouteAliases || [],
      host: page?.host || (item.finalUrl ? new URL(item.finalUrl).hostname : null),
      depth: item.depth,
      discoveredFrom: item.discoveredFrom,
      status: item.status,
      title: item.title || '',
      detectedCharset: encodingDiagnostics.encoding || item.documentEncoding || page?.documentEncoding || null,
      encodingSource: encodingDiagnostics.encodingSource,
      decodeConfidence: encodingDiagnostics.decodeConfidence,
      suspectedEncodingMismatch: encodingDiagnostics.suspectedEncodingMismatch,
      encodingEvidence: encodingDiagnostics.encodingEvidence,
      loginGated: item.loginGated,
      crawlState: item.crawlState || 'completed',
      replayable: Boolean(page?.savedPath && page?.replayRoute),
      skippedReason: item.skippedReason || null,
      error: item.error || null,
      linksFound: item.linksFound ?? page?.internalLinks?.length ?? 0,
      pageClass: item.pageClass || page?.classification?.pageClass || 'document',
      queueBudget: item.queueBudget ?? page?.classification?.queueBudget ?? null,
      linkCandidatesSeen: item.linkCandidatesSeen ?? page?.linkCandidates?.length ?? 0,
      linksSelected: item.linksSelected ?? 0,
      frontierTopCandidates: item.frontierTopCandidates || [],
      selectionReasons: item.selectionReasons || [],
      bootstrapSignals: page?.bootstrapSignals || page?.replayBootstrapSignals || {},
      replayBootstrapSignals: page?.replayBootstrapSignals || {},
      replayCandidates: page?.replayCandidates || [],
      expectedRenderCriticalCandidates: page?.expectedRenderCriticalCandidates || [],
      renderCriticalCandidates: page?.renderCriticalCandidates || [],
      hiddenNavigationSummary,
      contentHash: page ? hashContent(page.processedHtml || page.html || '') : null,
    };
  });
}

function annotatePagesWithRenderCriticalCandidates(pages, renderCriticalCandidates) {
  const groupedCandidates = new Map();

  for (const candidate of renderCriticalCandidates || []) {
    const pageKey = normalizeCrawlUrl(candidate.pageUrl || '');
    if (!pageKey) continue;
    const current = groupedCandidates.get(pageKey) || [];
    current.push(candidate);
    groupedCandidates.set(pageKey, current);
  }

  for (const page of pages) {
    const pageKey = normalizeCrawlUrl(page.finalUrl || page.url);
    const candidates = groupedCandidates.get(pageKey) || [];
    const normalizedCandidates = candidates.map((candidate) => ({
      method: candidate.method,
      replayRole: candidate.replayRole,
      expectedForReplay: candidate.expectedForReplay !== false,
      replayPath: candidate.replayPath,
      renderCriticalKind: candidate.renderCriticalKind,
      operationName: candidate.operationName,
    }));
    page.replayCandidates = normalizedCandidates;
    page.expectedRenderCriticalCandidates = normalizedCandidates.filter((candidate) => candidate.expectedForReplay !== false);
    page.renderCriticalCandidates = page.expectedRenderCriticalCandidates;
  }
}

function buildAssetManifest(interceptor, urlMap, resourceManifestEntries = []) {
  if (resourceManifestEntries.length > 0) {
    return resourceManifestEntries.map((entry) => ({
      ...entry,
      inScope: entry.savedPath ? !entry.savedPath.includes('/external/') && !entry.savedPath.includes('\\external\\') : false,
    }));
  }

  const assets = [];

  for (const [key, data] of interceptor.getAssets()) {
    const savedPath = urlMap.get(data.url) || null;
    assets.push({
      key,
      url: data.url,
      savedPath,
      inScope: savedPath ? !savedPath.includes('/external/') && !savedPath.includes('\\external\\') : false,
      resourceType: data.type,
      contentType: data.contentType || data.mimeType,
      status: data.status,
      size: data.bodyLength || data.body?.length || 0,
      bodyStored: Boolean(data.bodyStored),
      captureLane: 'browser',
      resourceClass: 'passive-static',
      replayCriticality: 'medium',
      pageUrl: data.pageUrl || '',
      encoding: data.encoding || null,
      encodingSource: data.encodingSource || 'unknown',
      decodeConfidence: data.decodeConfidence || 'low',
      suspectedEncodingMismatch: Boolean(data.suspectedEncodingMismatch),
      encodingEvidence: data.encodingEvidence || {},
    });
  }

  return assets;
}

function buildPageQualityReport(pages, assetManifest, cssRecoverySummary = {}) {
  const cssRecoveryPages = new Map(
    (cssRecoverySummary.pages || [])
      .filter((entry) => entry?.pageUrl)
      .map((entry) => [entry.pageUrl, entry]),
  );

  return pages.map((page) => {
    const pageUrl = page.finalUrl || page.url;
    const pageAssets = assetManifest.filter((asset) => asset.pageUrl === pageUrl);
    const hiddenNavigationSummary = extractHiddenNavigationSummary(page.processedHtml || page.html || '');
    const encodingDiagnostics = summarizeEncodingDiagnosis(page.encodingDiagnostics || {});
    const cssRecovery = cssRecoveryPages.get(pageUrl) || {
      cssRecoveryStatus: 'no-css-assets',
      missingCriticalCssAssets: 0,
      cssRecoveryWarnings: [],
    };
    const rawTextLength = page.qa?.rawTextLength || 0;
    const processedTextLength = String(page.processedHtml || page.decodedDocumentHtml || page.html || '')
      .replace(/<script[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style[\s\S]*?<\/style>/gi, ' ')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .length;
    const textDriftRatio = rawTextLength > 0
      ? Math.abs(processedTextLength - rawTextLength) / rawTextLength
      : 0;

    return {
      pageUrl,
      savedPath: page.savedPath || null,
      replayRoute: page.replayRoute || null,
      replayable: Boolean(page.savedPath && page.replayRoute),
      pageClass: page.classification?.pageClass || 'document',
      highValue: Boolean(page.classification?.highValue),
      resourceCountObserved: page.qa?.observedResources || 0,
      assetCountSaved: pageAssets.length,
      nonSuccessStatuses: pageAssets.filter((asset) => asset.status && asset.status >= 400).length,
      requestedChecks: page.qa?.requestedChecks || {},
      screenshotCaptured: Boolean(page.screenshot || page.screenshotPath),
      textDriftRatio: Number(textDriftRatio.toFixed(4)),
      flags: page.classification?.flags || [],
      bootstrapSignals: page.bootstrapSignals || page.replayBootstrapSignals || {},
      bootstrapEvidenceLevel: page.bootstrapSignals?.bootstrapEvidenceLevel || page.replayBootstrapSignals?.bootstrapEvidenceLevel || 'none',
      bootstrapSignalCount: page.bootstrapSignals?.bootstrapSignalCount || page.replayBootstrapSignals?.bootstrapSignalCount || 0,
      encoding: encodingDiagnostics.encoding,
      encodingSource: encodingDiagnostics.encodingSource,
      decodeConfidence: encodingDiagnostics.decodeConfidence,
      suspectedEncodingMismatch: encodingDiagnostics.suspectedEncodingMismatch,
      encodingEvidence: encodingDiagnostics.encodingEvidence,
      cssRecoveryStatus: cssRecovery.cssRecoveryStatus,
      missingCriticalCssAssets: cssRecovery.missingCriticalCssAssets || 0,
      cssRecoveryWarnings: cssRecovery.cssRecoveryWarnings || [],
      hiddenNavigationSummary,
      localizedHiddenNavigationCount: hiddenNavigationSummary.localizedHiddenNavigationCount,
      disabledHiddenNavigationCount: hiddenNavigationSummary.disabledHiddenNavigationCount,
      nonReplayableTargetCount: hiddenNavigationSummary.nonReplayableTargetCount,
    };
  });
}

function annotatePagesWithEncodingDiagnostics(pages = [], interceptor) {
  for (const page of pages) {
    const response = interceptor?.getLatestResponse?.(page.finalUrl || page.url)
      || interceptor?.getLatestResponse?.(page.url);
    const summarized = summarizeEncodingDiagnosis({
      encoding: response?.encoding || page.documentEncoding || null,
      encodingSource: response?.encodingSource || (page.documentEncoding ? 'document-character-set' : 'unknown'),
      decodeConfidence: response?.decodeConfidence || (page.documentEncoding ? 'medium' : 'low'),
      suspectedEncodingMismatch: Boolean(response?.suspectedEncodingMismatch),
      encodingEvidence: response?.encodingEvidence || {},
    });

    page.encodingDiagnostics = {
      ...summarized,
      contentType: response?.contentType || '',
    };
    if (response?.decodedText) {
      page.decodedDocumentHtml = response.decodedText;
    }
  }
}

function extractHiddenNavigationSummary(html = '') {
  const source = String(html || '');
  if (!source) {
    return {
      localizedHiddenNavigationCount: 0,
      disabledHiddenNavigationCount: 0,
      nonReplayableTargetCount: 0,
      localizedHiddenNavigationClasses: {},
      disabledHiddenNavigationClasses: {},
    };
  }

  const $ = cheerio.load(source, { decodeEntities: false });
  const localizedHiddenNavigationCount = $('[data-hidden-navigation-localized="true"]').length;
  const disabledHiddenNavigationCount = $('[data-hidden-navigation-disabled="true"]').length;
  const nonReplayableTargetCount = $('[data-hidden-navigation-disabled="true"][data-disabled-reason="uncloned-target"]').length;
  const localizedHiddenNavigationClasses = {};
  const disabledHiddenNavigationClasses = {};

  $('[data-hidden-navigation-localized="true"]').each((_, el) => {
    const key = $(el).attr('data-hidden-navigation-class') || 'unspecified';
    localizedHiddenNavigationClasses[key] = (localizedHiddenNavigationClasses[key] || 0) + 1;
  });

  $('[data-hidden-navigation-disabled="true"]').each((_, el) => {
    const key = $(el).attr('data-hidden-navigation-class') || ($(el).attr('data-disabled-reason') || 'unspecified');
    disabledHiddenNavigationClasses[key] = (disabledHiddenNavigationClasses[key] || 0) + 1;
  });

  return {
    localizedHiddenNavigationCount,
    disabledHiddenNavigationCount,
    nonReplayableTargetCount,
    localizedHiddenNavigationClasses,
    disabledHiddenNavigationClasses,
  };
}

function buildCrawlProfileManifest(options, pages) {
  const profile = resolveCrawlProfile(options.crawlProfile);
  const posture = resolveNetworkPosture(options.networkPosture);
  return {
    name: options.crawlProfile,
    networkPosture: options.networkPosture,
    representativeQA: Boolean(options.enableRepresentativeQA),
    profileSettings: profile,
    networkSettings: posture,
    sampledPages: pages
      .filter((page) => page.classification?.shouldRunReplayValidation)
      .slice(0, profile.replayValidationSampleSize)
      .map((page) => ({
        url: page.finalUrl || page.url,
        savedPath: page.savedPath || null,
        pageClass: page.classification?.pageClass || 'document',
      })),
  };
}

function buildQualitySummary(capture, artifacts) {
  const pagesCompleted = capture.siteMap.filter((page) => page.crawlState === 'completed').length;
  const pagesSaved = capture.pages.filter((page) => Boolean(page.savedPath)).length;
  const pagesReplayable = capture.pages.filter((page) => Boolean(page.savedPath && page.replayRoute)).length;
  const linksSelected = capture.siteMap.reduce((total, page) => total + (page.linksSelected || 0), 0);
  return {
    pagesCaptured: capture.pages.length,
    pagesCompleted,
    pagesSaved,
    pagesReplayable,
    linksSelected,
    pagesFailed: capture.siteMap.filter((page) => page.crawlState === 'failed').length,
    skippedPages: capture.siteMap.filter((page) => page.crawlState === 'skipped' || page.skippedReason).length,
    missingCriticalAssets: artifacts.verificationReport?.missingCriticalAssets?.length || 0,
    replayWarnings: artifacts.verificationWarnings?.length || 0,
    graphqlEndpoints: artifacts.apiArtifacts.apiSummary?.graphqlEndpointCount || 0,
  };
}

async function persistScreenshots(outputDir, pages) {
  const screensRoot = path.join(outputDir, 'server', 'docs', 'ui', 'screens');
  await ensureDir(screensRoot);

  for (const page of pages) {
    if (!page.screenshot) continue;
    const fileName = `${page.host}-${slugify(page.savedPath)}.png`;
    const relativePath = path.join('server', 'docs', 'ui', 'screens', fileName);
    await saveFile(path.join(outputDir, relativePath), page.screenshot);
    page.screenshotPath = relativePath.replace(/\\/g, '/');
  }
}

function slugify(value) {
  return String(value || 'page')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || 'page';
}
