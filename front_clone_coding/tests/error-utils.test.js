import test from 'node:test';
import assert from 'node:assert/strict';

import { serializeJobError, stringifyErrorLike } from '../src/utils/error-utils.js';

test('stringifyErrorLike flattens nested error-like objects', () => {
  const value = {
    error: {
      message: 'Nested failure',
      hint: { message: 'Try again later' },
    },
  };

  assert.match(stringifyErrorLike(value), /Nested failure|Try again later/);
});

test('serializeJobError converts object fields into stable strings', () => {
  const serialized = serializeJobError({
    code: 'TEST_ERROR',
    message: { message: 'Primary failure' },
    hint: { detail: 'Secondary hint' },
  });

  assert.equal(serialized.code, 'TEST_ERROR');
  assert.match(serialized.message, /Primary failure/);
  assert.match(serialized.hint, /Secondary hint/);
});
