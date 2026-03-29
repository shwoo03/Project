import {
  buildReplayRouteFromSavedPath,
  getNormalizedPageIdentityUrl,
  normalizeCrawlUrl,
  normalizePageIdentitySearch,
} from '../utils/url-utils.js';

function safeExtractNormalizedSearch(value) {
  try {
    return normalizePageIdentitySearch(new URL(value).search);
  } catch {
    return '';
  }
}

function safeExtractUrlPart(value, key) {
  try {
    return new URL(value)[key] || '';
  } catch {
    return '';
  }
}

export function buildPageRouteManifest(siteMap = [], pages = [], entryPagePath = 'index.html') {
  const pagesByUrl = new Map();
  for (const page of pages) {
    const key = normalizeCrawlUrl(page.finalUrl || page.url);
    pagesByUrl.set(key, page);
  }

  const routes = siteMap.map((item) => {
    const page = pagesByUrl.get(item.normalizedUrl);
    const targetUrl = item.finalUrl || item.url;
    const host = safeExtractUrlPart(targetUrl, 'hostname');
    const pathname = safeExtractUrlPart(targetUrl, 'pathname') || '/';
    const normalizedSearch = safeExtractNormalizedSearch(targetUrl);
    return {
      pageUrl: item.url,
      finalUrl: item.finalUrl,
      normalizedUrl: item.normalizedUrl,
      normalizedIdentityUrl: getNormalizedPageIdentityUrl(targetUrl),
      host,
      pathname,
      normalizedSearch,
      savedPath: page?.savedPath || null,
      replayRoute: page?.replayRoute || null,
      routeAliases: page?.replayRouteAliases || [],
      replayable: Boolean(page?.savedPath && page?.replayRoute),
      crawlState: item.crawlState || 'completed',
      skippedReason: item.skippedReason || null,
    };
  });

  return {
    generatedAt: new Date().toISOString(),
    entryPagePath,
    entryReplayRoute: buildReplayRouteFromSavedPath(entryPagePath),
    routes,
  };
}

export function buildPageRouteIndex(pageRouteManifest = { routes: [] }) {
  const exactUrlMap = new Map();
  const normalizedIdentityMap = new Map();
  const routePathMap = new Map();
  const groupedByHostPath = new Map();

  for (const route of pageRouteManifest.routes || []) {
    if (route.replayable) {
      for (const alias of [route.pageUrl, route.finalUrl, route.normalizedUrl]) {
        if (!alias) continue;
        exactUrlMap.set(alias, route);
      }
      if (route.normalizedIdentityUrl) {
        normalizedIdentityMap.set(route.normalizedIdentityUrl, route);
      }

      for (const routePath of [route.replayRoute, ...(route.routeAliases || [])]) {
        const normalizedRoutePath = normalizeRouteLookupPath(routePath);
        if (!normalizedRoutePath) continue;
        routePathMap.set(normalizedRoutePath, route);
      }
    }

    const fallbackKey = `${route.host || ''}${route.pathname || '/'}`;
    if (!groupedByHostPath.has(fallbackKey)) {
      groupedByHostPath.set(fallbackKey, new Set());
    }
    if (route.replayable) {
      groupedByHostPath.get(fallbackKey).add(route);
    }
  }

  const fallbackMap = new Map();
  for (const [fallbackKey, routeSet] of groupedByHostPath.entries()) {
    if (routeSet.size === 1) {
      fallbackMap.set(fallbackKey, [...routeSet][0]);
    }
  }

  return {
    exactUrlMap,
    normalizedIdentityMap,
    fallbackMap,
    routePathMap,
    entryReplayRoute: pageRouteManifest.entryReplayRoute || '/',
  };
}

export function buildLocaleStrippedFallbackKey(hostname, pathname) {
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length < 2) {
    return '';
  }

  const [firstSegment, ...restSegments] = segments;
  if (!/^[a-z]{2}(?:-[a-z]{2,4})?$/i.test(firstSegment)) {
    return '';
  }

  return `${hostname}/${restSegments.join('/')}`;
}

export function normalizeRouteLookupPath(value) {
  if (!value) return '';
  const normalized = String(value).replace(/\\/g, '/').replace(/\/+$/, '');
  return normalized || '/';
}

export function buildPagePathFallbackMap(pageUrlMap = new Map()) {
  const groupedPaths = new Map();

  for (const [pageUrl, savedPath] of pageUrlMap.entries()) {
    if (!pageUrl || !savedPath) continue;

    try {
      const parsed = new URL(pageUrl);
      let pathname = parsed.pathname || '/';
      if (pathname !== '/' && pathname.endsWith('/')) {
        pathname = pathname.slice(0, -1);
      }
      const key = `${parsed.hostname}${pathname}`;
      if (!groupedPaths.has(key)) {
        groupedPaths.set(key, new Set());
      }
      groupedPaths.get(key).add(savedPath);

      const localeAliasKey = buildLocaleStrippedFallbackKey(parsed.hostname, pathname);
      if (localeAliasKey) {
        if (!groupedPaths.has(localeAliasKey)) {
          groupedPaths.set(localeAliasKey, new Set());
        }
        groupedPaths.get(localeAliasKey).add(savedPath);
      }
    } catch {
      // Ignore non-URL aliases; fallback lookup only applies to navigable pages.
    }
  }

  const fallbackMap = new Map();
  for (const [key, savedPaths] of groupedPaths.entries()) {
    if (savedPaths.size === 1) {
      fallbackMap.set(key, [...savedPaths][0]);
    }
  }

  return fallbackMap;
}
