import express from 'express';
import path from 'path';
import fs from 'fs/promises';
import { fileURLToPath } from 'url';
import { randomUUID } from 'crypto';

import { cloneFrontend } from '../src/index.js';
import logger from '../src/utils/logger.js';
import { validateUrlSafety } from '../src/utils/url-utils.js';
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

  function pruneCompletedJobs() {
    const now = Date.now();
    const completedJobs = [];
    for (const [id, job] of jobs) {
      if (job.status === 'completed' || job.status === 'failed') {
        completedJobs.push({ id, updatedAt: new Date(job.updatedAt).getTime() });
      }
    }
    completedJobs.sort((a, b) => a.updatedAt - b.updatedAt);
    for (const { id, updatedAt } of completedJobs) {
      if (completedJobs.length > MAX_COMPLETED_JOBS || now - updatedAt > JOB_RETENTION_MS) {
        jobs.delete(id);
        completedJobs.shift();
      }
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

  logger.on('log', (entry) => {
    if (!activeJobId) return;
    const job = jobs.get(activeJobId);
    if (!job) return;

    job.logs.push(entry);
    if (job.logs.length > MAX_JOB_LOGS) {
      job.logs = job.logs.slice(-500);
    }
    job.updatedAt = new Date().toISOString();
    broadcast(job, entry);
  });

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
      progress: 'Queued',
      outputDir: null,
      error: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      logs: [],
      clients: new Set(),
      abortController,
    };

    jobs.set(jobId, job);
    activeJobId = jobId;
    broadcast(job, { type: 'info', text: `Job ${jobId} queued for ${job.url}` });
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
    broadcast(job, { type: 'warn', text: 'Job cancelled by user' });
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
    broadcast(job, { type: 'info', text: `Clone started for ${job.url}` });

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
        cookieFile: null,
        storageState: null,
        followLoginGated: Boolean(options.followLoginGated),
        domainScope: options.domainScope === 'hostname' ? 'hostname' : 'registrable-domain',
        updateExisting: Boolean(options.updateExisting),
        screenshot: Boolean(options.screenshot),
        signal: job.abortController.signal,
      });

      job.status = 'completed';
      job.progress = 'Completed';
      job.outputDir = result?.outputDir || null;
      job.updatedAt = new Date().toISOString();
      broadcast(job, {
        type: 'success',
        text: `Clone completed${job.outputDir ? `: ${job.outputDir}` : ''}`,
      });
    } catch (error) {
      if (job.status !== 'cancelled') {
        job.status = 'failed';
        job.progress = 'Failed';
        job.error = error.message;
        job.updatedAt = new Date().toISOString();
        broadcast(job, { type: 'error', text: `Clone failed: ${error.message}` });
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

  function broadcast(job, entry) {
    job.logs.push({
      ...entry,
      timestamp: entry.timestamp || new Date().toISOString(),
    });
    if (job.logs.length > MAX_JOB_LOGS) {
      job.logs = job.logs.slice(-500);
    }
    for (const client of job.clients) {
      client.write(`data: ${JSON.stringify(job.logs[job.logs.length - 1])}\n\n`);
    }
  }
}

export function startUIServer({ port = process.env.PORT || 4000, cloneRunner } = {}) {
  const app = createUIServerApp({ cloneRunner });
  return app.listen(port, () => {
    console.log(`\nWeb UI server is running at http://localhost:${port}\n`);
  });
}

function serializeJob(job) {
  return {
    id: job.id,
    url: job.url,
    status: job.status,
    progress: job.progress,
    outputDir: job.outputDir,
    error: job.error,
    createdAt: job.createdAt,
    updatedAt: job.updatedAt,
  };
}

function sseHeaders() {
  return {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  };
}
