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
    const specDir = path.join(this.outputDir, 'server', 'spec');
    const graphqlDir = path.join(specDir, 'graphql');
    const httpMockDir = path.join(this.outputDir, 'server', 'mocks', 'http');
    const wsMockDir = path.join(this.outputDir, 'server', 'mocks', 'ws');
    const serverDocsDir = path.join(this.outputDir, 'server', 'docs');

    await Promise.all([
      ensureDir(specDir),
      ensureDir(graphqlDir),
      ensureDir(httpMockDir),
      ensureDir(wsMockDir),
      ensureDir(serverDocsDir),
    ]);

    const filteredRequests = xhrRequests
      .filter((req) => this._isSameDomainApi(req.url))
      .map((req) => this._normalizeRequest(req));

    const groupedRequests = this._groupRequests(filteredRequests);
    const openApiSpec = this._buildOpenApi(groupedRequests);
    const graphqlReport = this._buildGraphqlReport(filteredRequests);
    const asyncApiSpec = this._buildAsyncApi(websocketEvents);
    const httpManifest = await this._emitHttpMocks(groupedRequests, httpMockDir);
    const apiSummary = this._buildApiSummary(groupedRequests);

    await saveFile(
      path.join(specDir, 'openapi.json'),
      JSON.stringify(openApiSpec, null, 2),
    );
    await saveFile(
      path.join(specDir, 'asyncapi.json'),
      JSON.stringify(asyncApiSpec, null, 2),
    );
    await saveFile(
      path.join(specDir, 'request-log.json'),
      JSON.stringify(filteredRequests, null, 2),
    );
    await saveFile(
      path.join(specDir, 'graphql', 'operations.json'),
      JSON.stringify(graphqlReport, null, 2),
    );
    await saveFile(
      path.join(wsMockDir, 'frames.json'),
      JSON.stringify(websocketEvents, null, 2),
    );
    await saveFile(
      path.join(this.outputDir, 'server', 'mocks', 'http-manifest.json'),
      JSON.stringify(httpManifest, null, 2),
    );

    logger.success('Captured HTTP, GraphQL, and WebSocket artifacts generated');
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
    const graphQLBody =
      requestBody && typeof requestBody === 'object' && !Array.isArray(requestBody) ? requestBody : null;
    const graphQLOperationName = graphQLBody?.operationName || null;
    const graphQLVariables = graphQLBody?.variables || null;

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
      graphQL: this._looksLikeGraphQL(url.pathname, graphQLBody),
      graphQLOperationName,
      graphQLVariables,
      graphQLVariablesHash: this._hashValue(graphQLVariables),
    };
  }

  _buildOpenApi(groupedRequests) {
    const parsedUrl = new URL(this.targetUrl);
    const host = parsedUrl.host;
    const protocol = parsedUrl.protocol.replace(':', '');

    const openApiSpec = {
      openapi: '3.1.0',
      info: {
        title: `Captured HTTP API for ${this.domainRoot}`,
        description: `Generated from ${this.targetUrl}`,
        version: '1.0.0',
      },
      jsonSchemaDialect: 'https://json-schema.org/draft/2020-12/schema',
      servers: [
        { url: `${protocol}://${host}`, description: 'Original server' },
        { url: 'http://localhost:3000', description: 'Generated Express adapter' },
      ],
      paths: {},
    };

    for (const [groupKey, variants] of groupedRequests) {
      const [method, pathname] = groupKey.split(' ');
      openApiSpec.paths[pathname] ??= {};

      const parameterMap = new Map();
      for (const variant of variants) {
        for (const param of variant.queryParams) {
          if (!parameterMap.has(param.name)) parameterMap.set(param.name, new Set());
          parameterMap.get(param.name).add(param.value);
        }
      }

      const responses = {};
      for (const variant of variants) {
        const statusKey = String(variant.responseStatus || 200);
        responses[statusKey] ??= { description: 'Captured response' };

        if (variant.responseBody !== null && variant.responseBody !== undefined) {
          responses[statusKey].content = {
            [variant.responseMimeType || 'application/json']: {
              schema: { type: this._inferSchemaType(variant.responseBody) },
              example: variant.responseBody,
            },
          };
        }
      }

      const operation = {
        summary: variants[0].graphQL
          ? `Captured GraphQL over HTTP ${method} ${pathname}`
          : `Captured HTTP ${method} ${pathname}`,
        responses,
        'x-captured-variants': variants.map((variant) => ({
          search: variant.search,
          requestBodyHash: variant.requestBodyHash,
          responseStatus: variant.responseStatus,
          pageUrl: variant.pageUrl,
          graphQLOperationName: variant.graphQLOperationName,
          graphQLVariablesHash: variant.graphQLVariablesHash,
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
            required: false,
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
      if (authHints) operation['x-auth-hints'] = authHints;
      if (variants.some((variant) => variant.graphQL)) operation['x-graphql-operation-names'] = [...new Set(variants.map((variant) => variant.graphQLOperationName).filter(Boolean))];

      openApiSpec.paths[pathname][method.toLowerCase()] = operation;
    }

    return openApiSpec;
  }

  _buildAsyncApi(websocketEvents) {
    const channels = {};

    for (const event of websocketEvents) {
      const key = this._channelKeyFromUrl(event.url);
      channels[key] ??= {
        address: event.url,
        messages: {},
      };
    }

    return {
      asyncapi: '3.0.0',
      info: {
        title: `Captured WebSocket API for ${this.domainRoot}`,
        version: '1.0.0',
      },
      channels,
    };
  }

  async _emitHttpMocks(groupedRequests, httpMockDir) {
    const manifest = [];

    for (const [groupKey, variants] of groupedRequests) {
      const [method, pathname] = groupKey.split(' ');
      for (const variant of variants) {
        const fileId = this._hashValue([
          method,
          pathname,
          variant.search,
          variant.graphQLOperationName || '',
          variant.graphQLVariablesHash || '',
          variant.requestBodyHash,
        ]);
        const relativeBodyFile = path.posix.join('mocks', 'http', `${fileId}.json`);

        await saveFile(
          path.join(httpMockDir, `${fileId}.json`),
          JSON.stringify(
            variant.responseBody !== undefined ? variant.responseBody : null,
            null,
            2,
          ),
        );

        manifest.push({
          id: fileId,
          method,
          path: pathname,
          query: Object.fromEntries(variant.queryParams.map((param) => [param.name, param.value])),
          search: variant.search,
          bodyHash: variant.requestBodyHash,
          graphQL: variant.graphQL,
          graphQLOperationName: variant.graphQLOperationName,
          graphQLVariablesHash: variant.graphQLVariablesHash,
          status: variant.responseStatus,
          responseMimeType: variant.responseMimeType,
          responseHeaders: variant.headers,
          pageUrl: variant.pageUrl,
          bodyFile: relativeBodyFile,
        });
      }
    }

    return manifest;
  }

  _buildGraphqlReport(requests) {
    const grouped = new Map();

    for (const req of requests) {
      if (!req.graphQL) continue;

      const operationName = req.graphQLOperationName || 'anonymous';
      const groupKey = `${operationName} ${req.graphQLVariablesHash}`;
      const current = grouped.get(groupKey) || {
        operationName,
        variablesHash: req.graphQLVariablesHash,
        hits: 0,
        urls: new Set(),
        pageUrls: new Set(),
        queryPreview: typeof req.requestBody?.query === 'string' ? req.requestBody.query.slice(0, 300) : null,
      };

      current.hits += 1;
      current.urls.add(req.url);
      if (req.pageUrl) current.pageUrls.add(req.pageUrl);
      grouped.set(groupKey, current);
    }

    return {
      operations: [...grouped.values()].map((entry) => ({
        operationName: entry.operationName,
        variablesHash: entry.variablesHash,
        hits: entry.hits,
        urls: [...entry.urls],
        pageUrls: [...entry.pageUrls],
        queryPreview: entry.queryPreview,
      })),
    };
  }

  _buildApiSummary(groupedRequests) {
    const routeGroups = {};

    for (const [, variants] of groupedRequests) {
      const pathname = variants[0].pathname;
      const group = pathname.split('/').filter(Boolean)[0] || 'root';
      routeGroups[group] ??= [];

      routeGroups[group].push({
        method: variants[0].method,
        pathname,
        responseMimeType: variants[0].responseMimeType,
        variants: variants.length,
        graphQL: variants.some((variant) => variant.graphQL),
      });
    }

    return {
      totalRequests: [...groupedRequests.values()].reduce((sum, variants) => sum + variants.length, 0),
      uniqueEndpoints: groupedRequests.size,
      routeGroups,
    };
  }

  _groupRequests(requests) {
    const grouped = new Map();

    for (const req of requests) {
      const groupKey = `${req.method} ${req.pathname}`;
      if (!grouped.has(groupKey)) grouped.set(groupKey, []);

      const variants = grouped.get(groupKey);
      const dedupeKey = req.graphQL
        ? `${req.search} ${req.graphQLOperationName || 'anonymous'} ${req.graphQLVariablesHash}`
        : `${req.search} ${req.requestBodyHash}`;

      if (!variants.some((variant) => {
        const candidateKey = variant.graphQL
          ? `${variant.search} ${variant.graphQLOperationName || 'anonymous'} ${variant.graphQLVariablesHash}`
          : `${variant.search} ${variant.requestBodyHash}`;
        return candidateKey === dedupeKey;
      })) {
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
      result[key] = sensitiveKeys.includes(lower) ? this._maskValue(value) : value;
    }
    return result;
  }

  _maskValue(value) {
    if (!value || typeof value !== 'string') return '[REDACTED]';
    if (value.length <= 8) return '[REDACTED]';
    return `${value.slice(0, 4)}***${value.slice(-4)}`;
  }

  _hashValue(value) {
    if (value === null || value === undefined || value === '') return 'no-body';
    return crypto.createHash('sha1').update(this._stableSerialize(value)).digest('hex').slice(0, 12);
  }

  _stableSerialize(value) {
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return `[${value.map((item) => this._stableSerialize(item)).join(',')}]`;
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

  _looksLikeGraphQL(pathname, requestBody) {
    return pathname.toLowerCase().includes('graphql')
      || Boolean(requestBody && typeof requestBody === 'object' && ('query' in requestBody || 'operationName' in requestBody));
  }

  _channelKeyFromUrl(url) {
    try {
      const parsed = new URL(url);
      return parsed.pathname || '/';
    } catch {
      return '/';
    }
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
