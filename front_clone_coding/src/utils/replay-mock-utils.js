import crypto from 'crypto';

import { normalizeCrawlUrl } from './url-utils.js';

const IGNORED_QUERY_PARAMS = new Set([
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_term',
  'utm_content',
  'utm_id',
  'gclid',
  'fbclid',
  'msclkid',
  '_ga',
  '_gl',
  'ref',
  'ref_src',
]);

export function hashValue(value) {
  if (
    value === null
    || value === undefined
    || value === ''
    || (typeof value === 'object' && Object.keys(value || {}).length === 0)
  ) {
    return 'no-body';
  }

  return crypto
    .createHash('sha1')
    .update(stableSerialize(value))
    .digest('hex')
    .slice(0, 12);
}

export function stableSerialize(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return `[${value.map((item) => stableSerialize(item)).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableSerialize(value[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

export function normalizeSearch(search = '') {
  const params = new URLSearchParams(String(search || '').replace(/^\?/, ''));
  const normalizedEntries = [];

  for (const [key, value] of params.entries()) {
    if (IGNORED_QUERY_PARAMS.has(key.toLowerCase())) continue;
    normalizedEntries.push([key, value]);
  }

  normalizedEntries.sort(([leftKey, leftValue], [rightKey, rightValue]) => {
    if (leftKey === rightKey) return leftValue.localeCompare(rightValue);
    return leftKey.localeCompare(rightKey);
  });

  const normalized = new URLSearchParams();
  for (const [key, value] of normalizedEntries) {
    normalized.append(key, value);
  }

  const rendered = normalized.toString();
  return rendered ? `?${rendered}` : '';
}

export function buildSearch(query = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query || {})) {
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, item);
    } else if (value !== undefined && value !== null) {
      params.append(key, String(value));
    }
  }
  return normalizeSearch(params.toString() ? `?${params.toString()}` : '');
}

export function normalizeAbsoluteRequestUrl(value) {
  try {
    const url = new URL(value);
    url.search = normalizeSearch(url.search);
    return url.href;
  } catch {
    return String(value || '');
  }
}

export function toReplayApiPath(pathname = '/', search = '') {
  const normalizedPath = pathname || '/';
  return `/api${normalizedPath}${normalizeSearch(search)}`;
}

export function buildRenderCriticalRuntimeMap(requests = []) {
  const map = new Map();

  for (const request of requests) {
    if (!['render-critical', 'render-supporting'].includes(request.replayRole)) continue;
    const absoluteUrl = normalizeAbsoluteRequestUrl(request.url);
    map.set(absoluteUrl, toReplayApiPath(request.pathname, request.search));
  }

  return map;
}

export function buildRenderCriticalCandidates(requests = []) {
  const seen = new Set();
  const candidates = [];

  for (const request of requests.filter((item) => ['render-critical', 'render-supporting'].includes(item.replayRole))) {
    const candidate = {
      candidateKey: buildRenderCriticalCandidateKey(request),
      pageUrl: request.pageUrl || '',
      normalizedPageUrl: normalizeCrawlUrl(request.pageUrl || ''),
      url: request.url,
      method: request.method,
      path: request.pathname,
      search: normalizeSearch(request.search),
      replayPath: toReplayApiPath(request.pathname, request.search),
      renderCriticalKind: request.renderCriticalKind || 'render-critical-bootstrap',
      replayRole: request.replayRole,
      expectedForReplay: request.expectedForReplay !== false,
      firstPaintDependency: request.firstPaintDependency || (request.expectedForReplay !== false ? 'strict' : 'supporting'),
      classificationReason: request.classificationReason || 'unclassified',
      dependencyEvidence: request.dependencyEvidence || [],
      bootstrapSignals: request.bootstrapSignals || {},
      operationName: request.graphQLOperationName || null,
      variablesHash: request.graphQLVariablesHash || 'no-body',
      documentHash: request.documentHash || 'no-body',
      graphQL: Boolean(request.graphQL),
    };
    const dedupeKey = `${candidate.normalizedPageUrl}|${candidate.candidateKey}`;
    if (seen.has(dedupeKey)) continue;
    seen.add(dedupeKey);
    candidates.push(candidate);
  }

  return candidates;
}

export function buildRenderCriticalCandidateKey(candidate) {
  return [
    candidate.method || 'GET',
    candidate.path || candidate.pathname || '/',
    normalizeSearch(candidate.search || ''),
    candidate.operationName || 'anonymous',
    candidate.variablesHash || 'no-body',
    candidate.documentHash || 'no-body',
  ].join(' ');
}

export function findHttpMockMatch(manifest = [], requestMeta = {}) {
  const normalizedSearch = normalizeSearch(requestMeta.search || '');

  const strictMatch = manifest.find((item) => {
    if (item.method !== requestMeta.method) return false;
    if (item.path !== requestMeta.path) return false;
    if ((item.normalizedSearch || normalizeSearch(item.search || '')) !== normalizedSearch) return false;

    if (item.matchStrategy === 'graphql-operation' || item.graphQL) {
      const details = item.graphQLDetails || {};
      const itemVariablesHash = details.variablesHash || item.graphQLVariablesHash || 'no-body';
      const itemDocumentHash = details.documentHash || 'no-body';
      return (details.operationName || item.graphQLOperationName || null) === (requestMeta.operationName || null)
        && itemVariablesHash === (requestMeta.variablesHash || 'no-body')
        && (
          (itemDocumentHash === (requestMeta.documentHash || 'no-body') && itemDocumentHash !== 'no-body')
          || (
            itemDocumentHash === 'no-body'
            && hashValue(details.extensions || null) === (requestMeta.extensionsHash || 'no-body')
          )
        );
    }

    return (item.bodyHash || 'no-body') === (requestMeta.bodyHash || 'no-body');
  });

  if (strictMatch) return strictMatch;

  return manifest.find((item) => {
    if (item.replayRole !== 'render-critical') return false;
    if (item.method !== requestMeta.method) return false;
    if (item.path !== requestMeta.path) return false;
    if ((item.normalizedSearch || normalizeSearch(item.search || '')) !== normalizedSearch) return false;
    if (!(item.matchStrategy === 'graphql-operation' || item.graphQL)) return false;

    const details = item.graphQLDetails || {};
    return (details.operationName || item.graphQLOperationName || null) === (requestMeta.operationName || null)
      && (details.variablesHash || item.graphQLVariablesHash || 'no-body') === (requestMeta.variablesHash || 'no-body');
  }) || null;
}
