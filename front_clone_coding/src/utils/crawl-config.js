export const DEFAULT_CRAWL_PROFILE = 'accurate';
export const DEFAULT_NETWORK_POSTURE = 'default';

const PROFILE_SETTINGS = {
  accurate: {
    name: 'accurate',
    linkBudget: 30,
    formHeavyLinkBudget: 20,
    spaLinkBudget: 40,
    replayValidationSampleSize: 3,
    waitMultiplier: 1.3,
    screenshot: true,
  },
  balanced: {
    name: 'balanced',
    linkBudget: 20,
    formHeavyLinkBudget: 12,
    spaLinkBudget: 24,
    replayValidationSampleSize: 2,
    waitMultiplier: 1,
    screenshot: false,
  },
  lightweight: {
    name: 'lightweight',
    linkBudget: 10,
    formHeavyLinkBudget: 8,
    spaLinkBudget: 12,
    replayValidationSampleSize: 1,
    waitMultiplier: 0.75,
    screenshot: false,
  },
  authenticated: {
    name: 'authenticated',
    linkBudget: 28,
    formHeavyLinkBudget: 18,
    spaLinkBudget: 32,
    replayValidationSampleSize: 3,
    waitMultiplier: 1.2,
    screenshot: true,
  },
};

const NETWORK_POSTURES = {
  default: {
    name: 'default',
    waitMultiplier: 1,
    retryBudget: 1,
  },
  authenticated: {
    name: 'authenticated',
    waitMultiplier: 1.15,
    retryBudget: 1,
  },
  'sensitive-site': {
    name: 'sensitive-site',
    waitMultiplier: 1.4,
    retryBudget: 2,
  },
  'manual-review': {
    name: 'manual-review',
    waitMultiplier: 1.6,
    retryBudget: 2,
  },
};

export function resolveCrawlProfile(profile) {
  return PROFILE_SETTINGS[profile] || PROFILE_SETTINGS[DEFAULT_CRAWL_PROFILE];
}

export function resolveNetworkPosture(posture) {
  return NETWORK_POSTURES[posture] || NETWORK_POSTURES[DEFAULT_NETWORK_POSTURE];
}

export function getEffectiveWaitTime(waitTime, crawlProfile, networkPosture) {
  const profile = resolveCrawlProfile(crawlProfile);
  const posture = resolveNetworkPosture(networkPosture);
  return Math.max(0, Math.round((waitTime || 0) * profile.waitMultiplier * posture.waitMultiplier));
}

export function classifyResource(url, mimeType = '', resourceType = '') {
  const lowerMime = String(mimeType || '').toLowerCase();
  const lowerType = String(resourceType || '').toLowerCase();
  const lowerUrl = String(url || '').toLowerCase();

  if (
    lowerType === 'stylesheet' ||
    lowerType === 'script' ||
    lowerType === 'font' ||
    lowerMime.includes('css') ||
    lowerMime.includes('javascript') ||
    lowerMime.startsWith('font/')
  ) {
    return {
      resourceClass: 'critical-render',
      replayCriticality: 'high',
    };
  }

  if (
    lowerType === 'xhr' ||
    lowerType === 'fetch' ||
    lowerUrl.includes('graphql') ||
    lowerMime.includes('json')
  ) {
    return {
      resourceClass: 'runtime-dependent',
      replayCriticality: 'high',
    };
  }

  return {
    resourceClass: 'passive-static',
    replayCriticality: lowerMime.startsWith('image/') ? 'medium' : 'low',
  };
}

export function classifyPageSnapshot(snapshot, finalUrl, options = {}) {
  const routeCount = snapshot.routeCount || 0;
  const formCount = snapshot.forms?.length || 0;
  const interactiveCount = snapshot.interactiveElements?.length || 0;
  const imageCount = snapshot.liveImageUrls?.length || 0;
  const scriptCount = snapshot.scriptCount || 0;
  const hasPasswordForm = snapshot.forms?.some((form) => form.hasPassword) || false;

  const flags = [];
  if (routeCount > 1) flags.push('spa-routes');
  if (hasPasswordForm) flags.push('auth-form');
  if (interactiveCount >= 10) flags.push('interactive-heavy');
  if (imageCount >= 12) flags.push('media-heavy');
  if (scriptCount >= 8) flags.push('script-heavy');

  const highValue = routeCount > 1 || hasPasswordForm || interactiveCount >= 10 || imageCount >= 12;
  const pageClass = hasPasswordForm
    ? 'auth-interactive'
    : routeCount > 1
      ? 'spa-route-heavy'
      : imageCount >= 12
        ? 'media-heavy'
        : 'document';

  const profile = resolveCrawlProfile(options.crawlProfile);
  const queueBudget = hasPasswordForm
    ? profile.formHeavyLinkBudget
    : routeCount > 1
      ? profile.spaLinkBudget
      : profile.linkBudget;

  return {
    pageClass,
    highValue,
    shouldRunReplayValidation: Boolean(options.enableRepresentativeQA) && highValue,
    shouldExpandSpaRoutes: routeCount > 1,
    shouldCaptureScreenshot: Boolean(options.takeScreenshot || profile.screenshot),
    queueBudget,
    routeCount,
    formCount,
    interactiveCount,
    imageCount,
    scriptCount,
    flags,
    finalUrl,
  };
}
