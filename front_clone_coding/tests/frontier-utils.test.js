import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  scoreLinkCandidate,
  classifyPriorityFamily,
  enrichLinkCandidate,
  prioritizeFrontierCandidates,
  buildPriorityFingerprint,
} from '../src/utils/frontier-utils.js';

const BASE_CONTEXT = {
  startUrl: 'https://example.com',
  currentPageUrl: 'https://example.com/home',
  domainScope: 'registrable-domain',
  nextDepth: 1,
};

test('scoreLinkCandidate gives high score to same-host main landmark link', () => {
  const candidate = enrichLinkCandidate({
    url: 'https://example.com/about',
    sourceKind: 'anchor',
    anchorText: 'About Us',
    domOrder: 1,
    landmark: 'main',
  }, BASE_CONTEXT);

  const scored = scoreLinkCandidate(candidate, { ...BASE_CONTEXT, weights: undefined });
  assert.ok(scored.score >= 20, `score ${scored.score} should be >= 20 (host+main+text+short)`);
  assert.ok(scored.selectionReasons.length > 0);
});

test('scoreLinkCandidate gives low score to footer external link', () => {
  const candidate = enrichLinkCandidate({
    url: 'https://other.com/privacy',
    sourceKind: 'anchor',
    anchorText: 'Privacy',
    domOrder: 100,
    landmark: 'footer',
  }, BASE_CONTEXT);

  const scored = scoreLinkCandidate(candidate, BASE_CONTEXT);
  assert.ok(scored.score < 0, `score ${scored.score} should be < 0 (footer + no host affinity + utility)`);
});

test('classifyPriorityFamily correctly classifies auth, search, docs, utility, content', () => {
  const classify = (tokens) => classifyPriorityFamily({ pathnameTokens: tokens, anchorText: '' });

  assert.equal(classify(['login']), 'auth');
  assert.equal(classify(['search']), 'search');
  assert.equal(classify(['docs', 'guide']), 'docs');
  assert.equal(classify(['help']), 'docs');
  assert.equal(classify(['products', 'detail']), 'content');
});

test('enrichLinkCandidate parses relative URL correctly', () => {
  const result = enrichLinkCandidate({
    url: '/about/team',
    sourceKind: 'anchor',
    anchorText: 'Team',
    domOrder: 5,
  }, BASE_CONTEXT);

  assert.ok(result);
  assert.equal(result.url, 'https://example.com/about/team');
  assert.equal(result.sameHost, true);
  assert.equal(result.pathDepth, 2);
});

test('prioritizeFrontierCandidates limits query variants per path', () => {
  const candidates = [
    { url: 'https://example.com/search?q=a', sourceKind: 'anchor', anchorText: 'A', domOrder: 1, landmark: 'main' },
    { url: 'https://example.com/search?q=b', sourceKind: 'anchor', anchorText: 'B', domOrder: 2, landmark: 'main' },
    { url: 'https://example.com/search?q=c', sourceKind: 'anchor', anchorText: 'C', domOrder: 3, landmark: 'main' },
  ];

  const result = prioritizeFrontierCandidates(candidates, {
    ...BASE_CONTEXT,
    queueBudget: 10,
  });

  const searchSelected = result.selectedCandidates.filter((c) => c.pathname === '/search');
  assert.ok(searchSelected.length <= 1, `expected at most 1 query variant, got ${searchSelected.length}`);
});

test('buildPriorityFingerprint removes tracking params and normalizes', () => {
  const fp = buildPriorityFingerprint('https://example.com/page?utm_source=google&q=hello&fbclid=abc');
  assert.ok(!fp.includes('utm_source'));
  assert.ok(!fp.includes('fbclid'));
  assert.ok(fp.includes('q=hello'));
});
