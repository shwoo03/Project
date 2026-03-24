import { createRequire } from 'module';
import { chromium } from 'playwright';

import {
  PLAYWRIGHT_DOCKER_IMAGE,
  PLAYWRIGHT_RUNTIME_ERROR_CODE,
  PLAYWRIGHT_VERSION,
} from './constants.js';

const require = createRequire(import.meta.url);

let runtimeCheckPromise = null;

export function getInstalledPlaywrightVersion() {
  try {
    const pkg = require('playwright/package.json');
    return pkg.version || PLAYWRIGHT_VERSION;
  } catch {
    return PLAYWRIGHT_VERSION;
  }
}

export function createPlaywrightRuntimeMismatchError(cause) {
  const error = new Error(
    'Playwright runtime is not ready. Rebuild the container with the matching Playwright image or run npx playwright install chromium.',
  );

  error.code = PLAYWRIGHT_RUNTIME_ERROR_CODE;
  error.hint = [
    `Expected Docker image: ${PLAYWRIGHT_DOCKER_IMAGE}`,
    'Recovery:',
    `  docker compose build --no-cache && docker compose up -d`,
    '  or run: npx playwright install chromium',
  ].join('\n');
  error.details = cause?.message || String(cause || 'Unknown Playwright launch failure');
  error.meta = {
    installedVersion: getInstalledPlaywrightVersion(),
    expectedDockerImage: PLAYWRIGHT_DOCKER_IMAGE,
  };

  return error;
}

export async function ensurePlaywrightRuntimeReady() {
  if (!runtimeCheckPromise) {
    runtimeCheckPromise = doRuntimeCheck().catch((error) => {
      runtimeCheckPromise = null;
      throw error;
    });
  }

  return runtimeCheckPromise;
}

async function doRuntimeCheck() {
  let browser = null;

  try {
    browser = await chromium.launch({ headless: true });
    return {
      installedVersion: getInstalledPlaywrightVersion(),
      expectedDockerImage: PLAYWRIGHT_DOCKER_IMAGE,
    };
  } catch (error) {
    throw createPlaywrightRuntimeMismatchError(error);
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
  }
}
