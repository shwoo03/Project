export function summarizeExternalRequests(detailMap) {
  const summary = {
    'render-critical-asset': 0,
    'render-critical-runtime': 0,
    'non-critical-runtime': 0,
    'anti-abuse': 0,
  };

  for (const detail of detailMap.values()) {
    summary[detail.category] = (summary[detail.category] || 0) + 1;
  }

  return summary;
}

export function summarizeRuntimeErrors(pageResults = []) {
  return pageResults.reduce((summary, page) => {
    summary.consoleErrors += page.runtimeErrorSummary?.consoleErrors || 0;
    summary.runtimeExceptions += page.runtimeErrorSummary?.runtimeExceptions || 0;
    summary.failedRuntimeRequests += page.runtimeErrorSummary?.failedRuntimeRequests || 0;
    for (const [failureClass, count] of Object.entries(page.runtimeFailureClasses || {})) {
      summary.failureClasses[failureClass] = (summary.failureClasses[failureClass] || 0) + count;
    }
    if ((page.runtimeErrorSummary?.total || 0) > 0) {
      summary.pagesWithRuntimeErrors += 1;
    }
    if (page.runtimeFailureSeverity === 'soft') {
      summary.pagesWithSoftRuntimeDegrade += 1;
    }
    summary.total += page.runtimeErrorSummary?.total || 0;
    return summary;
  }, {
    consoleErrors: 0,
    runtimeExceptions: 0,
    failedRuntimeRequests: 0,
    pagesWithRuntimeErrors: 0,
    pagesWithSoftRuntimeDegrade: 0,
    total: 0,
    failureClasses: {},
  });
}

export function classifyRuntimeConsoleMessage(text, runtimeOrigin) {
  const normalized = String(text || '').trim();
  if (!normalized) {
    return { category: 'unknown', warningEligible: false };
  }

  const lower = normalized.toLowerCase();
  const hasExternalUrl = /https?:\/\//i.test(normalized) && !normalized.includes(runtimeOrigin);
  if ((/failed to load resource|net::err_|blocked by client|access to fetch/i.test(lower)) && hasExternalUrl) {
    return { category: 'external-runtime-noise', warningEligible: false };
  }

  if (/hydrat/i.test(lower)) {
    return { category: 'hydration-failure', warningEligible: true };
  }
  if (/chunk|loading chunk|importing a module script failed|module script/i.test(lower)) {
    return { category: 'chunk-load-failure', warningEligible: true };
  }

  return { category: 'runtime-console-error', warningEligible: true };
}

export function buildRuntimeDiagnostics({
  consoleErrors = [],
  runtimeExceptions = [],
  failedRuntimeRequests = [],
  runtimeGuardState = null,
  runtimeOrigin = '',
}) {
  const sameOriginRuntimeExceptions = dedupeRuntimeExceptions([
    ...runtimeExceptions.map((entry) => ({
      ...entry,
      source: entry.source || 'pageerror',
      sameOrigin: true,
      failureClass: classifySameOriginRuntimeException(entry),
    })),
    ...((runtimeGuardState?.exceptions || []).map((entry) => ({
      ...entry,
      sameOrigin: entry.sameOrigin !== false,
      failureClass: entry.failureClass || classifySameOriginRuntimeException(entry),
    }))),
  ]);

  const sameOriginRuntimeMisses = dedupeRuntimeRequests([
    ...failedRuntimeRequests.map((entry) => classifyRuntimeRequestFailure(entry, runtimeOrigin)),
    ...((runtimeGuardState?.resourceErrors || []).map((entry) => classifyRuntimeRequestFailure(entry, runtimeOrigin))),
  ].filter((entry) => entry.sameOrigin));

  const failureClasses = summarizeRuntimeFailureClasses(sameOriginRuntimeExceptions, sameOriginRuntimeMisses);
  const summary = {
    consoleErrors: consoleErrors.length,
    runtimeExceptions: sameOriginRuntimeExceptions.length,
    failedRuntimeRequests: sameOriginRuntimeMisses.length,
    total: consoleErrors.length + sameOriginRuntimeExceptions.length + sameOriginRuntimeMisses.length,
  };
  const warningCodes = [];

  if (consoleErrors.some((entry) => entry.warningEligible !== false)) {
    warningCodes.push('runtime-console-error');
  }
  if (sameOriginRuntimeExceptions.length > 0) {
    warningCodes.push('runtime-exception');
  }
  if (sameOriginRuntimeMisses.some((entry) => entry.failureClass === 'runtime-script-failed')) {
    warningCodes.push('runtime-script-failed');
  } else if (sameOriginRuntimeMisses.some((entry) => entry.failureClass === 'runtime-style-failed')) {
    warningCodes.push('runtime-style-failed');
  } else if (sameOriginRuntimeMisses.some((entry) => entry.failureClass !== 'runtime-resource-missing')) {
    warningCodes.push('runtime-request-failed');
  }

  return {
    consoleErrors,
    runtimeExceptions: sameOriginRuntimeExceptions,
    failedRuntimeRequests: sameOriginRuntimeMisses,
    sameOriginRuntimeExceptions,
    sameOriginRuntimeMisses,
    failureClasses,
    summary,
    warningCodes,
  };
}

