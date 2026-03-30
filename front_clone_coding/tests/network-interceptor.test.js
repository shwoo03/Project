import { test } from 'node:test';
import assert from 'node:assert/strict';
import NetworkInterceptor from '../src/crawler/network-interceptor.js';

function makeEntry(overrides = {}) {
  return {
    key: overrides.key || 'GET https://example.com/a no-body',
    url: overrides.url || 'https://example.com/a',
    method: 'GET',
    requestBodyHash: 'no-body',
    type: overrides.type || 'stylesheet',
    mimeType: overrides.mimeType || 'text/css',
    contentType: 'text/css',
    headers: {},
    body: overrides.body ?? Buffer.from('body'),
    bodyLength: overrides.bodyLength || 4,
    bodyStored: true,
    status: 200,
    pageUrl: 'https://example.com',
    ...overrides,
  };
}

test('NetworkInterceptor._createRequestKey combines method, url, and bodyHash', () => {
  const interceptor = new NetworkInterceptor();
  const key = interceptor._createRequestKey('post', 'https://example.com/api', 'abc123');
  assert.equal(key, 'POST https://example.com/api abc123');
});

test('NetworkInterceptor._shouldStoreBody enforces API_BODY_LIMIT for xhr', () => {
  const interceptor = new NetworkInterceptor();
  assert.equal(interceptor._shouldStoreBody('xhr', 'application/json', 1000), true);
  assert.equal(interceptor._shouldStoreBody('fetch', 'application/json', 2 * 1024 * 1024), true);
  assert.equal(interceptor._shouldStoreBody('fetch', 'application/json', 2 * 1024 * 1024 + 1), false);
});

test('NetworkInterceptor._shouldStoreBody enforces ASSET_BODY_LIMIT for text-like assets', () => {
  const interceptor = new NetworkInterceptor();
  assert.equal(interceptor._shouldStoreBody('stylesheet', 'text/css', 5 * 1024 * 1024), true);
  assert.equal(interceptor._shouldStoreBody('stylesheet', 'text/css', 10 * 1024 * 1024 + 1), false);
  assert.equal(interceptor._shouldStoreBody('image', 'application/octet-stream', 100), false);
});

test('NetworkInterceptor.getAssets excludes document type and entries without body', () => {
  const interceptor = new NetworkInterceptor();
  interceptor.responses.set('k1', makeEntry({ key: 'k1', type: 'document' }));
  interceptor.responses.set('k2', makeEntry({ key: 'k2', type: 'stylesheet' }));
  interceptor.responses.set('k3', makeEntry({ key: 'k3', type: 'image', body: null }));

  const assets = interceptor.getAssets();
  assert.equal(assets.size, 1);
  assert.ok(assets.has('k2'));
});

test('NetworkInterceptor.getLatestResponse returns newest entry for URL', () => {
  const interceptor = new NetworkInterceptor();
  const url = 'https://example.com/style.css';
  interceptor.responses.set('k1', makeEntry({ key: 'k1', url, body: Buffer.from('v1') }));
  interceptor.responses.set('k2', makeEntry({ key: 'k2', url, body: Buffer.from('v2') }));
  interceptor._indexResponse(url, 'k1');
  interceptor._indexResponse(url, 'k2');

  const latest = interceptor.getLatestResponse(url);
  assert.equal(latest.body.toString(), 'v2');
});

test('NetworkInterceptor evicts oldest responses when exceeding MAX_RESPONSES', () => {
  const interceptor = new NetworkInterceptor();
  const limit = 5000;
  for (let i = 0; i < limit + 5; i++) {
    const key = `GET https://example.com/${i} no-body`;
    const url = `https://example.com/${i}`;
    interceptor.responses.set(key, makeEntry({ key, url }));
    interceptor._indexResponse(url, key);
  }
  interceptor._evictOldestResponses();

  assert.equal(interceptor.responses.size, limit);
  assert.equal(interceptor.getLatestResponse('https://example.com/0'), null);
  assert.ok(interceptor.getLatestResponse(`https://example.com/${limit + 4}`));
});
