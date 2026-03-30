import path from 'path';
import crypto from 'crypto';
import mime from 'mime-types';

import { saveFile, deduplicateFilename } from '../utils/file-utils.js';
import { getAssetPathFromUrl, isInDomainScope } from '../utils/url-utils.js';
import logger from '../utils/logger.js';
import { classifyResource } from '../utils/crawl-config.js';
import { batchParallel } from '../utils/concurrency-utils.js';
import { ASSET_DOWNLOAD_CONCURRENCY } from '../utils/constants.js';

const RECOVERY_TRACKER_PATTERNS = [
  'doubleclick.net',
  'googletagmanager.com',
  'google-analytics.com',
  'googlesyndication.com',
  'googleadservices.com',
  'gstatic.com/recaptcha',
  'recaptcha',
  'facebook.net',
  'facebook.com/tr',
  'tiktok.com',
  'snapchat.com',
  'taboola.com',
  'outbrain.com',
  'segment.io',
  'sentry.io',
  'newrelic.com',
  'nlog.naver.com',
  'siape.veta.naver.com',
  'nam.veta.naver.com',
  'ader.naver.com',
  'tivan.naver.com',
];

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
    let skipped = 0;

    logger.start(`Asset download start: ${total} items`);

    const writeTasks = [];
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
        const normalizedPath = relativePath.replace(/\\/g, '/');

        this.savedHashes.set(hash, normalizedPath);
        this.urlToRelativePath.set(data.url, normalizedPath);
        this._recordResourceEntry({
          url: data.url,
          savedPath: normalizedPath,
          mimeType: data.mimeType,
          contentType: data.contentType || '',
          resourceType: data.type,
          captureLane: 'browser',
          status: data.status,
          size: data.bodyLength || data.body?.length || 0,
          pageUrl: data.pageUrl || '',
          encoding: data.encoding || null,
          encodingSource: data.encodingSource || 'unknown',
          decodeConfidence: data.decodeConfidence || 'low',
          suspectedEncodingMismatch: Boolean(data.suspectedEncodingMismatch),
          encodingEvidence: data.encodingEvidence || {},
        });

        writeTasks.push({ absolutePath, body: data.body, url: data.url });
      } catch (err) {
        logger.debug(`Asset download failed: ${data.url} - ${err.message}`);
        skipped += 1;
      }
    }

    let completed = 0;
    const totalTasks = writeTasks.length;
    await batchParallel(writeTasks, ASSET_DOWNLOAD_CONCURRENCY, async (task) => {
      await saveFile(task.absolutePath, task.body);
      completed += 1;
      if (completed % 50 === 0 || completed === totalTasks) {
        logger.progress({
          stage: 'download',
          current: completed,
          total: totalTasks,
          label: `Downloading assets: ${completed} / ${totalTasks}`,
        });
      }
    });

    logger.succeed(`Asset download done: saved ${writeTasks.length}, skipped ${skipped}`);
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

  async recoverFailedAssets(failedRequests = []) {
    const candidates = (failedRequests || []).filter((entry) => this._shouldRecoverFailedRequest(entry));
    if (candidates.length === 0) return { attempted: 0, recovered: 0 };

    let recovered = 0;
    for (const request of candidates) {
      const didRecover = await this._recoverSingleAsset(request);
      if (didRecover) recovered += 1;
    }

    if (recovered > 0) {
      logger.info(`Recovered ${recovered}/${candidates.length} failed critical asset(s)`);
    }

    return { attempted: candidates.length, recovered };
  }

  _recordResourceEntry(entry) {
    const classification = classifyResource(entry.url, entry.mimeType, entry.resourceType);
    this.resourceManifestEntries.push({
      url: entry.url,
      savedPath: entry.savedPath,
      mimeType: entry.mimeType || '',
      contentType: entry.contentType || '',
      resourceType: entry.resourceType || '',
      captureLane: entry.captureLane || 'browser',
      status: entry.status || null,
      size: entry.size || 0,
      pageUrl: entry.pageUrl || '',
      resourceClass: classification.resourceClass,
      replayCriticality: classification.replayCriticality,
      encoding: entry.encoding || null,
      encodingSource: entry.encodingSource || 'unknown',
      decodeConfidence: entry.decodeConfidence || 'low',
      suspectedEncodingMismatch: Boolean(entry.suspectedEncodingMismatch),
      encodingEvidence: entry.encodingEvidence || {},
    });
  }

  _shouldRecoverFailedRequest(entry) {
    if (!entry?.url) return false;

    try {
      const url = new URL(entry.url);
      const lowerUrl = entry.url.toLowerCase();
      if (RECOVERY_TRACKER_PATTERNS.some((pattern) => url.hostname.includes(pattern) || lowerUrl.includes(pattern))) return false;
      if (entry.method && entry.method !== 'GET') return false;
      if (/(telemetry|tracking|metrics|analytic|analytics|beacon|logger|logging|impress|exposure|clicklog|nlog|veta|adtech|ads|conversion|pixel|collect|\blogs?\b)/.test(lowerUrl)) return false;

      const resourceType = String(entry.resourceType || '').toLowerCase();
      const pathName = url.pathname.toLowerCase();
      const inScope = isInDomainScope(entry.url, this.baseUrl, 'registrable-domain');
      const allowExternalCriticalAsset = !inScope && ['image', 'stylesheet', 'font'].includes(resourceType);

      if (resourceType === 'image' || resourceType === 'stylesheet' || resourceType === 'font') {
        return inScope || allowExternalCriticalAsset;
      }
      if (resourceType === 'script') {
        return inScope;
      }
      if (allowExternalCriticalAsset && /\.(css|woff2?|ttf|otf|svg|png|jpe?g|gif|webp|avif)$/i.test(pathName)) {
        return true;
      }
      return inScope && /\.(css|js|woff2?|ttf|otf|svg|png|jpe?g|gif|webp|avif)$/i.test(pathName);
    } catch {
      return false;
    }
  }

  async _recoverSingleAsset(entry) {
    if (this.urlToRelativePath.has(entry.url)) return false;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);

    try {
      const response = await fetch(entry.url, {
        method: 'GET',
        redirect: 'follow',
        signal: controller.signal,
      });
      if (!response.ok) return false;

      const arrayBuffer = await response.arrayBuffer();
      const body = Buffer.from(arrayBuffer);
      if (body.length === 0) return false;

      const mimeType = (response.headers.get('content-type') || mime.lookup(new URL(entry.url).pathname) || '').split(';')[0].trim();
      const resourceType = this._inferResourceType(entry, mimeType);
      const proposedPath = getAssetPathFromUrl(entry.url, this.baseUrl, mimeType, resourceType);
      if (!proposedPath) return false;

      const relativeDir = path.posix.dirname(proposedPath);
      const filename = path.posix.basename(proposedPath);
      const uniqueFilename = deduplicateFilename(this._usedNames, relativeDir, filename);
      const relativePath = path.posix.join(relativeDir, uniqueFilename).replace(/\\/g, '/');
      await saveFile(path.join(this.outputDir, 'public', relativePath), body);

      this.urlToRelativePath.set(entry.url, relativePath);
      this._recordResourceEntry({
        url: entry.url,
        savedPath: relativePath,
        mimeType,
        resourceType,
        captureLane: 'recovery',
        status: response.status,
        size: body.length,
        pageUrl: entry.pageUrl || '',
      });

      return true;
    } catch (error) {
      logger.debug(`Recovery fetch failed: ${entry.url} - ${error.message}`);
      return false;
    } finally {
      clearTimeout(timer);
    }
  }

  _inferResourceType(entry, mimeType) {
    if (entry.resourceType) return entry.resourceType;
    const lowerMime = String(mimeType || '').toLowerCase();
    if (lowerMime.includes('css')) return 'stylesheet';
    if (lowerMime.includes('javascript')) return 'script';
    if (lowerMime.startsWith('font/')) return 'font';
    if (lowerMime.startsWith('image/')) return 'image';
    return 'fetch';
  }
}
