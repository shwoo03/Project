import { URL } from 'url';

import { isInDomainScope, normalizeCrawlUrl } from './url-utils.js';

export const DEFAULT_FRONTIER_WEIGHTS = {
  sameHostEarly: 10,
  sameHostDeep: 6,
  sameDomain: 3,
  spaRoute: 3,
  formAction: -2,
  meaningfulAnchorText: 2,
  shortPath: 4,
  mediumPath: 2,
  deepPath: -2,
  mainLandmark: 8,
  contentLandmark: 4,
  navLandmark: -1,
  headerLandmark: -1,
  asideLandmark: -2,
  footerLandmark: -5,
  queryPenaltyPerParam: -1,
  trackingQueryPenalty: -2,
  hashOnlyPenalty: -8,
  utilityPenalty: -7,
  docsPenalty: -4,
  authPenalty: -8,
  searchPenalty: -5,
  marketingBoost: 3,
  utilityContextRelief: 5,
};

export const DEFAULT_FRONTIER_DIVERSITY_CAPS = {
  outOfHostRatio: 0.34,
  utilityFamilyPerBatch: 1,
  queryVariantPerPath: 1,
};

const TRACKING_QUERY_PARAM_PATTERNS = [
  /^utm_/i,
  /^fbclid$/i,
  /^gclid$/i,
  /^mc_/i,
  /^ref$/i,
  /^ref_/i,
  /^source$/i,
  /^source_/i,
  /^spm$/i,
  /^yclid$/i,
  /^igshid$/i,
];

const UTILITY_TOKENS = new Set([
  'help',
  'support',
  'faq',
  'privacy',
  'terms',
  'legal',
  'contact',
  'careers',
  'career',
  'blog',
  'search',
  'alias',
]);

const DOCS_TOKENS = new Set([
  'docs',
  'doc',
  'documentation',
  'guide',
  'guides',
  'manual',
  'reference',
  'kb',
  'knowledgebase',
  'help',
  'support',
  'faq',
]);

const AUTH_TOKENS = new Set([
  'login',
  'signin',
  'sign',
  'signup',
  'register',
  'logout',
  'auth',
  'account',
  'accounts',
  'sso',
  'join',
]);

const SEARCH_TOKENS = new Set([
  'search',
  'find',
  'query',
  'keyword',
]);

const MARKETING_TOKENS = new Set([
  'product',
  'products',
  'pricing',
  'feature',
  'features',
  'platform',
  'solution',
  'solutions',
  'service',
  'services',
  'app',
  'apps',
  'api',
  'developer',
  'developers',
  'dashboard',
]);

const CONTENT_LANDMARKS = new Set(['main', 'article', 'section']);
const UTILITY_FAMILIES = new Set(['utility', 'docs', 'auth', 'search']);

export function buildPriorityFingerprint(urlStr) {
  try {
    const url = new URL(urlStr);
    const entries = [...url.searchParams.entries()]
      .filter(([key]) => !isTrackingQueryParam(key))
      .sort(([left], [right]) => left.localeCompare(right));
    const signature = entries.map(([key, value]) => `${key}=${value}`).join('&');
    return `${url.hostname}${url.pathname || '/'}?${signature}`;
  } catch {
    return urlStr;
  }
}