export function classifySameOriginRuntimeException(entry = {}) {
  const lower = String(entry?.message || '').toLowerCase();
  if (/(cannot (set|read) properties of null|cannot (set|read) properties of undefined|null is not an object|undefined is not an object|appendchild|removechild|insertbefore|queryselector)/.test(lower)) {
    return 'runtime-dom-assumption';
  }
  if (/chunk|module script|loading chunk|importing a module script failed/.test(lower)) {
    return 'runtime-script-failed';
  }
  return 'runtime-exception';
}

export function classifyRuntimeRequestFailure(entry = {}, runtimeOrigin = '') {
  const url = String(entry.url || '');
  const parsed = safeParseUrl(url);
  const sameOrigin = entry.sameOrigin ?? Boolean(parsed && parsed.origin === runtimeOrigin);
  const resourceType = String(entry.resourceType || '').toLowerCase();
  const mimeHint = String(entry.mimeType || entry.responseMimeType || '').toLowerCase();
  const pathLower = parsed ? parsed.pathname.toLowerCase() : '';

  let failureClass = entry.failureClass || 'runtime-resource-missing';
  if (sameOrigin) {
    if (resourceType === 'script' || resourceType === 'module') {
      failureClass = 'runtime-script-failed';
    } else if (resourceType === 'stylesheet' || resourceType === 'style') {
      failureClass = 'runtime-style-failed';
    } else if (resourceType === 'fetch' || resourceType === 'xhr' || mimeHint.includes('json') || mimeHint.includes('xml') || /\.(json|xml|api)\b/.test(pathLower)) {
      failureClass = 'runtime-data-miss';
    } else if (resourceType === 'image' || resourceType === 'font' || /\.(png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|otf)\b/.test(pathLower)) {
      failureClass = 'runtime-asset-miss';
    } else if (!entry.failureClass) {
      failureClass = 'runtime-resource-missing';
    }
  }

  return {
    ...entry,
    url,
    sameOrigin,
    resourceType: resourceType || 'resource',
    failureClass,
  };
}

function summarizeRuntimeFailureClasses(runtimeExceptions = [], runtimeMisses = []) {
  const summary = {};
  for (const entry of [...runtimeExceptions, ...runtimeMisses]) {
    const failureClass = String(entry.failureClass || '').trim();
    if (!failureClass) continue;
    summary[failureClass] = (summary[failureClass] || 0) + 1;
  }
  return summary;
}

