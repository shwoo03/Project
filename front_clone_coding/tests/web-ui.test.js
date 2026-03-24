import test from 'node:test';
import assert from 'node:assert/strict';

import { createUIServerApp, startUIServer } from '../web/server.js';
import logger from '../src/utils/logger.js';
import { PLAYWRIGHT_RUNTIME_ERROR_CODE } from '../src/utils/constants.js';

const textDecoder = new TextDecoder();

test('web UI logs are recorded once per emitted logger event', { concurrency: false }, async () => {
  const server = startUIServer({
    port: 4011,
    cloneRunner: async () => {
      logger.info('unique-log-line');
      return { outputDir: './output/example.com' };
    },
  });

  try {
    const createResponse = await fetch('http://localhost:4011/api/clone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: 'https://example.com',
        options: {},
      }),
    });

    assert.equal(createResponse.status, 202);
    const created = await createResponse.json();

    await waitForJobStatus(created.jobId, 'completed', 4011);

    const controller = new AbortController();
    const response = await fetch(`http://localhost:4011/api/logs?jobId=${created.jobId}`, {
      signal: controller.signal,
    });

    const reader = response.body.getReader();
    let text = '';
    try {
      while (!text.includes('unique-log-line')) {
        const { done, value } = await reader.read();
        if (done) break;
        text += textDecoder.decode(value, { stream: true });
        if (text.includes('Clone completed')) break;
      }
    } finally {
      controller.abort();
    }

    const matches = text.match(/unique-log-line/g) || [];
    assert.equal(matches.length, 1);
  } finally {
    await closeServer(server);
  }
});

test('web UI exposes structured Playwright runtime errors in job status', { concurrency: false }, async () => {
  const error = new Error('Playwright runtime is not ready. Rebuild the container.');
  error.code = PLAYWRIGHT_RUNTIME_ERROR_CODE;
  error.hint = 'Expected Docker image: mcr.microsoft.com/playwright:v1.58.2-noble';

  const server = startUIServer({
    port: 4012,
    cloneRunner: async () => {
      throw error;
    },
  });

  try {
    const createResponse = await fetch('http://localhost:4012/api/clone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: 'https://example.com',
        options: {},
      }),
    });

    assert.equal(createResponse.status, 202);
    const created = await createResponse.json();
    const job = await waitForJobStatus(created.jobId, 'failed', 4012);

    assert.equal(job.error.code, PLAYWRIGHT_RUNTIME_ERROR_CODE);
    assert.match(job.error.message, /Playwright runtime is not ready/i);
    assert.match(job.error.hint, /Expected Docker image/i);
  } finally {
    await closeServer(server);
  }
});

test('web UI does not surface [object Object] for structured clone failures', { concurrency: false }, async () => {
  const server = startUIServer({
    port: 4013,
    cloneRunner: async () => {
      const error = new Error('Top level failure');
      error.hint = { message: 'Structured hint object' };
      throw error;
    },
  });

  try {
    const createResponse = await fetch('http://localhost:4013/api/clone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: 'https://example.com',
        options: {},
      }),
    });

    assert.equal(createResponse.status, 202);
    const created = await createResponse.json();
    await waitForJobStatus(created.jobId, 'failed', 4013);

    const controller = new AbortController();
    const logsResponse = await fetch(`http://localhost:4013/api/logs?jobId=${created.jobId}`, {
      signal: controller.signal,
    });
    const reader = logsResponse.body.getReader();
    let logsText = '';
    try {
      while (!logsText.includes('Structured hint object')) {
        const { done, value } = await reader.read();
        if (done) break;
        logsText += textDecoder.decode(value, { stream: true });
      }
    } finally {
      controller.abort();
    }

    assert.doesNotMatch(logsText, /\[object Object\]/);
    assert.match(logsText, /Structured hint object/);
  } finally {
    await closeServer(server);
  }
});

test('web UI forwards cookieFile to the clone runner', { concurrency: false }, async () => {
  let receivedOptions = null;
  const server = startUIServer({
    port: 4014,
    cloneRunner: async (options) => {
      receivedOptions = options;
      return { outputDir: './output/example.com' };
    },
  });

  try {
    const createResponse = await fetch('http://localhost:4014/api/clone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: 'https://example.com',
        options: {
          cookieFile: './cookies.json',
        },
      }),
    });

    assert.equal(createResponse.status, 202);
    const created = await createResponse.json();
    await waitForJobStatus(created.jobId, 'completed', 4014);

    assert.equal(receivedOptions?.cookieFile, './cookies.json');
  } finally {
    await closeServer(server);
  }
});

