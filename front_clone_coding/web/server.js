import express from 'express';
import path from 'path';
import fs from 'fs/promises';
import { fileURLToPath } from 'url';
import { randomUUID } from 'crypto';

import { cloneFrontend } from '../src/index.js';
import logger from '../src/utils/logger.js';
import { validateUrlSafety } from '../src/utils/url-utils.js';
import { serializeJobError, stringifyErrorLike } from '../src/utils/error-utils.js';
import {
  MAX_COMPLETED_JOBS,
  JOB_RETENTION_MS,
  SSE_HEARTBEAT_INTERVAL_MS,
  MAX_JOB_LOGS,
} from '../src/utils/constants.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export function createUIServerApp({ cloneRunner = cloneFrontend } = {}) {
  const app = express();
  const jobs = new Map();
  let activeJobId = null;
  const terminalStatuses = new Set(['completed', 'failed', 'cancelled']);

  function pruneCompletedJobs() {
    const now = Date.now();
    const terminalJobs = [];
    for (const [id, job] of jobs) {
      if (terminalStatuses.has(job.status)) {
        terminalJobs.push({ id, updatedAt: new Date(job.updatedAt).getTime() });
      }
    }

    terminalJobs.sort((a, b) => a.updatedAt - b.updatedAt);

    const deleteIds = new Set(
      terminalJobs
        .filter(({ updatedAt }) => now - updatedAt > JOB_RETENTION_MS)
        .map(({ id }) => id),
    );

    const remainingJobs = terminalJobs.filter(({ id }) => !deleteIds.has(id));
    const overflow = remainingJobs.length - MAX_COMPLETED_JOBS;
    if (overflow > 0) {
      for (const { id } of remainingJobs.slice(0, overflow)) {
        deleteIds.add(id);
      }
    }

    for (const id of deleteIds) {
      jobs.delete(id);
    }
  }

  app.disable('x-powered-by');

  app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('X-XSS-Protection', '1; mode=block');
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
    res.setHeader('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self'; img-src 'self' data:; connect-src 'self'");
    next();
  });

  app.use(express.static(path.join(__dirname, 'public')));
  app.use(express.json());

  const apiKey = process.env.API_KEY || null;
  app.use('/api', (req, res, next) => {
    if (!apiKey) return next();
    const provided = req.headers['x-api-key'] || req.query.apiKey;
    if (provided === apiKey) return next();
    return res.status(401).json({ error: 'Unauthorized: invalid or missing API key' });
  });

  function handleLoggerEntry(entry) {
    if (!activeJobId) return;
    const job = jobs.get(activeJobId);
    if (!job) return;

    if (entry.type === 'progress' && entry.progressData) {
      job.progress = entry.progressData;
    }

    const normalizedEntry = recordJobLog(job, entry);
    broadcast(job, normalizedEntry);
  }

  logger.on('log', handleLoggerEntry);
  app.locals.jobs = jobs;
  app.locals.cleanup = () => {
    logger.off('log', handleLoggerEntry);
  };

  app.post('/api/clone', (req, res) => {
    const { url, options = {} } = req.body || {};
    if (!url) {
      return res.status(400).json({ error: 'URL is required' });
    }

    if (activeJobId) {
      const activeJob = jobs.get(activeJobId);
      return res.status(409).json({
        error: 'A clone job is already running',
        activeJobId,
        status: activeJob?.status || 'running',
      });
    }

    const urlCheck = validateUrlSafety(url);
    if (!urlCheck.safe) {
      return res.status(400).json({ error: urlCheck.reason });
    }
    const parsedUrl = urlCheck.parsed;

    const jobId = randomUUID();
    const abortController = new AbortController();
    const job = {
      id: jobId,
      url: parsedUrl.href,
      status: 'queued',
      progress: { stage: 'queued', current: 0, total: 0, label: 'Queued', detail: '' },
      outputDir: null,
      error: null,
      verificationWarnings: [],
      qualitySummary: null,
      artifacts: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      logs: [],
      clients: new Set(),
      abortController,
    };

    jobs.set(jobId, job);
    activeJobId = jobId;
    emitJobLog(job, { type: 'info', text: `Job ${jobId} queued for ${job.url}` });
    runJob(job, options).catch((error) => {
      logger.error(`Job runner failed: ${error.message}`);
    });

    return res.status(202).json({
      jobId,
      status: job.status,
      progress: job.progress,
    });
  });

  app.get('/api/jobs/:jobId', (req, res) => {
    const job = jobs.get(req.params.jobId);
    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    return res.json(serializeJob(job));
  });

  app.get('/api/jobs/active/current', (req, res) => {
    const job = activeJobId ? jobs.get(activeJobId) : null;
    if (!job) {
      return res.json({ activeJobId: null });
    }
    return res.json({ activeJobId, job: serializeJob(job) });
  });

  app.post('/api/jobs/:jobId/cancel', (req, res) => {
    const job = jobs.get(req.params.jobId);
    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }
    if (job.status !== 'running' && job.status !== 'queued') {
      return res.status(400).json({ error: 'Job is not running' });
    }
    job.abortController.abort();
    job.status = 'cancelled';
    job.progress = 'Cancelled';
    job.updatedAt = new Date().toISOString();
    emitJobLog(job, { type: 'warn', text: 'Job cancelled by user' });
    return res.json({ jobId: job.id, status: 'cancelled' });
  });

  app.get('/api/logs', (req, res) => {
    const jobId = req.query.jobId || activeJobId;
    if (!jobId) {
      res.writeHead(200, sseHeaders());
      res.write(`data: ${JSON.stringify({ type: 'info', text: 'No active job' })}\n\n`);
      return res.end();
    }

    const job = jobs.get(jobId);
    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    res.writeHead(200, sseHeaders());
    for (const entry of job.logs) {
      res.write(`data: ${JSON.stringify(entry)}\n\n`);
    }

    job.clients.add(res);
    const heartbeat = setInterval(() => {
      res.write(':heartbeat\n\n');
    }, SSE_HEARTBEAT_INTERVAL_MS);
    res.on('error', () => {
      clearInterval(heartbeat);
      job.clients.delete(res);
    });
    req.on('close', () => {
      clearInterval(heartbeat);
      job.clients.delete(res);
    });
  });

  app.get('/api/output', async (req, res) => {
    const outputBase = path.resolve('./output');
    const relPath = req.query.path || '';
    const target = path.resolve(outputBase, relPath);

    if (!target.startsWith(outputBase)) {
      return res.status(403).json({ error: 'Access denied' });
    }

    try {
      const stat = await fs.stat(target);
      if (stat.isDirectory()) {
        const entries = await fs.readdir(target, { withFileTypes: true });
        const items = entries.map((e) => ({
          name: e.name,
          type: e.isDirectory() ? 'directory' : 'file',
          path: path.posix.join(relPath, e.name),
        }));
        items.sort((a, b) => {
          if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
          return a.name.localeCompare(b.name);
        });
        return res.json({ path: relPath || '/', entries: items });
      }
      res.download(target);
    } catch {
      return res.status(404).json({ error: 'Not found' });
    }
  });

  return app;

  async function runJob(job, options) {
    job.status = 'running';
    job.progress = 'Running';
    job.updatedAt = new Date().toISOString();
    emitJobLog(job, { type: 'info', text: `Clone started for ${job.url}` });

    try {
      if (job.abortController.signal.aborted) throw new Error('Job cancelled');

      const clamp = (val, min, max, fallback) => {
        const n = parseInt(val, 10);
        if (Number.isNaN(n)) return fallback;
        return Math.max(min, Math.min(max, n));
      };

      const result = await cloneRunner({
        url: job.url,
        output: './output',
        waitTime: clamp(options.waitTime, 0, 30000, 3000),
        viewport: options.viewport || '1920x1080',
        scrollCount: clamp(options.scrollCount, 0, 20, 5),
        recursive: Boolean(options.recursive),
        maxPages: clamp(options.maxPages, 1, 100, 10),
        maxDepth: clamp(options.maxDepth, 0, 10, 1),
        concurrency: clamp(options.concurrency, 1, 10, 3),
        scaffold: options.scaffold !== false,
        cookieFile: options.cookieFile || null,
        storageState: null,
        followLoginGated: Boolean(options.followLoginGated),
        crawlProfile: ['accurate', 'balanced', 'lightweight', 'authenticated'].includes(options.crawlProfile)
          ? options.crawlProfile
          : 'accurate',
        networkPosture: ['default', 'authenticated', 'sensitive-site', 'manual-review'].includes(options.networkPosture)
          ? options.networkPosture
          : 'default',
        enableRepresentativeQA: Boolean(options.enableRepresentativeQA),
        domainScope: options.domainScope === 'hostname' ? 'hostname' : 'registrable-domain',
        updateExisting: Boolean(options.updateExisting),
        screenshot: Boolean(options.screenshot),
        signal: job.abortController.signal,
      });

      const jobInsights = normalizeJobInsights(result);
      job.status = 'completed';
      job.progress = 'Completed';
      job.outputDir = result?.outputDir || null;
      job.verificationWarnings = jobInsights.verificationWarnings;
      job.qualitySummary = jobInsights.qualitySummary;
      job.artifacts = jobInsights.artifacts;
      job.updatedAt = new Date().toISOString();
      emitJobLog(job, {
        type: 'success',
        text: `Clone completed${job.outputDir ? `: ${job.outputDir}` : ''}`,
      });
    } catch (error) {
      if (job.status !== 'cancelled') {
        job.status = 'failed';
        job.progress = 'Failed';
        job.error = serializeJobError(error);
        job.updatedAt = new Date().toISOString();
        emitJobLog(job, { type: 'error', text: `Clone failed: ${job.error.message}` });
        if (job.error.hint) {
          emitJobLog(job, { type: 'warn', text: job.error.hint });
        }
      }
    } finally {
      activeJobId = null;
      for (const client of job.clients) {
        client.end();
      }
      job.clients.clear();
      pruneCompletedJobs();
    }
  }

  function emitJobLog(job, entry) {
    const normalizedEntry = recordJobLog(job, entry);
    broadcast(job, normalizedEntry);
    return normalizedEntry;
  }

  function recordJobLog(job, entry) {
    const normalizedEntry = {
      ...entry,
      text: stringifyErrorLike(entry.text),
      timestamp: entry.timestamp || new Date().toISOString(),
    };

    job.logs.push(normalizedEntry);
    if (job.logs.length > MAX_JOB_LOGS) {
      job.logs = job.logs.slice(-MAX_JOB_LOGS);
    }
    job.updatedAt = new Date().toISOString();
    return normalizedEntry;
  }

  function broadcast(job, entry) {
    const payload = `data: ${JSON.stringify(entry)}\n\n`;
    for (const client of job.clients) {
      try {
        client.write(payload);
      } catch {
        job.clients.delete(client);
      }
    }
  }
}