export function tokenizePathname(pathname = '') {
  return String(pathname || '')
    .toLowerCase()
    .split(/[/?#._-]+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

export function enrichLinkCandidate(candidate, context = {}) {
  const fallbackUrl = context.currentPageUrl || context.startUrl;
  let parsed;
  try {
    parsed = new URL(candidate.url, fallbackUrl);
  } catch {
    return null;
  }

  const startUrl = context.startUrl || fallbackUrl || parsed.href;
  const currentPageUrl = context.currentPageUrl || fallbackUrl || startUrl;
  const startHost = new URL(startUrl).hostname;
  const pathnameTokens = tokenizePathname(parsed.pathname);
  const queryParamKeys = [...parsed.searchParams.keys()];
  const trackingQueryCount = queryParamKeys.filter((key) => isTrackingQueryParam(key)).length;

  return {
    url: parsed.href,
    normalizedUrl: normalizeCrawlUrl(parsed.href),
    sourceKind: candidate.sourceKind || 'anchor',
    anchorText: String(candidate.anchorText || '').trim().slice(0, 160),
    domOrder: Number.isFinite(candidate.domOrder) ? candidate.domOrder : Number.MAX_SAFE_INTEGER,
    landmark: String(candidate.landmark || 'unknown').toLowerCase(),
    sameHost: parsed.hostname === startHost,
    sameRegistrableDomain: isInDomainScope(parsed.href, startUrl, context.domainScope || 'registrable-domain'),
    pathDepth: pathnameTokens.length,
    hasQuery: parsed.search.length > 1,
    queryParamCount: queryParamKeys.length,
    trackingQueryCount,
    pathnameTokens,
    isHashOnly: Boolean(candidate.isHashOnly) || _isHashOnlyRelative(candidate.rawHref || '', currentPageUrl),
    rel: String(candidate.rel || '').toLowerCase(),
    discoveredFromPageClass: candidate.discoveredFromPageClass || context.discoveredFromPageClass || 'document',
    currentPageUrl,
    host: parsed.hostname,
    pathname: parsed.pathname || '/',
    priorityFingerprint: buildPriorityFingerprint(parsed.href),
    priorityPathKey: `${parsed.hostname}${parsed.pathname || '/'}`,
  };
}

export function scoreLinkCandidate(candidate, context = {}) {
  const weights = { ...DEFAULT_FRONTIER_WEIGHTS, ...(context.weights || {}) };
  const reasons = [];
  let score = 0;

  if (candidate.sameHost) {
    const value = context.nextDepth <= 1 ? weights.sameHostEarly : weights.sameHostDeep;
    score += value;
    reasons.push(`same-host:${value}`);
  } else if (candidate.sameRegistrableDomain) {
    score += weights.sameDomain;
    reasons.push(`same-domain:${weights.sameDomain}`);
  }

  if (candidate.sourceKind === 'spa-route') {
    score += weights.spaRoute;
    reasons.push(`spa-route:${weights.spaRoute}`);
  } else if (candidate.sourceKind === 'form') {
    score += weights.formAction;
    reasons.push(`form-action:${weights.formAction}`);
  }

  const anchorText = candidate.anchorText.trim();
  if (anchorText.length >= 3) {
    score += weights.meaningfulAnchorText;
    reasons.push(`anchor-text:${weights.meaningfulAnchorText}`);
  }

  if (candidate.pathDepth <= 1) {
    score += weights.shortPath;
    reasons.push(`short-path:${weights.shortPath}`);
  } else if (candidate.pathDepth <= 2) {
    score += weights.mediumPath;
    reasons.push(`medium-path:${weights.mediumPath}`);
  } else if (candidate.pathDepth >= 4) {
    score += weights.deepPath;
    reasons.push(`deep-path:${weights.deepPath}`);
  }

  if (candidate.landmark === 'main') {
    score += weights.mainLandmark;
    reasons.push(`landmark-main:${weights.mainLandmark}`);
  } else if (CONTENT_LANDMARKS.has(candidate.landmark)) {
    score += weights.contentLandmark;
    reasons.push(`landmark-content:${weights.contentLandmark}`);
  } else if (candidate.landmark === 'nav') {
    score += weights.navLandmark;
    reasons.push(`landmark-nav:${weights.navLandmark}`);
  } else if (candidate.landmark === 'header') {
    score += weights.headerLandmark;
    reasons.push(`landmark-header:${weights.headerLandmark}`);
  } else if (candidate.landmark === 'aside') {
    score += weights.asideLandmark;
    reasons.push(`landmark-aside:${weights.asideLandmark}`);
  } else if (candidate.landmark === 'footer') {
    score += weights.footerLandmark;
    reasons.push(`landmark-footer:${weights.footerLandmark}`);
  }

  if (candidate.hasQuery) {
    const queryPenalty = Math.max(-6, candidate.queryParamCount * weights.queryPenaltyPerParam);
    score += queryPenalty;
    reasons.push(`query-params:${queryPenalty}`);
  }

  if (candidate.trackingQueryCount > 0) {
    score += weights.trackingQueryPenalty;
    reasons.push(`tracking-query:${weights.trackingQueryPenalty}`);
  }

  if (candidate.isHashOnly) {
    score += weights.hashOnlyPenalty;
    reasons.push(`hash-only:${weights.hashOnlyPenalty}`);
  }

  const familyKey = classifyPriorityFamily(candidate);
  if (familyKey === 'utility') {
    score += weights.utilityPenalty;
    reasons.push(`utility-family:${weights.utilityPenalty}`);
  } else if (familyKey === 'docs') {
    score += weights.docsPenalty;
    reasons.push(`docs-family:${weights.docsPenalty}`);
  } else if (familyKey === 'auth') {
    score += weights.authPenalty;
    reasons.push(`auth-family:${weights.authPenalty}`);
  } else if (familyKey === 'search') {
    score += weights.searchPenalty;
    reasons.push(`search-family:${weights.searchPenalty}`);
  }

  const marketingMatches = candidate.pathnameTokens.filter((token) => MARKETING_TOKENS.has(token)).length;
  if (marketingMatches > 0) {
    score += weights.marketingBoost;
    reasons.push(`marketing-token:${weights.marketingBoost}`);
  }

  if (_isUtilityContext(context.currentPageUrl, candidate.discoveredFromPageClass) && UTILITY_FAMILIES.has(familyKey)) {
    score += weights.utilityContextRelief;
    reasons.push(`utility-context-relief:${weights.utilityContextRelief}`);
  }

  return {
    ...candidate,
    score,
    familyKey,
    selectionReasons: reasons,
  };
}

export function prioritizeFrontierCandidates(candidates, context = {}) {
  const weights = { ...DEFAULT_FRONTIER_WEIGHTS, ...(context.weights || {}) };
  const diversityCaps = { ...DEFAULT_FRONTIER_DIVERSITY_CAPS, ...(context.diversityCaps || {}) };
  const queueBudget = Math.max(0, context.queueBudget || 0);
  const seen = new Map();

  for (const rawCandidate of candidates || []) {
    const enriched = rawCandidate?.normalizedUrl ? rawCandidate : enrichLinkCandidate(rawCandidate, context);
    if (!enriched) continue;

    const scored = scoreLinkCandidate(enriched, {
      ...context,
      weights,
    });
    const existing = seen.get(scored.normalizedUrl);
    if (!existing || scored.score > existing.score || (scored.score === existing.score && scored.domOrder < existing.domOrder)) {
      seen.set(scored.normalizedUrl, scored);
    }
  }

  const ranked = [...seen.values()].sort(compareFrontierCandidates);
  const selected = applyFrontierDiversity(ranked, queueBudget, diversityCaps);

  return {
    rankedCandidates: ranked,
    selectedCandidates: selected,
    topCandidates: ranked.slice(0, Math.max(queueBudget, 5)),
  };
}

export function compareFrontierCandidates(left, right) {
  if (right.score !== left.score) return right.score - left.score;
  if (left.sameHost !== right.sameHost) return left.sameHost ? -1 : 1;
  if (left.pathDepth !== right.pathDepth) return left.pathDepth - right.pathDepth;
  if (left.domOrder !== right.domOrder) return left.domOrder - right.domOrder;
  return left.normalizedUrl.localeCompare(right.normalizedUrl);
}

export function classifyPriorityFamily(candidate) {
  const tokens = new Set([
    ...candidate.pathnameTokens,
    ...tokenizePathname(candidate.anchorText),
  ]);

  if ([...tokens].some((token) => AUTH_TOKENS.has(token))) return 'auth';
  if ([...tokens].some((token) => SEARCH_TOKENS.has(token))) return 'search';
  if ([...tokens].some((token) => DOCS_TOKENS.has(token))) return 'docs';
  if ([...tokens].some((token) => UTILITY_TOKENS.has(token))) return 'utility';
  return 'content';
}

export function isTrackingQueryParam(key = '') {
  return TRACKING_QUERY_PARAM_PATTERNS.some((pattern) => pattern.test(String(key || '')));
}

function applyFrontierDiversity(rankedCandidates, queueBudget, diversityCaps) {
  if (queueBudget <= 0) return [];

  const selected = [];
  const deferred = [];
  const counts = {
    host: new Map(),
    family: new Map(),
    pathKey: new Map(),
    fingerprint: new Set(),
  };

  const otherHostCap = Math.max(1, Math.ceil(queueBudget * diversityCaps.outOfHostRatio));

  for (const candidate of rankedCandidates) {
    if (selected.length >= queueBudget) break;
    if (counts.fingerprint.has(candidate.priorityFingerprint)) continue;

    const hostCap = candidate.sameHost ? queueBudget : otherHostCap;
    if ((counts.host.get(candidate.host) || 0) >= hostCap) {
      deferred.push(candidate);
      continue;
    }

    const familyCap = UTILITY_FAMILIES.has(candidate.familyKey) ? diversityCaps.utilityFamilyPerBatch : queueBudget;
    if ((counts.family.get(candidate.familyKey) || 0) >= familyCap) {
      deferred.push(candidate);
      continue;
    }

    if (candidate.hasQuery && (counts.pathKey.get(candidate.priorityPathKey) || 0) >= diversityCaps.queryVariantPerPath) {
      deferred.push(candidate);
      continue;
    }

    rememberSelection(candidate, counts);
    selected.push(candidate);
  }

  for (const candidate of deferred) {
    if (selected.length >= queueBudget) break;
    if (counts.fingerprint.has(candidate.priorityFingerprint)) continue;
    if (candidate.hasQuery && (counts.pathKey.get(candidate.priorityPathKey) || 0) >= diversityCaps.queryVariantPerPath) {
      continue;
    }
    rememberSelection(candidate, counts);
    selected.push(candidate);
  }

  return selected;
}

function rememberSelection(candidate, counts) {
  counts.fingerprint.add(candidate.priorityFingerprint);
  counts.host.set(candidate.host, (counts.host.get(candidate.host) || 0) + 1);
  counts.family.set(candidate.familyKey, (counts.family.get(candidate.familyKey) || 0) + 1);
  if (candidate.hasQuery) {
    counts.pathKey.set(candidate.priorityPathKey, (counts.pathKey.get(candidate.priorityPathKey) || 0) + 1);
  }
}

function _isUtilityContext(currentPageUrl = '', discoveredFromPageClass = '') {
  if (String(discoveredFromPageClass || '').includes('auth')) return true;
  try {
    const url = new URL(currentPageUrl);
    const tokens = tokenizePathname(url.pathname);
    return tokens.some((token) => DOCS_TOKENS.has(token) || UTILITY_TOKENS.has(token));
  } catch {
    return false;
  }
}

function _isHashOnlyRelative(rawHref = '', currentPageUrl = '') {
  if (!rawHref || !currentPageUrl) return false;
  return rawHref.startsWith('#');
}

export function getFrontierDefaults() {
  return {
    frontierStrategy: 'ranked',
    frontierWeights: { ...DEFAULT_FRONTIER_WEIGHTS },
    frontierDiversityCaps: { ...DEFAULT_FRONTIER_DIVERSITY_CAPS },
    utilityPathPenaltyMode: 'deprioritize',
  };
}
