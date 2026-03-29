import {
  buildReplayQuerySuffix,
  buildReplayRouteAliases,
  buildReplayRouteFromSavedPath,
  getNormalizedPageIdentityUrl,
  getViewPathFromUrl,
  normalizeCrawlUrl,
  normalizePageIdentitySearch,
} from '../utils/url-utils.js';

export function dedupeCapturedPages(pages = [], siteMap = [], { includeHostPrefix = false } = {}) {
  const dedupedPages = [];
  const pagesByKey = new Map();
  const pageUrlMap = new Map();

  for (const page of pages) {
    const canonicalUrl = page.finalUrl || page.url;
    const canonicalKey = normalizeCrawlUrl(canonicalUrl);
    const existing = pagesByKey.get(canonicalKey);

    if (!existing) {
      const representative = {
        ...page,
        canonicalKey,
        host: new URL(canonicalUrl).hostname,
        dedupeAliases: new Set(),
      };
      representative.dedupeAliases.add(page.url);
      representative.dedupeAliases.add(canonicalUrl);
      representative.dedupeAliases.add(normalizeCrawlUrl(page.url));
      representative.dedupeAliases.add(canonicalKey);
      pagesByKey.set(canonicalKey, representative);
      dedupedPages.push(representative);
      continue;
    }

    mergeCapturedPage(existing, page);
    existing.dedupeAliases.add(page.url);
    existing.dedupeAliases.add(canonicalUrl);
    existing.dedupeAliases.add(normalizeCrawlUrl(page.url));
    existing.dedupeAliases.add(canonicalKey);
  }

  const queryAwareGroups = buildQueryAwareCollisionGroups(dedupedPages);
  for (const page of dedupedPages) {
    const representativeUrl = chooseRepresentativePageUrl(page, page.canonicalKey);
    const hostPathKey = getHostPathCollisionKey(representativeUrl);
    const queryAware = queryAwareGroups.has(hostPathKey);
    const querySuffix = queryAware ? buildReplayQuerySuffix(new URL(representativeUrl).search) : '';
    const savedPath = getViewPathFromUrl(representativeUrl, {
      includeHostPrefix,
      querySuffix,
    });

    page.savedPath = savedPath;
    page.replayRoute = buildReplayRouteFromSavedPath(savedPath);
    page.replayRouteAliases = buildReplayRouteAliases(savedPath);
    page.replayable = true;
    page.normalizedIdentityUrl = getNormalizedPageIdentityUrl(representativeUrl);
  }

  for (const page of dedupedPages) {
    for (const alias of page.dedupeAliases || []) {
      if (!alias) continue;
      pageUrlMap.set(alias, page.savedPath);
    }
    if (page.normalizedIdentityUrl) {
      pageUrlMap.set(page.normalizedIdentityUrl, page.savedPath);
    }
  }

  const dedupedSiteMap = dedupeSiteMapEntries(siteMap, pagesByKey);
  return {
    pages: dedupedPages.map((page) => {
      const normalizedPage = { ...page };
      delete normalizedPage.dedupeAliases;
      return normalizedPage;
    }),
    siteMap: dedupedSiteMap,
    pageUrlMap,
  };
}

function buildQueryAwareCollisionGroups(pages = []) {
  const grouped = new Map();

  for (const page of pages) {
    const targetUrl = page.finalUrl || page.url;
    const groupKey = getHostPathCollisionKey(targetUrl);
    if (!groupKey) continue;
    if (!grouped.has(groupKey)) {
      grouped.set(groupKey, new Set());
    }
    grouped.get(groupKey).add(safeExtractNormalizedSearch(targetUrl));
  }

  const queryAwareGroups = new Set();
  for (const [groupKey, searches] of grouped.entries()) {
    const meaningfulSearches = [...searches];
    if (meaningfulSearches.length > 1) {
      queryAwareGroups.add(groupKey);
    }
  }

  return queryAwareGroups;
}

function getHostPathCollisionKey(value) {
  try {
    const url = new URL(value);
    let pathname = url.pathname || '/';
    if (pathname !== '/' && pathname.endsWith('/')) {
      pathname = pathname.slice(0, -1);
    }
    return `${url.hostname}${pathname}`;
  } catch {
    return '';
  }
}

function safeExtractNormalizedSearch(value) {
  try {
    return normalizePageIdentitySearch(new URL(value).search);
  } catch {
    return '';
  }
}

function chooseRepresentativePageUrl(page, canonicalKey) {
  const variants = [page.finalUrl, page.url].filter(Boolean);
  const prefersDirectoryStyle = variants.some((value) => endsWithDirectoryStylePath(value));
  if (!prefersDirectoryStyle) return canonicalKey;

  try {
    const url = new URL(canonicalKey);
    if (url.pathname && url.pathname !== '/' && !url.pathname.endsWith('/')) {
      url.pathname = `${url.pathname}/`;
    }
    return url.href;
  } catch {
    return canonicalKey;
  }
}

function endsWithDirectoryStylePath(value) {
  try {
    const url = new URL(value);
    return url.pathname !== '/' && url.pathname.endsWith('/');
  } catch {
    return false;
  }
}

