import path from 'path';
import * as cheerio from 'cheerio';

import { saveFile, deduplicateFilename } from './file-utils.js';
import { getAssetPathFromUrl } from './url-utils.js';
import { IMAGE_FETCH_TIMEOUT, IMAGE_DOWNLOAD_CONCURRENCY } from './constants.js';
import logger from './logger.js';

export async function downloadExternalImages(
  html,
  publicDir,
  urlMap,
  interceptor,
  liveImageUrls = [],
  baseUrl = '',
) {
  const $ = cheerio.load(html, { decodeEntities: false });
  const externalUrls = new Set();
  const usedNames = new Set();

  $('img').each((_, el) => {
    const src = $(el).attr('src') || '';
    if (src.startsWith('http')) externalUrls.add(src);

    const srcset = $(el).attr('srcset') || '';
    if (!srcset) return;
    srcset.split(',').forEach((entry) => {
      const url = entry.trim().split(/\s+/)[0];
      if (url.startsWith('http')) externalUrls.add(url);
    });
  });

  $('picture source').each((_, el) => {
    const srcset = $(el).attr('srcset') || '';
    if (!srcset) return;
    srcset.split(',').forEach((entry) => {
      const url = entry.trim().split(/\s+/)[0];
      if (url.startsWith('http')) externalUrls.add(url);
    });
  });

  $('[style]').each((_, el) => {
    const style = $(el).attr('style') || '';
    const matches = [...style.matchAll(/url\(['"]?(https?:[^'")\s]+)['"]?\)/g)];
    matches.forEach((match) => externalUrls.add(match[1]));
  });

  for (const url of liveImageUrls) {
    if (url.startsWith('http')) externalUrls.add(url);
  }

  for (const url of [...externalUrls]) {
    if (urlMap.has(url)) {
      externalUrls.delete(url);
    }
  }

  if (externalUrls.size === 0) return 0;

  logger.update(`Downloading ${externalUrls.size} additional external image(s)`);

  const CONCURRENCY = IMAGE_DOWNLOAD_CONCURRENCY;
  let saved = 0;
  const urls = [...externalUrls];

  for (let i = 0; i < urls.length; i += CONCURRENCY) {
    const batch = urls.slice(i, i + CONCURRENCY);
    const results = await Promise.allSettled(
      batch.map(async (url) => {
        let body = null;
        let mimeType = 'image/jpeg';
        const cached = interceptor.getLatestResponse(url);

        if (cached?.body) {
          body = cached.body;
          mimeType = cached.mimeType || 'image/jpeg';
        } else {
          const response = await fetch(url, { signal: AbortSignal.timeout(IMAGE_FETCH_TIMEOUT) });
          if (!response.ok) return null;

          const buffer = await response.arrayBuffer();
          body = Buffer.from(buffer);
          mimeType = response.headers.get('content-type')?.split(';')[0] || 'image/jpeg';
        }

        if (!body || body.length === 0) return null;
        return { url, body, mimeType, cached };
      }),
    );

    for (const result of results) {
      if (result.status !== 'fulfilled' || !result.value) continue;
      const { url, body, mimeType, cached } = result.value;

      try {
        const proposedPath = getAssetPathFromUrl(url, baseUrl, mimeType, 'image');
        if (!proposedPath) continue;

        const relativeDir = path.posix.dirname(proposedPath);
        const rawFilename = path.posix.basename(proposedPath);
        const filename = deduplicateFilename(usedNames, relativeDir, rawFilename);
        const relativePath = path.posix.join(relativeDir, filename);
        await saveFile(path.join(publicDir, relativePath), body);

        urlMap.set(url, relativePath);
        saved += 1;

        if (cached) {
          cached.body = null;
        }
      } catch (err) {
        logger.debug(`Image save failed: ${url} - ${err.message}`);
      }
    }
  }

  return saved;
}

