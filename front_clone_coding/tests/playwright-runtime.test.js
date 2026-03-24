import test from 'node:test';
import assert from 'node:assert/strict';

import { serializeJobError } from '../src/utils/error-utils.js';
import {
  createPlaywrightRuntimeMismatchError,
  getInstalledPlaywrightVersion,
} from '../src/utils/playwright-runtime.js';
import { PLAYWRIGHT_DOCKER_IMAGE, PLAYWRIGHT_RUNTIME_ERROR_CODE } from '../src/utils/constants.js';

test('createPlaywrightRuntimeMismatchError returns structured runtime guidance', () => {
  const rawError = new Error('Executable does not exist');
  const error = createPlaywrightRuntimeMismatchError(rawError);

  assert.equal(error.code, PLAYWRIGHT_RUNTIME_ERROR_CODE);
  assert.match(error.message, /Playwright runtime is not ready/i);
  assert.match(error.hint, /docker compose build --no-cache/i);
  assert.equal(error.meta.expectedDockerImage, PLAYWRIGHT_DOCKER_IMAGE);
  assert.equal(error.meta.installedVersion, getInstalledPlaywrightVersion());
  assert.equal(error.details, rawError.message);
});

test('serializeJobError preserves code, message, and hint', () => {
  const error = createPlaywrightRuntimeMismatchError(new Error('Executable does not exist'));
  const serialized = serializeJobError(error);

  assert.deepEqual(serialized, {
    code: PLAYWRIGHT_RUNTIME_ERROR_CODE,
    message: error.message,
    hint: error.hint,
  });
});
