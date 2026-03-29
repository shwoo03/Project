import test from 'node:test';
import assert from 'node:assert/strict';

import {
  assessContentComparison,
  assessRuntimeFailureState,
  computeTokenOverlap,
  classifySameOriginRuntimeException,
  classifyRuntimeRequestFailure,
  classifyRuntimeConsoleMessage,
  assessTitleComparison,
} from '../src/verifier/replay-verifier.js';

// --- computeTokenOverlap ---

test('computeTokenOverlap returns 1 for identical token sets', () => {
  assert.equal(computeTokenOverlap(['hello', 'world'], ['hello', 'world']), 1);
});

test('computeTokenOverlap returns 0 for disjoint token sets', () => {
  assert.equal(computeTokenOverlap(['hello', 'world'], ['foo', 'bar']), 0);
});

test('computeTokenOverlap returns partial overlap ratio', () => {
  const overlap = computeTokenOverlap(['a', 'b', 'c', 'd'], ['a', 'b', 'x', 'y']);
  assert.equal(overlap, 0.5);
});

test('computeTokenOverlap returns 1 when expected is empty (nothing to miss)', () => {
  assert.equal(computeTokenOverlap([], ['a', 'b']), 1);
});

// --- classifySameOriginRuntimeException ---

test('classifySameOriginRuntimeException identifies DOM assumption from null property access', () => {
  assert.equal(
    classifySameOriginRuntimeException({ message: "Cannot read properties of null (reading 'src')" }),
    'runtime-dom-assumption',
  );
});

test('classifySameOriginRuntimeException identifies DOM assumption from appendChild', () => {
  assert.equal(
    classifySameOriginRuntimeException({ message: 'Failed to execute appendChild on Node' }),
    'runtime-dom-assumption',
  );
});

test('classifySameOriginRuntimeException identifies script failure from chunk loading', () => {
  assert.equal(
    classifySameOriginRuntimeException({ message: 'Loading chunk 42 failed' }),
    'runtime-script-failed',
  );
});

test('classifySameOriginRuntimeException identifies script failure from module import', () => {
  assert.equal(
    classifySameOriginRuntimeException({ message: 'Importing a module script failed' }),
    'runtime-script-failed',
  );
});

test('classifySameOriginRuntimeException returns generic exception for unknown errors', () => {
  assert.equal(
    classifySameOriginRuntimeException({ message: 'TypeError: x is not a function' }),
    'runtime-exception',
  );
});

// --- classifyRuntimeRequestFailure ---

test('classifyRuntimeRequestFailure classifies same-origin script as runtime-script-failed', () => {
  const result = classifyRuntimeRequestFailure(
    { url: 'http://localhost:4000/app.js', resourceType: 'script' },
    'http://localhost:4000',
  );
  assert.equal(result.failureClass, 'runtime-script-failed');
  assert.equal(result.sameOrigin, true);
});

test('classifyRuntimeRequestFailure classifies same-origin fetch as runtime-data-miss', () => {
  const result = classifyRuntimeRequestFailure(
    { url: 'http://localhost:4000/api/data', resourceType: 'fetch' },
    'http://localhost:4000',
  );
  assert.equal(result.failureClass, 'runtime-data-miss');
});

test('classifyRuntimeRequestFailure classifies same-origin image as runtime-asset-miss', () => {
  const result = classifyRuntimeRequestFailure(
    { url: 'http://localhost:4000/logo.png', resourceType: 'image' },
    'http://localhost:4000',
  );
  assert.equal(result.failureClass, 'runtime-asset-miss');
});

test('classifyRuntimeRequestFailure classifies same-origin stylesheet as runtime-style-failed', () => {
  const result = classifyRuntimeRequestFailure(
    { url: 'http://localhost:4000/theme.css', resourceType: 'stylesheet' },
    'http://localhost:4000',
  );
  assert.equal(result.failureClass, 'runtime-style-failed');
});

test('classifyRuntimeRequestFailure keeps cross-origin default class', () => {
  const result = classifyRuntimeRequestFailure(
    { url: 'http://cdn.example.com/lib.js', resourceType: 'script' },
    'http://localhost:4000',
  );
  assert.equal(result.sameOrigin, false);
  assert.equal(result.failureClass, 'runtime-resource-missing');
});

test('classifyRuntimeRequestFailure classifies font path as runtime-asset-miss', () => {
  const result = classifyRuntimeRequestFailure(
    { url: 'http://localhost:4000/fonts/noto.woff2', resourceType: 'resource' },
    'http://localhost:4000',
  );
  assert.equal(result.failureClass, 'runtime-asset-miss');
});

test('classifyRuntimeRequestFailure classifies json path as runtime-data-miss', () => {
  const result = classifyRuntimeRequestFailure(
    { url: 'http://localhost:4000/config.json', resourceType: 'resource' },
    'http://localhost:4000',
  );
  assert.equal(result.failureClass, 'runtime-data-miss');
});

// --- classifyRuntimeConsoleMessage ---

test('classifyRuntimeConsoleMessage marks same-origin 404 as runtime-console-error', () => {
  const result = classifyRuntimeConsoleMessage(
    'Failed to load resource: the server responded with a status of 404 (Not Found) http://localhost:4000/missing.js',
    'http://localhost:4000',
  );
  // Same-origin errors are not classified as external-runtime-noise; they remain eligible warnings.
  assert.equal(result.category, 'runtime-console-error');
  assert.equal(result.warningEligible, true);
});

test('classifyRuntimeConsoleMessage marks cross-origin error as external-runtime-noise', () => {
  const result = classifyRuntimeConsoleMessage(
    'Failed to load resource: net::ERR_BLOCKED_BY_CLIENT https://cdn.analytics.com/tracker.js',
    'http://localhost:4000',
  );
  assert.equal(result.category, 'external-runtime-noise');
  assert.equal(result.warningEligible, false);
});

