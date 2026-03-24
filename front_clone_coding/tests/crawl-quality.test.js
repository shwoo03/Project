import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';

import AssetDownloader from '../src/downloader/asset-downloader.js';
import { classifyPageSnapshot } from '../src/utils/crawl-config.js';
import { writeManifest } from '../src/utils/manifest-writer.js';

test('classifyPageSnapshot marks route-heavy pages for representative QA', () => {
  const classification = classifyPageSnapshot({
    routeCount: 3,
    scriptCount: 10,
    liveImageUrls: new Array(4).fill('https://example.com/image.png'),
    forms: [],
    interactiveElements: new Array(12).fill({}),
  }, 'https://example.com/app', {
    crawlProfile: 'accurate',
    enableRepresentativeQA: true,
    takeScreenshot: false,
  });

  assert.equal(classification.pageClass, 'spa-route-heavy');
  assert.equal(classification.shouldRunReplayValidation, true);
  assert.equal(classification.queueBudget >= 30, true);
  assert.equal(classification.flags.includes('spa-routes'), true);
});

test('AssetDownloader records browser-lane resource metadata', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-assets-'));
  try {
    const downloader = new AssetDownloader(tempRoot, 'https://example.com');
    const interceptor = {
      getAssets() {
        return new Map([
          ['stylesheet https://example.com/app.css', {
            url: 'https://example.com/app.css',
            mimeType: 'text/css',
            type: 'stylesheet',
            body: Buffer.from('body { color: red; }'),
            bodyLength: 20,
            status: 200,
            pageUrl: 'https://example.com',
          }],
        ]);
      },
    };

    const urlMap = await downloader.downloadAll(interceptor);
    const resources = downloader.getResourceManifestEntries();

    assert.equal(urlMap.get('https://example.com/app.css').endsWith('.css'), true);
    assert.deepEqual(resources[0], {
      url: 'https://example.com/app.css',
      savedPath: urlMap.get('https://example.com/app.css'),
      mimeType: 'text/css',
      resourceType: 'stylesheet',
      captureLane: 'browser',
      status: 200,
      size: 20,
      pageUrl: 'https://example.com',
      resourceClass: 'critical-render',
      replayCriticality: 'high',
    });
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('writeManifest emits crawl profile and page quality reports', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-manifest-'));
  try {
    await writeManifest(tempRoot, {
      generatedAt: '2026-03-23T00:00:00.000Z',
      startUrl: 'https://example.com',
      domainRoot: 'example.com',
      pages: [],
      assets: [{ url: 'https://example.com/app.css', savedPath: 'css/app.css' }],
      pageQualityReport: [{ pageUrl: 'https://example.com', textDriftRatio: 0.02 }],
      crawlProfile: { name: 'accurate', networkPosture: 'default' },
    });

    const resourceManifest = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'resource-manifest.json'), 'utf8'));
    const pageQuality = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'page-quality-report.json'), 'utf8'));
    const crawlProfile = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'crawl-profile.json'), 'utf8'));

    assert.equal(resourceManifest.length, 1);
    assert.equal(pageQuality[0].pageUrl, 'https://example.com');
    assert.equal(crawlProfile.name, 'accurate');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
