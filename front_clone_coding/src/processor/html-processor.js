import * as cheerio from 'cheerio';
import {
  resolveUrl,
  getRelativePath,
  getNormalizedPageIdentityUrl,
  isInDomainScope,
} from '../utils/url-utils.js';
import { normalizeAbsoluteRequestUrl } from '../utils/replay-mock-utils.js';
import { shouldStaticallyFilterRuntime } from '../utils/external-runtime-utils.js';
import logger from '../utils/logger.js';

const STATIC_NOOP_ENDPOINT = '/__front_clone_noop__';
const STATIC_NOOP_IMAGE = 'data:,';
const RUNTIME_GUARD_SCRIPT = '/__front_clone_runtime_guard__.js';

export default class HtmlProcessor {
  constructor(targetUrl, options = {}) {
    this.targetUrl = targetUrl;
    this.baseUrl = targetUrl;
    this.options = options;
    this.renderCriticalRuntimeMap = options.renderCriticalRuntimeMap || new Map();
    this.pageRouteIndex = options.pageRouteIndex || null;
    this.pagePathFallbackMap = options.pagePathFallbackMap || new Map();
  }

  process(html, urlMap, outputHtmlPath = 'index.html') {
    logger.start('HTML processing');

    const $ = cheerio.load(html, { decodeEntities: false });
    this._removeUnnecessary($);

    if (this.options.useBaseHref) {
      if ($('head base').length === 0) {
        $('head').prepend('  <base href="/">\n');
      } else {
        $('head base').attr('href', '/');
      }
    }

    this._replaceUrls($, urlMap, outputHtmlPath);

    if (!this.options.useBaseHref) {
      $('base').remove();
    }

    this._injectReplayRuntimeGuard($);
    this._preserveMetadata($);
    logger.succeed('HTML processing done');
    return $.html();
  }

  _getFinalLocalPath(localPath, outputHtmlPath) {
    if (this.options.useBaseHref) {
      let normalized = localPath.replace(/\\/g, '/');
      return normalized.startsWith('/') ? normalized : `/${normalized}`;
    }
    return getRelativePath(outputHtmlPath, localPath);
  }

  _getFinalNavigationPath(localPath, outputHtmlPath) {
    const replayRoutePath = this._toReplayRoutePath(localPath);
    return this._getFinalLocalPath(replayRoutePath, outputHtmlPath);
  }