export function startUIServer({ port = process.env.PORT || 4000, cloneRunner } = {}) {
  const app = createUIServerApp({ cloneRunner });
  const server = app.listen(port, () => {
    console.log(`\nWeb UI server is running at http://localhost:${port}\n`);
  });

  server.on('close', () => {
    app.locals.cleanup?.();
  });

  return server;
}

function serializeJob(job) {
  return {
    id: job.id,
    url: job.url,
    status: job.status,
    progress: job.progress,
    outputDir: job.outputDir,
    error: job.error,
    verificationWarnings: cloneSerializable(job.verificationWarnings) || [],
    qualitySummary: cloneSerializable(job.qualitySummary),
    artifacts: cloneSerializable(job.artifacts),
    createdAt: job.createdAt,
    updatedAt: job.updatedAt,
  };
}

function normalizeJobInsights(result) {
  return {
    verificationWarnings: normalizeVerificationWarnings(result?.verificationWarnings),
    qualitySummary: normalizeQualitySummary(result?.qualitySummary, result),
    artifacts: normalizeArtifacts(result?.artifacts),
  };
}

function normalizeVerificationWarnings(warnings) {
  if (!Array.isArray(warnings)) return [];
  return warnings
    .map((warning) => stringifyErrorLike(warning))
    .map((warning) => warning.trim())
    .filter(Boolean);
}

