import path from 'path';
import fs from 'fs/promises';
import { init, parse as parseModuleImports } from 'es-module-lexer';
import { parse } from '@babel/parser';
import traverseModule from '@babel/traverse';
import generateModule from '@babel/generator';

import { resolveUrl, getRelativePath } from '../utils/url-utils.js';
import logger from '../utils/logger.js';

const traverse = traverseModule.default;
const generate = generateModule.default;

export default class JsProcessor {
  constructor(outputDir, baseUrl, urlMap) {
    this.outputDir = outputDir;
    this.baseUrl = baseUrl;
    this.urlMap = urlMap;
    this.report = {
      removed: [],
      kept: [],
      apiCalls: [],
      rewritten: [],
    };
  }

  async processAll() {
    logger.start('Starting JS processing');
    await init;

    const jsFiles = [];
    for (const [url, localPath] of this.urlMap) {
      if (localPath.endsWith('.js') || localPath.includes('/js/')) {
        jsFiles.push({ url, localPath });
      }
    }

    logger.update(`Analyzing ${jsFiles.length} JS files`);

    for (const { url, localPath } of jsFiles) {
      await this._processJsFile(url, localPath);
    }

    logger.succeed(
      `JS processing done: ${jsFiles.length} files, ${this.report.removed.length} removed, ` +
      `${this.report.apiCalls.length} API calls detected, ${this.report.rewritten.length} rewrites`,
    );

    return {
      removed: this.report.removed.length,
      kept: this.report.kept.length,
      apiCalls: this.report.apiCalls.length,
      rewritten: this.report.rewritten.length,
    };
  }

  async _processJsFile(url, localPath) {
    const absolutePath = path.join(this.outputDir, 'public', localPath);
    let content;

    try {
      content = await fs.readFile(absolutePath, 'utf-8');
    } catch {
      logger.debug(`Failed to read JS file: ${absolutePath}`);
      return;
    }

    if (this._isTrackingScript(url, content)) {
      try {
        await fs.unlink(absolutePath);
      } catch {
        // Ignore unlink failures for already-missing files.
      }
      this.report.removed.push(localPath);
      this.urlMap.delete(url);
      logger.debug(`Tracking script removed: ${localPath}`);
      return;
    }

    this.report.kept.push(localPath);
    this.report.apiCalls.push(...this._detectApiCalls(content, localPath));

    const rewritten = await this._rewriteJsModule(content, url, localPath);
    if (rewritten.changed) {
      await fs.writeFile(absolutePath, rewritten.code, 'utf-8');
      this.report.rewritten.push(localPath);
    }
  }

