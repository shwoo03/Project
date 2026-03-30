import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import AssetDownloader from '../src/downloader/asset-downloader.js';

function makeMockInterceptor(assets = []) {
  const assetMap = new Map();
  for (const a of assets) {
    assetMap.set(a.url, a);
  }
  return {
    getAssets: () => assetMap,
    getFailedRequests: () => [],
    getLatestResponse: () => null,
  };
}

test('AssetDownloader.downloadAll saves assets and populates urlToRelativePath', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ad-test-'));
  try {
    const downloader = new AssetDownloader(tempRoot, 'https://example.com');
    const interceptor = makeMockInterceptor([
      { url: 'https://example.com/style.css', body: Buffer.from('body{}'), mimeType: 'text/css', type: 'stylesheet', status: 200 },
    ]);
    const urlMap = await downloader.downloadAll(interceptor);

    assert.equal(urlMap.size, 1);
    assert.ok(urlMap.get('https://example.com/style.css'));
    const savedPath = path.join(tempRoot, 'public', urlMap.get('https://example.com/style.css'));
    const content = await fs.readFile(savedPath, 'utf8');
    assert.equal(content, 'body{}');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('AssetDownloader.downloadAll deduplicates assets by content hash', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ad-dedup-'));
  try {
    const downloader = new AssetDownloader(tempRoot, 'https://example.com');
    const sameBody = Buffer.from('identical-content');
    const interceptor = makeMockInterceptor([
      { url: 'https://example.com/a.css', body: sameBody, mimeType: 'text/css', type: 'stylesheet', status: 200 },
      { url: 'https://example.com/b.css', body: sameBody, mimeType: 'text/css', type: 'stylesheet', status: 200 },
    ]);
    const urlMap = await downloader.downloadAll(interceptor);

    assert.equal(urlMap.get('https://example.com/a.css'), urlMap.get('https://example.com/b.css'));
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('AssetDownloader.downloadAll skips assets with empty body', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ad-empty-'));
  try {
    const downloader = new AssetDownloader(tempRoot, 'https://example.com');
    const interceptor = makeMockInterceptor([
      { url: 'https://example.com/empty.css', body: Buffer.alloc(0), mimeType: 'text/css', type: 'stylesheet', status: 200 },
    ]);
    const urlMap = await downloader.downloadAll(interceptor);

    assert.equal(urlMap.size, 0);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('AssetDownloader.registerDirectAsset adds entry to resource manifest', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ad-direct-'));
  try {
    const downloader = new AssetDownloader(tempRoot, 'https://example.com');
    downloader.registerDirectAsset({
      url: 'https://example.com/font.woff2',
      savedPath: 'font/font.woff2',
      mimeType: 'font/woff2',
      resourceType: 'font',
      status: 200,
      size: 1024,
      pageUrl: 'https://example.com',
    });

    const entries = downloader.resourceManifestEntries;
    assert.equal(entries.length, 1);
    assert.equal(entries[0].captureLane, 'direct');
    assert.equal(entries[0].url, 'https://example.com/font.woff2');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('AssetDownloader.recoverFailedAssets skips tracking domains', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ad-track-'));
  try {
    const downloader = new AssetDownloader(tempRoot, 'https://example.com');
    const result = await downloader.recoverFailedAssets([
      { url: 'https://www.googletagmanager.com/gtm.js', method: 'GET', resourceType: 'script' },
      { url: 'https://doubleclick.net/ad.js', method: 'GET', resourceType: 'script' },
    ]);

    assert.equal(result.recovered, 0);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('AssetDownloader.recoverFailedAssets skips non-GET requests', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ad-post-'));
  try {
    const downloader = new AssetDownloader(tempRoot, 'https://example.com');
    const result = await downloader.recoverFailedAssets([
      { url: 'https://example.com/api/submit', method: 'POST', resourceType: 'fetch' },
    ]);

    assert.equal(result.recovered, 0);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
