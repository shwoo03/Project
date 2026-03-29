import test from 'node:test';
import assert from 'node:assert/strict';

import {
  analyzeTextDecoding,
  detectCssEncodingDetails,
  detectHtmlEncodingDetails,
  extractTextMarkers,
  looksLikeEncodingNoise,
  normalizeComparisonText,
} from '../src/utils/encoding-utils.js';

test('detectHtmlEncodingDetails respects meta charset when transport metadata is missing', () => {
  const html = Buffer.from('<html><head><meta charset="euc-kr"></head><body>test</body></html>', 'latin1');
  const result = detectHtmlEncodingDetails(html, '');

  assert.equal(result.encoding, 'euc-kr');
  assert.equal(result.encodingSource, 'meta-charset');
  assert.equal(result.decodeConfidence, 'high');
  assert.equal(result.suspectedEncodingMismatch, false);
});

test('detectHtmlEncodingDetails preserves precedence while flagging header and meta conflicts', () => {
  const html = Buffer.from('<html><head><meta charset="euc-kr"></head><body>test</body></html>', 'latin1');
  const result = detectHtmlEncodingDetails(html, 'text/html; charset=utf-8');

  assert.equal(result.encoding, 'utf-8');
  assert.equal(result.encodingSource, 'content-type');
  assert.equal(result.decodeConfidence, 'medium');
  assert.equal(result.suspectedEncodingMismatch, true);
});

test('detectCssEncodingDetails uses @charset when transport metadata is missing', () => {
  const css = Buffer.from('@charset "euc-kr";\nbody{color:red;}', 'latin1');
  const result = detectCssEncodingDetails(css, '');

  assert.equal(result.encoding, 'euc-kr');
  assert.equal(result.encodingSource, 'css-charset');
  assert.equal(result.decodeConfidence, 'high');
});

test('analyzeTextDecoding falls back safely when the selected charset is unsupported', () => {
  const html = Buffer.from('<html><head><meta charset="x-unknown-charset"></head><body>test</body></html>', 'latin1');
  const result = analyzeTextDecoding(html, {
    resourceType: 'document',
    mimeType: 'text/html',
    contentType: '',
  });

  assert.equal(result.encoding, 'x-unknown-charset');
  assert.equal(result.decodedEncoding, 'utf-8');
  assert.equal(result.decodeFallbackUsed, true);
  assert.equal(result.decodeConfidence, 'low');
  assert.equal(typeof result.decodedText, 'string');
});

test('extractTextMarkers prefers distinct meaningful tokens over repeated boilerplate fragments', () => {
  const markers = extractTextMarkers('Home Home Home Privacy Privacy Policy Main Content Guide Guide Contact Contact', 10);

  assert.deepEqual(markers, ['Home', 'Privacy', 'Policy', 'Main', 'Content', 'Guide', 'Contact']);
});

test('normalizeComparisonText strips punctuation and zero-width noise for title comparison', () => {
  const normalized = normalizeComparisonText('  Hello\u200B,   World!  ');
  assert.equal(normalized, 'Hello World');
});

test('looksLikeEncodingNoise detects mixed-script mojibake-like strings', () => {
  assert.equal(looksLikeEncodingNoise('醫낅줈援ъ껌'), true);
  assert.equal(looksLikeEncodingNoise('종로구청'), false);
});
