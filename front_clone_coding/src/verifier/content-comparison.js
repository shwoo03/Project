import { load as loadHtml } from 'cheerio';

import {
  extractTextMarkers,
  looksLikeEncodingNoise,
  normalizeComparisonText,
} from '../utils/encoding-utils.js';
import {
  CONTENT_GAP_CEILING,
  PARTIAL_MATCH_CEILING,
  BOILERPLATE_DOMINANCE_RATIO,
  HEADING_MAIN_OVERLAP_FLOOR,
  LENGTH_DRIFT_FLOOR,
} from '../utils/constants.js';

export function assessContentComparison(pageInfo, actualProfile = {}) {
  const expectedProfile = buildExpectedContentProfile(pageInfo);
  const actualMarkers = {
    heading: extractTextMarkers(actualProfile.headingText || '', 24),
    main: extractTextMarkers(actualProfile.mainText || actualProfile.bodyText || '', 80),
    body: extractTextMarkers(actualProfile.bodyText || '', 120),
  };
  const overlap = {
    heading: computeTokenOverlap(expectedProfile.markers.heading, actualMarkers.heading),
    main: computeTokenOverlap(expectedProfile.markers.main, actualMarkers.main),
    body: computeTokenOverlap(expectedProfile.markers.body, actualMarkers.body),
  };
  const markerOverlapRatio = computeWeightedOverlap(overlap, expectedProfile.markers);
  const expectedBodyLength = expectedProfile.lengths.body;
  const boilerplateBytes = (actualProfile.navTextLength || 0) + (actualProfile.footerTextLength || 0);
  const actualBodyLength = String(actualProfile.bodyText || '').length;
  const boilerplateDominanceLikely = actualBodyLength > 0
    && boilerplateBytes / actualBodyLength >= BOILERPLATE_DOMINANCE_RATIO
    && overlap.main >= CONTENT_GAP_CEILING;

  let contentDriftAssessment = 'content-match';
  if (
    boilerplateDominanceLikely
    && (overlap.heading >= HEADING_MAIN_OVERLAP_FLOOR || overlap.main >= HEADING_MAIN_OVERLAP_FLOOR)
    && (
      overlap.body + LENGTH_DRIFT_FLOOR < overlap.main
      || computeLengthDrift(expectedBodyLength, actualBodyLength) >= LENGTH_DRIFT_FLOOR
    )
  ) {
    contentDriftAssessment = 'comparison-noise-likely';
  } else if (markerOverlapRatio < CONTENT_GAP_CEILING && overlap.main < CONTENT_GAP_CEILING && overlap.heading < CONTENT_GAP_CEILING) {
    contentDriftAssessment = 'high-confidence-content-gap';
  } else if (markerOverlapRatio < PARTIAL_MATCH_CEILING) {
    contentDriftAssessment = 'partial-content-match';
  }

  const contentComparisonConfidence = boilerplateDominanceLikely
    ? 'medium'
    : (expectedProfile.markers.main.length === 0 && expectedProfile.markers.heading.length === 0)
      ? 'low'
      : 'high';
  const titleComparison = assessTitleComparison(pageInfo.title || '', actualProfile.title || '');

  return {
    markerOverlapRatio,
    contentDriftAssessment,
    contentComparisonConfidence,
    boilerplateDominanceLikely,
    titleComparison,
    markerExtractionProfile: {
      expected: {
        headingMarkers: expectedProfile.markers.heading.length,
        mainMarkers: expectedProfile.markers.main.length,
        bodyMarkers: expectedProfile.markers.body.length,
      },
      actual: {
        headingMarkers: actualMarkers.heading.length,
        mainMarkers: actualMarkers.main.length,
        bodyMarkers: actualMarkers.body.length,
      },
      overlap,
      sourcesUsed: buildMarkerSourceList(expectedProfile),
    },
  };
}

