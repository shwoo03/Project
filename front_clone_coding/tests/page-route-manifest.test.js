import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildPageRouteManifest,
  buildPageRouteIndex,
  buildPagePathFallbackMap,
  normalizeRouteLookupPath,
} from '../src/pipeline/page-route-manifest.js';

const SITE_MAP = [
  { url: 'https://example.com/page-a', finalUrl: 'https://example.com/page-a', normalizedUrl: 'https://example.com/page-a', crawlState: 'completed' },
  { url: 'https://example.com/page-b?id=1', finalUrl: 'https://example.com/page-b?id=1', normalizedUrl: 'https://example.com/page-b?id=1', crawlState: 'completed' },
];

const PAGES = [
  { url: 'https://example.com/page-a', finalUrl: 'https://example.com/page-a', savedPath: 'page-a.html', replayRoute: '/page-a', routeAliases: ['/page-a.html'] },
  { url: 'https://example.com/page-b?id=1', finalUrl: 'https://example.com/page-b?id=1', savedPath: 'page-b__q_id-1.html', replayRoute: '/page-b__q_id-1', routeAliases: [] },
];

test('buildPageRouteManifest creates routes with correct replayable flag', () => {
  const manifest = buildPageRouteManifest(SITE_MAP, PAGES, 'page-a.html');

  assert.ok(manifest.generatedAt);
  assert.equal(manifest.entryPagePath, 'page-a.html');
  assert.equal(manifest.routes.length, 2);
  assert.equal(manifest.routes[0].replayable, true);
  assert.equal(manifest.routes[0].savedPath, 'page-a.html');
  assert.equal(manifest.routes[1].replayable, true);
});

test('buildPageRouteIndex exactUrlMap includes pageUrl, finalUrl, normalizedUrl', () => {
  const manifest = buildPageRouteManifest(SITE_MAP, PAGES, 'page-a.html');
  const index = buildPageRouteIndex(manifest);

  assert.ok(index.exactUrlMap.get('https://example.com/page-a'));
  assert.equal(index.exactUrlMap.get('https://example.com/page-a').replayRoute, '/page-a');
});

test('buildPageRouteIndex fallbackMap includes single-route host+pathname', () => {
  const manifest = buildPageRouteManifest(SITE_MAP, PAGES, 'page-a.html');
  const index = buildPageRouteIndex(manifest);

  const fallback = index.fallbackMap.get('example.com/page-a');
  assert.ok(fallback);
  assert.equal(fallback.replayRoute, '/page-a');
});

test('buildPageRouteIndex fallbackMap excludes ambiguous host+pathname', () => {
  const ambiguousSiteMap = [
    { url: 'https://example.com/list?cat=1', finalUrl: 'https://example.com/list?cat=1', normalizedUrl: 'https://example.com/list?cat=1', crawlState: 'completed' },
    { url: 'https://example.com/list?cat=2', finalUrl: 'https://example.com/list?cat=2', normalizedUrl: 'https://example.com/list?cat=2', crawlState: 'completed' },
  ];
  const ambiguousPages = [
    { url: 'https://example.com/list?cat=1', finalUrl: 'https://example.com/list?cat=1', savedPath: 'list-cat1.html', replayRoute: '/list-cat1', routeAliases: [] },
    { url: 'https://example.com/list?cat=2', finalUrl: 'https://example.com/list?cat=2', savedPath: 'list-cat2.html', replayRoute: '/list-cat2', routeAliases: [] },
  ];
  const manifest = buildPageRouteManifest(ambiguousSiteMap, ambiguousPages, 'list-cat1.html');
  const index = buildPageRouteIndex(manifest);

  assert.equal(index.fallbackMap.has('example.com/list'), false);
});

test('buildPagePathFallbackMap creates locale-stripped fallback keys', () => {
  const pageUrlMap = new Map([
    ['https://example.com/en/docs/guide', 'en/docs/guide.html'],
  ]);
  const fallbackMap = buildPagePathFallbackMap(pageUrlMap);

  assert.equal(fallbackMap.get('example.com/docs/guide'), 'en/docs/guide.html');
});

test('normalizeRouteLookupPath strips trailing slashes and backslashes', () => {
  assert.equal(normalizeRouteLookupPath('/path/to/page/'), '/path/to/page');
  assert.equal(normalizeRouteLookupPath('path\\to\\page\\'), 'path/to/page');
  assert.equal(normalizeRouteLookupPath(''), '');
  assert.equal(normalizeRouteLookupPath(null), '');
});
