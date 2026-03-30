import { URL } from 'url';
import path from 'path';
import crypto from 'crypto';
import { getDomain } from 'tldts';
import { ensureExtension } from './file-utils.js';

const MAX_ASSET_PATH_LENGTH = 220;
const MAX_PATH_SEGMENT_LENGTH = 100;
const ASSET_HASH_LENGTH = 10;
const PAGE_IDENTITY_IGNORED_QUERY_PARAMS = new Set([
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

export function getDomainRoot(input, domainScope = 'registrable-domain') {
  const hostname = _getHostname(input);
  if (!hostname) return 'site';
  if (domainScope === 'hostname') return _toSafeName(hostname);
  return _toSafeName(getDomain(hostname) || hostname);
}

export function isInDomainScope(targetInput, baseInput, domainScope = 'registrable-domain') {
  const targetHost = _getHostname(targetInput);
  const baseHost = _getHostname(baseInput);
  if (!targetHost || !baseHost) return false;

  if (domainScope === 'hostname') {
    return targetHost === baseHost;
  }

  return getDomain(targetHost) === getDomain(baseHost);
}

export function normalizeCrawlUrl(urlStr) {
  try {
    const url = new URL(urlStr);
    url.hash = '';
    if (url.pathname !== '/' && url.pathname.endsWith('/')) {
      url.pathname = url.pathname.slice(0, -1);
    }
    return url.href;
  } catch {
    return urlStr;
  }
}

export function getPagePathFromUrl(absoluteUrl, options = {}) {
  return getViewPathFromUrl(absoluteUrl, options);
}

export function getViewPathFromUrl(absoluteUrl, options = {}) {
  try {
    const url = new URL(absoluteUrl);
    let pathname = decodeURIComponent(url.pathname || '/');
    pathname = pathname.replace(/\\/g, '/');
    pathname = pathname.replace(/;[^/]*/g, '');
    if (!pathname || pathname === '/') {
      pathname = '/index';
    } else if (pathname.endsWith('/')) {
      pathname = `${pathname}index`;
    } else if (!path.posix.extname(pathname)) {
      pathname = `${pathname}.html`;
    }

    pathname = pathname.split('?')[0].split('#')[0].replace(/^\/+/, '');
    let finalPath = pathname.endsWith('.html') ? pathname : `${pathname}.html`;
    finalPath = _applyQuerySuffixToViewPath(finalPath, options.querySuffix || '');
    if (!options.includeHostPrefix) {
      return finalPath;
    }

    return path.posix.join(_toSafeName(url.hostname || 'site'), finalPath);
  } catch {
    return 'index.html';
  }
}

export function normalizePageIdentitySearch(search = '') {
  const params = new URLSearchParams(String(search || '').replace(/^\?/, ''));
  const entries = [];

  for (const [key, value] of params.entries()) {
    if (PAGE_IDENTITY_IGNORED_QUERY_PARAMS.has(String(key || '').toLowerCase())) continue;
    entries.push([key, value]);
  }

  entries.sort(([leftKey, leftValue], [rightKey, rightValue]) => {
    if (leftKey === rightKey) return leftValue.localeCompare(rightValue);
    return leftKey.localeCompare(rightKey);
  });

  const normalized = new URLSearchParams();
  for (const [key, value] of entries) {
    normalized.append(key, value);
  }

  const rendered = normalized.toString();
  return rendered ? `?${rendered}` : '';
}

export function getNormalizedPageIdentityUrl(urlStr) {
  try {
    const url = new URL(urlStr);
    url.hash = '';
    url.search = normalizePageIdentitySearch(url.search);
    if (url.pathname !== '/' && url.pathname.endsWith('/')) {
      url.pathname = url.pathname.slice(0, -1);
    }
    return url.href;
  } catch {
    return urlStr;
  }
}

export function buildReplayQuerySuffix(search = '') {
  const normalizedSearch = normalizePageIdentitySearch(search);
  if (!normalizedSearch) return '';

  const params = new URLSearchParams(normalizedSearch.replace(/^\?/, ''));
  const parts = [];

  for (const [key, value] of params.entries()) {
    const safeKey = _toSafeName(key).slice(0, 24) || 'key';
    const safeValue = _toSafeName(value).slice(0, 24) || 'value';
    parts.push(`${safeKey}-${safeValue}`);
  }

  if (parts.length === 0) {
    return `__q_${crypto.createHash('sha1').update(normalizedSearch).digest('hex').slice(0, ASSET_HASH_LENGTH)}`;
  }

  let suffixBody = parts.join('_');
  if (suffixBody.length > 80) {
    const hash = crypto.createHash('sha1').update(normalizedSearch).digest('hex').slice(0, ASSET_HASH_LENGTH);
    suffixBody = `${suffixBody.slice(0, 60)}_${hash}`;
  }

  return `__q_${suffixBody}`;
}

export function buildReplayRouteFromSavedPath(savedPath = 'index.html') {
  const normalizedSavedPath = String(savedPath || 'index.html').replace(/\\/g, '/').replace(/^\/+/, '');
  if (!normalizedSavedPath || normalizedSavedPath === 'index.html') {
    return '/';
  }

  if (normalizedSavedPath.endsWith('/index.html')) {
    return `/${normalizedSavedPath.slice(0, -'/index.html'.length)}`;
  }

  return `/${normalizedSavedPath.replace(/\.html$/i, '')}`;
}

export function buildReplayRouteAliases(savedPath = 'index.html') {
  const normalizedSavedPath = String(savedPath || 'index.html').replace(/\\/g, '/').replace(/^\/+/, '');
  const primaryRoute = buildReplayRouteFromSavedPath(normalizedSavedPath);
  const aliases = new Set();

  aliases.add(`/${normalizedSavedPath}`);
  if (normalizedSavedPath === 'index.html') {
    aliases.add('/index');
  } else if (normalizedSavedPath.endsWith('/index.html')) {
    aliases.add(`/${normalizedSavedPath.slice(0, -'.html'.length)}`);
  }

  aliases.delete(primaryRoute);
  return [...aliases];
}

export function urlToLocalPath(absoluteUrl, baseUrl, domainScope = 'registrable-domain') {
  try {
    const url = new URL(absoluteUrl);
    let filePath = url.pathname;
    filePath = filePath.split('?')[0].split('#')[0];
    if (filePath.endsWith('/')) filePath += 'index.html';
    if (!path.extname(filePath)) filePath += '.html';
    filePath = filePath.replace(/^\//, '');

    if (!isInDomainScope(url.hostname, baseUrl, domainScope)) {
      filePath = path.join('external', _toSafeName(url.hostname), filePath);
    }

    return filePath;
  } catch {
    return absoluteUrl;
  }
}

export function resolveUrl(relativeUrl, baseUrl) {
  try {
    if (
      relativeUrl.startsWith('data:') ||
      relativeUrl.startsWith('blob:') ||
      relativeUrl.startsWith('javascript:')
    ) {
      return relativeUrl;
    }
    return new URL(relativeUrl, baseUrl).href;
  } catch {
    return relativeUrl;
  }
}

export function getAssetDir(mimeType, resourceType) {
  if (!mimeType) mimeType = '';

  if (resourceType === 'stylesheet' || mimeType.includes('css')) return 'css';
  if (resourceType === 'script' || mimeType.includes('javascript')) return 'js';
  if (resourceType === 'font' || mimeType.includes('font')) return 'font';
  if (resourceType === 'image' || mimeType.startsWith('image/')) return 'img';
  if (mimeType.startsWith('video/') || mimeType.startsWith('audio/')) return 'media';
  if (resourceType === 'document' || mimeType.includes('html')) return 'views';

  return 'misc';
}

export function getAssetPathFromUrl(
  absoluteUrl,
  baseUrl,
  mimeType = '',
  resourceType = '',
  domainScope = 'registrable-domain',
) {
  try {
    const url = new URL(absoluteUrl);
    const base = baseUrl ? new URL(baseUrl) : null;

    let pathname = url.pathname || '/';
    pathname = pathname.replace(/\\/g, '/');
    pathname = pathname.replace(/;[^/]*/g, '');
    if (!pathname || pathname === '/') pathname = '/index';
    if (pathname.endsWith('/')) pathname = `${pathname}index`;
    pathname = pathname.split('?')[0].split('#')[0];

    const assetDir = getAssetDir(mimeType, resourceType) || 'other';
    const filename = ensureExtension(path.posix.basename(pathname), mimeType);
    const dirname = path.posix.dirname(pathname);
    const hostSafe = _toSafeName(url.hostname || 'external_host');
    const inScope = base ? isInDomainScope(url.hostname, base.hostname, domainScope) : false;

    const segments = [assetDir];
    if (!inScope) segments.push('external');
    segments.push(hostSafe);

    if (dirname && dirname !== '/' && dirname !== '.') {
      segments.push(dirname.replace(/^\//, ''));
    }
    segments.push(filename);

    const regularPath = path.posix.join(...segments);
    if (_needsPathFallback(segments, regularPath)) {
      return _hashFallbackAssetPath(url, mimeType, filename, assetDir, !inScope);
    }

    return regularPath;
  } catch {
    return null;
  }
}

export function getFilenameFromUrl(urlStr) {
  try {
    const url = new URL(urlStr);
    let pathname = url.pathname.replace(/;[^/]*/g, '').split('?')[0].split('#')[0];
    let filename = path.basename(pathname);
    if (!filename || filename === '/') filename = 'index.html';
    return filename;
  } catch {
    return 'unknown';
  }
}

export function getRelativePath(from, to) {
  const fromDir = path.dirname(from);
  let relative = path.relative(fromDir, to);
  relative = relative.replace(/\\/g, '/');

  if (!relative.startsWith('.') && !relative.startsWith('/')) {
    relative = `./${relative}`;
  }

  return relative;
}

function _needsPathFallback(segments, candidatePath) {
  if (candidatePath.length > MAX_ASSET_PATH_LENGTH) return true;
  if (segments.some((part) => part.length > MAX_PATH_SEGMENT_LENGTH)) return true;
  return false;
}

function _applyQuerySuffixToViewPath(finalPath, querySuffix) {
  if (!querySuffix) return finalPath;

  const normalized = String(finalPath || '').replace(/\\/g, '/');
  if (!normalized) return normalized;

  if (normalized !== 'index.html' && normalized.endsWith('/index.html')) {
    return normalized.replace(/\/index\.html$/i, `${querySuffix}/index.html`);
  }

  return normalized.replace(/\.html$/i, `${querySuffix}.html`);
}

function _toSafeName(name) {
  const safe = String(name)
    .replace(/[^a-zA-Z0-9._-]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^[-._]+|[-._]+$/g, '');
  return safe || 'asset';
}

function _hashFallbackAssetPath(url, mimeType, filename, assetDir, isExternal) {
  const hash = crypto.createHash('sha1').update(url.href).digest('hex');
  const hashPrefix = hash.slice(0, ASSET_HASH_LENGTH);
  const hashShard1 = hash.slice(0, 2);
  const hashShard2 = hash.slice(2, 4);
  const safeHost = _toSafeName(url.hostname || 'local').slice(0, 40) || 'local';
  const ext = path.extname(filename);
  const stem = path.posix.basename(filename, ext) || 'asset';
  const safeStem = _toSafeName(stem).slice(0, 24) || 'asset';
  let safeLeaf = `${safeStem}_${hashPrefix}`;
  if (ext) {
    safeLeaf = `${safeLeaf}${ext}`;
  } else {
    safeLeaf = ensureExtension(safeLeaf, mimeType);
  }

  const segments = [_toSafeName(assetDir || 'misc')];
  if (isExternal) segments.push('external');
  segments.push(safeHost, hashShard1, hashShard2, safeLeaf);
  return path.posix.join(...segments);
}

const PRIVATE_IP_RANGES = [
  /^127\./,
  /^10\./,
  /^172\.(1[6-9]|2\d|3[01])\./,
  /^192\.168\./,
  /^0\./,
  /^169\.254\./,
  /^::1$/,
  /^fc00:/i,
  /^fd/i,
  /^fe80:/i,
];

export function validateUrlSafety(urlStr) {
  let parsed;
  try {
    parsed = new URL(urlStr);
  } catch {
    return { safe: false, reason: 'Invalid URL' };
  }

  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return { safe: false, reason: `Blocked protocol: ${parsed.protocol}` };
  }

  const hostname = parsed.hostname.toLowerCase();
  if (hostname === 'localhost' || hostname === '[::1]') {
    return { safe: false, reason: 'Localhost URLs are not allowed' };
  }

  for (const pattern of PRIVATE_IP_RANGES) {
    if (pattern.test(hostname)) {
      return { safe: false, reason: 'Private/internal IP addresses are not allowed' };
    }
  }

  return { safe: true, parsed };
}

function _getHostname(input) {
  try {
    if (input instanceof URL) return input.hostname;
    if (typeof input === 'string' && /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(input)) {
      return new URL(input).hostname;
    }
    if (typeof input === 'string') return input;
    return '';
  } catch {
    return '';
  }
}
