import iconv from 'iconv-lite';
import logger from './logger.js';

const BOM_SIGNATURES = [
  { encoding: 'utf-8', bytes: [0xef, 0xbb, 0xbf] },
  { encoding: 'utf-16le', bytes: [0xff, 0xfe] },
  { encoding: 'utf-16be', bytes: [0xfe, 0xff] },
];

export function parseCharsetFromContentType(contentType = '') {
  const match = String(contentType || '').match(/charset=([^;]+)/i);
  return normalizeEncodingLabel(match ? match[1].trim() : '');
}

export function parseContentTypeInfo(contentType = '') {
  const raw = String(contentType || '').trim();
  const [mimeType] = raw.split(';');
  return {
    contentType: raw,
    mimeType: (mimeType || '').trim().toLowerCase(),
    charset: parseCharsetFromContentType(raw),
  };
}

export function detectBomEncoding(buffer) {
  if (!Buffer.isBuffer(buffer)) return null;
  for (const signature of BOM_SIGNATURES) {
    if (signature.bytes.every((byte, index) => buffer[index] === byte)) {
      return signature.encoding;
    }
  }
  return null;
}

export function detectHtmlEncoding(buffer, contentType = '') {
  return detectHtmlEncodingDetails(buffer, contentType).encoding;
}