  async _rewriteJsModule(content, fileUrl, fileLocalPath) {
    let lexerImports = [];
    try {
      const [imports] = parseModuleImports(content);
      lexerImports = imports;
    } catch {
      lexerImports = [];
    }

    const parserPlugins = this._detectParserPlugins(content);
    let ast;
    try {
      ast = parse(content, {
        sourceType: 'unambiguous',
        allowReturnOutsideFunction: true,
        errorRecovery: true,
        plugins: parserPlugins,
      });
    } catch (error) {
      logger.debug(`AST parse failed for ${fileLocalPath}: ${error.message}`);
      return { changed: false, code: content };
    }

    let changed = false;
    const seenRewriteTargets = new Set();
    const rewriteLiteral = (node, usageType = 'asset') => {
      if (!node || typeof node.value !== 'string') return;
      const replacement = this._toLocalReference(node.value, fileUrl, fileLocalPath, usageType);
      if (!replacement || replacement === node.value) return;
      node.value = replacement;
      if (typeof node.extra?.raw === 'string') {
        node.extra.raw = JSON.stringify(replacement);
      }
      changed = true;
    };

    traverse(ast, {
      ImportDeclaration: (pathRef) => {
        rewriteLiteral(pathRef.node.source, 'module');
      },
      ExportAllDeclaration: (pathRef) => {
        rewriteLiteral(pathRef.node.source, 'module');
      },
      ExportNamedDeclaration: (pathRef) => {
        rewriteLiteral(pathRef.node.source, 'module');
      },
      ImportExpression: (pathRef) => {
        const source = pathRef.node.source;
        if (source?.type === 'StringLiteral') rewriteLiteral(source, 'module');
      },
      NewExpression: (pathRef) => {
        const calleeName = pathRef.node.callee?.name;
        if (calleeName === 'URL') {
          const [firstArg, secondArg] = pathRef.node.arguments;
          const usesImportMetaUrl = secondArg?.type === 'MemberExpression'
            && secondArg.object?.type === 'MetaProperty'
            && secondArg.object.meta?.name === 'import'
            && secondArg.object.property?.name === 'meta'
            && secondArg.property?.type === 'Identifier'
            && secondArg.property.name === 'url';
          if (firstArg?.type === 'StringLiteral' && usesImportMetaUrl) {
            rewriteLiteral(firstArg, 'asset');
          }
        }
        if ((calleeName === 'WebSocket' || calleeName === 'EventSource') && pathRef.node.arguments[0]?.type === 'StringLiteral') {
          const arg = pathRef.node.arguments[0];
          this._recordApiCall(calleeName.toLowerCase(), arg.value, fileLocalPath, arg.loc?.start?.line);
          rewriteLiteral(arg, 'runtime-endpoint');
        }
      },
      CallExpression: (pathRef) => {
        const callee = pathRef.node.callee;
        if (callee?.type === 'Identifier' && callee.name === 'fetch' && pathRef.node.arguments[0]?.type === 'StringLiteral') {
          const arg = pathRef.node.arguments[0];
          this._recordApiCall('fetch', arg.value, fileLocalPath, arg.loc?.start?.line);
          rewriteLiteral(arg, 'runtime-endpoint');
          return;
        }

        if (
          callee?.type === 'MemberExpression'
          && callee.object?.type === 'Identifier'
          && callee.object.name === 'axios'
          && callee.property?.type === 'Identifier'
          && pathRef.node.arguments[0]?.type === 'StringLiteral'
        ) {
          const arg = pathRef.node.arguments[0];
          this._recordApiCall('axios', arg.value, fileLocalPath, arg.loc?.start?.line);
          rewriteLiteral(arg, 'runtime-endpoint');
        }
      },
      StringLiteral: (pathRef) => {
        const parentType = pathRef.parent?.type;
        if (parentType === 'ImportDeclaration' || parentType === 'ExportAllDeclaration' || parentType === 'ExportNamedDeclaration') {
          return;
        }
        if (pathRef.parent?.type === 'CallExpression' || pathRef.parent?.type === 'NewExpression') {
          return;
        }
        if (!this._looksLikeStaticReference(pathRef.node.value)) return;
        const key = `${pathRef.node.start}:${pathRef.node.value}`;
        if (seenRewriteTargets.has(key)) return;
        seenRewriteTargets.add(key);
        rewriteLiteral(pathRef.node, 'asset');
      },
    });

    for (const importInfo of lexerImports) {
      if (importInfo.n > 0) {
        // Touching lexer output keeps the fast pre-scan in the pipeline for future diagnostics.
      }
    }

    if (!changed) {
      return { changed: false, code: content };
    }

    const output = generate(ast, {
      comments: true,
      retainLines: false,
      compact: false,
      jsescOption: { minimal: true },
    }, content);

    return {
      changed: true,
      code: output.code,
    };
  }

  _toLocalReference(rawValue, fileUrl, fileLocalPath, usageType) {
    if (!rawValue || rawValue.startsWith('data:') || rawValue.startsWith('blob:') || rawValue.startsWith('javascript:')) {
      return null;
    }

    const absoluteUrl = resolveUrl(rawValue, fileUrl);
    const mapped = this.urlMap.get(absoluteUrl);
    if (!mapped) return null;

    if (usageType === 'runtime-endpoint') {
      return this._toRuntimeEndpoint(mapped);
    }

    return getRelativePath(fileLocalPath, mapped);
  }

  _toRuntimeEndpoint(mappedPath) {
    const normalized = mappedPath.replace(/\\/g, '/');
    if (normalized.startsWith('views/')) {
      return `/${normalized.replace(/^views\//, '').replace(/\.html$/, '') || ''}`;
    }
    return `/public/${normalized}`;
  }

