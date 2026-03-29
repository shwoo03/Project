import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';

import ProjectScaffolder from '../src/scaffolder/project-scaffolder.js';

test('ProjectScaffolder emits replay server with port fallback guidance', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-scaffold-'));

  try {
    const scaffolder = new ProjectScaffolder(tempRoot, 'www.netflix.com');
    await scaffolder.scaffold({
      entryPagePath: 'kr-en/index.html',
      entryReplayRoute: '/kr-en',
      siteMap: [],
      pages: [],
    });

    const serverShim = await fs.readFile(path.join(tempRoot, 'server.js'), 'utf-8');
    const adapter = await fs.readFile(path.join(tempRoot, 'server', 'adapters', 'express', 'app.js'), 'utf-8');
    const readme = await fs.readFile(path.join(tempRoot, 'README.md'), 'utf-8');
    const runtimeGuard = await fs.readFile(path.join(tempRoot, 'public', '__front_clone_runtime_guard__.js'), 'utf-8');

    assert.match(serverShim, /await startExpressAdapter\(\);/);
    assert.match(adapter, /findAvailablePort/);
    assert.match(adapter, /Preferred port .* is busy/);
    assert.match(adapter, /const manifest = await readJson\(path\.join\(ROOT, 'server', 'mocks', 'http-manifest\.json'\), \[\]\);/);
    assert.match(adapter, /findHttpMockMatch/);
    assert.match(adapter, /normalizeSearch/);
    assert.match(adapter, /page-route-manifest\.json/);
    assert.match(adapter, /buildPageRouteLookup/);
    assert.ok(adapter.includes("replace(/^\\?/, '')"));
    assert.match(adapter, /const staticOptions = \{/);
    assert.match(adapter, /Cache-Control', 'public, max-age=3600'/);
    assert.match(adapter, /res\.setHeader\('Cache-Control', 'no-cache'\);/);
    assert.match(adapter, /express\.static\(path\.join\(ROOT, 'public'\), staticOptions\)/);
    assert.match(runtimeGuard, /__FRONT_CLONE_RUNTIME__/);
    assert.match(runtimeGuard, /EventTarget\.prototype\.addEventListener/);
    assert.match(readme, /automatically tries the next available port/);
    assert.match(adapter, /Entry page: \/kr-en/);
    assert.match(readme, /Open `http:\/\/localhost:3000\/kr-en`/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
