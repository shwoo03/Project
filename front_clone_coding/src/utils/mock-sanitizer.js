import { SANITIZER_MAX_DEPTH, SANITIZER_MAX_FIELDS } from './constants.js';

const TIER1_KEY_PATTERN = /^(user_?id|member_?id|account_?id|profile_?id|subscriber_?id|viewer_?id|customer_?id|session_?id|auth_?token|access_?token|refresh_?token|csrf_?token|xsrf_?token|session_?token|bearer_?token|jwt|api_?key|secret|password|passwd|credential)$/i;

const TIER2_KEY_PATTERN = /(?:^|[._-])(email|phone|mobile|address|street|zip|postal|ssn|birth|dob|avatar|photo|profile_?url|display_?name|full_?name|first_?name|last_?name|nick_?name|screen_?name|username|login_?name|last_?login|logged_?in_?at|expires_?at|issued_?at|member(?:ship)?_?status|auth_?status|login_?status)(?:$|[._-])/i;

const TIER3_KEY_PATTERN = /(?:^|[._-])(session|token|cookie|auth|csrf|xsrf|nonce|signature)(?:$|[._-])/i;

const VALUE_HEURISTICS = [
  { name: 'email', test: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, strength: 'strong' },
  { name: 'jwt', test: /^eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/, strength: 'strong' },
  { name: 'uuid', test: /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i, strength: 'strong' },
  { name: 'long-hex', test: /^[0-9a-f]{24,}$/i, strength: 'medium' },
  { name: 'long-base64', test: /^[A-Za-z0-9+/=]{40,}$/, strength: 'medium' },
  { name: 'phone', test: /^\+?[0-9\s()-]{7,20}$/, strength: 'medium' },
];

const STRENGTH_ORDER = { strong: 3, medium: 2, weak: 1 };

function _getValueHeuristic(value) {
  if (typeof value === 'string' && value.length >= 2) {
    for (const heuristic of VALUE_HEURISTICS) {
      if (heuristic.test.test(value)) return heuristic;
    }
  }
  if (typeof value === 'number' && Number.isInteger(value) && value > 1000) {
    return { name: 'numeric-id', strength: 'weak' };
  }
  return null;
}

function _getPlaceholder(value, heuristic) {
  if (!heuristic) {
    if (typeof value === 'number') return 0;
    return '[sanitized]';
  }
  switch (heuristic.name) {
    case 'email': return 'user@example.com';
    case 'jwt': return 'eyJwbGFjZWhvbGRlciI6dHJ1ZX0.placeholder.signature';
    case 'uuid': return '00000000-0000-0000-0000-000000000000';
    case 'long-hex': return '0'.repeat(String(value).length);
    case 'long-base64': return 'A'.repeat(String(value).length - 2) + '==';
    case 'phone': return '+0-000-000-0000';
    case 'numeric-id': return 0;
    default: return '[sanitized]';
  }
}

function _shouldSanitize(key, value) {
  if (value === null || value === undefined || typeof value === 'boolean') return false;
  if (typeof value === 'string' && value.length < 2) return false;
  if (typeof value === 'number' && (value === 0 || value === 1)) return false;
  if (typeof value === 'string' && /^https?:\/\//.test(value)) return false;

  const heuristic = _getValueHeuristic(value);

  if (TIER1_KEY_PATTERN.test(key)) return true;
  if (TIER2_KEY_PATTERN.test(key)) {
    return heuristic !== null;
  }
  if (TIER3_KEY_PATTERN.test(key)) {
    return heuristic !== null && STRENGTH_ORDER[heuristic.strength] >= STRENGTH_ORDER.medium;
  }
  return false;
}

function _walkAndSanitize(value, path, sanitizedFields, visited, depth) {
  if (depth > SANITIZER_MAX_DEPTH) return value;
  if (sanitizedFields.length >= SANITIZER_MAX_FIELDS) return value;
  if (value === null || value === undefined || typeof value !== 'object') return value;
  if (visited.has(value)) return value;
  visited.add(value);

  if (Array.isArray(value)) {
    return value.map((item, i) => _walkAndSanitize(item, `${path}[${i}]`, sanitizedFields, visited, depth + 1));
  }

  const result = {};
  for (const [key, val] of Object.entries(value)) {
    const fieldPath = `${path}.${key}`;
    if (_shouldSanitize(key, val)) {
      const heuristic = _getValueHeuristic(val);
      result[key] = _getPlaceholder(val, heuristic);
      sanitizedFields.push(fieldPath);
    } else if (val !== null && typeof val === 'object') {
      result[key] = _walkAndSanitize(val, fieldPath, sanitizedFields, visited, depth + 1);
    } else {
      result[key] = val;
    }
  }
  return result;
}

export function sanitizeResponseBody(responseEnvelope, { replayRole } = {}) {
  const noChange = { body: responseEnvelope, sanitized: false, sanitizedFields: [] };
  if (replayRole !== 'render-supporting') return noChange;
  if (responseEnvelope === null || responseEnvelope === undefined || typeof responseEnvelope !== 'object') return noChange;

  const sanitizedFields = [];
  const body = _walkAndSanitize(responseEnvelope, '$', sanitizedFields, new WeakSet(), 0);
  return {
    body,
    sanitized: sanitizedFields.length > 0,
    sanitizedFields,
  };
}