function normalizeQualitySummary(summary, result = {}) {
  const fallbackPageCount = toCountOrNull(result?.pageCount);
  const fallbackGraphqlEndpoints = toCountOrNull(result?.apiSummary?.uniqueEndpoints);
  const source = summary && typeof summary === 'object' && !Array.isArray(summary) ? summary : {};

  return {
    pagesCaptured: toCountOrNull(source.pagesCaptured ?? fallbackPageCount),
    pagesFailed: toCountOrNull(source.pagesFailed),
    skippedPages: toCountOrNull(source.skippedPages),
    missingCriticalAssets: toCountOrNull(source.missingCriticalAssets),
    replayWarnings: toCountOrNull(source.replayWarnings),
    graphqlEndpoints: toCountOrNull(source.graphqlEndpoints ?? fallbackGraphqlEndpoints),
  };
}

function normalizeArtifacts(artifacts) {
  if (!artifacts || typeof artifacts !== 'object' || Array.isArray(artifacts)) return null;
  return cloneSerializable(artifacts);
}

function toCountOrNull(value) {
  if (value === null || value === undefined || value === '') return null;
  const count = Number(value);
  return Number.isFinite(count) ? count : null;
}

function cloneSerializable(value) {
  if (value === null || value === undefined) return null;

  if (typeof globalThis.structuredClone === 'function') {
    try {
      return globalThis.structuredClone(value);
    } catch {
      // Fall through to JSON clone.
    }
  }

  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return value;
  }
}

function sseHeaders() {
  return {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  };
}
