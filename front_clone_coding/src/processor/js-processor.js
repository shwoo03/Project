import path from 'path';
import fs from 'fs/promises';
import logger from '../utils/logger.js';

/**
 * JS ??
 * ???JavaScript ????, / ???,
 * API ? ??? ????
 */
export default class JsProcessor {
  /**
   * @param {string} outputDir -  ??
   * @param {string} baseUrl - ? ???URL
   * @param {Map<string, string>} urlMap - URL ??  
   */
  constructor(outputDir, baseUrl, urlMap) {
    this.outputDir = outputDir;
    this.baseUrl = baseUrl;
    this.urlMap = urlMap;

    /** @type {{ removed: string[], kept: string[], apiCalls: object[] }} */
    this.report = {
      removed: [],
      kept: [],
      apiCalls: [],
    };
  }

  /**
   *  JS ? 
   * @returns {{ removed: number, kept: number, apiCalls: number }}
   */
  async processAll() {
    logger.start('Starting JS processing');

    const jsFiles = [];
    for (const [url, localPath] of this.urlMap) {
      if (localPath.endsWith('.js') || localPath.includes('assets/js/')) {
        jsFiles.push({ url, localPath });
      }
    }

    logger.update(`Analyzing ${jsFiles.length} JS files`);

    for (const { url, localPath } of jsFiles) {
      await this._processJsFile(url, localPath);
    }

    logger.succeed(
      `JS processing done: ${jsFiles.length} files, ${this.report.removed.length} removed, ` +
      `${this.report.apiCalls.length} API calls detected`
    );

    return {
      removed: this.report.removed.length,
      kept: this.report.kept.length,
      apiCalls: this.report.apiCalls.length,
    };
  }

  /**
   *  JS ? 
   */
  async _processJsFile(url, localPath) {
    const absolutePath = path.join(this.outputDir, 'public', localPath);
    let content;

    try {
      content = await fs.readFile(absolutePath, 'utf-8');
    } catch {
      logger.debug(`Failed to read JS file: ${absolutePath}`);
      return;
    }

    // 1. / ? ? ??? ???? ??
    if (this._isTrackingScript(url, content)) {
      try {
        await fs.unlink(absolutePath);
      } catch { /* ignore */ }
      this.report.removed.push(localPath);
      // urlMap? ? (HTML??? ?)
      this.urlMap.delete(url);
      logger.debug(`Tracking script removed: ${localPath}`);
      return;
    }

    this.report.kept.push(localPath);

    // 2. API ? ? ? (?  - ???)
    const apiCalls = this._detectApiCalls(content, localPath);
    this.report.apiCalls.push(...apiCalls);

    // 3. API ???  ? (?? ?  ????
    if (apiCalls.length > 0) {
      const markedContent = this._addApiMarkers(content, apiCalls);
      await fs.writeFile(absolutePath, markedContent, 'utf-8');
    }
  }

  /**
   * / ? ?
   * @param {string} url - ? URL
   * @param {string} content - ? ?
   * @returns {boolean}
   */
  _isTrackingScript(url, content) {
    // URL  ?
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
    if (trackingUrls.some(t => urlLower.includes(t))) {
      return true;
    }

    // ?  ? (?? ??  ?????)
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

      const matchCount = trackingPatterns.filter(p => p.test(content)).length;
      // 3???? ????  ???
      if (matchCount >= 3) return true;

      // ? ?    ??
      if (content.length < 5000 && matchCount >= 1) {
        // UI ?? ?? ?
        const uiPatterns = [
          /document\.(getElementById|querySelector|createElement)/,
          /addEventListener\s*\(/,
          /\.className\b/,
          /\.style\b/,
          /\.innerHTML\b/,
          /\.classList\b/,
        ];
        const hasUiCode = uiPatterns.some(p => p.test(content));
        if (!hasUiCode) return true;
      }
    }

    return false;
  }

