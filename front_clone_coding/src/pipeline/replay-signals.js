import { normalizeCrawlUrl } from '../utils/url-utils.js';

export function buildPageReplaySignals(pages = []) {
  const signals = new Map();

  for (const page of pages) {
    const pageKey = normalizeCrawlUrl(page.finalUrl || page.url);
    const replaySignals = extractPageReplaySignals(page.processedHtml || page.html || '');
    const augmentedSignals = {
      ...replaySignals,
      hasDocumentTitle: replaySignals.hasDocumentTitle || Boolean(page.title),
      hasNavigationStructure: replaySignals.hasNavigationStructure
        || (Array.isArray(page.internalLinks) && page.internalLinks.length >= 20)
        || (Array.isArray(page.interactiveElements) && page.interactiveElements.length >= 10),
      hasDenseServerRenderedText: replaySignals.hasDenseServerRenderedText
        || (page.qa?.rawTextLength || 0) >= 400,
    };
    augmentedSignals.hasServerRenderedShell = Boolean(
      augmentedSignals.hasServerRenderedShell
      || (
        augmentedSignals.hasDocumentTitle
        && augmentedSignals.hasDenseServerRenderedText
        && (augmentedSignals.hasPrimaryHeading || augmentedSignals.hasNavigationStructure || augmentedSignals.hasPrimaryLandmarks)
      )
    );

    page.replayBootstrapSignals = augmentedSignals;
    page.bootstrapSignals = augmentedSignals;
    signals.set(pageKey, augmentedSignals);
  }

  return signals;
}

export function extractPageReplaySignals(html = '') {
  const source = String(html || '');
  const normalized = source
    .replace(/\\x2f/gi, '/')
    .replace(/\\u002f/gi, '/')
    .replace(/\\\//g, '/');
  const lower = normalized.toLowerCase();
  const strippedText = normalized
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const frameworkKinds = [];
  const markFramework = (flag, kind) => {
    if (flag) frameworkKinds.push(kind);
    return flag;
  };

  const hasNextDataScript = markFramework(/__NEXT_DATA__/.test(normalized), 'next-pages-router');
  const hasInitialStateBlob = markFramework(/__INITIAL_STATE__|window\.__INITIAL_STATE__|window\.__APOLLO_STATE__|__NUXT__|__remixContext/i.test(normalized), 'inline-state-blob');
  const hasStreamingHydrationHints = markFramework(/__next_f\.push|self\.__next_f|react-server|_rsc=|flight/i.test(normalized), 'streaming-hydration');
  const hasHydrationContainer = markFramework(/id=["']__next["']|data-reactroot|data-react-helmet|ng-version|data-server-rendered|<script[^>]+type=["']application\/json["']/i.test(normalized), 'hydration-container');
  const hasUserInfoModel = /userInfo(?:["']?\s*:\s*|\.data)/.test(normalized);
  const hasMembershipStatusFallback = /membershipStatus/.test(normalized) && /userInfo/.test(normalized);
  const hasSessionStateFallback = /session|authurl|viewer|account|profile|identity/.test(lower)
    && /(models|reactcontext|__next_data__|__initial_state__|window\.__|__nuxt__|__apollo_state__)/.test(lower);
  const hasDocumentTitle = /<title[^>]*>\s*[^<\s][\s\S]*?<\/title>/i.test(normalized);
  const hasPrimaryHeading = /<h1\b/i.test(normalized);
  const hasNavigationStructure = /<nav\b/i.test(normalized) || /class=["'][^"']*(?:gnb|lnb|menu|nav|header-nav|sitemap)[^"']*["']/i.test(normalized);
  const hasPrimaryLandmarks = ['<header', '<main', '<footer', '<section', '<article']
    .filter((marker) => lower.includes(marker))
    .length >= 2;
  const hasDenseServerRenderedText = strippedText.length >= 400;
  const hasServerRenderedShell = hasDocumentTitle
    && (hasPrimaryHeading || hasNavigationStructure || hasPrimaryLandmarks)
    && hasDenseServerRenderedText;
  const hasRenderableStateFallback = hasUserInfoModel
    || hasMembershipStatusFallback
    || hasSessionStateFallback
    || hasNextDataScript
    || hasInitialStateBlob;
  const hasInlineBootstrapState = hasRenderableStateFallback
    || /netflix\.reactContext|window\.__|["']models["']\s*:|models\s*:/.test(normalized);
  const hasFrameworkBootstrap = frameworkKinds.length > 0;
  const bootstrapEvidenceLevel = hasRenderableStateFallback
    ? 'strong'
    : (hasFrameworkBootstrap || hasHydrationContainer)
      ? 'partial'
      : 'none';
  const signalCount = [
    hasInlineBootstrapState,
    hasFrameworkBootstrap,
    hasHydrationContainer,
    hasStreamingHydrationHints,
    hasUserInfoModel,
    hasMembershipStatusFallback,
    hasSessionStateFallback,
  ].filter(Boolean).length;

  return {
    hasInlineBootstrapState,
    hasFrameworkBootstrap,
    hasHydrationContainer,
    hasNextDataScript,
    hasInitialStateBlob,
    hasStreamingHydrationHints,
    hasUserInfoModel,
    hasMembershipStatusFallback,
    hasSessionStateFallback,
    hasRenderableStateFallback,
    hasDocumentTitle,
    hasPrimaryHeading,
    hasNavigationStructure,
    hasPrimaryLandmarks,
    hasDenseServerRenderedText,
    hasServerRenderedShell,
    bootstrapEvidenceLevel,
    bootstrapSignalCount: signalCount,
    frameworkKinds,
  };
}
