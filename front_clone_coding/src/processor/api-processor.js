import crypto from 'crypto';
import path from 'path';

import { ensureDir, saveFile } from '../utils/file-utils.js';
import logger from '../utils/logger.js';
import { getDomainRoot, isInDomainScope, normalizeCrawlUrl } from '../utils/url-utils.js';
import {
  buildRenderCriticalCandidates,
  normalizeSearch,
} from '../utils/replay-mock-utils.js';

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
  constructor(outputDir, targetUrl, domainScope = 'registrable-domain', pageReplaySignals = new Map()) {
    this.outputDir = outputDir;
    this.targetUrl = targetUrl;
    this.domainScope = domainScope;
    this.domainRoot = getDomainRoot(targetUrl, domainScope);
    this.pageReplaySignals = pageReplaySignals;
  }

  async generateArtifacts(xhrRequests = [], websocketEvents = [], graphqlArtifacts = []) {
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
    const graphqlReport = this._buildGraphqlReport(filteredRequests, graphqlArtifacts);
    const asyncApiSpec = this._buildAsyncApi(websocketEvents);
    const httpManifest = await this._emitHttpMocks(groupedRequests, httpMockDir);
    const apiSummary = this._buildApiSummary(groupedRequests);
    const renderCriticalCandidates = this._buildRenderCriticalCandidates(filteredRequests);

    await saveFile(path.join(specDir, 'openapi.json'), JSON.stringify(openApiSpec, null, 2));
    await saveFile(path.join(specDir, 'asyncapi.json'), JSON.stringify(asyncApiSpec, null, 2));
    await saveFile(path.join(specDir, 'request-log.json'), JSON.stringify(filteredRequests, null, 2));
    await saveFile(path.join(graphqlDir, 'operations.json'), JSON.stringify(graphqlReport, null, 2));
    await saveFile(path.join(wsMockDir, 'frames.json'), JSON.stringify(websocketEvents, null, 2));
    await saveFile(
      path.join(this.outputDir, 'server', 'mocks', 'http-manifest.json'),
      JSON.stringify(httpManifest, null, 2),
    );
    await saveFile(
      path.join(specDir, 'render-critical-requests.json'),
      JSON.stringify(renderCriticalCandidates, null, 2),
    );

    if (graphqlArtifacts.length > 0) {
      const primarySchema = graphqlArtifacts[0];
      await saveFile(path.join(graphqlDir, 'schema.json'), JSON.stringify(primarySchema, null, 2));
    }

    logger.success('Captured HTTP, GraphQL, and WebSocket artifacts generated');
    return {
      apiSummary,
      filteredRequests,
      graphqlReport,
      graphqlArtifacts,
      httpManifest,
      renderCriticalCandidates,
    };
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
    const responseEnvelope = this.safeParseJson(req.responseBody);
    const queryParams = [...url.searchParams.entries()].map(([name, value]) => ({ name, value }));
    const graphQLDetails = this._extractGraphQLDetails(url, requestBody);

    const pageSignals = this._getPageReplaySignals(req.pageUrl || '');
    const replayDetails = this._classifyReplayRoleDetails(
      req.url,
      req.pageUrl || '',
      graphQLDetails,
      req,
      pageSignals,
      requestBody,
      responseEnvelope,
    );

    return {
      key: req.key || `${req.method || 'GET'} ${req.url}`,
      method: (req.method || 'GET').toUpperCase(),
      transportMethod: (req.method || 'GET').toUpperCase(),
      url: req.url,
      pageUrl: req.pageUrl || '',
      pathname: url.pathname,
      search: url.search,
      queryParams,
      resourceType: req.resourceType || 'fetch',
      httpStatus: req.responseStatus || 200,
      responseStatus: req.responseStatus || 200,
      responseContentType: req.responseMimeType || 'application/json',
      responseMimeType: req.responseMimeType || 'application/json',
      requestBody,
      requestBodyHash: req.requestBodyHash || this._hashValue(requestBody),
      responseEnvelope,
      responseBody: responseEnvelope,
      responseBodyStored: req.responseBodyStored !== false,
      authHints: this._collectAuthHints(req.headers || {}),
      headers: this._pickInterestingHeaders(req.headers || {}),
      graphQL: graphQLDetails.graphQL,
      graphQLDetails,
      graphQLOperationName: graphQLDetails.operationName,
      graphQLVariables: graphQLDetails.variables,
      graphQLVariablesHash: graphQLDetails.variablesHash,
      documentHash: graphQLDetails.documentHash,
      persistedOperationHint: graphQLDetails.persistedOperationHint,
      bootstrapSignals: this._summarizeBootstrapSignals(pageSignals),
      replayRole: replayDetails.replayRole,
      renderCriticalKind: replayDetails.renderCriticalKind,
      expectedForReplay: replayDetails.expectedForReplay,
      firstPaintDependency: replayDetails.firstPaintDependency
        || (replayDetails.expectedForReplay !== false
          ? 'strict'
          : replayDetails.replayRole === 'render-supporting'
            ? 'supporting'
            : 'non-critical'),
      classificationReason: replayDetails.classificationReason || 'unclassified',
      dependencyEvidence: replayDetails.dependencyEvidence || [],
    };
  }

  _extractGraphQLDetails(url, requestBody) {
    const bodyPayload = requestBody && typeof requestBody === 'object' && !Array.isArray(requestBody) ? requestBody : {};
    const queryPayload = this._extractQueryGraphqlPayload(url);
    const payload = Object.keys(bodyPayload).length > 0 ? bodyPayload : queryPayload;
    const graphQL = this._looksLikeGraphQL(url.pathname, payload) || this._looksLikeGraphQL(url.pathname, queryPayload);
    const documentText = typeof payload.query === 'string'
      ? payload.query
      : (typeof queryPayload.query === 'string' ? queryPayload.query : null);
    const operationName = payload.operationName || queryPayload.operationName || null;
    const variables = payload.variables ?? queryPayload.variables ?? null;
    const extensions = payload.extensions ?? queryPayload.extensions ?? null;

    return {
      graphQL,
      operationName,
      operationType: this._extractOperationType(documentText),
      documentText,
      documentHash: this._hashValue(documentText || null),
      variables,
      variablesHash: this._hashValue(variables),
      extensions,
      persistedOperationHint: this._detectPersistedOperationHint(extensions),
    };
  }

  _extractQueryGraphqlPayload(url) {
    const payload = {};
    for (const key of ['query', 'operationName', 'variables', 'extensions']) {
      if (!url.searchParams.has(key)) continue;
      payload[key] = this.safeParseJson(url.searchParams.get(key));
    }
    return payload;
  }

  _extractOperationType(documentText) {
    if (typeof documentText !== 'string') return null;
    const match = documentText.match(/\b(query|mutation|subscription)\b/i);
    return match ? match[1].toLowerCase() : null;
  }

  _detectPersistedOperationHint(extensions) {
    if (!extensions || typeof extensions !== 'object' || Array.isArray(extensions)) return null;
    if (extensions.persistedQuery && typeof extensions.persistedQuery === 'object') {
      return {
        type: 'persistedQuery',
        sha256Hash: extensions.persistedQuery.sha256Hash || null,
        version: extensions.persistedQuery.version || null,
      };
    }
    return { type: 'extensions-present' };
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
        const statusKey = String(variant.httpStatus || 200);
        responses[statusKey] ??= { description: 'Captured response' };

        if (variant.responseEnvelope !== null && variant.responseEnvelope !== undefined) {
          responses[statusKey].content = {
            [variant.responseContentType || 'application/json']: {
              schema: this._inferSchema(variant.responseEnvelope),
              example: variant.responseEnvelope,
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
          responseStatus: variant.httpStatus,
          pageUrl: variant.pageUrl,
          graphQLOperationName: variant.graphQLOperationName,
          graphQLVariablesHash: variant.graphQLVariablesHash,
          documentHash: variant.documentHash,
          persistedOperationHint: variant.persistedOperationHint,
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

      if (['POST', 'PUT', 'PATCH'].includes(method) || variants.some((variant) => variant.graphQL)) {
        const bodyExample = variants.find((variant) => variant.requestBody !== null && variant.requestBody !== undefined);
        if (bodyExample) {
          operation.requestBody = {
            required: false,
            content: {
              'application/json': {
                schema: this._inferSchema(bodyExample.requestBody),
                example: bodyExample.requestBody,
              },
            },
          };
        }
      }

      const authHints = variants.find((variant) => Object.values(variant.authHints).some(Boolean))?.authHints;
      if (authHints) operation['x-auth-hints'] = authHints;
      if (variants.some((variant) => variant.graphQL)) {
        operation['x-graphql-operation-names'] = [...new Set(variants.map((variant) => variant.graphQLOperationName).filter(Boolean))];
      }

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
          variant.graphQL ? this._buildGraphqlReplayKey(variant) : `${variant.search} ${variant.requestBodyHash}`,
        ]);
        const relativeBodyFile = path.posix.join('mocks', 'http', `${fileId}.json`);

        await saveFile(
          path.join(httpMockDir, `${fileId}.json`),
          JSON.stringify(variant.responseEnvelope !== undefined ? variant.responseEnvelope : null, null, 2),
        );

        manifest.push({
          id: fileId,
          method,
          path: pathname,
          query: Object.fromEntries(variant.queryParams.map((param) => [param.name, param.value])),
          search: variant.search,
          bodyHash: variant.requestBodyHash,
          matchStrategy: variant.graphQL ? 'graphql-operation' : 'rest-body',
          graphQL: variant.graphQL,
          graphQLDetails: variant.graphQL ? {
            operationName: variant.graphQLOperationName,
            documentHash: variant.documentHash,
            variablesHash: variant.graphQLVariablesHash,
            persistedOperationHint: variant.persistedOperationHint,
            extensions: variant.graphQLDetails.extensions,
          } : null,
          graphQLOperationName: variant.graphQLOperationName,
          graphQLVariablesHash: variant.graphQLVariablesHash,
          normalizedSearch: normalizeSearch(variant.search),
          status: variant.httpStatus,
          responseMimeType: variant.responseContentType,
          responseHeaders: variant.headers,
          responseContentType: variant.responseContentType,
          httpStatus: variant.httpStatus,
          pageUrl: variant.pageUrl,
          replayRole: variant.replayRole,
          renderCriticalKind: variant.renderCriticalKind,
          expectedForReplay: variant.expectedForReplay !== false,
          bodyFile: relativeBodyFile,
        });
      }
    }

    return manifest;
  }

  _buildGraphqlReport(requests, graphqlArtifacts = []) {
    const grouped = new Map();

    for (const req of requests) {
      if (!req.graphQL) continue;

      const operationName = req.graphQLOperationName || 'anonymous';
      const groupKey = `${operationName} ${req.graphQLVariablesHash} ${req.documentHash}`;
      const current = grouped.get(groupKey) || {
        operationName,
        operationType: req.graphQLDetails.operationType,
        variablesHash: req.graphQLVariablesHash,
        documentHash: req.documentHash,
        persistedOperationHint: req.persistedOperationHint,
        hits: 0,
        urls: new Set(),
        pageUrls: new Set(),
        queryPreview: typeof req.graphQLDetails.documentText === 'string' ? req.graphQLDetails.documentText.slice(0, 300) : null,
        responseShape: this._inferSchema(req.responseEnvelope),
        responseContentTypes: new Set(),
      };

      current.hits += 1;
      current.urls.add(req.url);
      current.responseContentTypes.add(req.responseContentType || 'application/json');
      if (req.pageUrl) current.pageUrls.add(req.pageUrl);
      grouped.set(groupKey, current);
    }

    return {
      schemas: graphqlArtifacts.map((artifact) => ({
        endpoint: artifact.endpoint,
        capturedAt: artifact.capturedAt,
        responseContentType: artifact.responseContentType,
        httpStatus: artifact.httpStatus,
        authSessionHash: artifact.authSessionHash,
        schemaMayBeClientSpecific: artifact.schemaMayBeClientSpecific,
      })),
      operations: [...grouped.values()].map((entry) => ({
        operationName: entry.operationName,
        operationType: entry.operationType,
        variablesHash: entry.variablesHash,
        documentHash: entry.documentHash,
        persistedOperationHint: entry.persistedOperationHint,
        hits: entry.hits,
        urls: [...entry.urls],
        pageUrls: [...entry.pageUrls],
        queryPreview: entry.queryPreview,
        observedResponseShape: entry.responseShape,
        responseContentTypes: [...entry.responseContentTypes],
      })),
    };
  }

  _buildApiSummary(groupedRequests) {
    const routeGroups = {};
    const graphqlEndpoints = new Set();

    for (const [, variants] of groupedRequests) {
      const pathname = variants[0].pathname;
      const group = pathname.split('/').filter(Boolean)[0] || 'root';
      routeGroups[group] ??= [];

      routeGroups[group].push({
        method: variants[0].method,
        pathname,
        responseMimeType: variants[0].responseContentType,
        variants: variants.length,
        graphQL: variants.some((variant) => variant.graphQL),
      });

      if (variants.some((variant) => variant.graphQL)) {
        graphqlEndpoints.add(pathname);
      }
    }

    return {
      totalRequests: [...groupedRequests.values()].reduce((sum, variants) => sum + variants.length, 0),
      uniqueEndpoints: groupedRequests.size,
      graphqlEndpointCount: graphqlEndpoints.size,
      renderCriticalRequestCount: [...groupedRequests.values()].flat().filter((variant) => variant.replayRole === 'render-critical').length,
      renderSupportingRequestCount: [...groupedRequests.values()].flat().filter((variant) => variant.replayRole === 'render-supporting').length,
      nonCriticalRequestCount: [...groupedRequests.values()].flat().filter((variant) => variant.replayRole === 'non-critical').length,
      renderCriticalBootstrapCount: [...groupedRequests.values()].flat().filter((variant) => variant.renderCriticalKind === 'render-critical-bootstrap').length,
      renderCriticalGraphqlCount: [...groupedRequests.values()].flat().filter((variant) => variant.renderCriticalKind === 'render-critical-graphql').length,
      renderSupportingRuntimeCount: [...groupedRequests.values()].flat().filter((variant) => variant.renderCriticalKind === 'render-supporting-runtime').length,
      routeGroups,
    };
  }

  _buildRenderCriticalCandidates(filteredRequests) {
    return buildRenderCriticalCandidates(filteredRequests);
  }

  _classifyReplayRoleDetails(requestUrl, pageUrl = '', graphQLDetails = {}, req = {}, pageSignals = {}, requestBody = null, responseEnvelope = null) {
    try {
      const url = new URL(requestUrl);
      const lower = `${url.hostname}${url.pathname}${url.search}`.toLowerCase();
      const responseMimeType = String(req.responseMimeType || '').toLowerCase();
      const resourceType = String(req.resourceType || '').toLowerCase();
      const hasRequestBody = Boolean(req.postData);
      const hasServerRenderedShell = this._hasServerRenderedShellEvidence(pageSignals);
      const looksStrictBootstrapPath = /(?:^|\/)(bootstrap|route|render|initial|manifest)(?:\/|$)|_next\/data/.test(lower);
      const looksStructuredApiHint = /(?:^|\/)(api|widget|feed|section|content|data|personalization)(?:\/|$)|_next\/data/.test(lower);
      const looksSecondaryAsyncModule = this._looksLikeSecondaryAsyncModule(lower, responseEnvelope);
      if (this._isLoggingEnvelopeRequest(requestBody)) {
        return this._buildReplayClassification('non-critical', null, false, 'non-critical', 'logging-envelope-payload', [
          'request-body:logging-envelope',
        ]);
      }
      if (/(telemetry|tracking|metrics|analytic|analytics|beacon|logger|logging|impress|exposure|clicklog|nlog|veta|adtech|\bads?\b|\blogs?\b|\/log(?:\/|$))/.test(lower)) {
        return this._buildReplayClassification('non-critical', null, false, 'non-critical', 'telemetry-or-logging-path', [
          'url:telemetry-or-logging',
        ]);
      }
      if (graphQLDetails.graphQL) {
        if (this._isSupportingGraphqlStateRefresh(graphQLDetails, pageSignals)) {
          return this._buildReplayClassification(
            'render-supporting',
            'render-supporting-runtime',
            false,
            'supporting',
            'bootstrap-backed-state-refresh',
            this._buildDependencyEvidence(pageSignals, ['graphql-state-refresh']),
          );
        }
        return this._buildReplayClassification(
          'render-critical',
          'render-critical-graphql',
          true,
          'strict',
          'graphql-without-first-paint-fallback',
          this._buildDependencyEvidence(pageSignals, ['graphql-runtime']),
        );
      }
      if (!isInDomainScope(requestUrl, this.targetUrl, this.domainScope)) {
        return this._buildReplayClassification('non-critical', null, false, 'non-critical', 'out-of-scope-request', [
          'scope:external',
        ]);
      }
      const looksStructured = /(json|graphql)/.test(responseMimeType);
      if (this._isSupportingStructuredStateRefresh(lower, pageSignals, looksStructured)) {
        return this._buildReplayClassification(
          'render-supporting',
          'render-supporting-runtime',
          false,
          'supporting',
          'bootstrap-backed-structured-state-refresh',
          this._buildDependencyEvidence(pageSignals, ['structured-state-refresh']),
        );
      }
      if (looksStructured && hasServerRenderedShell && looksSecondaryAsyncModule && !looksStrictBootstrapPath) {
        return this._buildReplayClassification(
          'render-supporting',
          'render-supporting-runtime',
          false,
          'supporting',
          'server-rendered-shell-secondary-async-module',
          this._buildDependencyEvidence(pageSignals, [
            'server-rendered-shell',
            'secondary-async-module',
            'structured-response',
          ]),
        );
      }
      const looksReplayRelevant = looksStructured || looksStructuredApiHint || looksStrictBootstrapPath || (hasRequestBody && ['fetch', 'xhr'].includes(resourceType));
      if (looksReplayRelevant) {
        return this._buildReplayClassification(
          'render-critical',
          'render-critical-bootstrap',
          true,
          'strict',
          'structured-runtime-without-shell-fallback',
          this._buildDependencyEvidence(pageSignals, [
            looksStrictBootstrapPath ? 'path:bootstrap-like' : 'structured-runtime',
            hasRequestBody ? 'request:has-body' : 'request:no-body',
          ]),
        );
      }
      if (pageUrl && isInDomainScope(pageUrl, this.targetUrl, this.domainScope) && ['fetch', 'xhr'].includes(resourceType) && looksStructured) {
        return this._buildReplayClassification(
          'render-critical',
          'render-critical-bootstrap',
          true,
          'strict',
          'same-page-structured-runtime',
          this._buildDependencyEvidence(pageSignals, ['same-page-structured-runtime']),
        );
      }
      return this._buildReplayClassification('non-critical', null, false, 'non-critical', 'not-replay-relevant', []);
    } catch {
      return this._buildReplayClassification('non-critical', null, false, 'non-critical', 'classification-error', []);
    }
  }

  _getPageReplaySignals(pageUrl) {
    const normalizedPageUrl = normalizeCrawlUrl(pageUrl || '');
    return this.pageReplaySignals.get(normalizedPageUrl) || {};
  }

  _isSupportingGraphqlStateRefresh(graphQLDetails = {}, pageSignals = {}) {
    const operationName = String(graphQLDetails.operationName || '').trim();
    if (!operationName) return false;
    if (!this._hasStrongBootstrapEvidence(pageSignals)) return false;

    const looksStateRefresh = /(membership|account|session|viewer|user|profile|auth|identity)/i.test(operationName);
    const hasEquivalentFallback = Boolean(
      pageSignals.hasMembershipStatusFallback
      || pageSignals.hasUserInfoModel
      || pageSignals.hasSessionStateFallback
      || pageSignals.hasRenderableStateFallback
    );

    return looksStateRefresh && hasEquivalentFallback;
  }

  _isSupportingStructuredStateRefresh(urlMarker = '', pageSignals = {}, looksStructured = false) {
    if (!looksStructured) return false;
    if (!this._hasStrongBootstrapEvidence(pageSignals)) return false;
    return /(membership|account|session|viewer|user|profile|auth|identity|status)/i.test(urlMarker);
  }

  _hasServerRenderedShellEvidence(pageSignals = {}) {
    return Boolean(
      pageSignals.hasServerRenderedShell
      || (
        pageSignals.hasDocumentTitle
        && pageSignals.hasDenseServerRenderedText
        && (pageSignals.hasPrimaryHeading || pageSignals.hasNavigationStructure || pageSignals.hasPrimaryLandmarks)
      )
    );
  }

  _looksLikeSecondaryAsyncModule(urlMarker = '', responseEnvelope = null) {
    const hasSecondaryKeyword = /(ticket|queue|wait|calendar|reservation|booking|widget|feed|weather|status|banner|popup|poll|counter|alert|notice|board|list|map|schedule|event|facility|place|guide)/i.test(urlMarker);
    if (!hasSecondaryKeyword) return false;
    return this._looksListLikeResponse(responseEnvelope) || /widget|feed|status|banner|popup|counter|board|list|map|calendar|schedule|event/i.test(urlMarker);
  }

  _looksListLikeResponse(value) {
    if (Array.isArray(value)) return true;
    if (!value || typeof value !== 'object') return false;
    return ['list', 'items', 'rows', 'results', 'resultData', 'data']
      .some((key) => Array.isArray(value[key]));
  }

  _buildReplayClassification(replayRole, renderCriticalKind, expectedForReplay, firstPaintDependency, classificationReason, dependencyEvidence = []) {
    return {
      replayRole,
      renderCriticalKind,
      expectedForReplay,
      firstPaintDependency,
      classificationReason,
      dependencyEvidence,
    };
  }

  _buildDependencyEvidence(pageSignals = {}, evidence = []) {
    const details = [...(evidence || [])];
    const bootstrapEvidenceLevel = pageSignals.bootstrapEvidenceLevel
      || (
        pageSignals.hasRenderableStateFallback || pageSignals.hasInlineBootstrapState
          ? 'strong'
          : (pageSignals.hasFrameworkBootstrap || pageSignals.hasStreamingHydrationHints)
            ? 'partial'
            : 'none'
      );
    if (bootstrapEvidenceLevel && bootstrapEvidenceLevel !== 'none') details.push(`bootstrap:${bootstrapEvidenceLevel}`);
    if (pageSignals.hasServerRenderedShell) details.push('shell:server-rendered');
    if (pageSignals.hasDocumentTitle) details.push('shell:title');
    if (pageSignals.hasNavigationStructure) details.push('shell:navigation');
    if (pageSignals.hasPrimaryHeading) details.push('shell:heading');
    if (pageSignals.hasDenseServerRenderedText) details.push('shell:dense-text');
    return [...new Set(details.filter(Boolean))];
  }

  _hasStrongBootstrapEvidence(pageSignals = {}) {
    return Boolean(
      pageSignals.hasRenderableStateFallback
      || pageSignals.hasInlineBootstrapState
      || pageSignals.bootstrapEvidenceLevel === 'strong'
    );
  }

  _summarizeBootstrapSignals(pageSignals = {}) {
    const hasRenderableStateFallback = Boolean(
      pageSignals.hasRenderableStateFallback
      || pageSignals.hasMembershipStatusFallback
      || pageSignals.hasUserInfoModel
      || pageSignals.hasSessionStateFallback
    );
    const hasInlineBootstrapState = Boolean(pageSignals.hasInlineBootstrapState);
    const hasFrameworkBootstrap = Boolean(pageSignals.hasFrameworkBootstrap);
    const hasStreamingHydrationHints = Boolean(pageSignals.hasStreamingHydrationHints);
    const bootstrapEvidenceLevel = pageSignals.bootstrapEvidenceLevel
      || (
        hasRenderableStateFallback || hasInlineBootstrapState
          ? 'strong'
          : (hasFrameworkBootstrap || hasStreamingHydrationHints)
            ? 'partial'
            : 'none'
      );
    return {
      hasInlineBootstrapState,
      hasFrameworkBootstrap,
      hasStreamingHydrationHints,
      hasRenderableStateFallback,
      hasDocumentTitle: Boolean(pageSignals.hasDocumentTitle),
      hasPrimaryHeading: Boolean(pageSignals.hasPrimaryHeading),
      hasNavigationStructure: Boolean(pageSignals.hasNavigationStructure),
      hasPrimaryLandmarks: Boolean(pageSignals.hasPrimaryLandmarks),
      hasDenseServerRenderedText: Boolean(pageSignals.hasDenseServerRenderedText),
      hasServerRenderedShell: Boolean(pageSignals.hasServerRenderedShell),
      bootstrapEvidenceLevel,
      bootstrapSignalCount: pageSignals.bootstrapSignalCount || 0,
      frameworkKinds: pageSignals.frameworkKinds || [],
    };
  }

  _isLoggingEnvelopeRequest(requestBody) {
    if (!requestBody || typeof requestBody !== 'object' || Array.isArray(requestBody)) return false;

    if (requestBody.type === 'CompactConsolidatedLoggingEnvelope') return true;
    if (!('currentState' in requestBody) || !('reverseDeltas' in requestBody)) return false;

    return this._payloadContainsLoggingSignal(requestBody, new Set());
  }

  _payloadContainsLoggingSignal(value, visited) {
    if (!value || typeof value !== 'object') return false;
    if (visited.has(value)) return false;
    visited.add(value);

    if (Array.isArray(value)) {
      return value.some((item) => this._payloadContainsLoggingSignal(item, visited));
    }

    if (typeof value.type === 'string' && value.type === 'CompactConsolidatedLoggingEnvelope') {
      return true;
    }

    if (Array.isArray(value.type)) {
      const typeMarkers = value.type.filter((item) => typeof item === 'string');
      if (typeMarkers.some((item) => /^(Log|LoggerInitialized|ViewportDimensions|SessionEnded|SessionCanceled|cs\.HostLoggingSource)$/.test(item))) {
        return true;
      }
    }

    if (typeof value.source === 'string' && /logging|helpcenter|helpCenter/i.test(value.source)) {
      return true;
    }

    return Object.values(value).some((item) => this._payloadContainsLoggingSignal(item, visited));
  }

  _groupRequests(requests) {
    const grouped = new Map();

    for (const req of requests) {
      const groupKey = `${req.method} ${req.pathname}`;
      if (!grouped.has(groupKey)) grouped.set(groupKey, []);

      const variants = grouped.get(groupKey);
      const dedupeKey = req.graphQL
        ? this._buildGraphqlReplayKey(req)
        : `${req.search} ${req.requestBodyHash}`;

      if (!variants.some((variant) => {
        const candidateKey = variant.graphQL
          ? this._buildGraphqlReplayKey(variant)
          : `${variant.search} ${variant.requestBodyHash}`;
        return candidateKey === dedupeKey;
      })) {
        variants.push(req);
      }
    }

    return grouped;
  }

  _buildGraphqlReplayKey(req) {
    if (req.documentHash && req.documentHash !== 'no-body') {
      return [
        req.search,
        req.graphQLOperationName || 'anonymous',
        req.documentHash,
        req.graphQLVariablesHash,
      ].join(' ');
    }

    return [
      req.search,
      req.graphQLOperationName || 'anonymous',
      this._hashValue(req.persistedOperationHint),
      req.graphQLVariablesHash,
      this._hashValue(req.graphQLDetails.extensions),
    ].join(' ');
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

  _inferSchema(value) {
    if (Array.isArray(value)) {
      return {
        type: 'array',
        items: value.length > 0 ? this._inferSchema(value[0]) : {},
      };
    }
    if (value === null) return { type: 'null' };
    if (typeof value === 'object') {
      const properties = {};
      for (const [key, child] of Object.entries(value)) {
        properties[key] = this._inferSchema(child);
      }
      return { type: 'object', properties };
    }
    return { type: typeof value };
  }

  _looksLikeGraphQL(pathname, requestBody) {
    return pathname.toLowerCase().includes('graphql')
      || Boolean(requestBody && typeof requestBody === 'object' && ('query' in requestBody || 'operationName' in requestBody || 'extensions' in requestBody));
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