  /**
   * API ? ? ? (? )
   * @param {string} content - JS ?
   * @param {string} filePath - ?  (?)
   * @returns {object[]} ???API ? 
   */
  _detectApiCalls(content, filePath) {
    const apiCalls = [];
    const lines = content.split('\n');

    const patterns = [
      // fetch API
      {
        regex: /\bfetch\s*\(\s*(['"`])([^'"`\r\n]+)\1/g,
        type: 'fetch',
        extract: (m) => ({ url: m[2] }),
      },
      {
        regex: /\bfetch\s*\(\s*`([^`\r\n]+)`/g,
        type: 'fetch-template',
        extract: (m) => ({ url: m[1] }),
      },
      // XMLHttpRequest
      {
        regex: /\.open\s*\(\s*['"](\w+)['"]\s*,\s*['"]([^'"\r\n]+)['"]/g,
        type: 'xhr',
        extract: (m) => ({ method: m[1], url: m[2] }),
      },
      // axios
      {
        regex: /axios\.(get|post|put|delete|patch|head|options)\s*\(\s*['"`]([^'"`\r\n]+)['"`]/g,
        type: 'axios',
        extract: (m) => ({ method: m[1].toUpperCase(), url: m[2] }),
      },
      {
        regex: /axios\s*\(\s*\{[^}]{0,200}url\s*:\s*['"`]([^'"`\r\n]+)['"`]/g,
        type: 'axios-config',
        extract: (m) => ({ url: m[1] }),
      },
      // jQuery AJAX
      {
        regex: /\$\.(ajax|get|post|getJSON)\s*\(\s*['"`]([^'"`\r\n]+)['"`]/g,
        type: 'jquery',
        extract: (m) => ({ method: m[1], url: m[2] }),
      },
      {
        regex: /\$\.ajax\s*\(\s*\{[^}]{0,200}url\s*:\s*['"`]([^'"`\r\n]+)['"`]/g,
        type: 'jquery-config',
        extract: (m) => ({ url: m[1] }),
      },
      // WebSocket
      {
        regex: /new\s+WebSocket\s*\(\s*['"`]([^'"`\r\n]+)['"`]/g,
        type: 'websocket',
        extract: (m) => ({ url: m[1] }),
      },
      // EventSource (SSE)
      {
        regex: /new\s+EventSource\s*\(\s*['"`]([^'"`\r\n]+)['"`]/g,
        type: 'sse',
        extract: (m) => ({ url: m[1] }),
      },
    ];

    for (const { regex, type, extract } of patterns) {
      let match;
      regex.lastIndex = 0;
      while ((match = regex.exec(content)) !== null) {
        const extracted = extract(match);
        // ?? URL (? ???API)???
        const urlStr = extracted.url || '';
        // ? ? URL? ?
        if (this._isStaticAssetUrl(urlStr)) continue;

        // ?  
        const pos = match.index;
        let line = 1;
        for (let i = 0; i < pos && i < content.length; i++) {
          if (content[i] === '\n') line++;
        }

        apiCalls.push({
          type,
          ...extracted,
          file: filePath,
          line,
          raw: match[0].substring(0, 200),
        });
      }
    }

    return apiCalls;
  }

  /**
   * ? ? URL?? ?
   * @param {string} url
   * @returns {boolean}
   */
  _isStaticAssetUrl(url) {
    const staticExts = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',
      '.woff', '.woff2', '.ttf', '.eot', '.ico', '.map'];
    const lower = url.toLowerCase();
    return staticExts.some(ext => lower.endsWith(ext));
  }

  /**
   * API ???  ?
   * @param {string} content - ? JS
   * @param {object[]} apiCalls - ???API ?
   * @returns {string}  ???JS
   */
  _addApiMarkers(content, apiCalls) {
    // ?  ?? ?? ? (??????? ??? ???
    const sorted = [...apiCalls].sort((a, b) => b.line - a.line);
    const lines = content.split('\n');

    for (const call of sorted) {
      const lineIdx = call.line - 1;
      if (lineIdx >= 0 && lineIdx < lines.length) {
        const marker = `/* [FRONT-CLONE] API CALL: ${call.type} ??${call.url || 'dynamic'} */`;
        lines[lineIdx] = marker + '\n' + lines[lineIdx];
      }
    }

    return lines.join('\n');
  }

  /**
   *  ??
   * @returns {object}
   */
  getReport() {
    return this.report;
  }
}