function preferCanonicalSavedPath(existingPath, nextPath) {
  const existingScore = scoreSavedPathShape(existingPath);
  const nextScore = scoreSavedPathShape(nextPath);
  return nextScore > existingScore ? nextPath : existingPath;
}

function scoreSavedPathShape(savedPath = '') {
  if (String(savedPath).endsWith('/index.html')) return 2;
  if (String(savedPath).endsWith('.html')) return 1;
  return 0;
}

function mergeCapturedPage(target, incoming) {
  target.linkCandidates = mergeUniqueObjects(target.linkCandidates, incoming.linkCandidates, (item) => `${item?.url || ''}|${item?.sourceKind || ''}|${item?.domOrder ?? ''}`);
  target.captureWarnings = mergeUniqueStrings(target.captureWarnings, incoming.captureWarnings);
  target.liveImageUrls = mergeUniqueStrings(target.liveImageUrls, incoming.liveImageUrls);
  target.internalLinks = mergeUniqueStrings(target.internalLinks, incoming.internalLinks);
  target.forms = mergeUniqueObjects(target.forms, incoming.forms, (item) => JSON.stringify(item || {}));
  target.interactiveElements = mergeUniqueObjects(target.interactiveElements, incoming.interactiveElements, (item) => JSON.stringify(item || {}));
  target.graphqlArtifacts = mergeUniqueObjects(target.graphqlArtifacts, incoming.graphqlArtifacts, (item) => JSON.stringify(item || {}));
  target.qa = pickPreferredQa(target.qa, incoming.qa);
  target.processedHtml = target.processedHtml || incoming.processedHtml;
  target.html = target.html || incoming.html;
  target.title = target.title || incoming.title;
  target.documentEncoding = target.documentEncoding || incoming.documentEncoding;
  target.storageState = target.storageState || incoming.storageState;
  target.sessionStorageState = target.sessionStorageState || incoming.sessionStorageState;
  target.screenshot = target.screenshot || incoming.screenshot;
  target.screenshotPath = target.screenshotPath || incoming.screenshotPath;
  target.classification = target.classification || incoming.classification;
}

export function mergeUniqueStrings(left = [], right = []) {
  return [...new Set([...(left || []), ...(right || [])].filter(Boolean))];
}

export function mergeUniqueObjects(left = [], right = [], getKey = (item) => JSON.stringify(item || {})) {
  const seen = new Set();
  const merged = [];
  for (const item of [...(left || []), ...(right || [])]) {
    const key = getKey(item);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
  }
  return merged;
}

function pickPreferredQa(existing, incoming) {
  if (!existing) return incoming || null;
  if (!incoming) return existing;
  const existingScore = (existing.rawTextLength || 0) + (existing.observedResources || 0);
  const incomingScore = (incoming.rawTextLength || 0) + (incoming.observedResources || 0);
  return incomingScore > existingScore ? { ...existing, ...incoming } : { ...incoming, ...existing };
}

export function dedupeSiteMapEntries(siteMap = [], pagesByKey = new Map()) {
  const deduped = [];
  const byKey = new Map();

  for (const item of siteMap || []) {
    const normalizedUrl = item.normalizedUrl || normalizeCrawlUrl(item.finalUrl || item.url);
    const page = pagesByKey.get(normalizedUrl);
    const candidate = {
      ...item,
      normalizedUrl,
      finalUrl: page?.finalUrl || item.finalUrl,
      title: page?.title || item.title,
      documentEncoding: page?.documentEncoding || item.documentEncoding || null,
    };
    const existing = byKey.get(normalizedUrl);
    if (!existing) {
      byKey.set(normalizedUrl, {
        ...candidate,
        frontierTopCandidates: [...(candidate.frontierTopCandidates || [])],
        selectionReasons: [...(candidate.selectionReasons || [])],
      });
      deduped.push(byKey.get(normalizedUrl));
      continue;
    }

    existing.finalUrl = existing.finalUrl || candidate.finalUrl;
    existing.title = existing.title || candidate.title;
    existing.documentEncoding = existing.documentEncoding || candidate.documentEncoding;
    existing.status = existing.status || candidate.status;
    existing.discoveredFrom = existing.discoveredFrom || candidate.discoveredFrom;
    existing.linksFound = Math.max(existing.linksFound ?? 0, candidate.linksFound ?? 0);
    existing.linkCandidatesSeen = Math.max(existing.linkCandidatesSeen ?? 0, candidate.linkCandidatesSeen ?? 0);
    existing.linksSelected = Math.max(existing.linksSelected ?? 0, candidate.linksSelected ?? 0);
    existing.frontierTopCandidates = mergeUniqueObjects(
      existing.frontierTopCandidates,
      candidate.frontierTopCandidates,
      (entry) => `${entry?.normalizedUrl || entry?.url || ''}|${entry?.score ?? ''}`,
    ).slice(0, 10);
    existing.selectionReasons = mergeUniqueStrings(existing.selectionReasons, candidate.selectionReasons).slice(0, 12);
    if (existing.crawlState !== 'completed' && candidate.crawlState === 'completed') {
      existing.crawlState = candidate.crawlState;
      existing.skippedReason = candidate.skippedReason || null;
      existing.error = candidate.error || null;
    }
  }

  return deduped;
}