  _removeUnnecessary($) {
    const trackingDomains = [
      'google-analytics.com',
      'googletagmanager.com',
      'google-analytics',
      'gtag',
      'fbevents',
      'facebook.net',
      'hotjar.com',
      'clarity.ms',
      'segment.com',
      'mixpanel.com',
      'amplitude.com',
    ];

    $('script').each((_, el) => {
      const src = $(el).attr('src') || '';
      const text = $(el).html() || '';
      if (src && shouldStaticallyFilterRuntime(src, { targetUrl: this.targetUrl })) {
        $(el).remove();
        return;
      }
      for (const domain of trackingDomains) {
        if (src.includes(domain) || text.includes(domain)) {
          $(el).remove();
          return;
        }
      }
    });

    $('iframe').each((_, el) => {
      const src = $(el).attr('src') || '';
      const title = $(el).attr('title') || '';
      const marker = `${src} ${title} ${$(el).attr('data-uia') || ''}`.trim();
      if (marker && shouldStaticallyFilterRuntime(marker, { targetUrl: this.targetUrl })) {
        $(el).remove();
      }
    });

    $('noscript').each((_, el) => {
      const markup = $(el).html() || '';
      if (!markup) return;
      const matches = markup.match(/https?:\/\/[^\s"'`<\\]+/g) || [];
      if (matches.some((value) => shouldStaticallyFilterRuntime(value, { targetUrl: this.targetUrl }))) {
        $(el).remove();
      }
    });

    $('.grecaptcha-badge, .g-recaptcha-response').remove();
    $('iframe').each((_, el) => {
      const src = $(el).attr('src') || '';
      const title = $(el).attr('title') || '';
      const name = $(el).attr('name') || '';
      const marker = `${src} ${title} ${name}`.trim();
      if (/recaptcha/i.test(marker)) {
        $(el).remove();
      }
    });
    $('textarea').each((_, el) => {
      const id = $(el).attr('id') || '';
      const name = $(el).attr('name') || '';
      const classes = $(el).attr('class') || '';
      if (/g-recaptcha-response/i.test(`${id} ${name} ${classes}`)) {
        $(el).remove();
      }
    });

    $('[id*="google_ads"]').remove();
    $('[class*="ad-container"]').remove();
    $('ins.adsbygoogle').remove();
  }

  _replaceUrls($, urlMap, outputHtmlPath) {
    const srcTags = ['img', 'script', 'iframe', 'video', 'audio', 'source', 'embed', 'input[type="image"]'];
    for (const tag of srcTags) {
      $(tag).each((_, el) => {
        this._replaceAttr($, el, 'src', urlMap, outputHtmlPath);
      });
    }

    $('link, a, area').each((_, el) => {
      this._replaceAttr($, el, 'href', urlMap, outputHtmlPath);
    });

    $('form').each((_, el) => {
      this._replaceAttr($, el, 'action', urlMap, outputHtmlPath);
    });

    $('option[value]').each((_, el) => {
      const value = $(el).attr('value');
      if (!this._looksLikeNavigationValue(value)) return;
      this._replaceAttr($, el, 'value', urlMap, outputHtmlPath);
    });

    $('img, source').each((_, el) => {
      const srcset = $(el).attr('srcset');
      if (!srcset) return;
      const newSrcset = srcset
        .split(',')
        .map((entry) => {
          const parts = entry.trim().split(/\s+/);
          const url = parts[0];
          const absoluteUrl = resolveUrl(url, this.baseUrl);
          const localPath = urlMap.get(absoluteUrl);
          if (localPath) parts[0] = this._getFinalLocalPath(localPath, outputHtmlPath);
          return parts.join(' ');
        })
        .join(', ');
      $(el).attr('srcset', newSrcset);
    });

    const dataAttrs = [
      'data-src', 'data-lazy-src', 'data-original', 'data-bg',
      'data-imagesrc', 'data-image-src', 'data-img-src',
      'data-poster', 'data-thumb', 'data-thumbnail', 'data-full-src',
    ];
    for (const attr of dataAttrs) {
      $(`[${attr}]`).each((_, el) => {
        this._replaceAttr($, el, attr, urlMap, outputHtmlPath);
      });
    }

    $('[data-srcset]').each((_, el) => {
      const srcset = $(el).attr('data-srcset');
      if (!srcset) return;
      const newSrcset = srcset.split(',').map((entry) => {
        const parts = entry.trim().split(/\s+/);
        const url = parts[0];
        const absoluteUrl = resolveUrl(url, this.baseUrl);
        const localPath = urlMap.get(absoluteUrl);
        if (localPath) parts[0] = this._getFinalLocalPath(localPath, outputHtmlPath);
        return parts.join(' ');
      }).join(', ');
      $(el).attr('data-srcset', newSrcset);
    });

    $('[style]').each((_, el) => {
      const style = $(el).attr('style');
      if (!style || !style.includes('url(')) return;
      const newStyle = style.replace(/url\((['"]?)([^)'"\r\n]+)\1\)/g, (match, quote, url) => {
        const absoluteUrl = resolveUrl(url, this.baseUrl);
        const localPath = urlMap.get(absoluteUrl);
        if (localPath) {
          return `url(${quote}${this._getFinalLocalPath(localPath, outputHtmlPath)}${quote})`;
        }
        return match;
      });
      $(el).attr('style', newStyle);
    });

    $('style').each((_, el) => {
      const css = $(el).html();
      if (!css || !css.includes('url(')) return;
      const newCss = css.replace(/url\((['"]?)([^)'"\r\n]+)\1\)/g, (match, quote, url) => {
        if (url.startsWith('data:')) return match;
        const absoluteUrl = resolveUrl(url, this.baseUrl);
        const localPath = urlMap.get(absoluteUrl);
        if (localPath) {
          return `url(${quote}${this._getFinalLocalPath(localPath, outputHtmlPath)}${quote})`;
        }
        return match;
      });
      $(el).html(newCss);
    });

    $('script:not([src])').each((_, el) => {
      const scriptText = $(el).html();
      if (!scriptText || !scriptText.includes('http')) return;

      const rewrittenScript = this._rewriteInlineScriptUrls(scriptText, urlMap, outputHtmlPath);
      if (rewrittenScript !== scriptText) {
        $(el).html(rewrittenScript);
      }
    });

    $('video').each((_, el) => {
      this._replaceAttr($, el, 'poster', urlMap, outputHtmlPath);
    });

    $('*').each((_, el) => {
      const attributes = el.attribs || {};
      for (const [attrName, attrValue] of Object.entries(attributes)) {
        if (!/^on/i.test(attrName) || !attrValue) continue;
        this._replaceHiddenNavigationAttr($, el, attrName, attrValue, urlMap, outputHtmlPath);
      }
    });

    this._annotateValueDrivenHiddenNavigation($);
  }

  _replaceAttr($, el, attr, urlMap, outputHtmlPath) {
    const value = $(el).attr(attr);
    if (!value) return;
    if (attr === 'href' && this._isJavascriptNavigationValue(value)) {
      this._replaceJavascriptHref($, el, value, urlMap, outputHtmlPath);
      return;
    }
    if (this._shouldPreserveUrlValue(value)) return;
    const absoluteUrl = resolveUrl(value, this.baseUrl);
    const resolvedTarget = this._resolveLocalPageOrAssetTarget(absoluteUrl, urlMap);
    if (resolvedTarget) {
      const replacement = resolvedTarget.kind === 'page'
        ? this._getFinalReplayRoute(resolvedTarget.route, outputHtmlPath)
        : this._isNavigationAttr(el, attr)
          ? this._getFinalNavigationPath(resolvedTarget.localPath, outputHtmlPath)
          : this._getFinalLocalPath(resolvedTarget.localPath, outputHtmlPath);
      $(el).attr(attr, replacement);
      this._stripLocalAssetIntegrity($, el);
      return;
    }

    if (this._shouldDisableNavigationTarget(el, attr)) {
      this._disableNavigationTarget($, el, attr, absoluteUrl);
    }
  }

  _shouldPreserveUrlValue(value) {
    return (
      value.startsWith('#') ||
      value.startsWith('mailto:') ||
      value.startsWith('tel:') ||
      value.startsWith('data:') ||
      value.startsWith('blob:')
    );
  }

  _shouldDisableNavigationTarget(el, attr) {
    const tagName = el.tagName?.toLowerCase();
    if (attr === 'href' && (tagName === 'a' || tagName === 'area')) {
      return true;
    }

    if (attr === 'action' && tagName === 'form') {
      return true;
    }

    if (attr === 'value' && tagName === 'option') {
      return true;
    }

    return false;
  }

  _isNavigationAttr(el, attr) {
    const tagName = el.tagName?.toLowerCase();
    return (attr === 'href' && (tagName === 'a' || tagName === 'area'))
      || (attr === 'action' && tagName === 'form')
      || (attr === 'value' && tagName === 'option');
  }

  _disableNavigationTarget($, el, attr, absoluteUrl) {
    const tagName = el.tagName?.toLowerCase();
    const reason = this._getDisabledReason(absoluteUrl);
    $(el).attr(attr, '#');
    $(el).attr('data-disabled-link', 'true');
    $(el).attr('data-disabled-reason', reason);

    if (tagName === 'form') {
      $(el).attr('onsubmit', 'return false;');
      return;
    }

    if (tagName === 'option') {
      $(el).attr('value', '');
      return;
    }

    $(el).attr('aria-disabled', 'true');
    $(el).removeAttr('target');
    $(el).attr('onclick', 'return false;');
  }

  _disableHiddenNavigationTarget($, el, attrName, reason, classification = '') {
    const tagName = el.tagName?.toLowerCase();
    $(el).attr('data-hidden-navigation-disabled', 'true');
    $(el).attr('data-disabled-link', 'true');
    $(el).attr('data-disabled-reason', reason);
    if (classification) {
      $(el).attr('data-hidden-navigation-class', classification);
    }

    if (tagName === 'form' || attrName === 'onsubmit') {
      $(el).attr('onsubmit', 'return false;');
      return;
    }

    if (tagName === 'option') {
      $(el).attr('value', '');
      return;
    }

    if ((tagName === 'a' || tagName === 'area') && $(el).attr('href')) {
      $(el).attr('href', '#');
    }

    $(el).attr('aria-disabled', 'true');
    $(el).removeAttr('target');
    $(el).attr(attrName, 'return false;');
  }

  _markLocalizedHiddenNavigation($, el, localizedCount, classification = '') {
    $(el).attr('data-hidden-navigation-localized', 'true');
    $(el).attr('data-hidden-navigation-count', String(localizedCount));
    $(el).removeAttr('data-hidden-navigation-disabled');
    $(el).removeAttr('data-disabled-link');
    $(el).removeAttr('data-disabled-reason');
    $(el).removeAttr('aria-disabled');
    if (classification) {
      $(el).attr('data-hidden-navigation-class', classification);
    }
  }

  _annotateValueDrivenHiddenNavigation($) {
    $('select[onchange], form[onsubmit]').each((_, el) => {
      const tagName = el.tagName?.toLowerCase();
      const attrName = tagName === 'form' ? 'onsubmit' : 'onchange';
      const handler = String($(el).attr(attrName) || '');
      if (!/(?:^|[^A-Za-z0-9_$])(?:value|this\.value|this\.form\b|form\.submit\b|window\.open\s*\(\s*value\b|location(?:\.href)?\s*=\s*(?:value|this\.options\b|document\.location\s*=\s*value)\b)/i.test(handler)) {
        return;
      }

      const replayableValueCount = $(el).find('option').toArray().filter((option) => {
        const value = String($(option).attr('value') || '');
        return Boolean(value) && !$(option).attr('data-disabled-link') && this._looksLikeNavigationValue(value);
      }).length;

      if (replayableValueCount > 0) {
        this._markLocalizedHiddenNavigation($, el, replayableValueCount, 'value-driven-navigation');
        return;
      }

      const disabledOptionCount = $(el).find('option[data-disabled-link="true"]').length;
      if (disabledOptionCount > 0) {
        this._disableHiddenNavigationTarget($, el, attrName, 'uncloned-target', 'value-driven-navigation');
      }
    });
  }

  _getDisabledReason(absoluteUrl) {
    if (!absoluteUrl || absoluteUrl === '#') {
      return 'uncloned-target';
    }

    if (isInDomainScope(absoluteUrl, this.targetUrl, this.options.domainScope || 'registrable-domain')) {
      return 'uncloned-target';
    }

    return 'external-target';
  }

  _resolveLocalPageOrAssetTarget(absoluteUrl, urlMap) {
    if (!absoluteUrl) return '';

    const pageRoute = this._resolvePageRoute(absoluteUrl);
    if (pageRoute) {
      return {
        kind: 'page',
        localPath: pageRoute.savedPath,
        route: pageRoute.replayRoute,
      };
    }

    const exactLocalPath = urlMap.get(absoluteUrl);
    if (exactLocalPath) {
      return { kind: 'asset', localPath: exactLocalPath };
    }

    const normalizedUrl = this._normalizeResolvedUrl(absoluteUrl);
    if (normalizedUrl && urlMap.get(normalizedUrl)) {
      return { kind: 'asset', localPath: urlMap.get(normalizedUrl) };
    }

    if (!isInDomainScope(absoluteUrl, this.targetUrl, this.options.domainScope || 'registrable-domain')) {
      return '';
    }

    const fallbackKey = this._getPageFallbackKey(absoluteUrl);
    const fallbackPath = fallbackKey ? this.pagePathFallbackMap.get(fallbackKey) || '' : '';
    return fallbackPath ? { kind: 'asset', localPath: fallbackPath } : '';
  }

  _resolvePageRoute(absoluteUrl) {
    if (!this.pageRouteIndex) return null;

    const exactRoute = this.pageRouteIndex.exactUrlMap?.get(absoluteUrl);
    if (exactRoute?.replayable) {
      return exactRoute;
    }

    const normalizedIdentityUrl = this._normalizeIdentityUrl(absoluteUrl);
    if (normalizedIdentityUrl) {
      const normalizedRoute = this.pageRouteIndex.normalizedIdentityMap?.get(normalizedIdentityUrl);
      if (normalizedRoute?.replayable) {
        return normalizedRoute;
      }
    }

    const fallbackKey = this._getPageFallbackKey(absoluteUrl);
    const fallbackRoute = fallbackKey ? this.pageRouteIndex.fallbackMap?.get(fallbackKey) : null;
    if (fallbackRoute?.replayable) {
      return fallbackRoute;
    }

    return null;
  }

  _normalizeResolvedUrl(value) {
    try {
      const url = new URL(value);
      url.hash = '';
      if (url.pathname !== '/' && url.pathname.endsWith('/')) {
        url.pathname = url.pathname.slice(0, -1);
      }
      return url.href;
    } catch {
      return value;
    }
  }

  _getPageFallbackKey(value) {
    try {
      const url = new URL(value);
      let pathname = url.pathname || '/';
      if (pathname !== '/' && pathname.endsWith('/')) {
        pathname = pathname.slice(0, -1);
      }
      return `${url.hostname}${pathname}`;
    } catch {
      return '';
    }
  }

  _normalizeIdentityUrl(value) {
    return getNormalizedPageIdentityUrl(value);
  }

  _getFinalReplayRoute(replayRoute, outputHtmlPath) {
    if (!replayRoute) {
      return this._getFinalLocalPath('index.html', outputHtmlPath);
    }

    if (this.options.useBaseHref) {
      const normalized = replayRoute.replace(/\\/g, '/');
      return normalized.startsWith('/') ? normalized : `/${normalized}`;
    }

    return replayRoute;
  }

  _looksLikeNavigationValue(value) {
    const candidate = String(value || '').trim();
    return /^https?:/i.test(candidate)
      || candidate.startsWith('/')
      || candidate.startsWith('./')
      || candidate.startsWith('../')
      || candidate.startsWith('?')
      || this._looksLikeRelativeNavigationValue(candidate);
  }

  _isJavascriptNavigationValue(value) {
    return /^javascript:/i.test(String(value || ''));
  }

  _replaceJavascriptHref($, el, value, urlMap, outputHtmlPath) {
    const scriptBody = String(value || '').replace(/^javascript:/i, '');
    const result = this._rewriteHiddenNavigationScript(scriptBody, urlMap, outputHtmlPath);

    if (result.disabledReason) {
      this._disableHiddenNavigationTarget($, el, 'onclick', result.disabledReason, result.classification);
      $(el).attr('href', '#');
      return;
    }

    if (result.primaryNavigationTarget) {
      $(el).attr('href', result.primaryNavigationTarget);
      $(el).removeAttr('onclick');
      this._markLocalizedHiddenNavigation($, el, result.localizedCount, result.classification);
      return;
    }

    if (result.changed) {
      $(el).attr('href', `javascript:${result.scriptText}`);
      this._markLocalizedHiddenNavigation($, el, result.localizedCount, result.classification);
    }
  }

  _replaceHiddenNavigationAttr($, el, attrName, attrValue, urlMap, outputHtmlPath) {
    if (!this._looksLikeHiddenNavigationScript(attrValue)) return;

    const result = this._rewriteHiddenNavigationScript(attrValue, urlMap, outputHtmlPath);
    if (result.disabledReason) {
      this._disableHiddenNavigationTarget($, el, attrName, result.disabledReason, result.classification);
      return;
    }

    if (!result.changed) return;
    $(el).attr(attrName, result.scriptText);
    this._markLocalizedHiddenNavigation($, el, result.localizedCount, result.classification);
  }

  _looksLikeHiddenNavigationScript(scriptText = '') {
    const value = String(scriptText || '');
    return /(location(?:\.href)?|window\.location(?:\.href)?|document\.location(?:\.href)?|top\.location(?:\.href)?|self\.location(?:\.href)?|window\.open|\.submit\s*\(|\bgo[A-Z_]\w*|\bmove[A-Z_]\w*|\bmenu[A-Z_]\w*|\bpage[A-Z_]\w*|\bpopup[A-Z_]\w*|\blink[A-Z_]\w*|\bfn[A-Z_]\w*|\bnav[A-Z_]\w*|\bjump[A-Z_]\w*)/i.test(value)
      || /(['"`])([^'"`\r\n]+)\1/.test(value);
  }

  _rewriteHiddenNavigationScript(scriptText, urlMap, outputHtmlPath) {
    const state = {
      changed: false,
      localizedCount: 0,
      primaryNavigationTarget: '',
      disabledReason: '',
      classification: '',
    };

    const rewriteLiteral = (rawUrl) => {
      const decodedUrl = this._decodeInlineScriptUrl(rawUrl);
      if (!decodedUrl || !this._looksLikeNavigationValue(decodedUrl)) {
        return rawUrl;
      }

      const absoluteUrl = resolveUrl(decodedUrl, this.baseUrl);
      const resolvedTarget = this._resolveLocalPageOrAssetTarget(absoluteUrl, urlMap);
      if (resolvedTarget?.kind === 'page') {
        const finalPath = this._getFinalReplayRoute(resolvedTarget.route, outputHtmlPath);
        state.changed = true;
        state.localizedCount += 1;
        state.primaryNavigationTarget ||= finalPath;
        state.classification ||= 'page-route';
        return finalPath;
      }

      if (isInDomainScope(absoluteUrl, this.targetUrl, this.options.domainScope || 'registrable-domain')) {
        state.changed = true;
        state.disabledReason ||= 'uncloned-target';
        state.classification ||= 'uncloned-target';
        return '#';
      }

      state.changed = true;
      state.disabledReason ||= 'external-target';
      state.classification ||= 'external-target';
      return '#';
    };

    let rewritten = String(scriptText || '');
    const directNavigationPatterns = [
      /((?:window|document|top|self)?\.?location(?:\.href)?\s*=\s*)(['"`])([^'"`\r\n]+)\2(?!\s*\+)/gi,
      /((?:window|document|top|self)?\.?location\.(?:assign|replace)\s*\(\s*)(['"`])([^'"`\r\n]+)\2(?!\s*\+)(\s*\))/gi,
      /((?:window\.)?open\s*\(\s*)(['"`])([^'"`\r\n]+)\2(?!\s*\+)/gi,
      /((?:^|[=(:,;]\s*)(?!fetch\b|axios\b|sendBeacon\b)(?:[A-Za-z_$][\w$.]*\s*\(\s*))(['"`])([^'"`\r\n]+)\2(?!\s*\+)/gi,
    ];

    for (const pattern of directNavigationPatterns) {
      rewritten = rewritten.replace(pattern, (match, prefix, quote, rawUrl, suffix = '') => {
        const safeSuffix = typeof suffix === 'string' ? suffix : '';
        const replacement = rewriteLiteral(rawUrl);
        if (replacement === rawUrl) {
          return match;
        }
        return `${prefix}${quote}${replacement}${quote}${safeSuffix}`;
      });
    }

    rewritten = this._rewriteHiddenNavigationLiteralConcats(rewritten, rewriteLiteral);

    return {
      scriptText: rewritten,
      changed: state.changed && rewritten !== scriptText,
      localizedCount: state.localizedCount,
      primaryNavigationTarget: state.primaryNavigationTarget,
      disabledReason: state.disabledReason,
      classification: state.classification,
    };
  }

  _rewriteHiddenNavigationLiteralConcats(scriptText, rewriteLiteral) {
    const concatPatterns = [
      /((?:window|document|top|self)?\.?location(?:\.href)?\s*=\s*)((?:['"`][^'"`\r\n]*['"`]\s*(?:\+\s*['"`][^'"`\r\n]*['"`]\s*)+))/gi,
      /((?:window|document|top|self)?\.?location\.(?:assign|replace)\s*\(\s*)((?:['"`][^'"`\r\n]*['"`]\s*(?:\+\s*['"`][^'"`\r\n]*['"`]\s*)+))(\s*\))/gi,
      /((?:window\.)?open\s*\(\s*)((?:['"`][^'"`\r\n]*['"`]\s*(?:\+\s*['"`][^'"`\r\n]*['"`]\s*)+))/gi,
      /((?:^|[=(:,;]\s*)(?!fetch\b|axios\b|sendBeacon\b)(?:[A-Za-z_$][\w$.]*\s*\(\s*))((?:['"`][^'"`\r\n]*['"`]\s*(?:\+\s*['"`][^'"`\r\n]*['"`]\s*)+))/gi,
    ];

    let rewritten = scriptText;
    for (const pattern of concatPatterns) {
      rewritten = rewritten.replace(pattern, (match, prefix, expression, suffix = '') => {
        const safeSuffix = typeof suffix === 'string' ? suffix : '';
        const evaluated = this._evaluateLiteralStringConcat(expression);
        if (!evaluated) return match;
        const replacement = rewriteLiteral(evaluated.value);
        if (replacement === evaluated.value) return match;
        return `${prefix}${evaluated.quote}${replacement}${evaluated.quote}${safeSuffix}`;
      });
    }

    return rewritten;
  }

  _evaluateLiteralStringConcat(expression = '') {
    const source = String(expression || '').trim();
    if (!source || !source.includes('+')) return null;

    const partPattern = /(['"`])([^'"`\r\n]*)\1/g;
    const parts = [];
    let match = null;
    while ((match = partPattern.exec(source)) !== null) {
      parts.push({
        quote: match[1],
        value: match[2],
        fullMatch: match[0],
        index: match.index,
      });
    }

    if (parts.length < 2) return null;

    const remainder = source.replace(partPattern, '').replace(/\+/g, '').replace(/\s+/g, '');
    if (remainder) return null;

    const value = parts.map((part) => part.value).join('');
    if (!this._looksLikeNavigationValue(value)) return null;

    return {
      quote: parts[0].quote,
      value,
    };
  }

  _looksLikeRelativeNavigationValue(value = '') {
    const candidate = String(value || '').trim();
    if (!candidate) return false;
    if (/^(?:#|mailto:|tel:|data:|blob:|javascript:)/i.test(candidate)) return false;
    if (/[<>'"`\s]/.test(candidate)) return false;
    if (/^[A-Za-z]:[\\/]/.test(candidate)) return false;
    if (/^[A-Za-z_$][\w$-]*$/.test(candidate)) return false;
    if (/^(?:[a-z0-9-]+\.){2,}[a-z]{2,}(?:\/|$)/i.test(candidate)) return false;

    return /[/?]/.test(candidate) || /\.[A-Za-z0-9]{1,8}(?:$|[?#])/.test(candidate);
  }

  _rewriteInlineScriptUrls(scriptText, urlMap, outputHtmlPath) {
    const rewriteMatch = (match) => {
      const decodedUrl = this._decodeInlineScriptUrl(match);
      if (!decodedUrl || this._shouldPreserveUrlValue(decodedUrl)) {
        return match;
      }

      const resolvedTarget = this._resolveLocalPageOrAssetTarget(decodedUrl, urlMap);
      if (!resolvedTarget) {
        const runtimeTarget = this.renderCriticalRuntimeMap.get(normalizeAbsoluteRequestUrl(decodedUrl));
        return runtimeTarget || match;
      }

      const finalPath = resolvedTarget.kind === 'page'
        ? this._getFinalReplayRoute(resolvedTarget.route, outputHtmlPath)
        : /\.html?$/i.test(resolvedTarget.localPath)
          ? this._getFinalNavigationPath(resolvedTarget.localPath, outputHtmlPath)
          : this._getFinalLocalPath(resolvedTarget.localPath, outputHtmlPath);
      return finalPath;
    };

    const plainHttpPattern = /https?:\/\/[^\s"'`<\\]+/g;
    const escapedHttpPattern = /https?:((?:\\x[0-9A-Fa-f]{2})|(?:\\u[0-9A-Fa-f]{4})|(?:\\\/)|[^"'`\s<])+/g;

    let rewritten = scriptText
      .replace(escapedHttpPattern, rewriteMatch)
      .replace(plainHttpPattern, rewriteMatch);

    rewritten = this._rewriteInlineAssetBaseAssignments(rewritten, urlMap, outputHtmlPath);
    rewritten = this._rewriteInlineRenderCriticalRuntimeCalls(rewritten);
    rewritten = this._rewriteInlineNonCriticalRuntimeCalls(rewritten);

    return rewritten;
  }

  _decodeInlineScriptUrl(value) {
    if (!value || typeof value !== 'string') return '';

    return value
      .replace(/\\x([0-9A-Fa-f]{2})/g, (_, hex) => String.fromCharCode(Number.parseInt(hex, 16)))
      .replace(/\\u([0-9A-Fa-f]{4})/g, (_, hex) => String.fromCharCode(Number.parseInt(hex, 16)))
      .replace(/\\\//g, '/');
  }

  _toReplayRoutePath(localPath) {
    if (!localPath || !/\.html?$/i.test(localPath)) {
      return localPath;
    }

    let normalized = localPath.replace(/\\/g, '/');
    normalized = normalized.replace(/\/index\.html$/i, '');
    normalized = normalized.replace(/\.html$/i, '');
    return normalized || 'index.html';
  }

  _stripLocalAssetIntegrity($, el) {
    const tagName = el.tagName?.toLowerCase();
    if (tagName !== 'script' && tagName !== 'link') {
      return;
    }

    $(el).removeAttr('integrity');

    if (tagName === 'link') {
      const rel = ($(el).attr('rel') || '').toLowerCase();
      if (rel.includes('stylesheet') || rel.includes('preload') || rel.includes('modulepreload')) {
        $(el).removeAttr('crossorigin');
      }
      return;
    }

    $(el).removeAttr('crossorigin');
  }

  _resolveMappedAssetBase(prefixUrl, urlMap, outputHtmlPath) {
    for (const [mappedUrl, localPath] of urlMap.entries()) {
      if (!mappedUrl.startsWith(prefixUrl) || !localPath) continue;

      const suffix = mappedUrl.slice(prefixUrl.length).split('?')[0].split('#')[0];
      if (!suffix) continue;

      const normalizedLocalPath = localPath.replace(/\\/g, '/');
      if (!normalizedLocalPath.endsWith(suffix)) continue;

      const localBasePath = normalizedLocalPath.slice(0, normalizedLocalPath.length - suffix.length);
      return this._getFinalLocalPath(localBasePath, outputHtmlPath);
    }

    return '';
  }

  _rewriteInlineAssetBaseAssignments(scriptText, urlMap, outputHtmlPath) {
    const assignmentPatterns = [
      /(window\.__public_path__\s*=\s*)(['"])(https?:\/\/[^'"]+\/)\2/g,
      /(__webpack_public_path__\s*=\s*)(['"])(https?:\/\/[^'"]+\/)\2/g,
      /(__webpack_require__\.p\s*=\s*)(['"])(https?:\/\/[^'"]+\/)\2/g,
      /((?:window\.)?assetPrefix\s*[:=]\s*)(['"])(https?:\/\/[^'"]+\/)\2/g,
      /((?:window\.)?(?:publicPath|cdnBaseUrl|assetBaseUrl)\s*[:=]\s*)(['"])(https?:\/\/[^'"]+\/)\2/g,
    ];

    let rewritten = scriptText;
    for (const pattern of assignmentPatterns) {
      rewritten = rewritten.replace(pattern, (match, prefix, quote, absoluteBaseUrl) => {
        const localPublicPath = this._resolveMappedAssetBase(absoluteBaseUrl, urlMap, outputHtmlPath);
        if (!localPublicPath) {
          return match;
        }

        return `${prefix}${quote}${localPublicPath}${quote}`;
      });
    }

    return rewritten;
  }

  _rewriteInlineNonCriticalRuntimeCalls(scriptText) {
    let rewritten = scriptText;

    rewritten = rewritten.replace(
      /(\.open\s*\(\s*['"`][A-Z]+['"`]\s*,\s*)(['"`])(https?:\/\/[^'"`\r\n]+)\2(?:\s*\+\s*(?:['"`][^'"`]*['"`]|[^,()]+|\([^)]*\)))*(\s*,)/gi,
      (match, prefix, quote, absoluteUrl, suffix) => (shouldStaticallyFilterRuntime(absoluteUrl, { targetUrl: this.targetUrl })
        ? `${prefix}${quote}${STATIC_NOOP_ENDPOINT}${quote}${suffix}`
        : match),
    );

    rewritten = rewritten.replace(
      /(fetch\s*\(\s*)(['"`])(https?:\/\/[^'"`\r\n]+)\2/g,
      (match, prefix, quote, absoluteUrl) => (shouldStaticallyFilterRuntime(absoluteUrl, { targetUrl: this.targetUrl })
        ? `${prefix}${quote}${STATIC_NOOP_ENDPOINT}${quote}`
        : match),
    );

    rewritten = rewritten.replace(
      /(\.open\s*\(\s*['"`][A-Z]+['"`]\s*,\s*)(['"`])(https?:\/\/[^'"`\r\n]+)\2/gi,
      (match, prefix, quote, absoluteUrl) => (shouldStaticallyFilterRuntime(absoluteUrl, { targetUrl: this.targetUrl })
        ? `${prefix}${quote}${STATIC_NOOP_ENDPOINT}${quote}`
        : match),
    );

    rewritten = rewritten.replace(
      /(navigator\.sendBeacon\s*\(\s*)(['"`])(https?:\/\/[^'"`\r\n]+)\2/g,
      (match, prefix, quote, absoluteUrl) => (shouldStaticallyFilterRuntime(absoluteUrl, { targetUrl: this.targetUrl })
        ? `${prefix}${quote}${STATIC_NOOP_ENDPOINT}${quote}`
        : match),
    );

    rewritten = rewritten.replace(
      /((?:new\s+Image\s*\(\s*\)|[\w$.]+)\.src\s*=\s*)(['"`])(https?:\/\/[^'"`\r\n]+)\2/g,
      (match, prefix, quote, absoluteUrl) => (shouldStaticallyFilterRuntime(absoluteUrl, { targetUrl: this.targetUrl })
        ? `${prefix}${quote}${STATIC_NOOP_IMAGE}${quote}`
        : match),
    );

    rewritten = rewritten.replace(
      /((?:src|url)\s*:\s*)(['"`])(https?:\/\/[^'"`\r\n]+)\2/gi,
      (match, prefix, quote, absoluteUrl) => (shouldStaticallyFilterRuntime(absoluteUrl, { targetUrl: this.targetUrl })
        ? `${prefix}${quote}${STATIC_NOOP_ENDPOINT}${quote}`
        : match),
    );

    return rewritten;
  }

  _rewriteInlineRenderCriticalRuntimeCalls(scriptText) {
    let rewritten = scriptText;

    rewritten = rewritten.replace(
      /(fetch\s*\(\s*)(['"`])([^'"`\r\n]+)\2/g,
      (match, prefix, quote, rawUrl) => {
        const absoluteUrl = normalizeAbsoluteRequestUrl(resolveUrl(rawUrl, this.baseUrl));
        const runtimeTarget = this.renderCriticalRuntimeMap.get(absoluteUrl);
        return runtimeTarget ? `${prefix}${quote}${runtimeTarget}${quote}` : match;
      },
    );

    rewritten = rewritten.replace(
      /(\.open\s*\(\s*['"`][A-Z]+['"`]\s*,\s*)(['"`])([^'"`\r\n]+)\2/gi,
      (match, prefix, quote, rawUrl) => {
        const absoluteUrl = normalizeAbsoluteRequestUrl(resolveUrl(rawUrl, this.baseUrl));
        const runtimeTarget = this.renderCriticalRuntimeMap.get(absoluteUrl);
        return runtimeTarget ? `${prefix}${quote}${runtimeTarget}${quote}` : match;
      },
    );

    rewritten = rewritten.replace(
      /(navigator\.sendBeacon\s*\(\s*)(['"`])([^'"`\r\n]+)\2/g,
      (match, prefix, quote, rawUrl) => {
        const absoluteUrl = normalizeAbsoluteRequestUrl(resolveUrl(rawUrl, this.baseUrl));
        const runtimeTarget = this.renderCriticalRuntimeMap.get(absoluteUrl);
        return runtimeTarget ? `${prefix}${quote}${runtimeTarget}${quote}` : match;
      },
    );

    return rewritten;
  }

  _preserveMetadata($) {
    if (!$('meta[name="cloned-from"]').length) {
      $('head').append(`\n    <meta name="cloned-from" content="${this.baseUrl}">`);
      $('head').append(`\n    <meta name="cloned-at" content="${new Date().toISOString()}">`);
    }
  }

  _injectReplayRuntimeGuard($) {
    if ($('script[data-front-clone-guard="true"]').length) return;

    if ($('head').length === 0) {
      $('html').prepend('<head></head>');
    }

    const guardMarkup = `<script src="${RUNTIME_GUARD_SCRIPT}" data-front-clone-guard="true"></script>`;
    $('head').prepend(`    ${guardMarkup}\n`);
  }
}
