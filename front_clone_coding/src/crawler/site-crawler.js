import { URL } from 'url';
import { chromium } from 'playwright';

import logger from '../utils/logger.js';
import PageCrawler from './page-crawler.js';
import NetworkInterceptor from './network-interceptor.js';
import { getDomainRoot, isInDomainScope, normalizeCrawlUrl } from '../utils/url-utils.js';

export const TRACKER_HOST_PATTERNS = [
  'google-analytics.com',
  'googletagmanager.com',
  'doubleclick.net',
  'facebook.net',
  'clarity.ms',
  'hotjar.com',
  'segment.com',
];

export const STATIC_EXCLUDED_EXTENSIONS = [
  '.pdf',
  '.zip',
  '.mp4',
  '.mp3',
  '.apk',
  '.exe',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.svg',
];

export const DESTRUCTIVE_PATTERNS = [
  '/logout',
  '/signout',
  '/delete',
  '/remove',
  'logout=',
  'signout=',
];

export const LOGIN_PATH_PATTERNS = [
  '/login',
  '/signin',
  '/sign-in',
  '/auth',
  '/auth/',
  '/auth/login',
  '/youraccount',
  '/account/login',
  '/user/login',
  '/sso/login',
];

export default class SiteCrawler {
  constructor(options) {
    this.startUrl = options.url;
    this.maxPages = options.maxPages || 20;
    this.maxDepth = options.maxDepth || 3;
    this.waitTime = options.waitTime || 3000;
    this.viewport = options.viewport || '1920x1080';
    this.screenshot = options.screenshot || false;
    this.scrollCount = options.scrollCount || 5;
    this.followLoginGated = options.followLoginGated || false;
    this.storageState = options.storageState || null;
    this.cookieFile = options.cookieFile || null;
    this.headful = options.headful || false;
    this.concurrency = options.concurrency || 3;
    this.domainScope = options.domainScope || 'registrable-domain';

    this.queue = [{ url: this.startUrl, depth: 0, discoveredFrom: null }];
    this.visited = new Set([normalizeCrawlUrl(this.startUrl)]);
    this.domainRoot = getDomainRoot(this.startUrl, this.domainScope);
    this.interceptor = new NetworkInterceptor();
    this.siteMap = [];
    this.pageCount = 0;
    this.inFlight = 0;
  }

  async crawlAll() {
    logger.start(
      `[SiteCrawler] Start site crawling (max ${this.maxPages} pages, max depth ${this.maxDepth}, concurrency ${this.concurrency})`,
    );

    const results = [];
    const browser = await chromium.launch({ headless: !this.headful });

    try {
      await Promise.all(Array.from({ length: this.concurrency }, () => this._worker(browser, results)));
    } finally {
      await browser.close().catch(() => {});
    }

    logger.succeed(`[SiteCrawler] Crawl finished: total ${this.pageCount} pages`);
    return { results, siteMap: this.siteMap, interceptor: this.interceptor };
  }

  async _worker(browser, results) {
    while (true) {
      const job = this._nextJob();
      if (!job) break;

      const { url, depth, discoveredFrom } = job;
      const currentCount = this.pageCount;
      this.inFlight += 1;

      logger.info(`\n[${currentCount}/${this.maxPages}] Current page: ${url} (Depth: ${depth})`);

      const crawler = new PageCrawler({
        url,
        waitTime: this.waitTime,
        viewport: this.viewport,
        screenshot: this.screenshot,
        scrollCount: this.scrollCount,
        interceptor: this.interceptor,
        storageState: this.storageState,
        cookieFile: this.cookieFile,
        headful: this.headful,
        browser,
      });

      try {
        const pageResult = await crawler.crawl();
        const finalUrl = pageResult.finalUrl || url;
        const isLogin = this._isLoginPage(finalUrl, pageResult.html);
        const skippedReason = isLogin && !this.followLoginGated ? 'login-gated' : null;

        if (!skippedReason) {
          this._enqueueLinks(pageResult.internalLinks, depth + 1, finalUrl);
        } else {
          logger.warn(`Login-gated page detected. Link queueing is skipped: ${finalUrl}`);
        }

        results.push({
          url,
          finalUrl,
          depth,
          isLogin,
          html: pageResult.html,
          interceptor: pageResult.interceptor,
          computedStyles: pageResult.computedStyles,
          liveImageUrls: pageResult.liveImageUrls,
          screenshot: pageResult.screenshot,
          forms: pageResult.forms,
          interactiveElements: pageResult.interactiveElements,
          title: pageResult.title,
          status: pageResult.status,
          discoveredFrom,
          skippedReason,
        });

        this.siteMap.push({
          url,
          finalUrl,
          normalizedUrl: normalizeCrawlUrl(finalUrl),
          depth,
          status: pageResult.status,
          discoveredFrom,
          title: pageResult.title,
          loginGated: isLogin,
          skippedReason,
          crawlState: 'completed',
          linksFound: pageResult.internalLinks.length,
        });
      } catch (err) {
        logger.error(`Failed to crawl page (${url}): ${err.message}`);
        this.siteMap.push({
          url,
          finalUrl: url,
          normalizedUrl: normalizeCrawlUrl(url),
          depth,
          status: null,
          discoveredFrom,
          title: '',
          loginGated: false,
          skippedReason: null,
          crawlState: 'failed',
          error: err.message,
          linksFound: 0,
        });
      } finally {
        this.inFlight -= 1;
      }
    }
  }

