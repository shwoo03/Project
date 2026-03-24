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
import {
  copyPath,
  ensureDir,
  movePath,
  pathExists,
  removePath,
  saveFile,
} from './utils/file-utils.js';
import { downloadExternalImages, injectCapturedImages } from './utils/image-utils.js';
import { getDomainRoot, getViewPathFromUrl, normalizeCrawlUrl } from './utils/url-utils.js';
import { hashContent, writeManifest } from './utils/manifest-writer.js';
import logger from './utils/logger.js';
import { ensurePlaywrightRuntimeReady } from './utils/playwright-runtime.js';
import {
  DEFAULT_CRAWL_PROFILE,
  DEFAULT_NETWORK_POSTURE,
  resolveCrawlProfile,
  resolveNetworkPosture,
} from './utils/crawl-config.js';

const MERGED_OUTPUT_ENTRIES = [
  'public',
  'views',
  'server',
  'server.js',
  'package.json',
  'README.md',
];
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
    const capture = await capturePages(context);

    checkAborted(signal);
    const transformed = await transformCapturedOutput(context, capture);

    checkAborted(signal);
    const artifacts = await generateArtifacts(context, capture, transformed);

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
    };
  } catch (err) {
    console.error('[Unexpected Error]');
    console.error(err.stack);
    if (err.details) {
      logger.error(err.details);
    }
    logger.error(`Operation failed: ${err.message}`);
    await removePath(context.stagingDir).catch(() => {});
    throw err;
  }
}

export function getOutputDomainRoot(targetUrl) {
  return getDomainRoot(targetUrl, 'registrable-domain');
}

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
  const outputDir = path.join(outputParent, domainRoot);
  const stageRoot = path.join(outputParent, '.front-clone-tmp');
  const runId = `${domainRoot}-${Date.now()}-${process.pid}`;
  const stagingDir = path.join(stageRoot, runId);

  return {
    options: normalizedOptions,
    outputParent,
    outputDir,
    domainRoot,
    domainScope: normalizedOptions.domainScope,
    shouldUpdate: Boolean(normalizedOptions.updateExisting),
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

async function capturePages(context) {
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
        classification: crawlResult.classification,
        crawlProfile: crawlResult.crawlProfile,
        networkPosture: crawlResult.networkPosture,
        qa: crawlResult.qa,
        status: crawlResult.status,
        storageState: crawlResult.storageState,
        sessionStorageState: crawlResult.sessionStorageState,
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
        loginGated: false,
        skippedReason: null,
        crawlState: 'completed',
        linksFound: crawlResult.internalLinks.length,
      },
    ],
  };
}

async function transformCapturedOutput(context, capture) {
  const pageUrlMap = new Map();

  for (const page of capture.pages) {
    const canonicalUrl = page.finalUrl || page.url;
    const savedPath = getViewPathFromUrl(canonicalUrl);
    page.savedPath = savedPath;
    page.host = new URL(canonicalUrl).hostname;

    pageUrlMap.set(page.url, savedPath);
    pageUrlMap.set(canonicalUrl, savedPath);
    pageUrlMap.set(normalizeCrawlUrl(page.url), savedPath);
    pageUrlMap.set(normalizeCrawlUrl(canonicalUrl), savedPath);
  }

  const downloader = new AssetDownloader(context.stagingDir, context.options.url);
  const fullUrlMap = await downloader.downloadAll(capture.interceptor);
  for (const [url, localPath] of pageUrlMap) {
    fullUrlMap.set(url, localPath);
  }

  const cssProcessor = new CssProcessor(context.stagingDir, context.options.url, fullUrlMap, capture.interceptor);
  const jsProcessor = new JsProcessor(context.stagingDir, context.options.url, fullUrlMap);
  await Promise.all([cssProcessor.processAll(), jsProcessor.processAll()]);

  const htmlProcessor = new HtmlProcessor(context.options.url, { useBaseHref: true });
  for (const page of capture.pages) {
    htmlProcessor.baseUrl = page.finalUrl || page.url;
    let processedHtml = htmlProcessor.process(page.html, fullUrlMap, page.savedPath);

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
      processedHtml = htmlProcessor.process(processedHtml, fullUrlMap, page.savedPath);
    }

    processedHtml = injectCapturedImages(processedHtml, fullUrlMap);
    await saveFile(path.join(context.viewsDir, page.savedPath), processedHtml);
    page.processedHtml = processedHtml;

    logger.info(`Saved HTML: views/${page.savedPath}`);
  }

  const entryPagePath = capture.pages[0].savedPath;

  if (context.captureVisualDocs) {
    await persistScreenshots(context.stagingDir, capture.pages);
  }

  return {
    entryPagePath,
    fullUrlMap,
    resourceManifestEntries: downloader.getResourceManifestEntries(),
  };
}

