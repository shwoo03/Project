import path from 'path';
import fs from 'fs/promises';
import { resolveUrl, getRelativePath, getAssetPathFromUrl } from '../utils/url-utils.js';
import { saveFile, deduplicateFilename } from '../utils/file-utils.js';
import logger from '../utils/logger.js';

/**
 * CSS ??
 * ???CSS ? ????url(), @import, @font-face ??
 * ? ????? ???.
 */
export default class CssProcessor {
  /**
   * @param {string} outputDir -  ??
   * @param {string} baseUrl - ? ???URL
   * @param {Map<string, string>} urlMap -  URL ??  
   * @param {import('../crawler/network-interceptor.js').default} interceptor - ?? ??
   */
  constructor(outputDir, baseUrl, urlMap, interceptor) {
    this.outputDir = outputDir;
    this.baseUrl = baseUrl;
    this.urlMap = urlMap;
    this.interceptor = interceptor;
    this.processedFiles = new Set();
    this._usedNames = new Set();
  }

  /**
   *  CSS ???
   * @returns {{ additionalAssets: number, importChains: number }}
   */
  async processAll() {
    logger.start('Starting CSS processing');

    let additionalAssets = 0;
    let importChains = 0;

    // urlMap? CSS ???
    const cssFiles = [];
    for (const [url, localPath] of this.urlMap) {
      if (localPath.endsWith('.css') || localPath.includes('assets/css/')) {
        cssFiles.push({ url, localPath });
      }
    }

    logger.update(`Analyzing ${cssFiles.length} CSS files`);

    for (const { url, localPath } of cssFiles) {
      const result = await this._processCssFile(url, localPath);
      additionalAssets += result.additionalAssets;
      importChains += result.importChains;
    }

    logger.succeed(`CSS processing done: ${cssFiles.length} files, +${additionalAssets} assets, ${importChains} import chains`);

    return { additionalAssets, importChains };
  }

  /**
   *  CSS ? 
   * @param {string} cssUrl - CSS ???? URL
   * @param {string} localPath -  ?? 
   * @returns {{ additionalAssets: number, importChains: number }}
   */
  async _processCssFile(cssUrl, localPath) {
    if (this.processedFiles.has(cssUrl)) {
      return { additionalAssets: 0, importChains: 0 };
    }
    this.processedFiles.add(cssUrl);

    // css ???? ?????public/ ?
    const absolutePath = path.join(this.outputDir, 'public', localPath);
    let cssContent;

    try {
      cssContent = await fs.readFile(absolutePath, 'utf-8');
    } catch {
      logger.debug(`Failed to read CSS file: ${absolutePath}`);
      return { additionalAssets: 0, importChains: 0 };
    }

    let additionalAssets = 0;
    let importChains = 0;

    // 1. @import 
    const importResult = await this._processImports(cssContent, cssUrl, localPath);
    cssContent = importResult.css;
    importChains += importResult.importCount;
    additionalAssets += importResult.additionalAssets;

    // 2. url()  
    const urlResult = await this._processUrls(cssContent, cssUrl, localPath);
    cssContent = urlResult.css;
    additionalAssets += urlResult.additionalAssets;

    // 3. ??CSS ? ???    await saveFile(absolutePath, cssContent);

    return { additionalAssets, importChains };
  }

  /**
   * @import  
   * - @import url("path") ??? ? ?? ?
   * - @import "path" ???? ?
   */
  async _processImports(css, cssUrl, cssLocalPath) {
    let importCount = 0;
    let additionalAssets = 0;

    // @import url("...") ? @import "..."
    const importRegex = /@import\s+(?:url\()?['"]?([^'"\);]+)['"]?\)?([^;]*);/g;
    const matches = [...css.matchAll(importRegex)];

    for (const match of matches) {
      const importUrl = match[1].trim();
      if (!importUrl || importUrl.startsWith('data:')) continue;

      const absoluteImportUrl = resolveUrl(importUrl, cssUrl);

      // ?? ?????? ?
      let importLocalPath = this.urlMap.get(absoluteImportUrl);

      if (!importLocalPath) {
        // ?? ???  ?
        const response = this.interceptor.getLatestResponse(absoluteImportUrl);
        if (response && response.body) {
          importLocalPath = await this._saveAdditionalAsset(absoluteImportUrl, response);
          additionalAssets++;
        }
      }

      if (importLocalPath) {
        // @import ? ?? ?
        const relativePath = getRelativePath(cssLocalPath, importLocalPath);
        const mediaQuery = match[2] ? match[2].trim() : '';
        const importSrc = match[0];
        const newImport = mediaQuery
          ? `@import url("${relativePath}") ${mediaQuery};`
          : `@import url("${relativePath}");`;
        
        // replace() ? ? ??? (???? ??
        css = css.replace(importSrc, newImport);

        // ????import??CSS??
        await this._processCssFile(absoluteImportUrl, importLocalPath);
        importCount++;
      }
    }

    return { css, importCount, additionalAssets };
  }

