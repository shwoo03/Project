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
    await scaffolder.scaffold({ entryPagePath: 'kr-en/index.html', siteMap: [], pages: [] });

    const serverShim = await fs.readFile(path.join(tempRoot, 'server.js'), 'utf-8');
    const adapter = await fs.readFile(path.join(tempRoot, 'server', 'adapters', 'express', 'app.js'), 'utf-8');
    const readme = await fs.readFile(path.join(tempRoot, 'README.md'), 'utf-8');

    assert.match(serverShim, /await startExpressAdapter\(\);/);
    assert.match(adapter, /findAvailablePort/);
    assert.match(adapter, /Preferred port .* is busy/);
    assert.match(adapter, /express\.static\(path\.join\(ROOT, 'public'\), \{ index: false \}\)/);
    assert.match(readme, /automatically tries the next available port/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
