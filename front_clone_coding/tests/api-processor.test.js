import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';

import ApiProcessor from '../src/processor/api-processor.js';
import { normalizeCrawlUrl } from '../src/utils/url-utils.js';

test('ApiProcessor preserves GraphQL request details and writes schema artifacts', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-api-'));
  try {
    const processor = new ApiProcessor(tempRoot, 'https://example.com');
    const xhrRequests = [
      {
        method: 'GET',
        url: 'https://example.com/graphql?query=%7Bviewer%7Bid%7D%7D&operationName=ViewerQuery&variables=%7B%22id%22%3A%221%22%7D',
        pageUrl: 'https://example.com/app',
        postData: '',
        headers: {},
        responseStatus: 200,
        responseMimeType: 'application/graphql-response+json',
        responseBody: JSON.stringify({ data: { viewer: { id: '1' } }, errors: [] }),
      },
      {
        method: 'POST',
        url: 'https://example.com/graphql',
        pageUrl: 'https://example.com/app',
        postData: JSON.stringify({
          operationName: 'ViewerQuery',
          query: 'query ViewerQuery { viewer { id name } }',
          variables: { id: '1' },
          extensions: { persistedQuery: { sha256Hash: 'abc', version: 1 } },
        }),
        headers: { 'content-type': 'application/json' },
        responseStatus: 200,
        responseMimeType: 'application/json',
        responseBody: JSON.stringify({ data: { viewer: { id: '1', name: 'Ada' } }, extensions: { traceId: 't-1' } }),
      },
    ];

    const graphqlArtifacts = [
      {
        endpoint: 'https://example.com/graphql',
        capturedAt: '2026-03-26T00:00:00.000Z',
        responseContentType: 'application/json',
        httpStatus: 200,
        authSessionHash: 'session-1',
        schemaMayBeClientSpecific: true,
        schema: { data: { __schema: { queryType: { name: 'Query' } } } },
      },
    ];

    const result = await processor.generateArtifacts(xhrRequests, [], graphqlArtifacts);
    const operations = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'graphql', 'operations.json'), 'utf-8'));
    const schema = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'spec', 'graphql', 'schema.json'), 'utf-8'));
    const manifest = JSON.parse(await fs.readFile(path.join(tempRoot, 'server', 'mocks', 'http-manifest.json'), 'utf-8'));

    assert.equal(result.apiSummary.graphqlEndpointCount, 1);
    assert.equal(operations.operations.length, 2);
    assert.equal(operations.operations[0].operationName, 'ViewerQuery');
    assert.equal(schema.endpoint, 'https://example.com/graphql');
    assert.equal(manifest.some((item) => item.matchStrategy === 'graphql-operation'), true);
    assert.equal(manifest.some((item) => item.graphQLDetails?.documentHash), true);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('ApiProcessor separates render-critical bootstrap, render-critical graphql, and non-critical runtime', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-api-role-'));
  try {
    const processor = new ApiProcessor(tempRoot, 'https://example.com');
    const result = await processor.generateArtifacts([
      {
        method: 'GET',
        url: 'https://example.com/bootstrap',
        pageUrl: 'https://example.com',
        resourceType: 'fetch',
        headers: {},
        responseStatus: 200,
        responseMimeType: 'application/json',
        responseBody: JSON.stringify({ hero: true }),
      },
      {
        method: 'POST',
        url: 'https://example.com/graphql',
        pageUrl: 'https://example.com',
        resourceType: 'xhr',
        postData: JSON.stringify({
          operationName: 'HomeQuery',
          query: 'query HomeQuery { hero { id } }',
          variables: { locale: 'ko-KR' },
        }),
        headers: { 'content-type': 'application/json' },
        responseStatus: 200,
        responseMimeType: 'application/json',
        responseBody: JSON.stringify({ data: { hero: { id: '1' } } }),
      },
      {
        method: 'POST',
        url: 'https://example.com/log/www',
        pageUrl: 'https://example.com',
        resourceType: 'fetch',
        postData: JSON.stringify({ event: 'view' }),
        headers: { 'content-type': 'application/json' },
        responseStatus: 204,
        responseMimeType: 'application/json',
        responseBody: JSON.stringify({ ok: true }),
      },
    ], [], []);

    assert.equal(result.filteredRequests.find((item) => item.pathname === '/bootstrap').renderCriticalKind, 'render-critical-bootstrap');
    assert.equal(result.filteredRequests.find((item) => item.pathname === '/graphql').renderCriticalKind, 'render-critical-graphql');
    assert.equal(result.filteredRequests.find((item) => item.pathname === '/log/www').replayRole, 'non-critical');
    assert.equal(result.renderCriticalCandidates.length, 2);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('ApiProcessor downgrades membership state GraphQL with inline fallback to render-supporting runtime', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-api-supporting-'));
  try {
    const pageSignals = new Map([
      [normalizeCrawlUrl('https://example.com'), {
        hasInlineBootstrapState: true,
        hasUserInfoModel: true,
        hasMembershipStatusFallback: true,
        hasSessionStateFallback: false,
      }],
    ]);
    const processor = new ApiProcessor(tempRoot, 'https://example.com', 'registrable-domain', pageSignals);
    const result = await processor.generateArtifacts([
      {
        method: 'POST',
        url: 'https://example.com/graphql',
        pageUrl: 'https://example.com',
        resourceType: 'fetch',
        postData: JSON.stringify({
          operationName: 'MembershipStatus',
          variables: {},
          extensions: { persistedQuery: { version: 1, sha256Hash: 'abc' } },
        }),
        headers: { 'content-type': 'application/json' },
        responseStatus: 200,
        responseMimeType: 'application/json',
        responseBody: JSON.stringify({ data: { growthAccount: { membershipStatus: 'ANONYMOUS' } } }),
      },
    ], [], []);

    assert.equal(result.filteredRequests[0].replayRole, 'render-supporting');
    assert.equal(result.filteredRequests[0].renderCriticalKind, 'render-supporting-runtime');
    assert.equal(result.filteredRequests[0].expectedForReplay, false);
    assert.equal(result.filteredRequests[0].firstPaintDependency, 'supporting');
    assert.equal(result.filteredRequests[0].classificationReason, 'bootstrap-backed-state-refresh');
    assert.equal(result.filteredRequests[0].dependencyEvidence.includes('bootstrap:strong'), true);
    assert.equal(result.filteredRequests[0].bootstrapSignals.bootstrapEvidenceLevel, 'strong');
    assert.equal(result.renderCriticalCandidates[0].expectedForReplay, false);
    assert.equal(result.renderCriticalCandidates[0].firstPaintDependency, 'supporting');
    assert.equal(result.renderCriticalCandidates[0].classificationReason, 'bootstrap-backed-state-refresh');
    assert.equal(result.renderCriticalCandidates[0].bootstrapSignals.hasRenderableStateFallback, true);
    assert.equal(result.renderCriticalCandidates[0].candidateKey.startsWith('POST /graphql '), true);
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('ApiProcessor downgrades secondary async module endpoints when a server-rendered shell already exists', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-api-secondary-module-'));
  try {
    const pageSignals = new Map([
      [normalizeCrawlUrl('https://example.com/portal'), {
        hasDocumentTitle: true,
        hasPrimaryHeading: true,
        hasNavigationStructure: true,
        hasDenseServerRenderedText: true,
        hasServerRenderedShell: true,
        bootstrapEvidenceLevel: 'none',
      }],
    ]);
    const processor = new ApiProcessor(tempRoot, 'https://example.com', 'registrable-domain', pageSignals);
    const result = await processor.generateArtifacts([{
      method: 'GET',
      url: 'https://example.com/api/ticket/wait',
      pageUrl: 'https://example.com/portal',
      resourceType: 'xhr',
      headers: {},
      responseStatus: 200,
      responseMimeType: 'application/json',
      responseBody: JSON.stringify({
        resultData: [{ id: 1, waitCount: 0 }],
      }),
    }], [], []);

    assert.equal(result.filteredRequests[0].replayRole, 'render-supporting');
    assert.equal(result.filteredRequests[0].renderCriticalKind, 'render-supporting-runtime');
    assert.equal(result.filteredRequests[0].expectedForReplay, false);
    assert.equal(result.filteredRequests[0].firstPaintDependency, 'supporting');
    assert.equal(result.filteredRequests[0].classificationReason, 'server-rendered-shell-secondary-async-module');
    assert.equal(result.filteredRequests[0].dependencyEvidence.includes('shell:server-rendered'), true);
    assert.equal(result.renderCriticalCandidates[0].expectedForReplay, false);
    assert.equal(result.renderCriticalCandidates[0].classificationReason, 'server-rendered-shell-secondary-async-module');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('ApiProcessor keeps structured endpoints strict when server-rendered shell evidence is missing', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-api-strict-without-shell-'));
  try {
    const processor = new ApiProcessor(tempRoot, 'https://example.com');
    const result = await processor.generateArtifacts([{
      method: 'GET',
      url: 'https://example.com/api/ticket/wait',
      pageUrl: 'https://example.com/portal',
      resourceType: 'xhr',
      headers: {},
      responseStatus: 200,
      responseMimeType: 'application/json',
      responseBody: JSON.stringify({
        resultData: [{ id: 1, waitCount: 0 }],
      }),
    }], [], []);

    assert.equal(result.filteredRequests[0].replayRole, 'render-critical');
    assert.equal(result.filteredRequests[0].renderCriticalKind, 'render-critical-bootstrap');
    assert.equal(result.filteredRequests[0].expectedForReplay, true);
    assert.equal(result.filteredRequests[0].firstPaintDependency, 'strict');
    assert.equal(result.filteredRequests[0].classificationReason, 'structured-runtime-without-shell-fallback');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('ApiProcessor classifies logging envelope POST bodies as non-critical even on same-site paths', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-api-logging-envelope-'));
  try {
    const processor = new ApiProcessor(tempRoot, 'https://www.netflix.com');
    const result = await processor.generateArtifacts([
      {
        method: 'POST',
        url: 'https://help.netflix.com/cl2',
        pageUrl: 'https://www.netflix.com/kr-en/',
        resourceType: 'fetch',
        postData: JSON.stringify({
          currentState: {
            '1': {
              source: 'helpCenter',
              type: ['Log', 'Session'],
            },
            '2': {
              type: ['cs.HostLoggingSource'],
            },
          },
          reverseDeltas: [
            [
              {
                type: ['LoggerInitialized', 'DiscreteEvent'],
              },
            ],
            [
              {
                type: ['ViewportDimensions', 'DiscreteEvent'],
              },
            ],
          ],
          type: 'CompactConsolidatedLoggingEnvelope',
          version: 2,
        }),
        headers: { 'content-type': 'application/json' },
        responseStatus: 204,
        responseMimeType: 'application/json',
        responseBody: '',
      },
      {
        method: 'POST',
        url: 'https://www.netflix.com/bootstrap',
        pageUrl: 'https://www.netflix.com/kr-en/',
        resourceType: 'fetch',
        postData: JSON.stringify({ hero: true }),
        headers: { 'content-type': 'application/json' },
        responseStatus: 200,
        responseMimeType: 'application/json',
        responseBody: JSON.stringify({ ok: true }),
      },
    ], [], []);

    const loggingRequest = result.filteredRequests.find((item) => item.pathname === '/cl2');
    const bootstrapRequest = result.filteredRequests.find((item) => item.pathname === '/bootstrap');

    assert.equal(loggingRequest.replayRole, 'non-critical');
    assert.equal(loggingRequest.expectedForReplay, false);
    assert.equal(result.renderCriticalCandidates.some((item) => item.path === '/cl2'), false);
    assert.equal(bootstrapRequest.renderCriticalKind, 'render-critical-bootstrap');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('ApiProcessor sanitizes render-supporting mock bodies and tags manifest entries', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-api-sanitize-'));
  try {
    const pageSignals = new Map([
      [normalizeCrawlUrl('https://example.com'), {
        hasInlineBootstrapState: true,
        hasUserInfoModel: true,
        hasMembershipStatusFallback: true,
        hasSessionStateFallback: false,
      }],
    ]);
    const processor = new ApiProcessor(tempRoot, 'https://example.com', 'registrable-domain', pageSignals);
    const result = await processor.generateArtifacts([
      {
        method: 'POST',
        url: 'https://example.com/graphql',
        pageUrl: 'https://example.com',
        resourceType: 'fetch',
        postData: JSON.stringify({
          operationName: 'MembershipStatus',
          variables: {},
          extensions: { persistedQuery: { version: 1, sha256Hash: 'abc' } },
        }),
        headers: { 'content-type': 'application/json' },
        responseStatus: 200,
        responseMimeType: 'application/json',
        responseBody: JSON.stringify({ data: { userId: 99999, email: 'test@live.com', membershipStatus: 'ACTIVE' } }),
      },
    ], [], []);

    const manifestEntry = result.httpManifest[0];
    assert.equal(manifestEntry.sanitized, true);
    assert.ok(manifestEntry.sanitizedFields.length > 0);

    const mockFilePath = path.join(tempRoot, 'server', manifestEntry.bodyFile);
    const mockContent = JSON.parse(await fs.readFile(mockFilePath, 'utf8'));
    assert.equal(mockContent.data.userId, 0);
    assert.equal(mockContent.data.email, 'user@example.com');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});

test('ApiProcessor does NOT sanitize render-critical mock bodies', async () => {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'front-clone-api-no-sanitize-'));
  try {
    const processor = new ApiProcessor(tempRoot, 'https://example.com');
    const result = await processor.generateArtifacts([
      {
        method: 'POST',
        url: 'https://example.com/bootstrap',
        pageUrl: 'https://example.com',
        resourceType: 'fetch',
        postData: JSON.stringify({ init: true }),
        headers: { 'content-type': 'application/json' },
        responseStatus: 200,
        responseMimeType: 'application/json',
        responseBody: JSON.stringify({ userId: 99999, email: 'test@live.com' }),
      },
    ], [], []);

    const manifestEntry = result.httpManifest[0];
    assert.equal(manifestEntry.sanitized, false);

    const mockFilePath = path.join(tempRoot, 'server', manifestEntry.bodyFile);
    const mockContent = JSON.parse(await fs.readFile(mockFilePath, 'utf8'));
    assert.equal(mockContent.userId, 99999);
    assert.equal(mockContent.email, 'test@live.com');
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
});
