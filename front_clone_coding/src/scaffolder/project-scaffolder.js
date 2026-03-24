import path from 'path';

import { ensureDir, saveFile } from '../utils/file-utils.js';
import logger from '../utils/logger.js';

export default class ProjectScaffolder {
  constructor(outputDir, targetHost) {
    this.outputDir = outputDir;
    this.targetHost = targetHost;
  }

  async scaffold(reportData = {}) {
    logger.start('Generate replay adapter scaffold');

    try {
      await this._createDirectories();
      await this._createPackageJson();
      await this._createRootServerShim();
      await this._createExpressAdapter(reportData.entryPagePath || 'index.html');
      await this._createReadme(reportData.entryPagePath || 'index.html');
      await this._createMissingBehaviors(reportData.siteMap || [], reportData.pages || []);
      logger.succeed('Replay adapter scaffold generated');
    } catch (err) {
      logger.error(`Scaffolding failed: ${err.message}`);
    }
  }

  async _createDirectories() {
    const dirs = [
      'public',
      'views',
      'server',
      'server/spec',
      'server/spec/graphql',
      'server/mocks',
      'server/mocks/http',
      'server/mocks/ws',
      'server/adapters',
      'server/adapters/express',
      'server/docs',
      'server/docs/ui',
      'server/docs/crawl',
      'server/docs/integration',
    ];

    for (const dir of dirs) {
      await ensureDir(path.join(this.outputDir, dir));
    }
  }

  async _createPackageJson() {
    const pkg = {
      name: `clone-${this.targetHost.replace(/\./g, '-')}`,
      version: '1.0.0',
      description: `Generated browser-capture replay package for ${this.targetHost}`,
      main: 'server.js',
      type: 'module',
      scripts: {
        start: 'node server.js',
        dev: 'node --watch server.js',
      },
      dependencies: {
        cors: '^2.8.5',
        express: '^4.21.0',
      },
    };

    await saveFile(path.join(this.outputDir, 'package.json'), JSON.stringify(pkg, null, 2));
  }

  async _createRootServerShim() {
    const content = `import { startExpressAdapter } from './server/adapters/express/app.js';

await startExpressAdapter();
`;

    await saveFile(path.join(this.outputDir, 'server.js'), content);
  }

  async _createExpressAdapter(entryPagePath) {
    const normalizedEntryPath = entryPagePath.replace(/\\/g, '/');
    const content = `import crypto from 'crypto';
import net from 'net';
import express from 'express';
import cors from 'cors';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..', '..', '..');

export async function startExpressAdapter({ port = process.env.PORT || 3000, maxPort } = {}) {
  const app = express();

  app.use(cors());
  app.use(express.json({ limit: '20mb' }));
  app.use(express.urlencoded({ extended: true }));
  app.use(express.static(path.join(ROOT, 'public'), { index: false }));
  app.use('/public', express.static(path.join(ROOT, 'public'), { index: false }));

  app.all('/api/*', async (req, res, next) => {
    try {
      const manifest = await readJson(path.join(ROOT, 'server', 'mocks', 'http-manifest.json'), []);
      const pathname = req.path.replace(/^\\/api/, '') || '/';
      const search = buildSearch(req.query || {});
      const bodyHash = hashValue(req.body);
      const operationName = typeof req.body?.operationName === 'string' ? req.body.operationName : null;
      const variablesHash = hashValue(req.body?.variables ?? null);

      const match = manifest.find((item) => {
        if (item.method !== req.method) return false;
        if (item.path !== pathname) return false;
        if ((item.search || '') !== search) return false;
        if (item.graphQL) {
          return (item.graphQLOperationName || null) === operationName
            && (item.graphQLVariablesHash || 'no-body') === variablesHash;
        }
        return (item.bodyHash || 'no-body') === bodyHash;
      }) || manifest.find((item) => item.method === req.method && item.path === pathname);

      if (!match) return next();

      const body = await readJson(path.join(ROOT, 'server', match.bodyFile), null);
      res.type(match.responseMimeType || 'application/json');
      res.status(match.status || 200);
      return res.send(body);
    } catch (error) {
      return next(error);
    }
  });

  app.get('*', async (req, res, next) => {
    try {
      const viewFile = resolveViewFile(req.path);
      await fs.access(viewFile);
      return res.sendFile(viewFile);
    } catch {
      return next();
    }
  });

  app.use((_req, res) => {
    res.status(404).send('Not Found');
  });

  const preferredPort = normalizePort(port, 3000);
  const fallbackMaxPort = normalizePort(maxPort, preferredPort + 20);
  const resolvedPort = await findAvailablePort(preferredPort, Math.max(preferredPort, fallbackMaxPort));

  if (resolvedPort !== preferredPort) {
    console.warn('Preferred port ' + preferredPort + ' is busy. Using http://localhost:' + resolvedPort + ' instead.');
  }

  const server = app.listen(resolvedPort, () => {
    console.log('Replay adapter is running on http://localhost:' + resolvedPort);
    console.log('Entry page: /${normalizedEntryPath.replace(/\\.html$/, '')}');
  });

  return { app, server, port: resolvedPort };
}

function resolveViewFile(routePath) {
  let normalized = routePath || '/';
  if (normalized === '/') return path.join(ROOT, 'views', '${normalizedEntryPath}');
  normalized = normalized.replace(/\\/+$/, '');
  return path.join(ROOT, 'views', normalized.replace(/^\\//, '') + '.html');
}

async function readJson(filePath, fallback) {
  try {
    const raw = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function buildSearch(query) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query || {})) {
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, item);
    } else if (value !== undefined && value !== null) {
      params.append(key, String(value));
    }
  }
  const rendered = params.toString();
  return rendered ? '?' + rendered : '';
}

function hashValue(value) {
  if (value === null || value === undefined || value === '' || (typeof value === 'object' && Object.keys(value || {}).length === 0)) {
    return 'no-body';
  }
  return crypto.createHash('sha1').update(stableSerialize(value)).digest('hex').slice(0, 12);
}

function stableSerialize(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return '[' + value.map((item) => stableSerialize(item)).join(',') + ']';
  if (value && typeof value === 'object') {
    return '{' + Object.keys(value).sort().map((key) => JSON.stringify(key) + ':' + stableSerialize(value[key])).join(',') + '}';
  }
  return JSON.stringify(value);
}

function normalizePort(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1 || parsed > 65535) {
    return fallback;
  }
  return parsed;
}

async function findAvailablePort(startPort, maxPort) {
  for (let current = startPort; current <= maxPort; current += 1) {
    const available = await canListenOnPort(current);
    if (available) return current;
  }

  throw new Error('No available port found between ' + startPort + ' and ' + maxPort + '. Set PORT to an open port and retry.');
}

function canListenOnPort(port) {
  return new Promise((resolve) => {
    const tester = net.createServer();

    tester.once('error', () => resolve(false));
    tester.once('listening', () => {
      tester.close(() => resolve(true));
    });

    tester.listen(port);
  });
}
`;

    await saveFile(path.join(this.outputDir, 'server', 'adapters', 'express', 'app.js'), content);
  }

