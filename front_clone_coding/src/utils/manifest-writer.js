import path from 'path';
import crypto from 'crypto';
import { ensureDir, saveFile } from './file-utils.js';

export async function writeManifest(outputDir, manifest) {
  const manifestDir = path.join(outputDir, 'server', 'spec', 'manifest');
  const specDir = path.join(outputDir, 'server', 'spec');
  const crawlDocsDir = path.join(outputDir, 'server', 'docs', 'crawl');
  await ensureDir(manifestDir);
  await ensureDir(specDir);
  await ensureDir(crawlDocsDir);

  const pagesCompleted = manifest.pages.filter((page) => page.crawlState === 'completed').length;
  const pagesSaved = manifest.pages.filter((page) => Boolean(page.savedPath)).length;
  const pagesReplayable = manifest.pages.filter((page) => page.replayable !== false && Boolean(page.savedPath && page.replayRoute)).length;
  const linksSelected = manifest.pages.reduce((total, page) => total + (page.linksSelected || 0), 0);
  const disabledInScopeTargets = manifest.pages.filter((page) => page.crawlState !== 'completed' || !page.replayable).length;
  const localizedHiddenNavigationCount = manifest.pages.reduce((total, page) => total + (page.hiddenNavigationSummary?.localizedHiddenNavigationCount || 0), 0);
  const disabledHiddenNavigationCount = manifest.pages.reduce((total, page) => total + (page.hiddenNavigationSummary?.disabledHiddenNavigationCount || 0), 0);
  const nonReplayableTargetCount = manifest.pages.reduce((total, page) => total + (page.hiddenNavigationSummary?.nonReplayableTargetCount || 0), 0);
  const pagesWithSuspectedEncodingMismatch = manifest.pages.filter((page) => page.suspectedEncodingMismatch).length;
  const pagesWithLowDecodeConfidence = manifest.pages.filter((page) => page.decodeConfidence === 'low').length;
  const cssRecoverySummary = manifest.cssRecoverySummary || {};

  await saveFile(
    path.join(manifestDir, 'crawl-manifest.json'),
    JSON.stringify(manifest, null, 2),
  );

  await saveFile(
    path.join(crawlDocsDir, 'crawl-report.json'),
    JSON.stringify({
      generatedAt: manifest.generatedAt,
      startUrl: manifest.startUrl,
      domainRoot: manifest.domainRoot,
      counts: {
        pages: manifest.pages.length,
        linksSelected,
        pagesCompleted,
        pagesSaved,
        pagesReplayable,
        disabledInScopeTargets,
        localizedHiddenNavigationCount,
        disabledHiddenNavigationCount,
        nonReplayableTargetCount,
        pagesWithSuspectedEncodingMismatch,
        pagesWithLowDecodeConfidence,
        cssAssetsDiscovered: cssRecoverySummary.cssAssetsDiscovered || 0,
        cssAssetsRecovered: cssRecoverySummary.cssAssetsRecovered || 0,
        cssAssetsFailed: cssRecoverySummary.cssAssetsFailed || 0,
        cssAssetsSkipped: cssRecoverySummary.cssAssetsSkipped || 0,
        cssAssetCanonicalizationApplied: cssRecoverySummary.cssAssetCanonicalizationApplied || 0,
        assets: manifest.assets.length,
      },
      loginGatedPages: manifest.pages.filter((page) => page.loginGated).length,
    }, null, 2),
  );

  await saveFile(
    path.join(crawlDocsDir, 'site-map.json'),
    JSON.stringify(manifest.pages.map((page) => ({
      url: page.url,
      finalUrl: page.finalUrl,
      savedPath: page.savedPath,
      replayRoute: page.replayRoute || null,
      replayable: page.replayable !== false && Boolean(page.savedPath && page.replayRoute),
      depth: page.depth,
      discoveredFrom: page.discoveredFrom,
      status: page.status,
      loginGated: page.loginGated,
      crawlState: page.crawlState || 'completed',
      skippedReason: page.skippedReason || null,
      error: page.error || null,
      title: page.title,
    })), null, 2),
  );

  await saveFile(
    path.join(specDir, 'resource-manifest.json'),
    JSON.stringify(manifest.assets, null, 2),
  );

  await saveFile(
    path.join(specDir, 'page-quality-report.json'),
    JSON.stringify(manifest.pageQualityReport || [], null, 2),
  );

  await saveFile(
    path.join(specDir, 'page-route-manifest.json'),
    JSON.stringify(manifest.pageRoutes || { routes: [] }, null, 2),
  );

  await saveFile(
    path.join(specDir, 'bootstrap-summary.json'),
    JSON.stringify(buildBootstrapSummary(manifest.pages || []), null, 2),
  );

  await saveFile(
    path.join(specDir, 'css-recovery-summary.json'),
    JSON.stringify(cssRecoverySummary, null, 2),
  );

  await saveFile(
    path.join(specDir, 'crawl-profile.json'),
    JSON.stringify(manifest.crawlProfile || {}, null, 2),
  );
}

export function hashContent(value) {
  return crypto.createHash('sha1').update(value).digest('hex');
}

function buildBootstrapSummary(pages = []) {
  const entries = pages.map((page) => {
    const bootstrapSignals = page.bootstrapSignals || page.replayBootstrapSignals || {};
    return {
      pageUrl: page.finalUrl || page.url,
      savedPath: page.savedPath || null,
      replayRoute: page.replayRoute || null,
      replayable: page.replayable !== false && Boolean(page.savedPath && page.replayRoute),
      bootstrapSignals,
    };
  });

  return {
    generatedAt: new Date().toISOString(),
    counts: {
      pages: entries.length,
      pagesWithInlineBootstrapState: entries.filter((entry) => entry.bootstrapSignals.hasInlineBootstrapState).length,
      pagesWithFrameworkBootstrap: entries.filter((entry) => entry.bootstrapSignals.hasFrameworkBootstrap).length,
      pagesWithStreamingHydrationHints: entries.filter((entry) => entry.bootstrapSignals.hasStreamingHydrationHints).length,
      pagesWithRenderableStateFallback: entries.filter((entry) => entry.bootstrapSignals.hasRenderableStateFallback).length,
    },
    pages: entries,
  };
}
