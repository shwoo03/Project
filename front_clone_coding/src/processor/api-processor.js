import crypto from 'crypto';
import path from 'path';

import { ensureDir, saveFile } from '../utils/file-utils.js';
import logger from '../utils/logger.js';
import { getDomainRoot, isInDomainScope } from '../utils/url-utils.js';

const STATIC_EXTENSIONS = [
  '.css',
  '.js',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.svg',
  '.webp',
  '.woff',
  '.woff2',
  '.ttf',
  '.ico',
  '.map',
];

export default class ApiProcessor {
  constructor(outputDir, targetUrl, domainScope = 'registrable-domain') {
    this.outputDir = outputDir;
    this.targetUrl = targetUrl;
    this.domainScope = domainScope;
    this.domainRoot = getDomainRoot(targetUrl, domainScope);
  }

  async generateArtifacts(xhrRequests = [], websocketEvents = []) {
    await ensureDir(path.join(this.outputDir, 'docs', 'api'));
    await ensureDir(path.join(this.outputDir, 'mocks', 'api'));

    const filteredRequests = xhrRequests
      .filter((req) => this._isSameDomainApi(req.url))
      .map((req) => this._normalizeRequest(req));

    const openApiSpec = this._buildOpenApi(filteredRequests);
    const graphqlReport = this._buildGraphqlReport(filteredRequests);
    const mockData = this._buildMockData(filteredRequests);
    const apiSummary = this._buildApiSummary(filteredRequests);

    await saveFile(
      path.join(this.outputDir, 'docs', 'api', 'openapi.json'),
      JSON.stringify(openApiSpec, null, 2),
    );
    await saveFile(
      path.join(this.outputDir, 'docs', 'api', 'request-log.json'),
      JSON.stringify(filteredRequests, null, 2),
    );
    await saveFile(
      path.join(this.outputDir, 'docs', 'api', 'websocket-log.json'),
      JSON.stringify(websocketEvents, null, 2),
    );
    await saveFile(
      path.join(this.outputDir, 'mocks', 'api', 'mock-data.json'),
      JSON.stringify(mockData, null, 2),
    );

    if (graphqlReport.operations.length > 0) {
      await saveFile(
        path.join(this.outputDir, 'docs', 'api', 'graphql-report.json'),
        JSON.stringify(graphqlReport, null, 2),
      );
    }

    logger.success('API docs and mock artifacts generated');
    return { apiSummary, filteredRequests, graphqlReport };
  }

  _isSameDomainApi(url) {
    if (!isInDomainScope(url, this.targetUrl, this.domainScope)) return false;
    try {
      const pathname = new URL(url).pathname.toLowerCase();
      return !STATIC_EXTENSIONS.some((ext) => pathname.endsWith(ext));
    } catch {
      return false;
    }
  }

  _normalizeRequest(req) {
    const url = new URL(req.url);
    const requestBody = this.safeParseJson(req.postData);
    const responseBody = this.safeParseJson(req.responseBody);
    const queryParams = [...url.searchParams.entries()].map(([name, value]) => ({ name, value }));

    return {
      key: req.key || `${req.method || 'GET'} ${req.url}`,
      method: (req.method || 'GET').toUpperCase(),
      url: req.url,
      pageUrl: req.pageUrl || '',
      pathname: url.pathname,
      search: url.search,
      queryParams,
      resourceType: req.resourceType || 'fetch',
      responseStatus: req.responseStatus || 200,
      responseMimeType: req.responseMimeType || 'application/json',
      requestBody,
      requestBodyHash: req.requestBodyHash || this._hashValue(requestBody),
      responseBody,
      responseBodyStored: req.responseBodyStored !== false,
      authHints: this._collectAuthHints(req.headers || {}),
      headers: this._pickInterestingHeaders(req.headers || {}),
    };
  }

