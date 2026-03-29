import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';

import { getOutputDomainRoot, resolveOutputDirForRun } from '../src/index.js';

test('output packages always use the registrable domain as the folder name', () => {
  assert.equal(getOutputDomainRoot('https://www.netflix.com/kr-en/'), 'netflix.com');
  assert.equal(getOutputDomainRoot('https://subdomain.example.co.uk/dashboard'), 'example.co.uk');
});

test('resolveOutputDirForRun allocates a numbered output directory instead of deleting an existing one', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-output-dir-'));
  try {
    await fs.mkdir(path.join(tempRoot, 'jongno.go.kr'));
    await fs.mkdir(path.join(tempRoot, 'jongno.go.kr-2'));

    const resolution = await resolveOutputDirForRun(tempRoot, 'jongno.go.kr');

    assert.equal(resolution.outputLabel, 'jongno.go.kr-3');
    assert.equal(resolution.sequence, 3);
    assert.equal(resolution.outputDir, path.join(tempRoot, 'jongno.go.kr-3'));
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('resolveOutputDirForRun keeps the canonical output directory for update-existing runs', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-output-dir-update-'));
  try {
    await fs.mkdir(path.join(tempRoot, 'jongno.go.kr'));

    const resolution = await resolveOutputDirForRun(tempRoot, 'jongno.go.kr', { updateExisting: true });

    assert.equal(resolution.outputLabel, 'jongno.go.kr');
    assert.equal(resolution.sequence, 0);
    assert.equal(resolution.outputDir, path.join(tempRoot, 'jongno.go.kr'));
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
