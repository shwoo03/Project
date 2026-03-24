import path from 'path';
import crypto from 'crypto';

import { saveFile, deduplicateFilename } from '../utils/file-utils.js';
import { getAssetPathFromUrl } from '../utils/url-utils.js';
import logger from '../utils/logger.js';
import { classifyResource } from '../utils/crawl-config.js';

export default class AssetDownloader {
  constructor(outputDir, baseUrl) {
    this.outputDir = outputDir;
    this.baseUrl = baseUrl;
    this.savedHashes = new Map();
    this.urlToRelativePath = new Map();
    this._usedNames = new Set();
    this.resourceManifestEntries = [];
  }

  async downloadAll(interceptor) {
    const assets = interceptor.getAssets();
    const total = assets.size;
    let saved = 0;
    let skipped = 0;

    logger.start(`Asset download start: ${total} items`);

    for (const [, data] of assets) {
      try {
        if (!data.body || data.body.length === 0) {
          skipped += 1;
          continue;
        }

        const hash = crypto.createHash('md5').update(data.body).digest('hex');
        const existingPath = this.savedHashes.get(hash);
        if (existingPath) {
          this.urlToRelativePath.set(data.url, existingPath);
          skipped += 1;
          continue;
        }

        const proposedPath = getAssetPathFromUrl(data.url, this.baseUrl, data.mimeType, data.type);
        if (!proposedPath) {
          skipped += 1;
          continue;
        }

        const relativeDir = path.posix.dirname(proposedPath);
        const filename = path.posix.basename(proposedPath);
        const uniqueFilename = deduplicateFilename(this._usedNames, relativeDir, filename);
        const relativePath = path.posix.join(relativeDir, uniqueFilename);
        const absolutePath = path.join(this.outputDir, 'public', relativePath);

        await saveFile(absolutePath, data.body);

        const normalizedPath = relativePath.replace(/\\/g, '/');
        this.savedHashes.set(hash, normalizedPath);
        this.urlToRelativePath.set(data.url, normalizedPath);
        this._recordResourceEntry({
          url: data.url,
          savedPath: normalizedPath,
          mimeType: data.mimeType,
          resourceType: data.type,
          captureLane: 'browser',
          status: data.status,
          size: data.bodyLength || data.body?.length || 0,
          pageUrl: data.pageUrl || '',
        });

        saved += 1;
        if (saved % 10 === 0) {
          logger.update(`Asset download progress: ${saved}/${total}`);
        }
      } catch (err) {
        logger.debug(`Asset download failed: ${data.url} - ${err.message}`);
        skipped += 1;
      }
    }

    logger.succeed(`Asset download done: saved ${saved}, skipped ${skipped}`);
    return this.urlToRelativePath;
  }

  getUrlMap() {
    return this.urlToRelativePath;
  }

  registerDirectAsset(entry) {
    this._recordResourceEntry({
      ...entry,
      captureLane: 'direct',
    });
  }

  getResourceManifestEntries() {
    return this.resourceManifestEntries.slice();
  }

  _recordResourceEntry(entry) {
    const classification = classifyResource(entry.url, entry.mimeType, entry.resourceType);
    this.resourceManifestEntries.push({
      url: entry.url,
      savedPath: entry.savedPath,
      mimeType: entry.mimeType || '',
      resourceType: entry.resourceType || '',
      captureLane: entry.captureLane || 'browser',
      status: entry.status || null,
      size: entry.size || 0,
      pageUrl: entry.pageUrl || '',
      resourceClass: classification.resourceClass,
      replayCriticality: classification.replayCriticality,
    });
  }
}