test('web UI exposes the active job only while it is running', { concurrency: false }, async () => {
  let releaseJob;
  const jobBlocked = new Promise((resolve) => {
    releaseJob = resolve;
  });

  const server = startUIServer({
    port: 4015,
    cloneRunner: async () => {
      await jobBlocked;
      return { outputDir: './output/example.com' };
    },
  });

  try {
    const createResponse = await fetch('http://localhost:4015/api/clone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: 'https://example.com',
        options: {},
      }),
    });

    assert.equal(createResponse.status, 202);
    const created = await createResponse.json();

    const activeResponse = await fetch('http://localhost:4015/api/jobs/active/current');
    assert.equal(activeResponse.status, 200);
    const activePayload = await activeResponse.json();
    assert.equal(activePayload.activeJobId, created.jobId);
    assert.equal(activePayload.job.id, created.jobId);
    assert.equal(activePayload.job.status, 'running');

    releaseJob();
    await waitForJobStatus(created.jobId, 'completed', 4015);

    const finalActiveResponse = await fetch('http://localhost:4015/api/jobs/active/current');
    assert.equal(finalActiveResponse.status, 200);
    const finalActivePayload = await finalActiveResponse.json();
    assert.equal(finalActivePayload.activeJobId, null);
  } finally {
    releaseJob?.();
    await closeServer(server);
  }
});

test('web UI prunes terminal jobs by age and keeps cancelled jobs eligible', { concurrency: false }, async () => {
  const app = createUIServerApp({
    cloneRunner: async () => ({ outputDir: './output/example.com' }),
  });
  const jobs = app.locals.jobs;
  const now = Date.now();

  jobs.set('completed-old', {
    id: 'completed-old',
    status: 'completed',
    updatedAt: new Date(now - (31 * 60 * 1000)).toISOString(),
    logs: [],
    clients: new Set(),
  });
  jobs.set('cancelled-old', {
    id: 'cancelled-old',
    status: 'cancelled',
    updatedAt: new Date(now - (31 * 60 * 1000)).toISOString(),
    logs: [],
    clients: new Set(),
  });
  jobs.set('failed-fresh', {
    id: 'failed-fresh',
    status: 'failed',
    updatedAt: new Date(now).toISOString(),
    logs: [],
    clients: new Set(),
  });

  const server = app.listen(4016);
  server.on('close', () => {
    app.locals.cleanup?.();
  });

  try {
    const createResponse = await fetch('http://localhost:4016/api/clone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: 'https://example.com',
        options: {},
      }),
    });

    assert.equal(createResponse.status, 202);
    const created = await createResponse.json();
    await waitForJobStatus(created.jobId, 'completed', 4016);

    assert.equal(jobs.has('completed-old'), false);
    assert.equal(jobs.has('cancelled-old'), false);
    assert.equal(jobs.has('failed-fresh'), true);
  } finally {
    await closeServer(server);
  }
});

test('web UI removes its logger listener when the server closes', { concurrency: false }, async () => {
  const initialCount = logger.listenerCount('log');
  const server = startUIServer({
    port: 4017,
    cloneRunner: async () => ({ outputDir: './output/example.com' }),
  });

  try {
    assert.equal(logger.listenerCount('log'), initialCount + 1);
  } finally {
    await closeServer(server);
  }

  assert.equal(logger.listenerCount('log'), initialCount);
});

async function waitForJobStatus(jobId, expectedStatus, port) {
  let job = null;

  for (let attempt = 0; attempt < 30; attempt += 1) {
    const response = await fetch(`http://localhost:${port}/api/jobs/${jobId}`);
    job = await response.json();
    if (job.status === expectedStatus) {
      return job;
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }

  throw new Error(`Timed out waiting for job ${jobId} to reach ${expectedStatus}`);
}

async function closeServer(server) {
  await new Promise((resolve, reject) => {
    if (!server.listening) {
      resolve();
      return;
    }
    server.close((error) => (error ? reject(error) : resolve()));
  });
}