  _nextJob() {
    if (this.pageCount >= this.maxPages) return null;

    const job = this.queue.shift();
    if (!job) return null;
    if (job.depth > this.maxDepth) {
      this.siteMap.push({
        url: job.url,
        finalUrl: job.url,
        normalizedUrl: normalizeCrawlUrl(job.url),
        depth: job.depth,
        status: null,
        discoveredFrom: job.discoveredFrom,
        title: '',
        loginGated: false,
        skippedReason: 'max-depth',
        crawlState: 'skipped',
        linksFound: 0,
      });
      return this._nextJob();
    }

    this.pageCount += 1;
    return job;
  }

  _enqueueLinks(links, nextDepth, discoveredFrom) {
    if (!links || links.length === 0) return;
    if (nextDepth > this.maxDepth) return;

    let added = 0;
    for (const link of links) {
      try {
        if (this._isExcludedPattern(link)) continue;
        const normalized = normalizeCrawlUrl(link);
        if (!this._isInScope(normalized)) continue;
        if (this.visited.has(normalized)) continue;

        this.visited.add(normalized);
        this.queue.push({ url: normalized, depth: nextDepth, discoveredFrom });
        added += 1;
      } catch {
        // Ignore malformed URLs discovered in DOM.
      }
    }

    if (added > 0) {
      logger.debug(`Added ${added} links to queue (depth ${nextDepth})`);
    }
  }

  _isInScope(urlStr) {
    return isInDomainScope(urlStr, this.startUrl, this.domainScope);
  }

  _isExcludedPattern(urlStr) {
    const lower = urlStr.toLowerCase();
    if (
      lower.startsWith('mailto:') ||
      lower.startsWith('tel:') ||
      lower.startsWith('javascript:') ||
      lower.startsWith('data:')
    ) {
      return true;
    }

    if (STATIC_EXCLUDED_EXTENSIONS.some((ext) => lower.endsWith(ext))) return true;
    if (DESTRUCTIVE_PATTERNS.some((pattern) => lower.includes(pattern))) return true;

    try {
      const host = new URL(urlStr).hostname.toLowerCase();
      return TRACKER_HOST_PATTERNS.some((pattern) => host.includes(pattern));
    } catch {
      return true;
    }
  }

  _isLoginPage(url, html) {
    let parsedUrl;
    try {
      parsedUrl = new URL(url);
    } catch {
      return false;
    }

    const pathName = parsedUrl.pathname.toLowerCase();
    if (LOGIN_PATH_PATTERNS.some((pattern) => pathName === pattern || pathName.startsWith(`${pattern}/`))) {
      return true;
    }

    if (!html) return false;

    const lowerHtml = html.toLowerCase();
    const hasPasswordInput = lowerHtml.includes('type="password"') || lowerHtml.includes('name="password"');
    const hasLoginMarker = ['login', 'log in', 'sign in', 'continue to'].some((text) => lowerHtml.includes(text));

    return Boolean(hasPasswordInput && hasLoginMarker);
  }
}
