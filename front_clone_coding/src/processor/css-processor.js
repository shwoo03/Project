import path from 'path';
import fs from 'fs/promises';
import postcss from 'postcss';
import postcssUrl from 'postcss-url';

import { resolveUrl, getRelativePath, getAssetPathFromUrl } from '../utils/url-utils.js';
import { saveFile, deduplicateFilename } from '../utils/file-utils.js';
import logger from '../utils/logger.js';
import { classifyExternalRuntime } from '../utils/external-runtime-utils.js';
import { batchParallel } from '../utils/concurrency-utils.js';
import { CSS_PROCESSING_CONCURRENCY } from '../utils/constants.js';

const CSS_ASSET_ROOT_SEGMENTS = new Set([
  'img',
  'image',
  'images',
  'css',
  'js',
  'font',
  'fonts',
  'media',
  'asset',
  'assets',
  'common',
  'portal',
  'board',
  'file',
  'files',
  'attach',
  'attached',
  'upload',
  'uploads',
]);

export default class CssProcessor {
  constructor(outputDir, baseUrl, urlMap, interceptor, options = {}) {
    this.outputDir = outputDir;
    this.baseUrl = baseUrl;
    this.urlMap = urlMap;
    this.interceptor = interceptor;
    this.assetRegistry = options.assetRegistry || null;
    this.processedFiles = new Set();
    this.cssFiles = new Map();
    this._usedNames = new Set();
    this.cssRecoveryRecords = new Map();
    this._pendingSaves = new Map();
  }

  async processAll() {
    logger.start('Starting CSS processing');

    let additionalAssets = 0;
    let importChains = 0;

    const cssFiles = [];
    for (const [url, localPath] of this.urlMap) {
      if (this._shouldProcessCssFile(url, localPath)) {
        const ownerPageUrl = this.interceptor.getLatestResponse(url)?.pageUrl || '';
        cssFiles.push({ url, localPath, ownerPageUrl });
        this.cssFiles.set(url, { localPath, ownerPageUrl });
      }
    }

    logger.update(`Analyzing ${cssFiles.length} CSS files`);

    const results = await batchParallel(cssFiles, CSS_PROCESSING_CONCURRENCY, async ({ url, localPath, ownerPageUrl }) => {
      return this._processCssFile(url, localPath, { ownerPageUrl, finalPass: false });
    });
    for (const entry of results) {
      if (entry.status === 'fulfilled' && entry.value) {
        additionalAssets += entry.value.additionalAssets;
        importChains += entry.value.importChains;
      }
    }

    const finalPass = await this._finalizeProcessedCssFiles();
    additionalAssets += finalPass.additionalAssets;

    const cssRecoverySummary = this._buildCssRecoverySummary();

    logger.succeed(`CSS processing done: ${cssFiles.length} files, +${additionalAssets} assets, ${importChains} import chains`);
    return { additionalAssets, importChains, cssRecoverySummary };
  }

  async _processCssFile(cssUrl, localPath, options = {}) {
    if (this.processedFiles.has(cssUrl)) {
      return { additionalAssets: 0, importChains: 0 };
    }
    this.processedFiles.add(cssUrl);

    const ownerPageUrl = options.ownerPageUrl || this.cssFiles.get(cssUrl)?.ownerPageUrl || '';
    this.cssFiles.set(cssUrl, { localPath, ownerPageUrl });

    const absolutePath = path.join(this.outputDir, 'public', localPath);
    let cssContent;

    try {
      cssContent = await fs.readFile(absolutePath, 'utf-8');
    } catch {
      logger.debug(`Failed to read CSS file: ${absolutePath}`);
      return { additionalAssets: 0, importChains: 0 };
    }

    cssContent = this._sanitizeCssContent(cssContent);
    if (!this._looksLikeCssContent(cssContent, cssUrl, localPath)) {
      logger.debug(`Skipping non-CSS asset that landed in the CSS pipeline: ${cssUrl}`);
      return { additionalAssets: 0, importChains: 0 };
    }

    const importResult = await this._processImports(cssContent, cssUrl, localPath, {
      ownerPageUrl,
      finalPass: Boolean(options.finalPass),
    });
    cssContent = importResult.css;

    const urlResult = await this._rewriteAssetUrls(cssContent, cssUrl, localPath, {
      ownerPageUrl,
      finalPass: Boolean(options.finalPass),
    });
    cssContent = urlResult.css;

    await saveFile(absolutePath, cssContent);

    return {
      additionalAssets: importResult.additionalAssets + urlResult.additionalAssets,
      importChains: importResult.importCount,
    };
  }

