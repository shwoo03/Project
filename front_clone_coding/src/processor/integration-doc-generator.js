import path from 'path';
import { ensureDir, saveFile } from '../utils/file-utils.js';

export default class IntegrationDocGenerator {
  constructor(outputDir) {
    this.outputDir = outputDir;
  }

  async generate({ pages, requests, websocketEvents }) {
    const docsDir = path.join(this.outputDir, 'docs', 'integration');
    await ensureDir(docsDir);

    const formsActions = [];
    const frontendBackendMap = [];
    const authPages = [];

    for (const page of pages) {
      const pageUrl = page.finalUrl || page.url;
      const hasPasswordForm = (page.forms || []).some((form) => form.hasPassword);
      if (page.isLogin || hasPasswordForm) {
        authPages.push({
          pageUrl,
          savedPath: page.savedPath,
          loginDetected: page.isLogin,
          hasPasswordForm,
        });
      }

      for (const form of page.forms || []) {
        const entry = {
          pageUrl,
          savedPath: page.savedPath,
          selectorHint: form.selectorHint,
          eventType: 'submit',
          method: form.method,
          action: form.resolvedAction || form.action || '',
          fields: form.fields,
          authHints: {
            hasPassword: form.hasPassword,
          },
          confidence: form.resolvedAction ? 'high' : 'medium',
          captureSource: 'dom-form-analysis',
        };
        formsActions.push(entry);
        frontendBackendMap.push({
          ...entry,
          responseContentType: null,
          requestPayloadShape: form.fields.map((field) => ({ name: field.name, type: field.type || field.tag })),
        });
      }
    }

    for (const req of requests) {
      frontendBackendMap.push({
        pageUrl: req.pageUrl || '',
        savedPath: this._findSavedPath(pages, req.pageUrl),
        selectorHint: null,
        eventType: req.resourceType || 'fetch',
        method: req.method,
        action: req.url,
        requestPayloadShape: req.requestBody,
        responseContentType: req.responseMimeType,
        authHints: req.authHints,
        confidence: req.pageUrl ? 'medium' : 'low',
        captureSource: 'network-capture',
      });
    }

    for (const ws of websocketEvents) {
      frontendBackendMap.push({
        pageUrl: ws.pageUrl || '',
        savedPath: this._findSavedPath(pages, ws.pageUrl),
        selectorHint: null,
        eventType: `websocket:${ws.type}`,
        method: 'WS',
        action: ws.url,
        requestPayloadShape: ws.payload || null,
        responseContentType: 'websocket',
        authHints: null,
        confidence: 'low',
        captureSource: 'websocket-capture',
      });
    }

    await saveFile(
      path.join(docsDir, 'forms-actions.json'),
      JSON.stringify(formsActions, null, 2),
    );
    await saveFile(
      path.join(docsDir, 'frontend-backend-map.json'),
      JSON.stringify(frontendBackendMap, null, 2),
    );
    await saveFile(
      path.join(docsDir, 'auth-and-guards.md'),
      this._buildAuthMarkdown(authPages, requests),
    );
  }

  _findSavedPath(pages, pageUrl) {
    const match = pages.find((page) => (page.finalUrl || page.url) === pageUrl);
    return match?.savedPath || null;
  }

  _buildAuthMarkdown(authPages, requests) {
    const lines = ['# Auth And Guards', ''];

    if (authPages.length === 0) {
      lines.push('No login-gated pages were detected during the crawl.');
    } else {
      lines.push('## Detected Guarded Pages');
      for (const page of authPages) {
        lines.push(`- ${page.pageUrl} (${page.savedPath || 'unsaved'}): loginDetected=${page.loginDetected}, hasPasswordForm=${page.hasPasswordForm}`);
      }
    }

    const authRequests = requests.filter((req) =>
      req.authHints?.hasAuthorizationHeader || req.authHints?.hasCookieHeader || req.authHints?.hasCsrfHeader,
    );

    lines.push('');
    lines.push('## Captured Auth Hints');
    if (authRequests.length === 0) {
      lines.push('- No explicit auth headers or cookies were captured on same-domain API requests.');
    } else {
      for (const req of authRequests) {
        lines.push(`- ${req.method} ${req.url}: ${JSON.stringify(req.authHints)}`);
      }
    }

    return lines.join('\n');
  }
}