  async _createReadme(entryPagePath) {
    const lines = [
      `# ${this.targetHost} Replay Package`,
      '',
      'This output was generated from a live browser capture and rebuilt as an offline replay package.',
      '',
      '## Structure',
      '',
      '- `public/`: captured CSS, JS, images, fonts, media, and misc assets',
      '- `views/`: path-based HTML snapshots',
      '- `server/spec/`: OpenAPI, AsyncAPI, GraphQL operation reports, and crawl manifests',
      '- `server/mocks/`: HTTP mock payloads, HTTP manifest, and WebSocket frames',
      '- `server/adapters/express/`: replay adapter',
      '- `server/docs/`: generated reports and missing behavior notes',
      '',
      '## Run',
      '',
      '```bash',
      'npm install',
      'npm start',
      '```',
      '',
      `Open \`http://localhost:3000/${entryPagePath.replace(/\\/g, '/').replace(/\\.html$/, '')}\` or the fallback port shown in the terminal.`,
      '',
      'If port `3000` is already in use, the replay server automatically tries the next available port.',
      'You can also force a specific port with `PORT=3010 npm start`.',
      '',
      'The Express adapter is a derived runtime. The source-of-truth artifacts live under `server/spec/` and `server/mocks/`.',
    ];

    await saveFile(path.join(this.outputDir, 'README.md'), lines.join('\n'));
  }

  async _createMissingBehaviors(siteMap, pages) {
    const lines = [
      '# Missing Behaviors',
      '',
      'The following items may require manual work after replay generation.',
      '',
    ];

    const loginPages = siteMap.filter((item) => item.loginGated || item.skippedReason === 'login-gated');
    for (const page of loginPages) {
      lines.push(`- Login-gated page detected: ${page.finalUrl || page.url}`);
    }

    for (const page of pages) {
      if ((page.interactiveElements || []).some((item) => item.hasOnClick)) {
        lines.push(`- Inline click handlers detected on ${page.finalUrl || page.url}`);
      }
      if (page.sessionStorageState && Object.keys(page.sessionStorageState).length > 0) {
        lines.push(`- sessionStorage was captured for ${page.finalUrl || page.url}; replay parity may still require custom restore logic.`);
      }
    }

    if (lines.length === 3) {
      lines.push('- No obvious unsupported behaviors were detected from current heuristics.');
    }

    await saveFile(path.join(this.outputDir, 'server', 'docs', 'missing-behaviors.md'), lines.join('\n'));
  }
}