  async _processImports(css, cssUrl, cssLocalPath, options = {}) {
    let importCount = 0;
    let additionalAssets = 0;
    const ownerPageUrl = options.ownerPageUrl || '';
    const finalPass = Boolean(options.finalPass);

    let root;
    try {
      root = this._parseCssRoot(css, cssUrl);
    } catch (error) {
      logger.debug(`CSS import parsing fell back to regex rewrite: ${cssUrl} - ${error.message}`);
      return this._rewriteImportsWithoutParse(css, cssUrl, cssLocalPath, { ownerPageUrl, finalPass });
    }

    for (const node of root.nodes || []) {
      if (node.type !== 'atrule' || node.name !== 'import') continue;

      const importUrl = this._extractImportUrl(node.params);
      if (!importUrl || importUrl.startsWith('data:')) continue;

      const existingLocalReference = await this._resolveExistingLocalReference(cssLocalPath, importUrl);
      if (existingLocalReference) {
        node.params = node.params.replace(importUrl, getRelativePath(cssLocalPath, existingLocalReference));
        continue;
      }

      const absoluteImportUrl = resolveUrl(importUrl, cssUrl);
      const importResolution = await this._ensureAssetAvailable(absoluteImportUrl, 'text/css', {
        ownerPageUrl,
        sourceUrl: cssUrl,
        finalPass,
      });
      additionalAssets += importResolution.additionalAssets;

      if (!importResolution.localPath) {
        if (importResolution.inertReplacement && finalPass) {
          node.params = node.params.replace(importUrl, importResolution.inertReplacement);
        }
        continue;
      }

      const relativePath = getRelativePath(cssLocalPath, importResolution.localPath);
      node.params = node.params.replace(importUrl, relativePath);
      await this._processCssFile(absoluteImportUrl, importResolution.localPath, { ownerPageUrl, finalPass });
      importCount += 1;
    }

    return {
      css: root.toString(),
      importCount,
      additionalAssets,
    };
  }

  async _rewriteAssetUrls(css, cssUrl, cssLocalPath, options = {}) {
    let additionalAssets = 0;
    const ownerPageUrl = options.ownerPageUrl || '';
    const finalPass = Boolean(options.finalPass);

    const runPostCss = async (inputCss) => postcss([
      postcssUrl({
        url: async ({ url }) => {
          if (!url || url.startsWith('data:') || url.startsWith('#') || url.startsWith('about:')) {
            return url;
          }

          const existingLocalReference = await this._resolveExistingLocalReference(cssLocalPath, url);
          if (existingLocalReference) {
            return getRelativePath(cssLocalPath, existingLocalReference);
          }

          const absoluteAssetUrl = resolveUrl(url, cssUrl);
          const assetResolution = await this._ensureAssetAvailable(absoluteAssetUrl, '', {
            ownerPageUrl,
            sourceUrl: cssUrl,
            finalPass,
          });
          additionalAssets += assetResolution.additionalAssets;

          if (!assetResolution.localPath) {
            return assetResolution.inertReplacement && finalPass ? assetResolution.inertReplacement : url;
          }
          return getRelativePath(cssLocalPath, assetResolution.localPath);
        },
      }),
    ]).process(inputCss, {
      from: undefined,
      map: false,
    });

    let result;
    try {
      result = await runPostCss(css);
    } catch (error) {
      const sanitizedCss = this._stripProblematicSourceMapLines(css);
      if (sanitizedCss !== css) {
        try {
          logger.debug(`CSS URL rewrite recovered after sanitizing malformed directives: ${cssUrl}`);
          result = await runPostCss(sanitizedCss);
          return { css: result.css, additionalAssets };
        } catch (retryError) {
          logger.debug(`CSS URL rewrite fell back to regex rewrite after sanitizing failure: ${cssUrl} - ${retryError.message}`);
          return this._rewriteAssetUrlsWithoutPostCss(sanitizedCss, cssUrl, cssLocalPath, { ownerPageUrl, finalPass });
        }
      }
      logger.debug(`CSS URL rewrite fell back to regex rewrite: ${cssUrl} - ${error.message}`);
      return this._rewriteAssetUrlsWithoutPostCss(css, cssUrl, cssLocalPath, { ownerPageUrl, finalPass });
    }

    return { css: result.css, additionalAssets };
  }