  _looksLikeStaticReference(value) {
    return /^(?:\/|\.\/|\.\.\/|https?:\/\/|\/\/)/i.test(value)
      && /\.(?:css|js|mjs|cjs|png|jpg|jpeg|gif|svg|webp|avif|ico|woff2?|ttf|otf|mp4|webm|mp3|json)(?:[?#].*)?$/i.test(value);
  }

  _recordApiCall(type, url, file, line) {
    this.report.apiCalls.push({
      type,
      url,
      file,
      line: line || null,
      raw: url,
    });
  }

  _detectParserPlugins(content) {
    const plugins = [
      'jsx',
      'importMeta',
      'dynamicImport',
      'classProperties',
      'classPrivateProperties',
      'classPrivateMethods',
      'optionalChaining',
      'nullishCoalescingOperator',
      'topLevelAwait',
      'objectRestSpread',
    ];

    if (/\binterface\b|\btype\b|:\s*[A-Z_a-z][\w<>, \[\]\|&?:]*/.test(content)) {
      plugins.push('typescript');
    }

    return plugins;
  }

  _isTrackingScript(url, content) {
    const trackingUrls = [
      'google-analytics.com',
      'googletagmanager.com',
      'googlesyndication.com',
      'google-analytics',
      'facebook.net',
      'fbevents.js',
      'connect.facebook',
      'hotjar.com',
      'clarity.ms',
      'segment.com',
      'segment.io',
      'mixpanel.com',
      'amplitude.com',
      'heap-analytics',
      'intercom.io',
      'crisp.chat',
      'tawk.to',
      'livechatinc.com',
      'doubleclick.net',
      'adservice.google',
      'analytics.js',
      'gtag/js',
      'gtm.js',
    ];

    const urlLower = url.toLowerCase();
    if (trackingUrls.some((item) => urlLower.includes(item))) {
      return true;
    }

    if (content.length < 50000) {
      const trackingPatterns = [
        /\bgoogle[_-]?analytics\b/i,
        /\b_gaq\.push\b/,
        /\bgtag\s*\(/,
        /\bfbq\s*\(/,
        /\bhotjar\b/i,
        /\bclarity\b.{0,100}?\bmicrosoft\b/i,
        /\bmixpanel\.track\b/,
        /\bamplitude\.getInstance\b/,
      ];

      const matchCount = trackingPatterns.filter((pattern) => pattern.test(content)).length;
      if (matchCount >= 3) return true;

      if (content.length < 5000 && matchCount >= 1) {
        const uiPatterns = [
          /document\.(getElementById|querySelector|createElement)/,
          /addEventListener\s*\(/,
          /\.className\b/,
          /\.style\b/,
          /\.innerHTML\b/,
          /\.classList\b/,
        ];
        const hasUiCode = uiPatterns.some((pattern) => pattern.test(content));
        if (!hasUiCode) return true;
      }
    }

    return false;
  }

  _detectApiCalls(content, filePath) {
    const apiCalls = [];
    const patterns = [
      {
        regex: /\bfetch\s*\(\s*(['"`])([^'"`\r\n]+)\1/g,
        type: 'fetch',
        extract: (match) => ({ url: match[2] }),
      },
      {
        regex: /\.open\s*\(\s*['"](\w+)['"]\s*,\s*['"]([^'"\r\n]+)['"]/g,
        type: 'xhr',
        extract: (match) => ({ method: match[1], url: match[2] }),
      },
      {
        regex: /axios\.(get|post|put|delete|patch|head|options)\s*\(\s*['"`]([^'"`\r\n]+)['"`]/g,
        type: 'axios',
        extract: (match) => ({ method: match[1].toUpperCase(), url: match[2] }),
      },
      {
        regex: /new\s+WebSocket\s*\(\s*['"`]([^'"`\r\n]+)['"`]/g,
        type: 'websocket',
        extract: (match) => ({ url: match[1] }),
      },
      {
        regex: /new\s+EventSource\s*\(\s*['"`]([^'"`\r\n]+)['"`]/g,
        type: 'sse',
        extract: (match) => ({ url: match[1] }),
      },
    ];

    for (const { regex, type, extract } of patterns) {
      let match;
      regex.lastIndex = 0;
      while ((match = regex.exec(content)) !== null) {
        const extracted = extract(match);
        if (this._isStaticAssetUrl(extracted.url || '')) continue;
        apiCalls.push({
          type,
          ...extracted,
          file: filePath,
          line: this._lineFromIndex(content, match.index),
          raw: match[0].slice(0, 200),
        });
      }
    }

    return apiCalls;
  }

  _isStaticAssetUrl(url) {
    const staticExts = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',
      '.woff', '.woff2', '.ttf', '.eot', '.ico', '.map'];
    const lower = url.toLowerCase();
    return staticExts.some((ext) => lower.endsWith(ext));
  }

  _lineFromIndex(content, index) {
    let line = 1;
    for (let i = 0; i < index && i < content.length; i += 1) {
      if (content[i] === '\n') line += 1;
    }
    return line;
  }

  getReport() {
    return this.report;
  }
}