export function detectHtmlEncodingDetails(buffer, contentType = '') {
  if (!Buffer.isBuffer(buffer) || buffer.length === 0) {
    return buildEncodingDecision({
      headerEncoding: parseCharsetFromContentType(contentType),
    });
  }

  const bomEncoding = detectBomEncoding(buffer);
  const headerEncoding = parseCharsetFromContentType(contentType);
  const headSnippet = buffer.slice(0, Math.min(buffer.length, 4096)).toString('latin1');
  const metaCharsetMatch = headSnippet.match(/<meta[^>]+charset=["']?\s*([^"'>\s/]+)/i);
  const httpEquivMatch = headSnippet.match(/<meta[^>]+content=["'][^"']*charset=([^"'>\s;]+)/i);

  return buildEncodingDecision({
    bomEncoding,
    headerEncoding,
    metaCharsetEncoding: metaCharsetMatch ? metaCharsetMatch[1] : null,
    httpEquivEncoding: httpEquivMatch ? httpEquivMatch[1] : null,
  });
}

export function detectCssEncoding(buffer, contentType = '') {
  return detectCssEncodingDetails(buffer, contentType).encoding;
}

export function detectCssEncodingDetails(buffer, contentType = '') {
  if (!Buffer.isBuffer(buffer) || buffer.length === 0) {
    return buildEncodingDecision({
      headerEncoding: parseCharsetFromContentType(contentType),
    });
  }

  const bomEncoding = detectBomEncoding(buffer);
  const headerEncoding = parseCharsetFromContentType(contentType);
  const snippet = buffer.slice(0, Math.min(buffer.length, 1024)).toString('latin1');
  const charsetMatch = snippet.match(/@charset\s+["']([^"']+)["']/i);

  return buildEncodingDecision({
    bomEncoding,
    headerEncoding,
    cssCharsetEncoding: charsetMatch ? charsetMatch[1] : null,
  });
}

export function analyzeTextDecoding(buffer, {
  resourceType = '',
  mimeType = '',
  contentType = '',
} = {}) {
  const normalizedType = String(resourceType || '').toLowerCase();
  const normalizedMimeType = String(mimeType || '').toLowerCase();

  let diagnosis;
  if (normalizedType === 'document' || normalizedMimeType.includes('html')) {
    diagnosis = detectHtmlEncodingDetails(buffer, contentType);
  } else if (normalizedType === 'stylesheet' || normalizedMimeType.includes('css')) {
    diagnosis = detectCssEncodingDetails(buffer, contentType);
  } else {
    diagnosis = buildEncodingDecision({
      headerEncoding: parseCharsetFromContentType(contentType),
    });
  }

  const decodeResult = decodeBufferWithEncoding(buffer, diagnosis.encoding || 'utf-8');
  if (decodeResult.fallbackUsed) {
    logger.debug(`Encoding fallback: requested '${diagnosis.encoding}', fell back to utf-8 (${normalizedType || normalizedMimeType})`);
  }
  return {
    ...diagnosis,
    decodedText: decodeResult.text,
    decodedEncoding: decodeResult.encoding,
    decodeFallbackUsed: decodeResult.fallbackUsed,
    decodeFallbackFrom: decodeResult.fallbackUsed ? diagnosis.encoding : null,
    decodeConfidence: decodeResult.fallbackUsed ? 'low' : diagnosis.decodeConfidence,
  };
}

export function decodeBufferWithEncoding(buffer, encoding = 'utf-8') {
  if (!Buffer.isBuffer(buffer)) {
    return {
      text: '',
      encoding: normalizeEncodingLabel(encoding) || 'utf-8',
      fallbackUsed: false,
    };
  }

  const normalized = normalizeEncodingLabel(encoding) || 'utf-8';
  try {
    if (iconv.encodingExists(normalized)) {
      return {
        text: iconv.decode(buffer, normalized),
        encoding: normalized,
        fallbackUsed: false,
      };
    }
  } catch {
    // fall through to utf-8
  }

  return {
    text: iconv.decode(buffer, 'utf-8'),
    encoding: 'utf-8',
    fallbackUsed: normalized !== 'utf-8',
  };
}

export function decodeWithEncoding(buffer, encoding = 'utf-8') {
  return decodeBufferWithEncoding(buffer, encoding).text;
}

function buildEncodingDecision({
  bomEncoding = null,
  headerEncoding = null,
  metaCharsetEncoding = null,
  httpEquivEncoding = null,
  cssCharsetEncoding = null,
  fallbackEncoding = 'utf-8',
} = {}) {
  const normalizedEvidence = {
    bomEncoding: normalizeEncodingLabel(bomEncoding),
    headerEncoding: normalizeEncodingLabel(headerEncoding),
    metaCharsetEncoding: normalizeEncodingLabel(metaCharsetEncoding),
    httpEquivEncoding: normalizeEncodingLabel(httpEquivEncoding),
    cssCharsetEncoding: normalizeEncodingLabel(cssCharsetEncoding),
  };

  const orderedEvidence = [
    ['bom', normalizedEvidence.bomEncoding],
    ['content-type', normalizedEvidence.headerEncoding],
    ['meta-charset', normalizedEvidence.metaCharsetEncoding],
    ['meta-http-equiv', normalizedEvidence.httpEquivEncoding],
    ['css-charset', normalizedEvidence.cssCharsetEncoding],
  ];

  const selected = orderedEvidence.find(([, value]) => value);
  const encoding = selected?.[1] || fallbackEncoding;
  const encodingSource = selected?.[0] || 'default';
  const nonEmptyEvidence = Object.values(normalizedEvidence).filter(Boolean);
  const suspectedEncodingMismatch = new Set(nonEmptyEvidence).size > 1;

  return {
    encoding,
    encodingSource,
    encodingEvidence: {
      ...normalizedEvidence,
      selectedEncoding: encoding,
      selectedSource: encodingSource,
    },
    decodeConfidence: encodingSource === 'default'
      ? 'low'
      : suspectedEncodingMismatch
        ? 'medium'
        : 'high',
    suspectedEncodingMismatch,
  };
}

export function summarizeEncodingDiagnosis(diagnosis = {}) {
  return {
    encoding: diagnosis.encoding || null,
    encodingSource: diagnosis.encodingSource || 'unknown',
    decodeConfidence: diagnosis.decodeConfidence || 'low',
    suspectedEncodingMismatch: Boolean(diagnosis.suspectedEncodingMismatch),
    encodingEvidence: diagnosis.encodingEvidence || {},
  };
}

export function normalizeEncodingLabel(label = '') {
  const value = String(label || '').trim().toLowerCase().replace(/["']/g, '');
  if (!value) return null;

  const aliases = new Map([
    ['utf8', 'utf-8'],
    ['utf-8', 'utf-8'],
    ['utf16', 'utf-16le'],
    ['utf-16', 'utf-16le'],
    ['utf-16le', 'utf-16le'],
    ['utf-16be', 'utf-16be'],
    ['latin1', 'latin1'],
    ['iso-8859-1', 'latin1'],
    ['euc-kr', 'euc-kr'],
    ['ks_c_5601-1987', 'euc-kr'],
    ['ksc5601', 'euc-kr'],
    ['cp949', 'cp949'],
    ['ms949', 'cp949'],
    ['shift_jis', 'shift_jis'],
    ['sjis', 'shift_jis'],
  ]);

  return aliases.get(value) || value;
}

export function normalizeComparisonText(text = '') {
  return String(text || '')
    .normalize('NFKC')
    .replace(/[\u200B-\u200D\uFEFF]/g, '')
    .replace(/[^\p{L}\p{N}\s-]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function looksLikeEncodingNoise(text = '') {
  const value = String(text || '').trim();
  if (!value) return false;
  if (value.includes('\uFFFD')) return true;

  const compact = value.replace(/\s+/g, '');
  const letterCount = [...compact].filter((char) => /\p{L}/u.test(char)).length;
  if (letterCount < 4) return false;

  const scripts = new Set();
  if (/[A-Za-z]/.test(compact)) scripts.add('latin');
  if (/[\uAC00-\uD7AF]/.test(compact)) scripts.add('hangul');
  if (/[\u4E00-\u9FFF]/.test(compact)) scripts.add('han');
  if (/[\u0400-\u04FF]/.test(compact)) scripts.add('cyrillic');
  if (/[\u3040-\u30FF]/.test(compact)) scripts.add('kana');

  const mojibakeMarkers = (compact.match(/[ÃÂÐÑØæåìëêíóú]/g) || []).length;
  const mixedScriptsLikelyNoise = compact.length >= 6 && scripts.size >= 3;
  return mojibakeMarkers >= 2 || mixedScriptsLikelyNoise;
}

export function extractTextMarkers(text = '', limit = 40, options = {}) {
  const resolvedLimit = typeof limit === 'object' && limit !== null
    ? Number(limit.limit ?? 40)
    : Number(limit ?? 40);
  const resolvedOptions = typeof limit === 'object' && limit !== null
    ? limit
    : options;
  const maxItems = Number.isFinite(resolvedLimit) && resolvedLimit > 0 ? resolvedLimit : 40;
  const normalizedText = normalizeComparisonText(text);
  const rawTokens = normalizedText
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);

  const tokenCounts = new Map();
  for (const token of rawTokens) {
    const key = token.toLowerCase();
    tokenCounts.set(key, (tokenCounts.get(key) || 0) + 1);
  }

  const seen = new Set();
  const markers = [];
  for (const token of rawTokens) {
    const lowered = token.toLowerCase();
    if (seen.has(lowered)) continue;
    seen.add(lowered);

    if (!isMeaningfulMarkerToken(token, tokenCounts.get(lowered) || 1, resolvedOptions)) {
      continue;
    }

    markers.push(token);
    if (markers.length >= maxItems) {
      break;
    }
  }

  return markers;
}

function isMeaningfulMarkerToken(token, occurrences, options = {}) {
  const value = String(token || '').trim();
  if (value.length < 2) return false;
  if (/^\d+$/.test(value)) return false;
  if (!/[\p{L}\p{N}]/u.test(value)) return false;

  const lowered = value.toLowerCase();
  const allowShortToken = new Set((options.allowShortTokens || []).map((entry) => String(entry).toLowerCase()));
  if (value.length < 3 && !allowShortToken.has(lowered) && !/\p{Script=Hangul}|\p{Script=Han}/u.test(value)) {
    return false;
  }

  if (occurrences >= 4 && value.length < 10) {
    return false;
  }

  const alphaNumericRatio = [...value].filter((char) => /[\p{L}\p{N}]/u.test(char)).length / value.length;
  if (alphaNumericRatio < 0.6) {
    return false;
  }

  return true;
}