  async _rewriteImportsWithoutParse(css, cssUrl, cssLocalPath, options = {}) {
    let importCount = 0;
    let additionalAssets = 0;
    const ownerPageUrl = options.ownerPageUrl || '';
    const finalPass = Boolean(options.finalPass);

    const rewrittenCss = await this._replaceAsync(
      css,
      /@import\s+(?:url\(\s*)?(['"]?)([^'")\s;]+)\1\s*\)?([^;]*);/gi,
      async (match, quote, importUrl, suffix = '') => {
        if (!importUrl || importUrl.startsWith('data:')) {
          return match;
        }

        const existingLocalReference = await this._resolveExistingLocalReference(cssLocalPath, importUrl);
        if (existingLocalReference) {
          const nextQuote = quote || '"';
          return `@import ${nextQuote}${getRelativePath(cssLocalPath, existingLocalReference)}${nextQuote}${suffix};`;
        }

        const absoluteImportUrl = resolveUrl(importUrl, cssUrl);
        const importResolution = await this._ensureAssetAvailable(absoluteImportUrl, 'text/css', {
          ownerPageUrl,
          sourceUrl: cssUrl,
          finalPass,
        });
        additionalAssets += importResolution.additionalAssets;

        if (!importResolution.localPath) {
          if (importResolution.inertReplacement && finalPass) {
            const nextQuote = quote || '"';
            return `@import ${nextQuote}${importResolution.inertReplacement}${nextQuote}${suffix};`;
          }
          return match;
        }

        const relativePath = getRelativePath(cssLocalPath, importResolution.localPath);
        await this._processCssFile(absoluteImportUrl, importResolution.localPath, { ownerPageUrl, finalPass });
        importCount += 1;

        const nextQuote = quote || '"';
        return `@import ${nextQuote}${relativePath}${nextQuote}${suffix};`;
      },
    );

    return {
      css: rewrittenCss,
      importCount,
      additionalAssets,
    };
  }

  async _rewriteAssetUrlsWithoutPostCss(css, cssUrl, cssLocalPath, options = {}) {
    let additionalAssets = 0;
    const ownerPageUrl = options.ownerPageUrl || '';
    const finalPass = Boolean(options.finalPass);

    const rewrittenCss = await this._replaceAsync(
      css,
      /url\(\s*(['"]?)([^'")]+)\1\s*\)/gi,
      async (match, quote, assetUrl) => {
        const normalizedUrl = String(assetUrl || '').trim();
        if (!normalizedUrl || normalizedUrl.startsWith('data:') || normalizedUrl.startsWith('#') || normalizedUrl.startsWith('about:')) {
          return match;
        }

        const existingLocalReference = await this._resolveExistingLocalReference(cssLocalPath, normalizedUrl);
        if (existingLocalReference) {
          const nextQuote = quote || '';
          return `url(${nextQuote}${getRelativePath(cssLocalPath, existingLocalReference)}${nextQuote})`;
        }

        const absoluteAssetUrl = resolveUrl(normalizedUrl, cssUrl);
        const assetResolution = await this._ensureAssetAvailable(absoluteAssetUrl, '', {
          ownerPageUrl,
          sourceUrl: cssUrl,
          finalPass,
        });
        additionalAssets += assetResolution.additionalAssets;

        if (!assetResolution.localPath) {
          if (assetResolution.inertReplacement && finalPass) {
            const nextQuote = quote || '';
            return `url(${nextQuote}${assetResolution.inertReplacement}${nextQuote})`;
          }
          return match;
        }

        const relativePath = getRelativePath(cssLocalPath, assetResolution.localPath);
        const nextQuote = quote || '';
        return `url(${nextQuote}${relativePath}${nextQuote})`;
      },
    );

    return {
      css: rewrittenCss,
      additionalAssets,
    };
  }

  async _ensureAssetAvailable(url, fallbackMimeType = '', options = {}) {
    const ownerPageUrl = options.ownerPageUrl || '';
    const finalPass = Boolean(options.finalPass);
    const resourceType = fallbackMimeType.includes('css')
      ? 'stylesheet'
      : this._inferResourceType(url, fallbackMimeType);
    const canonicalizedTarget = this._canonicalizeCssAssetUrl(url);
    const lookupUrls = [...new Set([url, canonicalizedTarget.url])].filter(Boolean);
    const record = this._getCssRecoveryRecord(url, canonicalizedTarget.url, ownerPageUrl, {
      resourceType,
      canonicalizationApplied: canonicalizedTarget.applied,
      canonicalizationReason: canonicalizedTarget.reason,
      renderCritical: this._isCssAssetRenderCritical(canonicalizedTarget.url, resourceType),
    });

    if (canonicalizedTarget.reason === 'malformed-unrecoverable') {
      this._updateCssRecoveryRecord(record, { status: 'failed', failureReason: canonicalizedTarget.reason });
      return {
        localPath: null,
        additionalAssets: 0,
        inertReplacement: finalPass ? this._buildInertCssReplacement(resourceType) : null,
      };
    }

    for (const candidateUrl of lookupUrls) {
      const existingPath = await this._resolveKnownLocalPath(candidateUrl, fallbackMimeType);
      if (existingPath) {
        this.urlMap.set(url, existingPath);
        this._updateCssRecoveryRecord(record, { status: 'recovered', resolvedUrl: candidateUrl, localPath: existingPath });
        return { localPath: existingPath, additionalAssets: 0, inertReplacement: null };
      }

      const response = this.interceptor.getLatestResponse(candidateUrl);
      if (response?.body) {
        const localPath = await this._saveAdditionalAsset(candidateUrl, response, { ownerPageUrl });
        if (localPath) {
          this.urlMap.set(url, localPath);
          this._updateCssRecoveryRecord(record, { status: 'recovered', resolvedUrl: candidateUrl, localPath });
        }
        return {
          localPath,
          additionalAssets: localPath ? 1 : 0,
          inertReplacement: null,
        };
      }
    }

    let lastFailureReason = 'fetch-failed';
    for (const candidateUrl of lookupUrls) {
      const fetchedResult = await this._fetchMissingAsset(candidateUrl, fallbackMimeType, { resourceType });
      const fetchedResponse = normalizeFetchedCssResponse(fetchedResult);
      if (fetchedResponse.response) {
        const localPath = await this._saveAdditionalAsset(candidateUrl, fetchedResponse.response, { ownerPageUrl });
        if (localPath) {
          this.urlMap.set(url, localPath);
          this._updateCssRecoveryRecord(record, { status: 'recovered', resolvedUrl: candidateUrl, localPath });
        }
        return {
          localPath,
          additionalAssets: localPath ? 1 : 0,
          inertReplacement: null,
        };
      }
      lastFailureReason = fetchedResponse.failureReason || lastFailureReason;
    }

    this._updateCssRecoveryRecord(record, { status: 'failed', failureReason: lastFailureReason });
    return {
      localPath: null,
      additionalAssets: 0,
      inertReplacement: finalPass ? this._buildInertCssReplacement(resourceType) : null,
    };
  }

  _extractImportUrl(params) {
    const match = params.match(/^(?:url\()?['"]?([^'")\s]+)['"]?\)?/i);
    return match ? match[1] : null;
  }

  async _saveAdditionalAsset(url, response, options = {}) {
    if (this._pendingSaves.has(url)) {
      return this._pendingSaves.get(url);
    }
    const promise = this._doSaveAdditionalAsset(url, response, options);
    this._pendingSaves.set(url, promise);
    try {
      return await promise;
    } finally {
      this._pendingSaves.delete(url);
    }
  }

  async _doSaveAdditionalAsset(url, response, options = {}) {
    const proposedPath = getAssetPathFromUrl(url, this.baseUrl, response.mimeType, response.type);
    if (!proposedPath) return null;

    const relativeDir = path.posix.dirname(proposedPath);
    const rawFilename = path.posix.basename(proposedPath);
    const filename = deduplicateFilename(this._usedNames, relativeDir, rawFilename);

    const relativePath = path.posix.join(relativeDir, filename);
    const absolutePath = path.join(this.outputDir, 'public', relativePath);

    await saveFile(absolutePath, response.body);

    const normalizedPath = relativePath.replace(/\\/g, '/');
    this.urlMap.set(url, normalizedPath);
    this.assetRegistry?.registerDirectAsset({
      url,
      savedPath: normalizedPath,
      mimeType: response.mimeType,
      resourceType: response.type,
      status: response.status || 200,
      size: response.body?.length || 0,
      pageUrl: response.pageUrl || options.ownerPageUrl || '',
      encoding: response.encoding || null,
    });

    return normalizedPath;
  }

  async _fetchMissingAsset(url, fallbackMimeType = '', options = {}) {
    const resourceType = fallbackMimeType.includes('css')
      ? 'stylesheet'
      : (options.resourceType || this._inferResourceType(url, fallbackMimeType));
    const classification = classifyExternalRuntime(url, { targetUrl: this.baseUrl });
    if (
      classification.category === 'anti-abuse'
      || (classification.category === 'non-critical-runtime' && !['font', 'image', 'stylesheet'].includes(resourceType))
    ) {
      return { response: null, failureReason: 'skipped-non-critical-external' };
    }

    const timeoutSequence = this._getFetchTimeoutSequence(url, resourceType);

    for (const timeoutMs of timeoutSequence) {
      try {
        const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
        if (!response.ok) {
          if (response.status >= 400 && response.status < 500) {
            return { response: null, failureReason: `http-${response.status}` };
          }
          continue;
        }

        const body = Buffer.from(await response.arrayBuffer());
        if (!body.length) {
          return { response: null, failureReason: 'empty-body' };
        }

        return {
          response: {
            body,
            mimeType: response.headers.get('content-type')?.split(';')[0] || fallbackMimeType || '',
            type: resourceType,
            status: response.status,
          },
          failureReason: null,
        };
      } catch (error) {
        logger.debug(`CSS asset fetch skipped: ${url} - ${error.message}`);
        if (/aborted|timeout/i.test(error.message)) {
          continue;
        }
        return { response: null, failureReason: 'fetch-failed' };
      }
    }

    return { response: null, failureReason: 'timeout' };
  }

  _sanitizeCssContent(css) {
    if (!css) return '';

    return String(css)
      .replace(/^\uFEFF/, '')
      .replace(/^[\t /*#@-]*sourceMappingURL=https?:\/\/[^\r\n]+$/gm, '')
      .replace(/^[\t /*#@-]*sourceURL=https?:\/\/[^\r\n]+$/gm, '')
      .replace(/\r?\n{3,}/g, '\n\n');
  }

  _shouldProcessCssFile(url, localPath) {
    const normalizedPath = String(localPath || '').toLowerCase();
    if (normalizedPath.endsWith('.css')) return true;

    const response = this.interceptor.getLatestResponse(url);
    const mimeType = String(response?.mimeType || '').toLowerCase();
    const resourceType = String(response?.type || '').toLowerCase();
    return mimeType.includes('css') || resourceType === 'stylesheet';
  }

  _looksLikeCssContent(css, cssUrl, localPath) {
    const normalizedPath = String(localPath || cssUrl || '').toLowerCase();
    if (normalizedPath.endsWith('.css')) return true;

    const response = this.interceptor.getLatestResponse(cssUrl);
    const mimeType = String(response?.mimeType || '').toLowerCase();
    if (mimeType.includes('css')) return true;

    const sample = String(css || '').slice(0, 256);
    if (!sample) return false;
    if (/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(sample)) return false;
    if (/(@import|@charset|url\(|\{|\}|--[a-z0-9_-]+\s*:)/i.test(sample)) return true;
    return /[.#][a-z0-9_-]+\s*\{|[a-z-]+\s*:\s*[^;]+;/i.test(sample);
  }

  _stripProblematicSourceMapLines(css) {
    return String(css)
      .replace(/^.*sourceMappingURL=.*$/gm, '')
      .replace(/^.*sourceURL=.*$/gm, '')
      .replace(/\r?\n{3,}/g, '\n\n');
  }

  _parseCssRoot(css, cssUrl = '') {
    try {
      return postcss.parse(css);
    } catch (error) {
      const sanitizedCss = this._stripProblematicSourceMapLines(css);
      if (sanitizedCss === css) {
        throw error;
      }
      logger.debug(`CSS parse recovered after sanitizing malformed directives: ${cssUrl}`);
      return postcss.parse(sanitizedCss);
    }
  }

  async _replaceAsync(input, pattern, replacer) {
    const source = String(input ?? '');
    const matches = Array.from(source.matchAll(pattern));
    if (matches.length === 0) {
      return source;
    }

    let output = '';
    let lastIndex = 0;
    for (const match of matches) {
      const [fullMatch] = match;
      const matchIndex = match.index ?? 0;
      output += source.slice(lastIndex, matchIndex);
      output += await replacer(...match);
      lastIndex = matchIndex + fullMatch.length;
    }

    output += source.slice(lastIndex);
    return output;
  }

  static extractCssVariables(css) {
    const variables = new Map();
    const varRegex = /--([\w-]+)\s*:\s*([^;]+);/g;
    let match;
    while ((match = varRegex.exec(css)) !== null) {
      variables.set(`--${match[1]}`, match[2].trim());
    }
    return variables;
  }

  static findUnusedSelectors(css, $) {
    const unused = [];
    const selectorRegex = /([^{}@]+)\{[^}]*\}/g;
    let match;
    while ((match = selectorRegex.exec(css)) !== null) {
      const selector = match[1].trim();
      if (selector.startsWith('@') || selector.startsWith(':') || selector === '') continue;
      const singleSelectors = selector.split(',').map((item) => item.trim());
      for (const sel of singleSelectors) {
        try {
          if ($(sel).length === 0) unused.push(sel);
        } catch {
          // Ignore selectors unsupported by cheerio.
        }
      }
    }
    return unused;
  }

  async _resolveKnownLocalPath(url, fallbackMimeType = '') {
    const mappedPath = this.urlMap.get(url);
    if (mappedPath) {
      return mappedPath;
    }

    const inferredType = fallbackMimeType.includes('css')
      ? 'stylesheet'
      : this._inferResourceType(url, fallbackMimeType);
    const proposedPath = getAssetPathFromUrl(url, this.baseUrl, fallbackMimeType, inferredType);
    if (!proposedPath) {
      return null;
    }

    const absolutePath = path.join(this.outputDir, 'public', proposedPath);
    try {
      await fs.access(absolutePath);
      const normalizedPath = proposedPath.replace(/\\/g, '/');
      this.urlMap.set(url, normalizedPath);
      return normalizedPath;
    } catch {
      return null;
    }
  }

  async _resolveExistingLocalReference(cssLocalPath, assetUrl) {
    const normalizedUrl = String(assetUrl || '').trim();
    if (!normalizedUrl || /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(normalizedUrl) || normalizedUrl.startsWith('//')) {
      return null;
    }

    const candidatePath = normalizedUrl.startsWith('/')
      ? normalizedUrl.replace(/^\/+/, '')
      : path.posix.normalize(path.posix.join(path.posix.dirname(cssLocalPath), normalizedUrl));

    if (!candidatePath || candidatePath.startsWith('..')) {
      return null;
    }

    const normalizedCandidatePath = candidatePath.replace(/\\/g, '/');
    if ([...this.urlMap.values()].includes(normalizedCandidatePath)) {
      return normalizedCandidatePath;
    }

    try {
      await fs.access(path.join(this.outputDir, 'public', candidatePath));
      return normalizedCandidatePath;
    } catch {
      return null;
    }
  }

  async _finalizeProcessedCssFiles() {
    let additionalAssets = 0;

    for (const [cssUrl, cssMeta] of this.cssFiles.entries()) {
      const absolutePath = path.join(this.outputDir, 'public', cssMeta.localPath);
      let cssContent;
      try {
        cssContent = await fs.readFile(absolutePath, 'utf-8');
      } catch {
        continue;
      }

      const sanitizedCss = this._sanitizeCssContent(cssContent);
      const importResult = await this._processImports(sanitizedCss, cssUrl, cssMeta.localPath, {
        ownerPageUrl: cssMeta.ownerPageUrl || '',
        finalPass: true,
      });
      const urlResult = await this._rewriteAssetUrls(importResult.css, cssUrl, cssMeta.localPath, {
        ownerPageUrl: cssMeta.ownerPageUrl || '',
        finalPass: true,
      });
      additionalAssets += importResult.additionalAssets + urlResult.additionalAssets;

      if (urlResult.css !== cssContent) {
        await saveFile(absolutePath, urlResult.css);
      }
    }

    return { additionalAssets };
  }

  _getFetchTimeoutSequence(url, resourceType) {
    const classification = classifyExternalRuntime(url, { targetUrl: this.baseUrl });
    const isRenderCritical = classification.category === 'render-critical-asset' || this._isCssAssetRenderCritical(url, resourceType);
    const isOwnedCssAsset = ['font', 'image', 'stylesheet'].includes(resourceType);
    if (isRenderCritical && isOwnedCssAsset) {
      return [10000, 20000];
    }
    return [10000];
  }

  _inferResourceType(url, fallbackMimeType = '') {
    const lowerMime = String(fallbackMimeType || '').toLowerCase();
    if (lowerMime.includes('css')) return 'stylesheet';
    if (/\.(woff2?|ttf|otf|eot)(?:$|\?)/i.test(url)) return 'font';
    if (/\.(png|jpe?g|gif|webp|avif|svg)(?:$|\?)/i.test(url)) return 'image';
    if (/\.css(?:$|\?)/i.test(url)) return 'stylesheet';
    return '';
  }

  _canonicalizeCssAssetUrl(url) {
    try {
      const targetUrl = new URL(url);
      const baseUrl = new URL(this.baseUrl);
      if (targetUrl.origin !== baseUrl.origin) {
        return { url: targetUrl.href, applied: false, reason: null };
      }

      const hostSegment = targetUrl.hostname.toLowerCase();
      let segments = targetUrl.pathname.split('/').filter(Boolean);
      let applied = false;

      const collapseSegments = () => {
        for (let index = 1; index < segments.length - 1; index += 1) {
          const current = segments[index]?.toLowerCase();
          if (current !== hostSegment) continue;

          const previous = segments[index - 1]?.toLowerCase();
          const next = segments[index + 1]?.toLowerCase();
          if (previous && next && previous === next && CSS_ASSET_ROOT_SEGMENTS.has(previous)) {
            segments = [...segments.slice(0, index), ...segments.slice(index + 2)];
            return true;
          }
          if (previous && CSS_ASSET_ROOT_SEGMENTS.has(previous)) {
            segments = [...segments.slice(0, index), ...segments.slice(index + 1)];
            return true;
          }
        }
        return false;
      };

      while (collapseSegments()) {
        applied = true;
      }

      if (!applied) {
        return { url: targetUrl.href, applied: false, reason: null };
      }
      if (segments.length === 0) {
        return { url: targetUrl.href, applied: false, reason: 'malformed-unrecoverable' };
      }

      const normalizedUrl = new URL(targetUrl.href);
      normalizedUrl.pathname = `/${segments.join('/')}`.replace(/\/{2,}/g, '/');
      return {
        url: normalizedUrl.href,
        applied: true,
        reason: 'same-origin-host-path-collapse',
      };
    } catch {
      return { url, applied: false, reason: 'malformed-unrecoverable' };
    }
  }

  _getCssRecoveryRecord(originalUrl, resolvedUrl, ownerPageUrl, options = {}) {
    const recordKey = `${ownerPageUrl || ''}|${resolvedUrl || originalUrl}`;
    if (!this.cssRecoveryRecords.has(recordKey)) {
      this.cssRecoveryRecords.set(recordKey, {
        key: recordKey,
        originalUrl,
        resolvedUrl: resolvedUrl || originalUrl,
        ownerPageUrl: ownerPageUrl || '',
        resourceType: options.resourceType || '',
        renderCritical: Boolean(options.renderCritical),
        canonicalizationApplied: Boolean(options.canonicalizationApplied),
        canonicalizationReason: options.canonicalizationReason || null,
        status: 'pending',
        failureReason: null,
        localPath: null,
      });
    }

    return this.cssRecoveryRecords.get(recordKey);
  }

  _updateCssRecoveryRecord(record, patch = {}) {
    const statusRank = {
      pending: 0,
      skipped: 1,
      failed: 2,
      recovered: 3,
    };
    const nextStatus = patch.status || record.status;
    if (statusRank[nextStatus] >= statusRank[record.status]) {
      record.status = nextStatus;
      if (patch.failureReason) {
        record.failureReason = patch.failureReason;
      }
      if (patch.localPath) {
        record.localPath = patch.localPath;
      }
      if (patch.resolvedUrl) {
        record.resolvedUrl = patch.resolvedUrl;
      }
    }

    if (patch.canonicalizationApplied) {
      record.canonicalizationApplied = true;
    }
    if (patch.canonicalizationReason) {
      record.canonicalizationReason = patch.canonicalizationReason;
    }
  }

  _isCssAssetRenderCritical(url, resourceType = '') {
    if (['font', 'image', 'stylesheet'].includes(resourceType) && isSameOrigin(url, this.baseUrl)) {
      return true;
    }
    return classifyExternalRuntime(url, { targetUrl: this.baseUrl }).category === 'render-critical-asset';
  }

  _buildInertCssReplacement(resourceType = '') {
    if (resourceType === 'stylesheet') {
      return 'data:text/css,';
    }
    return 'data:,';
  }

  _buildCssRecoverySummary() {
    const records = [...this.cssRecoveryRecords.values()];
    const cssAssetFailureReasons = {};
    const pages = new Map();

    for (const record of records) {
      if (record.failureReason) {
        cssAssetFailureReasons[record.failureReason] = (cssAssetFailureReasons[record.failureReason] || 0) + 1;
      }

      const pageKey = record.ownerPageUrl || '__unowned__';
      if (!pages.has(pageKey)) {
        pages.set(pageKey, {
          pageUrl: record.ownerPageUrl || '',
          cssAssetsDiscovered: 0,
          cssAssetsRecovered: 0,
          cssAssetsFailed: 0,
          cssAssetsSkipped: 0,
          missingCriticalCssAssets: 0,
          cssRecoveryWarnings: [],
        });
      }

      const pageSummary = pages.get(pageKey);
      pageSummary.cssAssetsDiscovered += 1;
      if (record.status === 'recovered') pageSummary.cssAssetsRecovered += 1;
      if (record.status === 'failed') pageSummary.cssAssetsFailed += 1;
      if (record.status === 'skipped') pageSummary.cssAssetsSkipped += 1;
      if (record.renderCritical && record.status !== 'recovered') {
        pageSummary.missingCriticalCssAssets += 1;
      }
      if (record.failureReason && !pageSummary.cssRecoveryWarnings.includes(record.failureReason)) {
        pageSummary.cssRecoveryWarnings.push(record.failureReason);
      }
    }

    const pageSummaries = [...pages.values()].map((summary) => ({
      ...summary,
      cssRecoveryStatus: getCssRecoveryStatus(summary),
    }));

    return {
      cssAssetsDiscovered: records.length,
      cssAssetsRecovered: records.filter((record) => record.status === 'recovered').length,
      cssAssetsFailed: records.filter((record) => record.status === 'failed').length,
      cssAssetsSkipped: records.filter((record) => record.status === 'skipped').length,
      cssAssetFailureReasons,
      cssAssetCanonicalizationApplied: records.filter((record) => record.canonicalizationApplied).length,
      pages: pageSummaries,
    };
  }
}

function getCssRecoveryStatus(summary) {
  if (!summary.cssAssetsDiscovered) {
    return 'no-css-assets';
  }
  if (summary.missingCriticalCssAssets > 0) {
    return 'missing-critical-assets';
  }
  if (summary.cssAssetsFailed > 0 || summary.cssAssetsSkipped > 0) {
    return 'partial';
  }
  return 'complete';
}

function isSameOrigin(left, right) {
  try {
    return new URL(left).origin === new URL(right).origin;
  } catch {
    return false;
  }
}

function normalizeFetchedCssResponse(value) {
  if (!value) {
    return { response: null, failureReason: 'fetch-failed' };
  }
  if (value.response || value.failureReason) {
    return value;
  }
  if (value.body) {
    return { response: value, failureReason: null };
  }
  return { response: null, failureReason: 'fetch-failed' };
}