  /**
   * url()  
   * - background: url("image.png") ?? ?
   * - @font-face src: url("font.woff2") ??? ? ?? 
   */
  async _processUrls(css, cssUrl, cssLocalPath) {
    let additionalAssets = 0;

    // url()  (data: URL ?, ???? ?)
    const urlRegex = /url\((['"]?)([^)'"\r\n]+)\1\)/g;
    const matches = [...css.matchAll(urlRegex)];

    for (const match of matches) {
      const quote = match[1];
      const assetUrl = match[2].trim();

      // data: URL, # ??? about: ?? ?
      if (
        assetUrl.startsWith('data:') ||
        assetUrl.startsWith('#') ||
        assetUrl.startsWith('about:') ||
        assetUrl === ''
      ) {
        continue;
      }

      const absoluteAssetUrl = resolveUrl(assetUrl, cssUrl);
      let assetLocalPath = this.urlMap.get(absoluteAssetUrl);

      if (!assetLocalPath) {
        // ???  ? ?
        const response = this.interceptor.getLatestResponse(absoluteAssetUrl);
        if (response && response.body) {
          assetLocalPath = await this._saveAdditionalAsset(absoluteAssetUrl, response);
          additionalAssets++;
        }
      }

      if (assetLocalPath) {
        const relativePath = getRelativePath(cssLocalPath, assetLocalPath);
        const urlSrc = match[0];
        // g ???????  (??????escape ?, ? ????)
        css = css.replace(
          new RegExp(urlSrc.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), 
          `url(${quote}${relativePath}${quote})`
        );
      }
    }

    return { css, additionalAssets };
  }

  /**
   * ? ? ???(CSS ??????)
   * @param {string} url - ? URL
   * @param {object} response - ?? ? 
   * @returns {string} ??  ?? 
   */
  async _saveAdditionalAsset(url, response) {
    const proposedPath = getAssetPathFromUrl(url, this.baseUrl, response.mimeType, response.type);
    if (!proposedPath) return null;

    const relativeDir = path.posix.dirname(proposedPath);
    const rawFilename = path.posix.basename(proposedPath);
    const filename = deduplicateFilename(this._usedNames, relativeDir, rawFilename);

    const relativePath = path.posix.join(relativeDir, filename);
    const absolutePath = path.join(this.outputDir, 'public', relativePath);

    await saveFile(absolutePath, response.body);

    // urlMap? ?
    const normalizedPath = relativePath.replace(/\\/g, '/');
    this.urlMap.set(url, normalizedPath);

    return normalizedPath;
  }

  /**
   * CSS ??(Custom Properties) 
   * @param {string} css - CSS ?
   * @returns {Map<string, string>} ? ???   */
  static extractCssVariables(css) {
    const variables = new Map();
    const varRegex = /--([\w-]+)\s*:\s*([^;]+);/g;
    let match;
    while ((match = varRegex.exec(css)) !== null) {
      variables.set(`--${match[1]}`, match[2].trim());
    }
    return variables;
  }

  /**
   * ??CSS ?? ? (? ?? ? ??
   * @param {string} css - CSS ?
   * @param {import('cheerio').CheerioAPI} $ - cheerio ??
   * @returns {string[]} ???? 
   */
  static findUnusedSelectors(css, $) {
    const unused = [];
    // ????  (???? ?? ?)
    const selectorRegex = /([^{}@]+)\{[^}]*\}/g;
    let match;
    while ((match = selectorRegex.exec(css)) !== null) {
      const selector = match[1].trim();
      // ? ??? ????? ?
      if (selector.startsWith('@') || selector.startsWith(':') || selector === '') continue;
      //  ?? 
      const singleSelectors = selector.split(',').map(s => s.trim());
      for (const sel of singleSelectors) {
        try {
          // cheerio?DOM?  ?
          if ($(sel).length === 0) {
            unused.push(sel);
          }
        } catch {
          // ? ?? ?? 
        }
      }
    }
    return unused;
  }
}

