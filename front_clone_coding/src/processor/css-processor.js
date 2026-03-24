import path from 'path';
import fs from 'fs/promises';
import postcss from 'postcss';
import postcssUrl from 'postcss-url';

import { resolveUrl, getRelativePath, getAssetPathFromUrl } from '../utils/url-utils.js';
import { saveFile, deduplicateFilename } from '../utils/file-utils.js';
import logger from '../utils/logger.js';

export default class CssProcessor {
  constructor(outputDir, baseUrl, urlMap, interceptor) {
    this.outputDir = outputDir;
    this.baseUrl = baseUrl;
    this.urlMap = urlMap;
    this.interceptor = interceptor;
    this.processedFiles = new Set();
    this._usedNames = new Set();
  }

  async processAll() {
    logger.start('Starting CSS processing');

    let additionalAssets = 0;
    let importChains = 0;

    const cssFiles = [];
    for (const [url, localPath] of this.urlMap) {
      if (localPath.endsWith('.css') || localPath.includes('/css/')) {
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

  async _processCssFile(cssUrl, localPath) {
    if (this.processedFiles.has(cssUrl)) {
      return { additionalAssets: 0, importChains: 0 };
    }
    this.processedFiles.add(cssUrl);

    const absolutePath = path.join(this.outputDir, 'public', localPath);
    let cssContent;

    try {
      cssContent = await fs.readFile(absolutePath, 'utf-8');
    } catch {
      logger.debug(`Failed to read CSS file: ${absolutePath}`);
      return { additionalAssets: 0, importChains: 0 };
    }

    const importResult = await this._processImports(cssContent, cssUrl, localPath);
    cssContent = importResult.css;

    const urlResult = await this._rewriteAssetUrls(cssContent, cssUrl, localPath);
    cssContent = urlResult.css;

    await saveFile(absolutePath, cssContent);

    return {
      additionalAssets: importResult.additionalAssets + urlResult.additionalAssets,
      importChains: importResult.importCount,
    };
  }

  async _processImports(css, cssUrl, cssLocalPath) {
    let importCount = 0;
    let additionalAssets = 0;
    const root = postcss.parse(css);

    for (const node of root.nodes || []) {
      if (node.type !== 'atrule' || node.name !== 'import') continue;

      const importUrl = this._extractImportUrl(node.params);
      if (!importUrl || importUrl.startsWith('data:')) continue;

      const absoluteImportUrl = resolveUrl(importUrl, cssUrl);
      let importLocalPath = this.urlMap.get(absoluteImportUrl);

      if (!importLocalPath) {
        const response = this.interceptor.getLatestResponse(absoluteImportUrl);
        if (response?.body) {
          importLocalPath = await this._saveAdditionalAsset(absoluteImportUrl, response);
          additionalAssets += 1;
        }
      }

      if (!importLocalPath) continue;

      const relativePath = getRelativePath(cssLocalPath, importLocalPath);
      node.params = node.params.replace(importUrl, relativePath);
      await this._processCssFile(absoluteImportUrl, importLocalPath);
      importCount += 1;
    }

    return {
      css: root.toString(),
      importCount,
      additionalAssets,
    };
  }

  async _rewriteAssetUrls(css, cssUrl, cssLocalPath) {
    let additionalAssets = 0;

    const result = await postcss([
      postcssUrl({
        url: async ({ url }) => {
          if (!url || url.startsWith('data:') || url.startsWith('#') || url.startsWith('about:')) {
            return url;
          }

          const absoluteAssetUrl = resolveUrl(url, cssUrl);
          let assetLocalPath = this.urlMap.get(absoluteAssetUrl);

          if (!assetLocalPath) {
            const response = this.interceptor.getLatestResponse(absoluteAssetUrl);
            if (response?.body) {
              assetLocalPath = await this._saveAdditionalAsset(absoluteAssetUrl, response);
              additionalAssets += 1;
            }
          }

          if (!assetLocalPath) return url;
          return getRelativePath(cssLocalPath, assetLocalPath);
        },
      }),
    ]).process(css, {
      from: undefined,
      map: false,
    });

    return { css: result.css, additionalAssets };
  }

  _extractImportUrl(params) {
    const match = params.match(/^(?:url\()?['"]?([^'")\s]+)['"]?\)?/i);
    return match ? match[1] : null;
  }

  async _saveAdditionalAsset(url, response) {
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

    return normalizedPath;
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
}
