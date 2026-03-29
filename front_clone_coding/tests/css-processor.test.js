import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';

import AssetDownloader from '../src/downloader/asset-downloader.js';
import CssProcessor from '../src/processor/css-processor.js';
import { ensureDir, saveFile } from '../src/utils/file-utils.js';

test('CssProcessor rewrites imports and asset URLs with PostCSS', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-css-'));
  try {
    await ensureDir(path.join(tempRoot, 'public', 'css'));
    await saveFile(path.join(tempRoot, 'public', 'css', 'main.css'), [
      '@import "./theme.css";',
      '.hero { background-image: url("/img/bg.png"); }',
      '.banner { background-image: image-set(url("/img/bg.png") 1x, url("/img/bg@2x.png") 2x); }',
    ].join('\n'));
    await saveFile(path.join(tempRoot, 'public', 'css', 'theme.css'), '.theme { background:url("../img/icon.svg"); }');

    const urlMap = new Map([
      ['https://example.com/assets/main.css', 'css/main.css'],
      ['https://example.com/assets/theme.css', 'css/theme.css'],
      ['https://example.com/img/bg.png', 'img/bg.png'],
      ['https://example.com/img/bg@2x.png', 'img/bg@2x.png'],
      ['https://example.com/img/icon.svg', 'img/icon.svg'],
    ]);

    const processor = new CssProcessor(tempRoot, 'https://example.com', urlMap, {
      getLatestResponse() {
        return null;
      },
    });

    await processor.processAll();

    const mainCss = await fs.readFile(path.join(tempRoot, 'public', 'css', 'main.css'), 'utf-8');
    const themeCss = await fs.readFile(path.join(tempRoot, 'public', 'css', 'theme.css'), 'utf-8');

    assert.match(mainCss, /@import "\.\/theme\.css"|@import url\("\.\/theme\.css"\)/);
    assert.match(mainCss, /url\("\.\.\/img\/bg\.png"\)|url\(\.\.\/img\/bg\.png\)/);
    assert.match(mainCss, /bg@2x\.png/);
    assert.match(themeCss, /url\("\.\.\/img\/icon\.svg"\)|url\(\.\.\/img\/icon\.svg\)/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('CssProcessor fetches and rewrites missing CSS assets when capture missed them', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-css-fetch-'));
  const originalFetch = global.fetch;
  try {
    await ensureDir(path.join(tempRoot, 'public', 'css'));
    await saveFile(
      path.join(tempRoot, 'public', 'css', 'main.css'),
      '.hero { background-image: url("https://cdn.example.com/img/hero.webp"); }\n@font-face { font-family: Test; src: url("https://cdn.example.com/fonts/test.woff2") format("woff2"); }',
    );

    const urlMap = new Map([
      ['https://example.com/assets/main.css', 'css/main.css'],
    ]);

    global.fetch = async (url) => {
      if (url === 'https://cdn.example.com/img/hero.webp') {
        return new Response(Buffer.from('hero-image'), {
          status: 200,
          headers: { 'content-type': 'image/webp' },
        });
      }

      if (url === 'https://cdn.example.com/fonts/test.woff2') {
        return new Response(Buffer.from('font-binary'), {
          status: 200,
          headers: { 'content-type': 'font/woff2' },
        });
      }

      return new Response('missing', { status: 404 });
    };

    const assetRegistry = new AssetDownloader(tempRoot, 'https://example.com');
    const processor = new CssProcessor(tempRoot, 'https://example.com', urlMap, {
      getLatestResponse() {
        return null;
      },
    }, {
      assetRegistry,
    });

    await processor.processAll();

    const output = await fs.readFile(path.join(tempRoot, 'public', 'css', 'main.css'), 'utf-8');
    const resourceEntries = assetRegistry.getResourceManifestEntries();

    assert.match(output, /hero\.webp/);
    assert.match(output, /test\.woff2/);
    assert.equal(output.includes('https://cdn.example.com/img/hero.webp'), false);
    assert.equal(output.includes('https://cdn.example.com/fonts/test.woff2'), false);
    assert.equal(await fs.stat(path.join(tempRoot, 'public', 'img', 'cdn.example.com', 'img', 'hero.webp')).then(() => true, () => false), true);
    assert.equal(await fs.stat(path.join(tempRoot, 'public', 'font', 'cdn.example.com', 'fonts', 'test.woff2')).then(() => true, () => false), true);
    assert.equal(resourceEntries.some((entry) => entry.url === 'https://cdn.example.com/img/hero.webp' && entry.captureLane === 'direct'), true);
    assert.equal(resourceEntries.some((entry) => entry.url === 'https://cdn.example.com/fonts/test.woff2' && entry.captureLane === 'direct'), true);
  } finally {
    global.fetch = originalFetch;
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('CssProcessor final pass can late-bind fonts that become available after first rewrite attempt', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-css-late-bind-'));
  try {
    await ensureDir(path.join(tempRoot, 'public', 'css'));
    await saveFile(
      path.join(tempRoot, 'public', 'css', 'main.css'),
      '@font-face { font-family: Test; src: url("https://cdn.example.com/fonts/test.woff2") format("woff2"); }',
    );

    const urlMap = new Map([
      ['https://example.com/assets/main.css', 'css/main.css'],
    ]);

    const assetRegistry = new AssetDownloader(tempRoot, 'https://example.com');
    const processor = new CssProcessor(tempRoot, 'https://example.com', urlMap, {
      getLatestResponse() {
        return null;
      },
    }, {
      assetRegistry,
    });

    let fontFetchCount = 0;
    processor._fetchMissingAsset = async (url) => {
      if (url !== 'https://cdn.example.com/fonts/test.woff2') {
        return null;
      }
      fontFetchCount += 1;
      if (fontFetchCount === 1) {
        return null;
      }
      return {
        body: Buffer.from('font-binary'),
        mimeType: 'font/woff2',
        type: 'font',
        status: 200,
      };
    };

    await processor.processAll();

    const output = await fs.readFile(path.join(tempRoot, 'public', 'css', 'main.css'), 'utf-8');

    assert.equal(fontFetchCount, 2);
    assert.equal(output.includes('https://cdn.example.com/fonts/test.woff2'), false);
    assert.match(output, /font\/cdn\.example\.com\/fonts\/test\.woff2/);
    assert.equal(urlMap.get('https://cdn.example.com/fonts/test.woff2').includes('font/cdn.example.com/fonts/test.woff2'), true);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('CssProcessor retries render-critical font fetches with an extended timeout window', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-css-retry-'));
  const originalFetch = global.fetch;
  try {
    await ensureDir(path.join(tempRoot, 'public', 'css'));
    await saveFile(
      path.join(tempRoot, 'public', 'css', 'main.css'),
      '@font-face { font-family: Test; src: url("https://assets.nflxext.com/fonts/test.woff2") format("woff2"); }',
    );

    const urlMap = new Map([
      ['https://example.com/assets/main.css', 'css/main.css'],
    ]);

    let attempts = 0;
    global.fetch = async (url) => {
      if (url !== 'https://assets.nflxext.com/fonts/test.woff2') {
        return new Response('missing', { status: 404 });
      }
      attempts += 1;
      if (attempts === 1) {
        throw new Error('The operation was aborted due to timeout');
      }
      return new Response(Buffer.from('font-binary'), {
        status: 200,
        headers: { 'content-type': 'font/woff2' },
      });
    };

    const processor = new CssProcessor(tempRoot, 'https://www.netflix.com', urlMap, {
      getLatestResponse() {
        return null;
      },
    });

    await processor.processAll();

    const output = await fs.readFile(path.join(tempRoot, 'public', 'css', 'main.css'), 'utf-8');
    assert.equal(attempts, 2);
    assert.equal(output.includes('https://assets.nflxext.com/fonts/test.woff2'), false);
    assert.match(output, /font\/external\/assets\.nflxext\.com\/fonts\/test\.woff2/);
  } finally {
    global.fetch = originalFetch;
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('CssProcessor canonicalizes malformed duplicated same-origin asset URLs before recovery', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-css-canonicalize-'));
  const originalFetch = global.fetch;
  try {
    await ensureDir(path.join(tempRoot, 'public', 'css'));
    await saveFile(
      path.join(tempRoot, 'public', 'css', 'main.css'),
      '.hero { background-image: url("https://example.com/img/example.com/img/banner.webp"); }',
    );

    const urlMap = new Map([
      ['https://example.com/assets/main.css', 'css/main.css'],
    ]);

    global.fetch = async (url) => {
      if (url === 'https://example.com/img/banner.webp') {
        return new Response(Buffer.from('banner-image'), {
          status: 200,
          headers: { 'content-type': 'image/webp' },
        });
      }
      return new Response('missing', { status: 404 });
    };

    const processor = new CssProcessor(tempRoot, 'https://example.com', urlMap, {
      getLatestResponse() {
        return null;
      },
    });

    const result = await processor.processAll();
    const output = await fs.readFile(path.join(tempRoot, 'public', 'css', 'main.css'), 'utf-8');

    assert.equal(output.includes('https://example.com/img/example.com/img/banner.webp'), false);
    assert.match(output, /img\/example\.com\/img\/banner\.webp/);
    assert.equal(result.cssRecoverySummary.cssAssetCanonicalizationApplied, 1);
    assert.equal(result.cssRecoverySummary.cssAssetsRecovered, 1);
  } finally {
    global.fetch = originalFetch;
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('CssProcessor final pass replaces unrecoverable missing CSS asset URLs with inert data targets and reports reasons', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-css-inert-fallback-'));
  const originalFetch = global.fetch;
  try {
    await ensureDir(path.join(tempRoot, 'public', 'css'));
    await saveFile(
      path.join(tempRoot, 'public', 'css', 'main.css'),
      [
        '@font-face { font-family: Missing; src: url("https://example.com/fonts/missing.woff2") format("woff2"); }',
        '.hero { background-image: url("https://example.com/img/missing.webp"); }',
      ].join('\n'),
    );

    const urlMap = new Map([
      ['https://example.com/assets/main.css', 'css/main.css'],
    ]);

    global.fetch = async () => new Response('missing', { status: 404 });

    const processor = new CssProcessor(tempRoot, 'https://example.com', urlMap, {
      getLatestResponse() {
        return null;
      },
    });

    const result = await processor.processAll();
    const output = await fs.readFile(path.join(tempRoot, 'public', 'css', 'main.css'), 'utf-8');

    assert.equal(output.includes('https://example.com/fonts/missing.woff2'), false);
    assert.equal(output.includes('https://example.com/img/missing.webp'), false);
    assert.match(output, /data:,/);
    assert.equal(result.cssRecoverySummary.cssAssetsFailed, 2);
    assert.equal(result.cssRecoverySummary.cssAssetFailureReasons['http-404'], 2);
    assert.equal(result.cssRecoverySummary.pages[0].cssRecoveryStatus, 'missing-critical-assets');
    assert.equal(result.cssRecoverySummary.pages[0].missingCriticalCssAssets, 2);
  } finally {
    global.fetch = originalFetch;
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('CssProcessor tolerates malformed bare source map directives in CSS files', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-css-sanitize-'));
  try {
    await ensureDir(path.join(tempRoot, 'public', 'css'));
    await saveFile(
      path.join(tempRoot, 'public', 'css', 'main.css'),
      [
        '.hero { background-image: url("/img/bg.png"); }',
        'sourceMappingURL=https://cdn.example.com/assets/main.css.map',
        '.cta { color: white; }',
      ].join('\n'),
    );

    const urlMap = new Map([
      ['https://example.com/assets/main.css', 'css/main.css'],
      ['https://example.com/img/bg.png', 'img/bg.png'],
    ]);

    const processor = new CssProcessor(tempRoot, 'https://example.com', urlMap, {
      getLatestResponse() {
        return null;
      },
    });

    await processor.processAll();

    const output = await fs.readFile(path.join(tempRoot, 'public', 'css', 'main.css'), 'utf-8');
    assert.equal(output.includes('sourceMappingURL=https://cdn.example.com/assets/main.css.map'), false);
    assert.match(output, /bg\.png/);
    assert.match(output, /\.cta/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('CssProcessor recovers when malformed source map directives are embedded in comment-like lines', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-css-sanitize-comment-'));
  try {
    await ensureDir(path.join(tempRoot, 'public', 'css'));
    await saveFile(
      path.join(tempRoot, 'public', 'css', 'main.css'),
      [
        '.hero { color: white; }',
        '/*# sourceMappingURL=https://cdn.example.com/assets/main.css.map */',
        '.cta { background-image: url("/img/bg.png"); }',
      ].join('\n'),
    );

    const urlMap = new Map([
      ['https://example.com/assets/main.css', 'css/main.css'],
      ['https://example.com/img/bg.png', 'img/bg.png'],
    ]);

    const processor = new CssProcessor(tempRoot, 'https://example.com', urlMap, {
      getLatestResponse() {
        return null;
      },
    });

    await processor.processAll();

    const output = await fs.readFile(path.join(tempRoot, 'public', 'css', 'main.css'), 'utf-8');
    assert.equal(output.includes('sourceMappingURL='), false);
    assert.match(output, /\.hero/);
    assert.match(output, /bg\.png/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('CssProcessor falls back to regex rewriting for malformed CSS with unclosed blocks', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-css-malformed-block-'));
  try {
    await ensureDir(path.join(tempRoot, 'public', 'css'));
    await saveFile(
      path.join(tempRoot, 'public', 'css', 'main.css'),
      [
        '@import "https://cdn.example.com/theme.css";',
        '.hero { background-image: url("https://cdn.example.com/img/hero.webp");',
        '.cta { color: white; }',
      ].join('\n'),
    );

    const urlMap = new Map([
      ['https://example.com/assets/main.css', 'css/main.css'],
      ['https://cdn.example.com/theme.css', 'css/theme.css'],
      ['https://cdn.example.com/img/hero.webp', 'img/cdn.example.com/img/hero.webp'],
    ]);

    await saveFile(
      path.join(tempRoot, 'public', 'css', 'theme.css'),
      '.theme { color: red; }',
    );

    const processor = new CssProcessor(tempRoot, 'https://example.com', urlMap, {
      getLatestResponse() {
        return null;
      },
    });

    await processor.processAll();

    const output = await fs.readFile(path.join(tempRoot, 'public', 'css', 'main.css'), 'utf-8');
    assert.match(output, /@import "\.\/theme\.css"/);
    assert.match(output, /url\("\.\.\/img\/cdn\.example\.com\/img\/hero\.webp"\)|url\(\.\.\/img\/cdn\.example\.com\/img\/hero\.webp\)/);
    assert.match(output, /\.cta/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('CssProcessor skips font or binary assets that accidentally land under css-like paths', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-css-binary-guard-'));
  try {
    await ensureDir(path.join(tempRoot, 'public', 'css', 'fonts'));
    const binaryBuffer = Buffer.from([0, 159, 146, 150, 0, 1, 2, 3, 4, 5]);
    await fs.writeFile(path.join(tempRoot, 'public', 'css', 'fonts', 'brand.woff2'), binaryBuffer);

    const urlMap = new Map([
      ['https://example.com/assets/fonts/brand.woff2', 'css/fonts/brand.woff2'],
    ]);

    const processor = new CssProcessor(tempRoot, 'https://example.com', urlMap, {
      getLatestResponse(url) {
        if (url === 'https://example.com/assets/fonts/brand.woff2') {
          return {
            mimeType: 'font/woff2',
            type: 'font',
          };
        }
        return null;
      },
    });

    const result = await processor.processAll();
    const output = await fs.readFile(path.join(tempRoot, 'public', 'css', 'fonts', 'brand.woff2'));

    assert.deepEqual(output, binaryBuffer);
    assert.equal(result.additionalAssets, 0);
    assert.equal(result.importChains, 0);
    assert.equal(result.cssRecoverySummary.cssAssetsDiscovered, 0);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