function dedupeRuntimeRequests(requests = []) {
  const seen = new Set();
  const deduped = [];
  for (const request of requests) {
    const key = `${request.resourceType || ''}|${request.status || ''}|${request.url || ''}|${request.failureText || ''}|${request.failureClass || ''}|${request.sameOrigin ? 'same' : 'cross'}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(request);
  }
  return deduped;
}

function dedupeRuntimeExceptions(exceptions = []) {
  const seen = new Set();
  const deduped = [];
  for (const entry of exceptions) {
    const key = `${entry.name || ''}|${entry.message || ''}|${entry.source || ''}|${entry.failureClass || ''}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(entry);
  }
  return deduped;
}

export function assessRuntimeFailureState({
  routeReached = false,
  criticalLocatorPresent = false,
  expectedRenderCritical = [],
  runtimeDiagnostics = {},
}) {
  const hasStrictDependencies = (expectedRenderCritical || []).length > 0;
  const exceptionClasses = new Set((runtimeDiagnostics.sameOriginRuntimeExceptions || []).map((entry) => entry.failureClass));
  const missClasses = new Set((runtimeDiagnostics.sameOriginRuntimeMisses || []).map((entry) => entry.failureClass));
  const hasDomAssumption = exceptionClasses.has('runtime-dom-assumption');
  const hasScriptFailure = exceptionClasses.has('runtime-script-failed') || missClasses.has('runtime-script-failed');
  const hasStyleFailure = missClasses.has('runtime-style-failed');
  const hasResourceMiss = missClasses.has('runtime-resource-missing');
  const hasDataMiss = missClasses.has('runtime-data-miss');
  const hasAssetMiss = missClasses.has('runtime-asset-miss');
  const hasOnlySoftMisses = !hasResourceMiss && !hasScriptFailure && !hasStyleFailure && (hasDataMiss || hasAssetMiss);

  if (!routeReached) {
    return {
      assessment: 'route-failed',
      severity: 'high',
      scope: 'page',
      suspectedFailureChain: 'route-unreachable',
    };
  }

  if (hasScriptFailure) {
    return {
      assessment: 'runtime-script-degraded',
      severity: 'high',
      scope: 'page',
      suspectedFailureChain: hasDomAssumption ? 'script-led-runtime-failure' : 'script-runtime-failure',
    };
  }

  if (hasStyleFailure) {
    return {
      assessment: 'runtime-style-degraded',
      severity: criticalLocatorPresent ? 'medium' : 'high',
      scope: criticalLocatorPresent ? 'widget' : 'page',
      suspectedFailureChain: 'style-runtime-failure',
    };
  }

  if (hasDomAssumption) {
    const softEligible = criticalLocatorPresent && !hasStrictDependencies;
    const dataOrAssetLed = hasOnlySoftMisses && !hasResourceMiss;
    return {
      assessment: softEligible ? 'runtime-widget-soft-fail' : 'runtime-page-degraded',
      severity: softEligible ? 'soft' : 'high',
      scope: softEligible ? 'widget' : 'page',
      suspectedFailureChain: hasResourceMiss
        ? 'resource-led-dom-assumption'
        : dataOrAssetLed
          ? 'data-or-asset-led-dom-assumption'
          : 'isolated-dom-assumption',
    };
  }

  if (hasResourceMiss) {
    return {
      assessment: 'runtime-resource-soft-miss',
      severity: 'soft',
      scope: 'widget',
      suspectedFailureChain: 'resource-soft-miss',
    };
  }

  if (hasDataMiss || hasAssetMiss) {
    return {
      assessment: 'runtime-resource-soft-miss',
      severity: 'soft',
      scope: 'widget',
      suspectedFailureChain: hasDataMiss ? 'data-soft-miss' : 'asset-soft-miss',
    };
  }

  if ((runtimeDiagnostics.summary?.total || 0) > 0) {
    return {
      assessment: 'runtime-warning-only',
      severity: 'low',
      scope: 'unknown',
      suspectedFailureChain: 'warning-only',
    };
  }

  return {
    assessment: 'runtime-clean',
    severity: 'none',
    scope: 'none',
    suspectedFailureChain: 'none',
  };
}

function safeParseUrl(value) {
  try {
    return new URL(value);
  } catch {
    return null;
  }
}
