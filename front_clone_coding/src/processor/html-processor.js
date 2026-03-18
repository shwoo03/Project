import * as cheerio from 'cheerio';
import { resolveUrl, getRelativePath } from '../utils/url-utils.js';
import logger from '../utils/logger.js';

export default class HtmlProcessor {
  constructor(targetUrl, options = {}) {
    this.targetUrl = targetUrl;
    this.baseUrl = targetUrl;
    this.options = options;
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
      for (const domain of trackingDomains) {
        if (src.includes(domain) || text.includes(domain)) {
          $(el).remove();
          return;
        }
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

    $('video').each((_, el) => {
      this._replaceAttr($, el, 'poster', urlMap, outputHtmlPath);
    });
  }

  _replaceAttr($, el, attr, urlMap, outputHtmlPath) {
    const value = $(el).attr(attr);
    if (!value) return;
    if (value.startsWith('data:') || value.startsWith('blob:') || value.startsWith('javascript:')) return;
    const absoluteUrl = resolveUrl(value, this.baseUrl);
    const localPath = urlMap.get(absoluteUrl);
    if (localPath) {
      $(el).attr(attr, this._getFinalLocalPath(localPath, outputHtmlPath));
    }
  }

  _preserveMetadata($) {
    if (!$('meta[name="cloned-from"]').length) {
      $('head').append(`\n    <meta name="cloned-from" content="${this.baseUrl}">`);
      $('head').append(`\n    <meta name="cloned-at" content="${new Date().toISOString()}">`);
    }
  }
}