async function generateArtifacts(context, capture, transformed) {
  const xhrRequests = capture.interceptor.getXhrRequests();
  const websocketEvents = capture.interceptor.getWebsocketEvents();

  const apiProcessor = new ApiProcessor(context.stagingDir, context.options.url, context.domainScope);
  const apiArtifacts = await apiProcessor.generateArtifacts(xhrRequests, websocketEvents);

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

  const assetManifest = buildAssetManifest(capture.interceptor, transformed.fullUrlMap, transformed.resourceManifestEntries);
  const pageManifest = buildPageManifest(capture.siteMap, capture.pages);
  const pageQualityReport = buildPageQualityReport(capture.pages, assetManifest);

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
    crawlProfile: buildCrawlProfileManifest(context.options, capture.pages),
  });

  if (context.options.scaffold !== false) {
    const scaffolder = new ProjectScaffolder(context.stagingDir, new URL(context.options.url).hostname);
    await scaffolder.scaffold({
      entryPagePath: transformed.entryPagePath,
      apiSummary: apiArtifacts.apiSummary,
      siteMap: capture.siteMap,
      pages: capture.pages,
    });
  }

  return { apiArtifacts };
}

async function finalizeOutput(context) {
  if (!context.shouldUpdate) {
    await removePath(context.outputDir);
    await ensureDir(path.dirname(context.outputDir));
    await movePath(context.stagingDir, context.outputDir);
    return;
  }

  await ensureDir(context.outputDir);

  for (const entry of MERGED_OUTPUT_ENTRIES) {
    const sourcePath = path.join(context.stagingDir, entry);
    if (!(await pathExists(sourcePath))) continue;

    const destinationPath = path.join(context.outputDir, entry);
    await replacePath(sourcePath, destinationPath);
  }

  const remainingEntries = await listRemainingEntries(context.stagingDir);
  for (const entry of remainingEntries) {
    const sourcePath = path.join(context.stagingDir, entry);
    const destinationPath = path.join(context.outputDir, entry);
    await copyPath(sourcePath, destinationPath);
  }

  await removePath(context.stagingDir);
}

async function listRemainingEntries(stagingDir) {
  const fs = await import('fs/promises');
  try {
    const entries = await fs.readdir(stagingDir);
    return entries;
  } catch {
    return [];
  }
}

function buildPageManifest(siteMap, pages) {
  const pagesByUrl = new Map();
  for (const page of pages) {
    const key = normalizeCrawlUrl(page.finalUrl || page.url);
    pagesByUrl.set(key, page);
  }

  return siteMap.map((item) => {
    const page = pagesByUrl.get(item.normalizedUrl);
    return {
      url: item.url,
      finalUrl: item.finalUrl,
      normalizedUrl: item.normalizedUrl,
      savedPath: page?.savedPath || null,
      host: page?.host || (item.finalUrl ? new URL(item.finalUrl).hostname : null),
      depth: item.depth,
      discoveredFrom: item.discoveredFrom,
      status: item.status,
      title: item.title || '',
      loginGated: item.loginGated,
      crawlState: item.crawlState || 'completed',
      skippedReason: item.skippedReason || null,
      error: item.error || null,
      contentHash: page ? hashContent(page.processedHtml || page.html || '') : null,
    };
  });
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
      contentType: data.mimeType,
      status: data.status,
      size: data.bodyLength || data.body?.length || 0,
      bodyStored: Boolean(data.bodyStored),
      captureLane: 'browser',
      resourceClass: 'passive-static',
      replayCriticality: 'medium',
      pageUrl: data.pageUrl || '',
    });
  }

  return assets;
}

function buildPageQualityReport(pages, assetManifest) {
  return pages.map((page) => {
    const pageUrl = page.finalUrl || page.url;
    const pageAssets = assetManifest.filter((asset) => asset.pageUrl === pageUrl);
    const rawTextLength = page.qa?.rawTextLength || 0;
    const processedTextLength = String(page.processedHtml || '')
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
      pageClass: page.classification?.pageClass || 'document',
      highValue: Boolean(page.classification?.highValue),
      resourceCountObserved: page.qa?.observedResources || 0,
      assetCountSaved: pageAssets.length,
      nonSuccessStatuses: pageAssets.filter((asset) => asset.status && asset.status >= 400).length,
      requestedChecks: page.qa?.requestedChecks || {},
      screenshotCaptured: Boolean(page.screenshot || page.screenshotPath),
      textDriftRatio: Number(textDriftRatio.toFixed(4)),
      flags: page.classification?.flags || [],
    };
  });
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
