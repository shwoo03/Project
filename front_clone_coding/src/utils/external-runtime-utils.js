import { isInDomainScope } from './url-utils.js';

const NON_CRITICAL_RUNTIME_PATTERNS = [
  /telemetry/i,
  /tracking/i,
  /metrics?/i,
  /analytics?/i,
  /beacon/i,
  /logger/i,
  /logging/i,
  /impress/i,
  /exposure/i,
  /clicklog/i,
  /nlog/i,
  /adtech/i,
  /\bads?\b/i,
  /pixel/i,
  /conversion/i,
  /collect/i,
  /\blogs?\b/i,
  /doubleclick/i,
  /googleadservices/i,
  /googlesyndication/i,
  /facebook\.com\/tr/i,
  /tiktok/i,
  /snapchat/i,
  /taboola/i,
  /outbrain/i,
  /segment/i,
  /newrelic/i,
  /sentry/i,
];

const ANTI_ABUSE_PATTERNS = [
  /recaptcha/i,
  /\bcaptcha\b/i,
  /challenge/i,
  /arkoselabs/i,
  /hcaptcha/i,
  /\bbot\b/i,
  /shield/i,
];

const RENDER_CRITICAL_RUNTIME_PATTERNS = [
  /graphql/i,
  /bootstrap/i,
  /\broute\b/i,
  /prefetch/i,
  /\bfeed\b/i,
  /widget/i,
  /manifest/i,
  /_next\/data/i,
  /section/i,
];

export function classifyExternalRuntime(value, options = {}) {
  const rendered = String(value || '');
  const lower = rendered.toLowerCase();
  const pathname = getPathname(rendered).toLowerCase();
  const targetUrl = options.targetUrl || '';

  if (matchesAny(lower, ANTI_ABUSE_PATTERNS)) {
    return {
      category: 'anti-abuse',
      resourceHint: inferExternalResourceHint(pathname),
    };
  }

  if (matchesAny(lower, NON_CRITICAL_RUNTIME_PATTERNS)) {
    return {
      category: 'non-critical-runtime',
      resourceHint: inferExternalResourceHint(pathname),
    };
  }

  if (
    /\.(woff2?|ttf|otf|eot)(?:$|\?)/.test(pathname)
    || /\.(png|jpe?g|gif|webp|svg|avif)(?:$|\?)/.test(pathname)
    || /\.css(?:$|\?)/.test(pathname)
  ) {
    return {
      category: 'render-critical-asset',
      resourceHint: inferExternalResourceHint(pathname),
    };
  }

  if (matchesAny(lower, RENDER_CRITICAL_RUNTIME_PATTERNS)) {
    return {
      category: 'render-critical-runtime',
      resourceHint: inferExternalResourceHint(pathname),
    };
  }

  if (targetUrl && isHttpUrl(rendered) && isInDomainScope(rendered, targetUrl, 'registrable-domain')) {
    return {
      category: 'render-critical-runtime',
      resourceHint: inferExternalResourceHint(pathname),
    };
  }

  return {
    category: pathname.endsWith('.js') ? 'render-critical-runtime' : 'non-critical-runtime',
    resourceHint: inferExternalResourceHint(pathname),
  };
}

export function shouldStaticallyFilterRuntime(value, options = {}) {
  const classification = classifyExternalRuntime(value, options);
  return classification.category === 'anti-abuse' || classification.category === 'non-critical-runtime';
}

export function isAntiAbuseRuntime(value, options = {}) {
  return classifyExternalRuntime(value, options).category === 'anti-abuse';
}

export function isNonCriticalRuntime(value, options = {}) {
  return classifyExternalRuntime(value, options).category === 'non-critical-runtime';
}

export function inferExternalResourceHint(pathname = '') {
  if (/\.(woff2?|ttf|otf|eot)(?:$|\?)/.test(pathname)) return 'font';
  if (/\.(png|jpe?g|gif|webp|svg|avif)(?:$|\?)/.test(pathname)) return 'image';
  if (/\.css(?:$|\?)/.test(pathname)) return 'stylesheet';
  if (/\.js(?:$|\?)/.test(pathname)) return 'script';
  return 'request';
}

function matchesAny(value, patterns) {
  return patterns.some((pattern) => pattern.test(value));
}

function getPathname(value) {
  try {
    return new URL(value).pathname || '';
  } catch {
    return value;
  }
}

function isHttpUrl(value) {
  return /^https?:\/\//i.test(String(value || ''));
}
