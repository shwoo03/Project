import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import * as cheerio from 'cheerio';

import { downloadExternalImages, injectCapturedImages } from '../src/utils/image-utils.js';
import { ensureDir, saveFile } from '../src/utils/file-utils.js';

test('injectCapturedImages does not preload unreferenced images into replay HTML', () => {
  const html = '<html><head></head><body><img src="https://example.com/hero.jpg" alt="hero"></body></html>';
  const urlMap = new Map([
    ['https://example.com/hero.jpg', 'img/hero.jpg'],
    ['https://example.com/gallery-1.jpg', 'img/gallery-1.jpg'],
    ['https://example.com/gallery-2.jpg', 'img/gallery-2.jpg'],
  ]);

  const output = injectCapturedImages(html, urlMap);
  const $ = cheerio.load(output);

  assert.equal($('img').first().attr('src'), './img/hero.jpg');
  assert.equal($('link[rel="preload"][as="image"]').length, 0);
  assert.equal($('#clone-preload-refs').length, 0);
  assert.equal($.html().includes('gallery-1.jpg'), false);
  assert.equal($.html().includes('gallery-2.jpg'), false);
});

test('downloadExternalImages captures image URLs referenced inside style tags', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-image-style-'));
  const originalFetch = global.fetch;
  try {
    const publicDir = path.join(tempRoot, 'public');
    await ensureDir(publicDir);

    global.fetch = async (url) => {
      if (url === 'https://cdn.example.com/images/hero.webp') {
        return new Response(Buffer.from('hero-image'), {
          status: 200,
          headers: { 'content-type': 'image/webp' },
        });
      }

      return new Response('missing', { status: 404 });
    };

    const html = [
      '<html><head>',
      '<style>.hero{background-image:url("https://cdn.example.com/images/hero.webp");}</style>',
      '</head><body><section class="hero"></section></body></html>',
    ].join('');

    const urlMap = new Map();
    const result = await downloadExternalImages(
      html,
      publicDir,
      urlMap,
      { getLatestResponse: () => null },
      [],
      'https://example.com',
      null,
    );

    assert.equal(result.savedCount, 1);
    assert.equal(urlMap.has('https://cdn.example.com/images/hero.webp'), true);
    assert.equal(
      await fs.stat(path.join(publicDir, 'img', 'cdn.example.com', 'images', 'hero.webp')).then(() => true, () => false),
      true,
    );
  } finally {
    global.fetch = originalFetch;
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
