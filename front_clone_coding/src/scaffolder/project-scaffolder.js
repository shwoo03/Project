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
      await this._createRuntimeGuardAsset();
      await this._createPackageJson();
      await this._createRootServerShim();
      await this._createExpressAdapter(reportData.entryPagePath || 'index.html', reportData.entryReplayRoute || '/');
      await this._createReadme(reportData.entryPagePath || 'index.html', reportData.entryReplayRoute || '/');
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

  async _createRuntimeGuardAsset() {
    const content = `(function () {
  if (window.__FRONT_CLONE_RUNTIME__?.guardActive) return;

  const runtime = window.__FRONT_CLONE_RUNTIME__ = {
    guardActive: true,
    version: 1,
    exceptions: [],
    resourceErrors: [],
  };

  function limit(list, entry) {
    if (!entry) return;
    list.push(entry);
    if (list.length > 100) list.shift();
  }

  function classifyDomAssumption(message) {
    const lower = String(message || '').toLowerCase();
    if (/(cannot (set|read) properties of null|cannot (set|read) properties of undefined|null is not an object|undefined is not an object|appendchild|removechild|insertbefore|queryselector)/.test(lower)) {
      return 'runtime-dom-assumption';
    }
    if (/chunk|module script|loading chunk|importing a module script failed/.test(lower)) {
      return 'runtime-script-failed';
    }
    return 'runtime-exception';
  }

  function classifyResource(resourceType, url) {
    if (resourceType === 'script') return 'runtime-script-failed';
    if (resourceType === 'stylesheet') return 'runtime-style-failed';
    return 'runtime-resource-missing';
  }

  function toResourceType(target, url) {
    const tag = String(target?.tagName || '').toLowerCase();
    if (tag === 'script') return 'script';
    if (tag === 'link') return 'stylesheet';
    if (tag === 'img' || tag === 'image') return 'image';
    if (tag === 'video' || tag === 'audio' || tag === 'source') return 'media';
    const lowerUrl = String(url || '').toLowerCase();
    if (lowerUrl.endsWith('.js')) return 'script';
    if (lowerUrl.endsWith('.css')) return 'stylesheet';
    return 'resource';
  }

  function normalizeUrl(rawUrl) {
    if (!rawUrl) return '';
    try {
      return new URL(rawUrl, location.href).href;
    } catch {
      return String(rawUrl || '');
    }
  }

  function recordException(error, source) {
    const message = String(error?.message || error || '').trim();
    if (!message) return;
    limit(runtime.exceptions, {
      name: String(error?.name || 'Error'),
      message,
      source: source || 'runtime',
      failureClass: classifyDomAssumption(message),
      sameOrigin: true,
      stack: String(error?.stack || '').split('\\n').slice(0, 5).join('\\n'),
    });
  }

  function recordResourceError(target, rawUrl, source) {
    const url = normalizeUrl(rawUrl || target?.src || target?.href || '');
    if (!url) return;
    let sameOrigin = false;
    try {
      sameOrigin = new URL(url, location.href).origin === location.origin;
    } catch {
      sameOrigin = false;
    }
    limit(runtime.resourceErrors, {
      url,
      sameOrigin,
      source: source || 'resource-error',
      resourceType: toResourceType(target, url),
      failureClass: classifyResource(toResourceType(target, url), url),
    });
  }

  window.addEventListener('error', (event) => {
    const target = event.target;
    if (target && target !== window) {
      recordResourceError(target, target.src || target.href || '', 'element-error');
      return;
    }
    recordException(event.error || new Error(event.message || 'runtime error'), 'window-error');
  }, true);

  window.addEventListener('unhandledrejection', (event) => {
    recordException(event.reason || new Error('unhandled rejection'), 'unhandledrejection');
  });

  const callbackMap = new WeakMap();
  function wrapCallback(callback, source) {
    if (typeof callback !== 'function') return callback;
    if (callbackMap.has(callback)) return callbackMap.get(callback);
    const wrapped = function (...args) {
      try {
        return callback.apply(this, args);
      } catch (error) {
        recordException(error, source);
        return undefined;
      }
    };
    callbackMap.set(callback, wrapped);
    return wrapped;
  }

  const originalSetTimeout = window.setTimeout.bind(window);
  window.setTimeout = function (callback, delay, ...args) {
    return originalSetTimeout(wrapCallback(callback, 'setTimeout'), delay, ...args);
  };

  const originalSetInterval = window.setInterval.bind(window);
  window.setInterval = function (callback, delay, ...args) {
    return originalSetInterval(wrapCallback(callback, 'setInterval'), delay, ...args);
  };

  const originalRequestAnimationFrame = window.requestAnimationFrame?.bind(window);
  if (originalRequestAnimationFrame) {
    window.requestAnimationFrame = function (callback) {
      return originalRequestAnimationFrame(wrapCallback(callback, 'requestAnimationFrame'));
    };
  }

  const originalAddEventListener = EventTarget.prototype.addEventListener;
  const originalRemoveEventListener = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    return originalAddEventListener.call(this, type, wrapCallback(listener, 'event:' + type), options);
  };
  EventTarget.prototype.removeEventListener = function (type, listener, options) {
    return originalRemoveEventListener.call(this, type, callbackMap.get(listener) || listener, options);
  };
})();
`;

    await saveFile(path.join(this.outputDir, 'public', '__front_clone_runtime_guard__.js'), content);
  }

  async _createRootServerShim() {
    const content = `import { startExpressAdapter } from './server/adapters/express/app.js';

await startExpressAdapter();
`;

    await saveFile(path.join(this.outputDir, 'server.js'), content);
  }

  async _createExpressAdapter(entryPagePath, entryReplayRoute) {
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
  const manifest = await readJson(path.join(ROOT, 'server', 'mocks', 'http-manifest.json'), []);
  const pageRouteManifest = await readJson(path.join(ROOT, 'server', 'spec', 'page-route-manifest.json'), { routes: [] });
  const routeLookup = buildPageRouteLookup(pageRouteManifest);
  const staticOptions = {
    index: false,
    etag: true,
    lastModified: true,
    maxAge: '1h',
    immutable: false,
    setHeaders(res) {
      res.setHeader('Cache-Control', 'public, max-age=3600');
    },
  };

  app.use(cors());
  app.use(express.json({ limit: '20mb' }));
  app.use(express.urlencoded({ extended: true }));
  app.all('/__front_clone_noop__', (_req, res) => res.status(204).end());
  app.use(express.static(path.join(ROOT, 'public'), staticOptions));
  app.use('/public', express.static(path.join(ROOT, 'public'), staticOptions));

  app.use('/api', async (req, res, next) => {
    try {
      const pathname = req.path.replace(/^\\/api/, '') || '/';
      const search = buildSearch(req.query || {});
      const bodyHash = hashValue(req.body);
      const graphQLBody = typeof req.body === 'object' && req.body ? req.body : {};
      const operationName = typeof graphQLBody.operationName === 'string' ? graphQLBody.operationName : null;
      const variablesHash = hashValue(graphQLBody.variables ?? null);
      const documentHash = hashValue(typeof graphQLBody.query === 'string' ? graphQLBody.query : null);
      const extensionsHash = hashValue(graphQLBody.extensions ?? null);

      const match = findHttpMockMatch(manifest, {
        method: req.method,
        path: pathname,
        search,
        bodyHash,
        operationName,
        documentHash,
        variablesHash,
        extensionsHash,
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

  app.use('/api', (req, res, next) => {
    if (isNonCriticalApiRequest(req.path)) {
      return res.status(204).end();
    }
    return next();
  });

  app.use(async (req, res, next) => {
    try {
      for (const viewFile of resolveViewCandidates(req.path, routeLookup)) {
        try {
          await fs.access(viewFile);
          res.setHeader('Cache-Control', 'no-cache');
          const html = await fs.readFile(viewFile, 'utf-8');
          res.type('html');
          return res.send(html);
        } catch {
          // Try the next candidate.
        }
      }
      return next();
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
    console.log('Entry page: ${entryReplayRoute}');
  });

  return { app, server, port: resolvedPort };
}

function resolveViewCandidates(routePath, routeLookup = new Map()) {
  const normalizedRoutePath = normalizeRoutePath(routePath);
  const mappedRoute = routeLookup.get(normalizedRoutePath);
  if (mappedRoute?.savedPath) {
    return [path.join(ROOT, 'views', mappedRoute.savedPath)];
  }

  if (normalizedRoutePath === '/') return [path.join(ROOT, 'views', '${normalizedEntryPath}')];
  const withoutLeadingSlash = normalizedRoutePath.replace(/^\\//, '');
  return [
    path.join(ROOT, 'views', withoutLeadingSlash + '.html'),
    path.join(ROOT, 'views', withoutLeadingSlash, 'index.html'),
  ];
}

function buildPageRouteLookup(pageRouteManifest = { routes: [] }) {
  const lookup = new Map();

  for (const route of pageRouteManifest.routes || []) {
    if (!route.replayable || !route.savedPath) continue;
    for (const routePath of [route.replayRoute, ...(route.routeAliases || [])]) {
      const normalizedRoutePath = normalizeRoutePath(routePath);
      if (!normalizedRoutePath) continue;
      lookup.set(normalizedRoutePath, route);
    }
  }

  return lookup;
}

function normalizeRoutePath(value) {
  const normalized = String(value || '/').replace(/\\\\/g, '/').replace(/\\/+$/, '');
  return normalized || '/';
}

function isNonCriticalApiRequest(value) {
  const lower = String(value || '').toLowerCase();
  return /(telemetry|tracking|metrics|analytic|analytics|beacon|logger|logging|impress|exposure|clicklog|nlog|veta|adtech|ads|conversion|pixel|collect|\blogs?\b|recaptcha|captcha|challenge|shield|bot)/.test(lower);
}

function findHttpMockMatch(manifest, requestMeta) {
  const normalizedSearch = normalizeSearch(requestMeta.search || '');

  const strictMatch = manifest.find((item) => {
    if (item.method !== requestMeta.method) return false;
    if (item.path !== requestMeta.path) return false;
    if ((item.normalizedSearch || normalizeSearch(item.search || '')) !== normalizedSearch) return false;

    if (item.matchStrategy === 'graphql-operation' || item.graphQL) {
      const details = item.graphQLDetails || {};
      const itemVariablesHash = details.variablesHash || item.graphQLVariablesHash || 'no-body';
      const itemDocumentHash = details.documentHash || 'no-body';
      return (details.operationName || item.graphQLOperationName || null) === (requestMeta.operationName || null)
        && itemVariablesHash === (requestMeta.variablesHash || 'no-body')
        && (
          (itemDocumentHash === (requestMeta.documentHash || 'no-body') && itemDocumentHash !== 'no-body')
          || (itemDocumentHash === 'no-body' && hashValue(details.extensions || null) === (requestMeta.extensionsHash || 'no-body'))
        );
    }

    return (item.bodyHash || 'no-body') === (requestMeta.bodyHash || 'no-body');
  });

  if (strictMatch) return strictMatch;

  return manifest.find((item) => {
    if (item.replayRole !== 'render-critical') return false;
    if (item.method !== requestMeta.method) return false;
    if (item.path !== requestMeta.path) return false;
    if ((item.normalizedSearch || normalizeSearch(item.search || '')) !== normalizedSearch) return false;
    if (!(item.matchStrategy === 'graphql-operation' || item.graphQL)) return false;

    const details = item.graphQLDetails || {};
    return (details.operationName || item.graphQLOperationName || null) === (requestMeta.operationName || null)
      && (details.variablesHash || item.graphQLVariablesHash || 'no-body') === (requestMeta.variablesHash || 'no-body');
  }) || null;
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
  return normalizeSearch(params.toString() ? '?' + params.toString() : '');
}

function normalizeSearch(search) {
  const params = new URLSearchParams(String(search || '').replace(/^\\?/, ''));
  const ignored = new Set(['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'utm_id', 'gclid', 'fbclid', 'msclkid', '_ga', '_gl', 'ref', 'ref_src']);
  const entries = [];

  for (const [key, value] of params.entries()) {
    if (ignored.has(key.toLowerCase())) continue;
    entries.push([key, value]);
  }

  entries.sort(([leftKey, leftValue], [rightKey, rightValue]) => {
    if (leftKey === rightKey) return leftValue.localeCompare(rightValue);
    return leftKey.localeCompare(rightKey);
  });

  const normalized = new URLSearchParams();
  for (const [key, value] of entries) {
    normalized.append(key, value);
  }

  const rendered = normalized.toString();
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

  async _createReadme(entryPagePath, entryReplayRoute) {
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
      `Open \`http://localhost:3000${entryReplayRoute}\` or the fallback port shown in the terminal.`,
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
