import { URL } from 'url';
import { chromium } from 'playwright';

import logger from '../utils/logger.js';
import PageCrawler from './page-crawler.js';
import NetworkInterceptor from './network-interceptor.js';
import { getDomainRoot, isInDomainScope, normalizeCrawlUrl } from '../utils/url-utils.js';
import {
  DEFAULT_CRAWL_PROFILE,
  DEFAULT_NETWORK_POSTURE,
  resolveCrawlProfile,
  resolveNetworkPosture,
} from '../utils/crawl-config.js';
import { prioritizeFrontierCandidates } from '../utils/frontier-utils.js';
import { WORKER_PAGE_TIMEOUT, VISITED_SET_SAFETY_MULTIPLIER } from '../utils/constants.js';

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
    this.crawlProfile = options.crawlProfile || DEFAULT_CRAWL_PROFILE;
    this.networkPosture = options.networkPosture || DEFAULT_NETWORK_POSTURE;
    this.enableRepresentativeQA = Boolean(options.enableRepresentativeQA);
    this.storageState = options.storageState || null;
    this.cookieFile = options.cookieFile || null;
    this.headful = options.headful || false;
    this.concurrency = options.concurrency || 3;
    this.domainScope = options.domainScope || 'registrable-domain';
    this.captureDir = options.captureDir || null;
    this.enableGraphqlIntrospection = options.enableGraphqlIntrospection !== false;
    this.signal = options.signal || null;

    this.queue = [{ url: this.startUrl, depth: 0, discoveredFrom: null }];
    this.visited = new Set([normalizeCrawlUrl(this.startUrl)]);
    this.domainRoot = getDomainRoot(this.startUrl, this.domainScope);
    this.interceptor = new NetworkInterceptor();
    this.siteMap = [];
    this.pageCount = 0;
    this.inFlight = 0;
    this.lastFailure = null;
    this.profileSettings = resolveCrawlProfile(this.crawlProfile);
    this.networkSettings = resolveNetworkPosture(this.networkPosture);
    this.interactionBudget = options.interactionBudget ?? this.profileSettings.interactionBudget ?? 0;
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
      // Browser cleanup errors are expected (already-closed contexts, aborted navigations).
      await browser.close().catch(() => {});
    }

    logger.succeed(`[SiteCrawler] Crawl finished: total ${this.pageCount} pages`);
    return {
      results,
      siteMap: this.siteMap,
      interceptor: this.interceptor,
      lastFailure: this.lastFailure,
    };
  }

  async _worker(browser, results) {
    while (true) {
      if (this.signal?.aborted) {
        logger.info('[SiteCrawler] Crawl cancelled by signal');
        break;
      }

      const job = this._nextJob();
      if (!job) break;

      const { url, depth, discoveredFrom } = job;
      const currentCount = this.pageCount;
      this.inFlight += 1;

      logger.info(`\n[${currentCount}/${this.maxPages}] Current page: ${url} (Depth: ${depth})`);
      logger.progress({
        stage: 'crawl',
        current: currentCount,
        total: this.maxPages,
        label: `Crawling page ${currentCount} of ${this.maxPages}`,
        detail: url,
      });

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
        captureDir: this.captureDir,
        crawlProfile: this.crawlProfile,
        networkPosture: this.networkPosture,
        enableRepresentativeQA: this.enableRepresentativeQA,
        interactionBudget: this.interactionBudget,
        enableGraphqlIntrospection: this.enableGraphqlIntrospection,
        frontierOriginUrl: this.startUrl,
        domainScope: this.domainScope,
        signal: this.signal,
      });

      try {
        const pageResult = await Promise.race([
          crawler.crawl(),
          new Promise((_, reject) => {
            setTimeout(() => reject(new Error(`Page crawl timed out after ${WORKER_PAGE_TIMEOUT}ms`)), WORKER_PAGE_TIMEOUT);
          }),
        ]);
        const finalUrl = pageResult.finalUrl || url;
        const normalizedFinalUrl = normalizeCrawlUrl(finalUrl);
        if (normalizedFinalUrl !== normalizeCrawlUrl(url)) {
          this.visited.add(normalizedFinalUrl);
        }
        const isLogin = this._isLoginPage(finalUrl, pageResult.html);
        const skippedReason = isLogin && !this.followLoginGated ? 'login-gated' : null;
        const queueBudget = pageResult.classification?.queueBudget || this.profileSettings.linkBudget;
        let frontierSelection = {
          linkCandidatesSeen: pageResult.linkCandidates?.length || pageResult.internalLinks.length,
          linksSelected: 0,
          frontierTopCandidates: [],
          selectionReasons: [],
        };

        if (!skippedReason) {
          frontierSelection = this._enqueueLinks(pageResult.linkCandidates || pageResult.internalLinks, depth + 1, finalUrl, queueBudget, pageResult.classification);
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
          documentEncoding: pageResult.documentEncoding,
          classification: pageResult.classification,
          crawlProfile: pageResult.crawlProfile,
          networkPosture: pageResult.networkPosture,
          qa: pageResult.qa,
          status: pageResult.status,
          storageState: pageResult.storageState,
          sessionStorageState: pageResult.sessionStorageState,
          graphqlArtifacts: pageResult.graphqlArtifacts,
          captureWarnings: pageResult.captureWarnings,
          linkCandidates: pageResult.linkCandidates || [],
          frontierSelection,
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
          documentEncoding: pageResult.documentEncoding,
          loginGated: isLogin,
          skippedReason,
          crawlState: 'completed',
          linksFound: pageResult.internalLinks.length,
          pageClass: pageResult.classification?.pageClass || 'document',
          queueBudget,
          linkCandidatesSeen: frontierSelection?.linkCandidatesSeen ?? (pageResult.linkCandidates?.length || pageResult.internalLinks.length),
          linksSelected: frontierSelection?.linksSelected ?? 0,
          frontierTopCandidates: frontierSelection?.frontierTopCandidates ?? [],
          selectionReasons: frontierSelection?.selectionReasons ?? [],
          crawlProfile: this.crawlProfile,
          networkPosture: this.networkPosture,
        });
      } catch (err) {
        if (err.message === 'Operation cancelled') {
          logger.info(`[SiteCrawler] Page crawl cancelled: ${url}`);
          break;
        }
        const isTimeout = err.message.includes('timed out');
        const crawlState = isTimeout ? 'timeout' : 'failed';
        logger.error(`Failed to crawl page (${url}): ${err.message}`);
        this.lastFailure = err.message;
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
          crawlState,
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

  _enqueueLinks(links, nextDepth, discoveredFrom, queueBudget = this.profileSettings.linkBudget, classification = null) {
    if (!links || links.length === 0) {
      return {
        linkCandidatesSeen: 0,
        linksSelected: 0,
        frontierTopCandidates: [],
        selectionReasons: [],
      };
    }
    if (nextDepth > this.maxDepth) {
      return {
        linkCandidatesSeen: links.length,
        linksSelected: 0,
        frontierTopCandidates: [],
        selectionReasons: [],
      };
    }

    if (this.visited.size > this.maxPages * VISITED_SET_SAFETY_MULTIPLIER) {
      logger.warn(`[SiteCrawler] Visited set exceeded safety cap (${this.visited.size}), skipping link enqueue`);
      return {
        linkCandidatesSeen: links.length,
        linksSelected: 0,
        frontierTopCandidates: [],
        selectionReasons: [],
      };
    }

    const eligibleCandidates = [];

    for (const link of links) {
      try {
        const candidate = typeof link === 'string' ? { url: link } : link;
        const normalized = normalizeCrawlUrl(candidate.normalizedUrl || candidate.url);
        if (this._isExcludedPattern(candidate.url || normalized)) continue;
        if (!this._isInScope(normalized)) continue;
        if (this.visited.has(normalized)) continue;

        eligibleCandidates.push({
          ...candidate,
          url: candidate.url || normalized,
          normalizedUrl: normalized,
        });
      } catch (err) {
        logger.debug(`Skipped malformed link candidate: ${err.message}`);
      }
    }

    const prioritized = prioritizeFrontierCandidates(eligibleCandidates, {
      startUrl: this.startUrl,
      currentPageUrl: discoveredFrom,
      nextDepth,
      queueBudget,
      domainScope: this.domainScope,
      discoveredFromPageClass: classification?.pageClass || 'document',
      weights: this.profileSettings.frontierWeights,
      diversityCaps: this.profileSettings.frontierDiversityCaps,
    });

    let added = 0;
    for (const candidate of prioritized.selectedCandidates) {
      this.visited.add(candidate.normalizedUrl);
      this.queue.push({ url: candidate.normalizedUrl, depth: nextDepth, discoveredFrom });
      added += 1;
    }

    if (added > 0) {
      logger.debug(`Added ${added} links to queue (depth ${nextDepth}, budget ${queueBudget})`);
    }

    return {
      linkCandidatesSeen: links.length,
      linksSelected: added,
      frontierTopCandidates: prioritized.topCandidates.map((candidate) => ({
        url: candidate.normalizedUrl,
        score: candidate.score,
        familyKey: candidate.familyKey,
        sourceKind: candidate.sourceKind,
        landmark: candidate.landmark,
        sameHost: candidate.sameHost,
        pathDepth: candidate.pathDepth,
        hasQuery: candidate.hasQuery,
        selectionReasons: candidate.selectionReasons,
      })),
      selectionReasons: prioritized.selectedCandidates.map((candidate) => ({
        url: candidate.normalizedUrl,
        score: candidate.score,
        familyKey: candidate.familyKey,
        selectionReasons: candidate.selectionReasons,
      })),
    };
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
