import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import * as cheerio from 'cheerio';

import CssProcessor from '../src/processor/css-processor.js';
import HtmlProcessor from '../src/processor/html-processor.js';
import JsProcessor from '../src/processor/js-processor.js';
import { ensureDir, saveFile } from '../src/utils/file-utils.js';

test('CssProcessor rewrites imports and asset URLs with PostCSS', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-css-'));
  try {
    await ensureDir(path.join(tempRoot, 'public', 'css'));
    await saveFile(path.join(tempRoot, 'public', 'css', 'main.css'), [
      '@import "./theme.css";',
      '.hero { background-image: url("/img/bg.png"); }',
      '.banner { background-image: image-set(url("/img/bg.png") 1x, url("/img/bg@2x.png") 2x); }',
    ].join('\n'));
    await saveFile(path.join(tempRoot, 'public', 'css', 'theme.css'), '.theme { background:url("../img/icon.svg"); }');

    const urlMap = new Map([
      ['https://example.com/assets/main.css', 'css/main.css'],
      ['https://example.com/assets/theme.css', 'css/theme.css'],
      ['https://example.com/img/bg.png', 'img/bg.png'],
      ['https://example.com/img/bg@2x.png', 'img/bg@2x.png'],
      ['https://example.com/img/icon.svg', 'img/icon.svg'],
    ]);

    const processor = new CssProcessor(tempRoot, 'https://example.com', urlMap, {
      getLatestResponse() {
        return null;
      },
    });

    await processor.processAll();

    const mainCss = await fs.readFile(path.join(tempRoot, 'public', 'css', 'main.css'), 'utf-8');
    const themeCss = await fs.readFile(path.join(tempRoot, 'public', 'css', 'theme.css'), 'utf-8');

    assert.match(mainCss, /@import "\.\/theme\.css"|@import url\("\.\/theme\.css"\)/);
    assert.match(mainCss, /url\("\.\.\/img\/bg\.png"\)|url\(\.\.\/img\/bg\.png\)/);
    assert.match(mainCss, /bg@2x\.png/);
    assert.match(themeCss, /url\("\.\.\/img\/icon\.svg"\)|url\(\.\.\/img\/icon\.svg\)/);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

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

test('HtmlProcessor disables unmapped navigation targets while preserving safe protocols', () => {
  const html = [
    '<html><head></head><body>',
    '<a id="local" href="/dashboard">Dashboard</a>',
    '<a id="external" href="https://policies.google.com/privacy" target="_blank">Privacy</a>',
    '<area id="support-map" href="https://help.example.com/support" shape="rect" coords="0,0,10,10">',
    '<a id="hash" href="#faq">FAQ</a>',
    '<a id="mail" href="mailto:test@example.com">Mail</a>',
    '<form id="signup" action="https://example.com/signup" method="post"></form>',
    '</body></html>',
  ].join('');

  const urlMap = new Map([
    ['https://example.com/dashboard', 'dashboard.html'],
  ]);

  const processor = new HtmlProcessor('https://example.com');
  const output = processor.process(html, urlMap, 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#local').attr('href'), './dashboard.html');
  assert.equal($('#external').attr('href'), '#');
  assert.equal($('#external').attr('data-disabled-link'), 'true');
  assert.equal($('#external').attr('data-disabled-reason'), 'unmapped-target');
  assert.equal($('#external').attr('aria-disabled'), 'true');
  assert.equal($('#external').attr('onclick'), 'return false;');
  assert.equal($('#external').attr('target'), undefined);
  assert.equal($('#support-map').attr('href'), '#');
  assert.equal($('#support-map').attr('data-disabled-link'), 'true');
  assert.equal($('#hash').attr('href'), '#faq');
  assert.equal($('#mail').attr('href'), 'mailto:test@example.com');
  assert.equal($('#signup').attr('action'), '#');
  assert.equal($('#signup').attr('data-disabled-link'), 'true');
  assert.equal($('#signup').attr('onsubmit'), 'return false;');
});
