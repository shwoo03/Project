import path from 'path';
import fs from 'fs/promises';
import { fileURLToPath } from 'url';

import { ensureDir, saveFile } from '../utils/file-utils.js';
import logger from '../utils/logger.js';

const TEMPLATES_DIR = path.dirname(fileURLToPath(new URL('./templates/runtime-guard.js', import.meta.url)));

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
      await this._createReadme(reportData);
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
    const content = await fs.readFile(path.join(TEMPLATES_DIR, 'runtime-guard.js'), 'utf-8');
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
    const templatePath = path.join(TEMPLATES_DIR, 'express-adapter.js.template');
    let content = await fs.readFile(templatePath, 'utf-8');
    content = content.replace(/\{\{ENTRY_REPLAY_ROUTE\}\}/g, entryReplayRoute);
    content = content.replace(/\{\{ENTRY_PAGE_PATH\}\}/g, normalizedEntryPath);
    await saveFile(path.join(this.outputDir, 'server', 'adapters', 'express', 'app.js'), content);
  }


  async _createReadme(reportData = {}) {
    const {
      entryReplayRoute = '/',
      apiSummary,
      siteMap,
      pages,
      cssRecoverySummary,
      httpManifest,
    } = reportData;

    const lines = [
      `# ${this.targetHost} Replay Package`,
      '',
      'This output was generated from a live browser capture and rebuilt as an offline replay package.',
      '',
    ];

    if (pages && pages.length > 0) {
      const pagesCount = pages.length;
      const replayableCount = pages.filter((p) => p.replayRoute).length;
      const cssRecovered = cssRecoverySummary?.cssAssetsRecovered || 0;
      const cssDiscovered = cssRecoverySummary?.cssAssetsDiscovered || 0;
      const cssFailed = cssRecoverySummary?.cssAssetsFailed || 0;
      const cssRate = cssDiscovered > 0 ? ((cssRecovered / cssDiscovered) * 100).toFixed(1) : '0';
      const loginGated = (siteMap || []).filter((p) => p.loginGated).length;

      lines.push(
        '## Crawl Summary',
        '',
        '| Metric | Value |',
        '|--------|-------|',
        `| Pages crawled | ${pagesCount} |`,
        `| Pages replayable | ${replayableCount} |`,
      );
      if (cssDiscovered > 0) {
        lines.push(`| CSS assets recovered | ${cssRecovered} / ${cssDiscovered} (${cssRate}%) |`);
      }
      if (loginGated > 0) {
        lines.push(`| Login-gated pages | ${loginGated} |`);
      }
      lines.push('');

      let localizedNav = 0;
      let disabledNav = 0;
      for (const page of pages) {
        localizedNav += page.hiddenNavigationSummary?.localizedHiddenNavigationCount || 0;
        disabledNav += page.hiddenNavigationSummary?.disabledHiddenNavigationCount || 0;
      }
      if (localizedNav > 0 || disabledNav > 0) {
        lines.push(
          '## Hidden Navigation',
          '',
          '| Status | Count |',
          '|--------|-------|',
          `| Localized (rewritten to local) | ${localizedNav} |`,
          `| Disabled (non-replayable) | ${disabledNav} |`,
          '',
        );
      }

      if (apiSummary && apiSummary.uniqueEndpoints > 0) {
        const sanitizedCount = (httpManifest || []).filter((e) => e.sanitized).length;
        lines.push(
          '## API Mocks',
          '',
          '| Category | Count |',
          '|----------|-------|',
          `| Total captured endpoints | ${apiSummary.uniqueEndpoints} |`,
          `| Render-critical | ${apiSummary.renderCriticalRequestCount || 0} |`,
          `| Render-supporting | ${apiSummary.renderSupportingRequestCount || 0} |`,
          `| Non-critical (filtered) | ${apiSummary.nonCriticalRequestCount || 0} |`,
        );
        if (sanitizedCount > 0) {
          lines.push(`| Sanitized entries | ${sanitizedCount} |`);
        }
        lines.push('');
      }

      const limitations = [];
      if (loginGated > 0) limitations.push(`${loginGated} login-gated page(s) detected`);
      if (disabledNav > 0) limitations.push(`${disabledNav} hidden navigation targets disabled (external or uncloned)`);
      if (cssFailed > 0) limitations.push(`${cssFailed} CSS assets could not be recovered`);

      if (limitations.length > 0) {
        lines.push('## Known Limitations', '');
        for (const item of limitations) {
          lines.push(`- ${item}`);
        }
        lines.push('');
      }
    }

    lines.push(
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
    );

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