  _buildOpenApi(requests) {
    const parsedUrl = new URL(this.targetUrl);
    const host = parsedUrl.host;
    const protocol = parsedUrl.protocol.replace(':', '');
    const grouped = this._groupRequests(requests);

    const openApiSpec = {
      openapi: '3.0.0',
      info: {
        title: `Captured API for ${this.domainRoot}`,
        description: `Generated from ${this.targetUrl}`,
        version: '1.0.0',
      },
      servers: [
        { url: `${protocol}://${host}`, description: 'Original server' },
        { url: 'http://localhost:3000', description: 'Generated backend scaffold' },
      ],
      paths: {},
    };

    for (const [groupKey, variants] of grouped) {
      const [method, pathname] = groupKey.split(' ');
      if (!openApiSpec.paths[pathname]) {
        openApiSpec.paths[pathname] = {};
      }

      const parameterMap = new Map();
      for (const variant of variants) {
        for (const param of variant.queryParams) {
          if (!parameterMap.has(param.name)) {
            parameterMap.set(param.name, new Set());
          }
          parameterMap.get(param.name).add(param.value);
        }
      }

      const responses = {};
      for (const variant of variants) {
        const statusKey = String(variant.responseStatus || 200);
        if (!responses[statusKey]) {
          responses[statusKey] = {
            description: 'Captured response',
          };
        }

        if (variant.responseBody !== null && variant.responseBody !== undefined) {
          responses[statusKey].content = {
            [variant.responseMimeType || 'application/json']: {
              schema: { type: this._inferSchemaType(variant.responseBody) },
              example: variant.responseBody,
            },
          };
        }
      }

      const firstVariant = variants[0];
      const operation = {
        summary: `Captured ${method} ${pathname}`,
        responses,
        'x-captured-variants': variants.map((variant) => ({
          search: variant.search,
          requestBodyHash: variant.requestBodyHash,
          responseStatus: variant.responseStatus,
          pageUrl: variant.pageUrl,
        })),
      };

      if (parameterMap.size > 0) {
        operation.parameters = [...parameterMap.entries()].map(([name, values]) => ({
          name,
          in: 'query',
          schema: { type: 'string' },
          examples: [...values].slice(0, 5),
        }));
      }

      if (['POST', 'PUT', 'PATCH'].includes(method)) {
        const bodyExample = variants.find((variant) => variant.requestBody !== null && variant.requestBody !== undefined);
        if (bodyExample) {
          operation.requestBody = {
            content: {
              'application/json': {
                schema: { type: this._inferSchemaType(bodyExample.requestBody) },
                example: bodyExample.requestBody,
              },
            },
          };
        }
      }

      const authHints = variants.find((variant) => Object.values(variant.authHints).some(Boolean))?.authHints;
      if (authHints) {
        operation['x-auth-hints'] = authHints;
      }

      openApiSpec.paths[pathname][method.toLowerCase()] = operation;
    }

    return openApiSpec;
  }

  _buildMockData(requests) {
    const grouped = this._groupRequests(requests);
    const mockData = {};

    for (const [groupKey, variants] of grouped) {
      const [method, pathname] = groupKey.split(' ');
      if (!mockData[pathname]) mockData[pathname] = {};

      const normalizedVariants = variants.map((variant) => ({
        match: {
          search: variant.search,
          query: Object.fromEntries(variant.queryParams.map((param) => [param.name, param.value])),
          bodyHash: variant.requestBodyHash,
        },
        response: {
          status: variant.responseStatus || 200,
          mimeType: variant.responseMimeType || 'application/json',
          body: variant.responseBody,
        },
        pageUrl: variant.pageUrl,
      }));

      mockData[pathname][method] = {
        default: normalizedVariants[0]?.response || {
          status: 200,
          mimeType: 'application/json',
          body: {},
        },
        variants: normalizedVariants,
      };
    }

    return mockData;
  }

