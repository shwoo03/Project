import path from 'path';

import { ensureDir, saveFile } from '../utils/file-utils.js';
import logger from '../utils/logger.js';

export default class ProjectScaffolder {
  constructor(outputDir, targetHost) {
    this.outputDir = outputDir;
    this.targetHost = targetHost;
  }

  async scaffold(reportData = {}) {
    logger.start('Generate backend-ready scaffold');

    try {
      await this._createDirectories();
      await this._createPackageJson();
      await this._createServerJs(reportData.entryPagePath || 'pages/index.html');
      await this._createMockService();
      await this._createRouteIndex(reportData.apiSummary || { routeGroups: {} });
      await this._createReadme(reportData.entryPagePath || 'pages/index.html');
      await this._createSchemaSnapshot(reportData.apiSummary || { routeGroups: {} });
      logger.succeed('Backend-ready scaffold generated');
    } catch (err) {
      logger.error(`Scaffolding failed: ${err.message}`);
    }
  }

  async _createDirectories() {
    const dirs = [
      'client',
      'server',
      'server/routes',
      'server/controllers',
      'server/services',
      'server/schemas',
      'mocks/api',
      'docs/api',
      'docs/ui',
      'docs/crawl',
      'docs/integration',
      'manifest',
    ];

    for (const dir of dirs) {
      await ensureDir(path.join(this.outputDir, dir));
    }
  }