export function injectCapturedImages(html, urlMap) {
  const $ = cheerio.load(html, { decodeEntities: false });
  let injected = 0;

  const toRelativeSrc = (localPath) => {
    if (localPath.startsWith('./') || localPath.startsWith('../')) return localPath;
    return `./${localPath}`;
  };

  $('img').each((_, el) => {
    const src = $(el).attr('src') || '';
    if (!src.startsWith('http')) return;

    const localPath = urlMap.get(src);
    if (!localPath) return;

    $(el).attr('src', toRelativeSrc(localPath));
    injected += 1;
  });

  $('img, source').each((_, el) => {
    const srcset = $(el).attr('srcset') || '';
    if (!srcset) return;

    let changed = false;
    const newSrcset = srcset
      .split(',')
      .map((entry) => {
        const parts = entry.trim().split(/\s+/);
        const url = parts[0];
        if (!url.startsWith('http')) return entry.trim();

        const localPath = urlMap.get(url);
        if (!localPath) return entry.trim();

        parts[0] = toRelativeSrc(localPath);
        changed = true;
        return parts.join(' ');
      })
      .join(', ');

    if (changed) {
      $(el).attr('srcset', newSrcset);
      injected += 1;
    }
  });

  const lazyAttrs = [
    'data-src',
    'data-lazy-src',
    'data-original',
    'data-bg',
    'data-imagesrc',
    'data-image-src',
    'data-img-src',
    'data-poster',
    'data-thumb',
    'data-thumbnail',
  ];

  for (const attr of lazyAttrs) {
    $(`[${attr}]`).each((_, el) => {
      const value = $(el).attr(attr) || '';
      if (!value.startsWith('http')) return;

      const localPath = urlMap.get(value);
      if (!localPath) return;

      $(el).attr(attr, toRelativeSrc(localPath));
      injected += 1;
    });
  }

  $('[style]').each((_, el) => {
    const style = $(el).attr('style') || '';
    if (!style.includes('url(')) return;

    const newStyle = style.replace(/url\((['"]?)(https?:[^)'"]+)\1\)/g, (match, quote, url) => {
      const localPath = urlMap.get(url);
      if (!localPath) return match;

      injected += 1;
      return `url(${quote}${toRelativeSrc(localPath)}${quote})`;
    });

    if (newStyle !== style) {
      $(el).attr('style', newStyle);
    }
  });

  if (injected > 0) {
    logger.info(`Injected ${injected} captured image reference(s) into HTML`);
  }

  const imageExtensions = new Set(['.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif']);
  const alreadyUsed = new Set();
  $('img').each((_, el) => {
    const value = $(el).attr('src');
    if (value) alreadyUsed.add(value);
  });

  const unreferencedImages = [];
  for (const [, localPath] of urlMap) {
    const ext = path.extname(localPath).toLowerCase();
    if (!imageExtensions.has(ext)) continue;
    if (/logo|icon|favicon|powered_by|ot_guard|ot_close|gif/i.test(localPath)) continue;

    const relative = toRelativeSrc(localPath);
    if (!alreadyUsed.has(relative)) {
      unreferencedImages.push(relative);
    }
  }

  if (unreferencedImages.length > 0) {
    const preloads = unreferencedImages
      .map((relative) => `<link rel="preload" as="image" href="${relative}">`)
      .join('\n    ');
    $('head').append(`\n    <!-- clone: preload captured images -->\n    ${preloads}`);

    const hiddenImages = unreferencedImages
      .map((relative) => `<img src="${relative}" loading="lazy" alt="captured" style="display:none;width:0;height:0;" aria-hidden="true">`)
      .join('\n      ');
    $('body').append(
      `\n<div id="clone-preload-refs" aria-hidden="true" style="position:absolute;width:0;height:0;overflow:hidden;">\n      ${hiddenImages}\n    </div>`,
    );

    logger.info(`Added preload references for ${unreferencedImages.length} captured image(s)`);
  }

  return $.html();
}