  _buildGraphqlReport(requests) {
    const grouped = new Map();

    for (const req of requests) {
      const pathname = req.pathname.toLowerCase();
      const requestBody = req.requestBody;
      const looksLikeGraphql =
        pathname.includes('graphql') ||
        (requestBody && typeof requestBody === 'object' && ('query' in requestBody || 'operationName' in requestBody));

      if (!looksLikeGraphql) continue;

      const operationName = requestBody?.operationName || 'anonymous';
      const current = grouped.get(operationName) || {
        operationName,
        hits: 0,
        urls: new Set(),
        pageUrls: new Set(),
        queryPreview: typeof requestBody?.query === 'string' ? requestBody.query.slice(0, 300) : null,
      };

      current.hits += 1;
      current.urls.add(req.url);
      if (req.pageUrl) current.pageUrls.add(req.pageUrl);
      grouped.set(operationName, current);
    }

    return {
      operations: [...grouped.values()].map((entry) => ({
        operationName: entry.operationName,
        hits: entry.hits,
        urls: [...entry.urls],
        pageUrls: [...entry.pageUrls],
        queryPreview: entry.queryPreview,
      })),
    };
  }

  _buildApiSummary(requests) {
    const routeGroups = {};
    const grouped = this._groupRequests(requests);

    for (const [groupKey, variants] of grouped) {
      const [, pathname] = groupKey.split(' ');
      const group = pathname.split('/').filter(Boolean)[0] || 'root';
      if (!routeGroups[group]) routeGroups[group] = [];

      routeGroups[group].push({
        method: variants[0].method,
        pathname,
        responseMimeType: variants[0].responseMimeType,
        variants: variants.length,
      });
    }

    return {
      totalRequests: requests.length,
      uniqueEndpoints: grouped.size,
      routeGroups,
    };
  }

  _groupRequests(requests) {
    const grouped = new Map();

    for (const req of requests) {
      const groupKey = `${req.method} ${req.pathname}`;
      if (!grouped.has(groupKey)) {
        grouped.set(groupKey, []);
      }

      const variants = grouped.get(groupKey);
      const dedupeKey = `${req.search} ${req.requestBodyHash}`;
      if (!variants.some((variant) => `${variant.search} ${variant.requestBodyHash}` === dedupeKey)) {
        variants.push(req);
      }
    }

    return grouped;
  }

  _collectAuthHints(headers) {
    const lower = Object.fromEntries(Object.entries(headers).map(([key, value]) => [key.toLowerCase(), value]));
    return {
      hasAuthorizationHeader: Boolean(lower.authorization),
      hasCookieHeader: Boolean(lower.cookie),
      hasCsrfHeader: Boolean(lower['x-csrf-token'] || lower['x-xsrf-token']),
    };
  }

  _pickInterestingHeaders(headers) {
    const interesting = ['authorization', 'cookie', 'content-type', 'x-csrf-token', 'x-xsrf-token'];
    const sensitiveKeys = ['authorization', 'cookie', 'x-csrf-token', 'x-xsrf-token'];
    const result = {};
    for (const [key, value] of Object.entries(headers)) {
      const lower = key.toLowerCase();
      if (!interesting.includes(lower)) continue;
      if (sensitiveKeys.includes(lower)) {
        result[key] = this._maskValue(value);
      } else {
        result[key] = value;
      }
    }
    return result;
  }

  _maskValue(value) {
    if (!value || typeof value !== 'string') return '[REDACTED]';
    if (value.length <= 8) return '[REDACTED]';
    return value.slice(0, 4) + '***' + value.slice(-4);
  }

  _hashValue(value) {
    if (value === null || value === undefined || value === '') return 'no-body';
    return crypto.createHash('sha1').update(this._stableSerialize(value)).digest('hex').slice(0, 12);
  }

  _stableSerialize(value) {
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) {
      return `[${value.map((item) => this._stableSerialize(item)).join(',')}]`;
    }
    if (value && typeof value === 'object') {
      return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${this._stableSerialize(value[key])}`).join(',')}}`;
    }
    return JSON.stringify(value);
  }

  _inferSchemaType(value) {
    if (Array.isArray(value)) return 'array';
    if (value === null) return 'null';
    return typeof value === 'object' ? 'object' : typeof value;
  }

  safeParseJson(value) {
    if (!value) return value ?? null;
    if (typeof value !== 'string') return value;
    try {
      return JSON.parse(value);
    } catch {
      return value;
    }
  }
}