  async _createPackageJson() {
    const pkg = {
      name: `clone-${this.targetHost.replace(/\./g, '-')}`,
      version: '1.0.0',
      description: `Generated clone handoff for ${this.targetHost}`,
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

  async _createServerJs(entryPagePath) {
    const normalizedEntryPath = entryPagePath.replace(/\\/g, '/');
    const content = `import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import apiRouter from './server/routes/api.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();
const PORT = process.env.PORT || 3000;
const clientPath = path.join(__dirname, 'client');

app.use(cors());
app.use(express.json({ limit: '5mb' }));
app.use(express.urlencoded({ extended: true }));
app.use(express.static(clientPath));
app.use('/api', apiRouter);

app.get('/', (req, res) => {
  res.sendFile(path.join(clientPath, '${normalizedEntryPath}'));
});

app.get('*', (req, res) => {
  const fallbackPath = path.join(clientPath, req.path);
  res.sendFile(fallbackPath, (err) => {
    if (err) {
      res.sendFile(path.join(clientPath, '${normalizedEntryPath}'));
    }
  });
});

app.listen(PORT, () => {
  console.log('Server is running on http://localhost:' + PORT);
  console.log('Entry page: /${normalizedEntryPath}');
});
`;

    await saveFile(path.join(this.outputDir, 'server.js'), content);
  }

  async _createMockService() {
    const serviceContent = `import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const mockDataPath = path.join(__dirname, '../../mocks/api/mock-data.json');

export function loadMockData() {
  if (!fs.existsSync(mockDataPath)) {
    return {};
  }
  return JSON.parse(fs.readFileSync(mockDataPath, 'utf-8'));
}

export function findMockResponse(mockData, pathname, method, req) {
  const upperMethod = method.toUpperCase();
  const entry = mockData[pathname]?.[upperMethod];
  if (!entry) return null;

  const actualSearch = buildSearchString(req?.query || {});
  const actualBodyHash = hashValue(req?.body);

  const matchedVariant = (entry.variants || []).find((variant) => {
    const sameSearch = (variant.match?.search || '') === actualSearch;
    const sameBody = (variant.match?.bodyHash || 'no-body') === actualBodyHash;
    return sameSearch && sameBody;
  });

  if (matchedVariant) {
    return matchedVariant.response;
  }

  const searchOnlyVariant = (entry.variants || []).find((variant) => (variant.match?.search || '') === actualSearch);
  if (searchOnlyVariant) {
    return searchOnlyVariant.response;
  }

  return entry.default || null;
}

function buildSearchString(query) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query || {})) {
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, item);
    } else if (value !== undefined && value !== null) {
      params.append(key, String(value));
    }
  }
  const rendered = params.toString();
  return rendered ? \`?\${rendered}\` : '';
}

function hashValue(value) {
  if (value === null || value === undefined || value === '' || (typeof value === 'object' && Object.keys(value).length === 0)) {
    return 'no-body';
  }
  return crypto.createHash('sha1').update(stableSerialize(value)).digest('hex').slice(0, 12);
}

function stableSerialize(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) {
    return \`[\${value.map((item) => stableSerialize(item)).join(',')}]\`;
  }
  if (value && typeof value === 'object') {
    return \`{\${Object.keys(value).sort().map((key) => \`\${JSON.stringify(key)}:\${stableSerialize(value[key])}\`).join(',')}}\`;
  }
  return JSON.stringify(value);
}
`;

    const controllerContent = `import { loadMockData, findMockResponse } from '../services/mock-api.service.js';

export function handleCapturedApi(req, res) {
  const mockData = loadMockData();
  const targetPath = req.path || '/';
  const responseConfig = findMockResponse(mockData, targetPath, req.method, req);

  if (!responseConfig) {
    res.status(404).json({
      error: 'Endpoint not found in captured mock data',
      path: targetPath,
      method: req.method,
    });
    return;
  }

  const body = responseConfig.body ?? {};
  const mimeType = responseConfig.mimeType || 'application/json';
  res.setHeader('Content-Type', mimeType);
  res.status(responseConfig.status || 200).send(
    typeof body === 'string' ? body : JSON.stringify(body),
  );
}
`;

    const routeContent = `import { Router } from 'express';
import { handleCapturedApi } from '../controllers/captured-api.controller.js';
import generatedRoutes from './generated-routes.js';

const router = Router();

generatedRoutes(router);
router.all('*', handleCapturedApi);

export default router;
`;

    await saveFile(path.join(this.outputDir, 'server', 'services', 'mock-api.service.js'), serviceContent);
    await saveFile(path.join(this.outputDir, 'server', 'controllers', 'captured-api.controller.js'), controllerContent);
    await saveFile(path.join(this.outputDir, 'server', 'routes', 'api.js'), routeContent);
  }

  async _createRouteIndex(apiSummary) {
    const lines = [
      'export default function generatedRoutes(router) {',
      '  // Captured endpoint stubs. Replace these handlers with real service logic.',
    ];

    const mergedRoutes = new Set();
    for (const [group, routes] of Object.entries(apiSummary.routeGroups || {})) {
      lines.push(`  // Group: ${group}`);

      for (const route of routes) {
        let paramCount = 1;
        const dynamicPath = route.pathname
          .replace(/\/[0-9a-fA-F-]{8,}(?=\/|$)/g, () => `/:param${paramCount++}`)
          .replace(/\/\d+(?=\/|$)/g, () => `/:param${paramCount++}`);

        const method = route.method.toLowerCase();
        const routeKey = `${method} ${dynamicPath}`;
        if (mergedRoutes.has(routeKey)) continue;

        mergedRoutes.add(routeKey);
        lines.push(`  router.${method}('${dynamicPath}', (req, res, next) => next());`);
      }
    }

    lines.push('}');
    lines.push('');

    await saveFile(path.join(this.outputDir, 'server', 'routes', 'generated-routes.js'), lines.join('\n'));
  }

  async _createSchemaSnapshot(apiSummary) {
    await saveFile(
      path.join(this.outputDir, 'server', 'schemas', 'captured-endpoints.schema.json'),
      JSON.stringify(apiSummary, null, 2),
    );
  }

  async _createReadme(entryPagePath) {
    const lines = [
      `# ${this.targetHost} Clone Handoff`,
      '',
      'This project was generated for backend handoff work.',
      '',
      '## Structure',
      '',
      '- `client/`: mirrored frontend pages and assets',
      '- `server/`: Express starter backend with captured route stubs',
      '- `mocks/api/`: captured mock responses with variants',
      '- `docs/api/`: API capture docs',
      '- `docs/ui/`: visual analysis docs',
      '- `docs/crawl/`: crawl manifest and reports',
      '- `docs/integration/`: frontend-to-backend mapping docs',
      '- `manifest/`: normalized crawl manifest',
      '',
      '## Run',
      '',
      '```bash',
      'npm install',
      'npm run dev',
      '```',
      '',
      `Open \`http://localhost:3000\`. The default entry page is \`/${entryPagePath.replace(/\\/g, '/')}\`.`,
      '',
      'Generated mock responses prefer an exact query/body variant match and fall back to the default captured response.',
    ];

    await saveFile(path.join(this.outputDir, 'README.md'), lines.join('\n'));
  }
}