// --- assessRuntimeFailureState ---

test('assessRuntimeFailureState returns route-failed when route not reached', () => {
  const result = assessRuntimeFailureState({
    routeReached: false,
    criticalLocatorPresent: false,
    expectedRenderCritical: [],
    runtimeDiagnostics: {},
  });
  assert.equal(result.assessment, 'route-failed');
  assert.equal(result.severity, 'high');
});

test('assessRuntimeFailureState returns runtime-clean when no issues', () => {
  const result = assessRuntimeFailureState({
    routeReached: true,
    criticalLocatorPresent: true,
    expectedRenderCritical: [],
    runtimeDiagnostics: { summary: { total: 0 } },
  });
  assert.equal(result.assessment, 'runtime-clean');
  assert.equal(result.severity, 'none');
});

test('assessRuntimeFailureState returns runtime-script-degraded for script failures', () => {
  const result = assessRuntimeFailureState({
    routeReached: true,
    criticalLocatorPresent: true,
    expectedRenderCritical: [],
    runtimeDiagnostics: {
      sameOriginRuntimeExceptions: [{ failureClass: 'runtime-script-failed' }],
      sameOriginRuntimeMisses: [],
    },
  });
  assert.equal(result.assessment, 'runtime-script-degraded');
  assert.equal(result.severity, 'high');
});

test('assessRuntimeFailureState returns runtime-widget-soft-fail for DOM assumption with locator', () => {
  const result = assessRuntimeFailureState({
    routeReached: true,
    criticalLocatorPresent: true,
    expectedRenderCritical: [],
    runtimeDiagnostics: {
      sameOriginRuntimeExceptions: [{ failureClass: 'runtime-dom-assumption' }],
      sameOriginRuntimeMisses: [],
    },
  });
  assert.equal(result.assessment, 'runtime-widget-soft-fail');
  assert.equal(result.severity, 'soft');
  assert.equal(result.scope, 'widget');
});

test('assessRuntimeFailureState returns runtime-page-degraded for DOM assumption without locator', () => {
  const result = assessRuntimeFailureState({
    routeReached: true,
    criticalLocatorPresent: false,
    expectedRenderCritical: [],
    runtimeDiagnostics: {
      sameOriginRuntimeExceptions: [{ failureClass: 'runtime-dom-assumption' }],
      sameOriginRuntimeMisses: [],
    },
  });
  assert.equal(result.assessment, 'runtime-page-degraded');
  assert.equal(result.severity, 'high');
});

test('assessRuntimeFailureState returns runtime-resource-soft-miss for data-miss only', () => {
  const result = assessRuntimeFailureState({
    routeReached: true,
    criticalLocatorPresent: true,
    expectedRenderCritical: [],
    runtimeDiagnostics: {
      sameOriginRuntimeExceptions: [],
      sameOriginRuntimeMisses: [{ failureClass: 'runtime-data-miss' }],
    },
  });
  assert.equal(result.assessment, 'runtime-resource-soft-miss');
  assert.equal(result.severity, 'soft');
  assert.equal(result.suspectedFailureChain, 'data-soft-miss');
});

test('assessRuntimeFailureState returns runtime-style-degraded for stylesheet miss', () => {
  const result = assessRuntimeFailureState({
    routeReached: true,
    criticalLocatorPresent: true,
    expectedRenderCritical: [],
    runtimeDiagnostics: {
      sameOriginRuntimeExceptions: [],
      sameOriginRuntimeMisses: [{ failureClass: 'runtime-style-failed' }],
    },
  });
  assert.equal(result.assessment, 'runtime-style-degraded');
  assert.equal(result.severity, 'medium');
});

// --- assessTitleComparison ---

test('assessTitleComparison reports match for identical titles', () => {
  const result = assessTitleComparison('Hello World', 'Hello World');
  assert.equal(result.shouldWarn, false);
  assert.equal(result.mismatchLikelyEncodingNoise, false);
});

test('assessTitleComparison reports drift for different titles', () => {
  const result = assessTitleComparison('Original Title', 'Completely Different Title');
  assert.equal(result.shouldWarn, true);
});

test('assessTitleComparison handles empty titles gracefully', () => {
  const result = assessTitleComparison('', '');
  assert.equal(result.shouldWarn, false);
});

// --- assessContentComparison ---

test('assessContentComparison returns content-match for matching profiles', () => {
  const pageInfo = {
    title: 'Test Page',
    html: '<html><head><title>Test Page</title></head><body><main><h1>Welcome</h1><p>Content here about the test page that is long enough to be meaningful</p></main></body></html>',
  };
  const actualProfile = {
    title: 'Test Page',
    headingText: 'Welcome',
    mainText: 'Welcome Content here about the test page that is long enough to be meaningful',
    bodyText: 'Welcome Content here about the test page that is long enough to be meaningful',
    navTextLength: 0,
    footerTextLength: 0,
  };
  const result = assessContentComparison(pageInfo, actualProfile);
  assert.equal(result.contentDriftAssessment, 'content-match');
});

test('assessContentComparison returns high-confidence-content-gap for empty replay', () => {
  const pageInfo = {
    title: 'Test Page',
    html: '<html><head><title>Test Page</title></head><body><main><h1>Welcome</h1><p>Important content that exists only in the original page</p></main></body></html>',
  };
  const actualProfile = {
    title: 'Test Page',
    headingText: '',
    mainText: '',
    bodyText: '',
    navTextLength: 0,
    footerTextLength: 0,
  };
  const result = assessContentComparison(pageInfo, actualProfile);
  assert.equal(result.contentDriftAssessment, 'high-confidence-content-gap');
});
