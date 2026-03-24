import test from 'node:test';
import assert from 'node:assert/strict';

import PageCrawler from '../src/crawler/page-crawler.js';
import { SCROLL_INTERVAL_MS } from '../src/utils/constants.js';

test('PageCrawler auto-scroll passes interval into page.evaluate', async () => {
  const calls = [];
  const crawler = new PageCrawler({
    url: 'https://example.com',
    scrollCount: 3,
  });

  crawler.page = {
    evaluate: async (_fn, payload) => {
      calls.push(payload);
    },
  };

  await crawler._autoScroll();

  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], {
    scrollCount: 3,
    scrollIntervalMs: SCROLL_INTERVAL_MS,
  });
});

test('PageCrawler auto-scroll skips evaluate when scrollCount is negative', async () => {
  let called = false;
  const crawler = new PageCrawler({
    url: 'https://example.com',
    scrollCount: -1,
  });

  crawler.page = {
    evaluate: async () => {
      called = true;
    },
  };

  await crawler._autoScroll();
  assert.equal(called, false);
});

test('PageCrawler uses lightweight HAR capture when captureDir is enabled', () => {
  const crawler = new PageCrawler({
    url: 'https://www.netflix.com',
    captureDir: 'tmp-capture',
  });

  const options = crawler._buildContextOptions(undefined);

  assert.equal(options.serviceWorkers, 'block');
  assert.equal(options.timezoneId, 'UTC');
  assert.deepEqual(options.recordHar, {
    path: 'tmp-capture\\https-www-netflix-com.har',
    content: 'omit',
    mode: 'minimal',
  });
});
