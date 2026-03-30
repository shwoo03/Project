import { test } from 'node:test';
import assert from 'node:assert/strict';
import { sanitizeResponseBody } from '../src/utils/mock-sanitizer.js';

const SUPPORTING = { replayRole: 'render-supporting' };
const CRITICAL = { replayRole: 'render-critical' };

test('sanitizeResponseBody does not sanitize non-object responses', () => {
  const result = sanitizeResponseBody('plain string', SUPPORTING);
  assert.equal(result.sanitized, false);
  assert.equal(result.body, 'plain string');
});

test('sanitizeResponseBody does not sanitize render-critical responses', () => {
  const input = { userId: 12345, email: 'test@live.com' };
  const result = sanitizeResponseBody(input, CRITICAL);
  assert.equal(result.sanitized, false);
  assert.equal(result.body.userId, 12345);
  assert.equal(result.body.email, 'test@live.com');
});

test('sanitizeResponseBody sanitizes Tier 1 keys (userId, sessionToken)', () => {
  const input = { userId: 99999, sessionToken: 'abc123longtoken' };
  const result = sanitizeResponseBody(input, SUPPORTING);
  assert.equal(result.sanitized, true);
  assert.equal(result.body.userId, 0);
  assert.equal(result.body.sessionToken, '[sanitized]');
  assert.equal(result.sanitizedFields.length, 2);
});

test('sanitizeResponseBody sanitizes email values under Tier 2 keys', () => {
  const input = { email: 'john@example.com', title: 'Welcome' };
  const result = sanitizeResponseBody(input, SUPPORTING);
  assert.equal(result.sanitized, true);
  assert.equal(result.body.email, 'user@example.com');
  assert.equal(result.body.title, 'Welcome');
});

test('sanitizeResponseBody sanitizes JWT tokens', () => {
  const input = { authToken: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature' };
  const result = sanitizeResponseBody(input, SUPPORTING);
  assert.equal(result.sanitized, true);
  assert.equal(result.body.authToken, 'eyJwbGFjZWhvbGRlciI6dHJ1ZX0.placeholder.signature');
});

test('sanitizeResponseBody sanitizes UUID values', () => {
  const input = { memberId: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890' };
  const result = sanitizeResponseBody(input, SUPPORTING);
  assert.equal(result.sanitized, true);
  assert.equal(result.body.memberId, '00000000-0000-0000-0000-000000000000');
});

test('sanitizeResponseBody preserves boolean values', () => {
  const input = { isPremiumMember: true, userId: 42000 };
  const result = sanitizeResponseBody(input, SUPPORTING);
  assert.equal(result.body.isPremiumMember, true);
  assert.equal(result.body.userId, 0);
});

test('sanitizeResponseBody preserves content-like string values', () => {
  const input = { title: 'Welcome to the site', description: 'A great platform for everyone', count: 5 };
  const result = sanitizeResponseBody(input, SUPPORTING);
  assert.equal(result.sanitized, false);
  assert.equal(result.body.title, 'Welcome to the site');
  assert.equal(result.body.description, 'A great platform for everyone');
});

test('sanitizeResponseBody recursively sanitizes nested objects', () => {
  const input = { data: { viewer: { email: 'a@b.com', displayName: 'Alice' } } };
  const result = sanitizeResponseBody(input, SUPPORTING);
  assert.equal(result.sanitized, true);
  assert.equal(result.body.data.viewer.email, 'user@example.com');
  assert.ok(result.sanitizedFields.includes('$.data.viewer.email'));
});

test('sanitizeResponseBody handles arrays of user objects', () => {
  const input = { users: [{ userId: 1001, name: 'A' }, { userId: 2002, name: 'B' }] };
  const result = sanitizeResponseBody(input, SUPPORTING);
  assert.equal(result.body.users[0].userId, 0);
  assert.equal(result.body.users[1].userId, 0);
  assert.equal(result.sanitizedFields.length, 2);
});

test('sanitizeResponseBody reports sanitizedFields with JSON paths', () => {
  const input = { profile: { email: 'x@y.com', userId: 5000 } };
  const result = sanitizeResponseBody(input, SUPPORTING);
  assert.ok(result.sanitizedFields.includes('$.profile.email'));
  assert.ok(result.sanitizedFields.includes('$.profile.userId'));
});

test('sanitizeResponseBody respects depth limit', () => {
  let deep = { userId: 99999 };
  for (let i = 0; i < 25; i++) {
    deep = { nested: deep };
  }
  const result = sanitizeResponseBody(deep, SUPPORTING);
  // The deeply nested userId should NOT be sanitized due to depth limit
  let current = result.body;
  for (let i = 0; i < 25; i++) {
    current = current.nested;
  }
  assert.equal(current.userId, 99999);
});

test('sanitizeResponseBody does not corrupt null or empty responses', () => {
  assert.equal(sanitizeResponseBody(null, SUPPORTING).sanitized, false);
  assert.equal(sanitizeResponseBody(null, SUPPORTING).body, null);
  assert.equal(sanitizeResponseBody(undefined, SUPPORTING).body, undefined);
});

test('sanitizeResponseBody Tier 3 key requires strong value match', () => {
  const weak = { session: 'short' };
  const weakResult = sanitizeResponseBody(weak, SUPPORTING);
  assert.equal(weakResult.sanitized, false);
  assert.equal(weakResult.body.session, 'short');

  const strong = { session: 'eyJhbGciOiJIUzI1NiJ9.eyJ1c2VySWQiOjF9.sig' };
  const strongResult = sanitizeResponseBody(strong, SUPPORTING);
  assert.equal(strongResult.sanitized, true);
  assert.equal(strongResult.body.session, 'eyJwbGFjZWhvbGRlciI6dHJ1ZX0.placeholder.signature');
});