export function buildExpectedContentProfile(pageInfo) {
  const html = pageInfo.processedHtml || pageInfo.decodedDocumentHtml || pageInfo.html || '';
  if (!html) {
    const title = pageInfo.title || '';
    return {
      markers: {
        heading: extractTextMarkers(title, 20),
        main: extractTextMarkers(title, 40),
        body: extractTextMarkers(title, 60),
      },
      lengths: {
        body: String(title).length,
      },
      sourcesUsed: ['title-fallback'],
    };
  }

  const $ = loadHtml(html, { decodeEntities: false });
  $('script, style, noscript').remove();
  const getTexts = (selectors, limit = 8) => selectors
    .flatMap((selector) => $(selector).slice(0, limit).toArray())
    .map((node) => $(node).text())
    .map((text) => text.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  const pickLongest = (selectors) => {
    const values = getTexts(selectors, 20).sort((left, right) => right.length - left.length);
    return values[0] || '';
  };

  const bodyText = ($('body').text() || $.root().text() || '').replace(/\s+/g, ' ').trim();
  const headingText = getTexts(['h1', 'h2', 'h3'], 8).join(' ');
  const mainText = pickLongest(['main', '[role="main"]', 'article', 'section']);

  return {
    markers: {
      heading: extractTextMarkers(`${pageInfo.title || ''} ${headingText}`, 24),
      main: extractTextMarkers(mainText || bodyText, 80),
      body: extractTextMarkers(`${pageInfo.title || ''} ${bodyText}`, 120),
    },
    lengths: {
      body: bodyText.length,
    },
    sourcesUsed: buildMarkerSourceList({
      headingText,
      mainText,
      bodyText,
    }),
  };
}

function buildMarkerSourceList(profile = {}) {
  const sources = [];
  if (profile.headingText || profile.markers?.heading?.length) sources.push('headings');
  if (profile.mainText || profile.markers?.main?.length) sources.push('main-content');
  if (profile.bodyText || profile.markers?.body?.length) sources.push('body-text');
  return sources.length > 0 ? sources : ['title-fallback'];
}

export function computeTokenOverlap(expected = [], actual = []) {
  if ((expected || []).length === 0) return 1;
  const actualSet = new Set((actual || []).map((token) => String(token).toLowerCase()));
  const hits = (expected || []).filter((token) => actualSet.has(String(token).toLowerCase())).length;
  return hits / expected.length;
}

function computeWeightedOverlap(overlap = {}, markers = {}) {
  const weights = [
    ['heading', 0.3],
    ['main', 0.5],
    ['body', 0.2],
  ];
  let totalWeight = 0;
  let score = 0;
  for (const [key, weight] of weights) {
    if ((markers[key] || []).length === 0) continue;
    totalWeight += weight;
    score += (overlap[key] || 0) * weight;
  }
  if (totalWeight === 0) return 1;
  return score / totalWeight;
}

function computeLengthDrift(expectedLength = 0, actualLength = 0) {
  if (!expectedLength) return 0;
  return Math.abs(actualLength - expectedLength) / expectedLength;
}

export function assessTitleComparison(expectedTitle = '', actualTitle = '') {
  const expectedNormalized = normalizeTitleForComparison(expectedTitle);
  const actualNormalized = normalizeTitleForComparison(actualTitle);
  const expectedNoise = looksLikeEncodingNoise(expectedTitle);
  const actualNoise = looksLikeEncodingNoise(actualTitle);
  const mismatchLikelyEncodingNoise = expectedNormalized !== actualNormalized && expectedNoise && actualNoise;

  return {
    normalizedExpected: expectedNormalized,
    normalizedActual: actualNormalized,
    confidence: mismatchLikelyEncodingNoise ? 'low' : (expectedNoise || actualNoise ? 'medium' : 'high'),
    mismatchLikelyEncodingNoise,
    shouldWarn: Boolean(expectedNormalized && actualNormalized && expectedNormalized !== actualNormalized && !mismatchLikelyEncodingNoise),
  };
}

function normalizeTitleForComparison(value = '') {
  return normalizeComparisonText(String(value || '')).toLowerCase();
}
