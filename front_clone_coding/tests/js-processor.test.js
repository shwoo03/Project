import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';

import JsProcessor from '../src/processor/js-processor.js';
import { ensureDir, saveFile } from '../src/utils/file-utils.js';

test('JsProcessor rewrites imports and runtime URLs using AST transforms', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-js-'));
  try {
    await ensureDir(path.join(tempRoot, 'public', 'js'));
    await saveFile(path.join(tempRoot, 'public', 'js', 'app.js'), [
      'import helper from "/js/helper.js";',
      'const img = new URL("/img/logo.png", import.meta.url);',
      'fetch("https://example.com/dashboard");',
      'console.log(img.href, helper);',
    ].join('\n'));

    const urlMap = new Map([
      ['https://example.com/js/app.js', 'js/app.js'],
      ['https://example.com/js/helper.js', 'js/helper.js'],
      ['https://example.com/img/logo.png', 'img/logo.png'],
      ['https://example.com/dashboard', 'views/dashboard.html'],
    ]);

    const processor = new JsProcessor(tempRoot, 'https://example.com', urlMap);
    await processor.processAll();

    const output = await fs.readFile(path.join(tempRoot, 'public', 'js', 'app.js'), 'utf-8');
    assert.match(output, /import helper from "\.\/helper\.js"/);
    assert.match(output, /new URL\("\.\.\/img\/logo\.png", import\.meta\.url\)/);
    assert.match(output, /fetch\("\/dashboard"\)|fetch\("\/dashboard"\s*\)/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('JsProcessor statically rewrites non-critical runtime endpoints but keeps render-critical ones', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-js-runtime-filter-'));
  try {
    await ensureDir(path.join(tempRoot, 'public', 'js'));
    await saveFile(path.join(tempRoot, 'public', 'js', 'runtime.js'), [
      'fetch("https://logs.netflix.com/log/www/cl/2");',
      'const xhr = new XMLHttpRequest(); xhr.open("GET", "https://www.netflix.com/log/www/1");',
      'const xhr2 = new XMLHttpRequest(); xhr2.open("GET", "https://logs.netflix.com/log/" + "wwwhead" + "/cl/2");',
      'fetch(`https://www.netflix.com/log/template`);',
      'navigator.sendBeacon("https://www.google.com/recaptcha/api.js", "{}");',
      'new Image().src = "https://www.facebook.com/tr?id=123";',
      'new EventSource("https://analytics.thirdparty.net/stream");',
      'new WebSocket("wss://tracking.thirdparty.net/socket");',
      'fetch("https://example.com/bootstrap");',
    ].join('\n'));

    const urlMap = new Map([
      ['https://example.com/js/runtime.js', 'js/runtime.js'],
      ['https://example.com/bootstrap', 'views/bootstrap.html'],
    ]);

    const processor = new JsProcessor(tempRoot, 'https://example.com', urlMap);
    await processor.processAll();

    const output = await fs.readFile(path.join(tempRoot, 'public', 'js', 'runtime.js'), 'utf-8');
    assert.match(output, /fetch\("\/__front_clone_noop__"\)/);
    assert.match(output, /open\("GET", "\/__front_clone_noop__"\)/);
    assert.equal(output.includes('logs.netflix.com/log/wwwhead/cl/2'), false);
    assert.equal(output.includes('https://www.netflix.com/log/template'), false);
    assert.match(output, /sendBeacon\("\/__front_clone_noop__"/);
    assert.match(output, /"data:,"/);
    assert.match(output, /new EventSource\("\/__front_clone_noop__"\)/);
    assert.match(output, /readyState: 3/);
    assert.match(output, /fetch\("\/bootstrap"\)/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('JsProcessor rewrites render-critical runtime endpoints to local api paths', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-js-runtime-api-'));
  try {
    await ensureDir(path.join(tempRoot, 'public', 'js'));
    await saveFile(path.join(tempRoot, 'public', 'js', 'runtime.js'), [
      'fetch("https://example.com/bootstrap");',
      'const xhr = new XMLHttpRequest(); xhr.open("GET", "/widget-data");',
    ].join('\n'));

    const urlMap = new Map([
      ['https://example.com/js/runtime.js', 'js/runtime.js'],
    ]);

    const processor = new JsProcessor(tempRoot, 'https://example.com', urlMap, {
      renderCriticalRuntimeMap: new Map([
        ['https://example.com/bootstrap', '/api/bootstrap'],
        ['https://example.com/widget-data', '/api/widget-data'],
      ]),
    });
    await processor.processAll();

    const output = await fs.readFile(path.join(tempRoot, 'public', 'js', 'runtime.js'), 'utf-8');
    assert.match(output, /fetch\("\/api\/bootstrap"\)/);
    assert.match(output, /open\("GET", "\/api\/widget-data"\)/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
