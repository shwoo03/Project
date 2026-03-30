import { chromium } from 'playwright';
import NetworkInterceptor from './network-interceptor.js';
import ComputedStyleExtractor from '../processor/computed-style-extractor.js';
import logger from '../utils/logger.js';
import {
  DEFAULT_WAIT_TIME,
  PAGE_LOAD_TIMEOUT,
  NETWORK_IDLE_TIMEOUT,
  IMAGE_WAIT_TIMEOUT,
  SCROLL_INTERVAL_MS,
  MAX_SCREENSHOT_HEIGHT,
  SAFE_INTERACTION_TIMEOUT,
  SAFE_INTERACTION_CANDIDATE_LIMIT,
} from '../utils/constants.js';
import {
  DEFAULT_CRAWL_PROFILE,
  DEFAULT_NETWORK_POSTURE,
  classifyPageSnapshot,
  getEffectiveWaitTime,
  resolveCrawlProfile,
} from '../utils/crawl-config.js';
import fs from 'fs/promises';
import path from 'path';
import { ensureDir } from '../utils/file-utils.js';
import { enrichLinkCandidate } from '../utils/frontier-utils.js';

export default class PageCrawler {
  constructor(options) {
    this.url = options.url;
    this.waitTime = options.waitTime || DEFAULT_WAIT_TIME;
    this.crawlProfile = options.crawlProfile || DEFAULT_CRAWL_PROFILE;
    this.networkPosture = options.networkPosture || DEFAULT_NETWORK_POSTURE;
    this.viewport = this._parseViewport(options.viewport || '1920x1080');
    this.takeScreenshot = options.screenshot || false;
    this.enableRepresentativeQA = Boolean(options.enableRepresentativeQA);
    this.scrollCount = options.scrollCount || 5;
    this.frontierOriginUrl = options.frontierOriginUrl || options.url;
    this.domainScope = options.domainScope || 'registrable-domain';
    this.storageState = options.storageState || null;
    this.cookieFile = options.cookieFile || null;
    this.headful = options.headful || false;
    this.captureDir = options.captureDir || null;
    this.interactionBudget = options.interactionBudget ?? resolveCrawlProfile(this.crawlProfile).interactionBudget ?? 0;
    this.enableGraphqlIntrospection = options.enableGraphqlIntrospection !== false;
    this.signal = options.signal || null;

    this.browser = null;
    this.injectedBrowser = options.browser || null;
    this.page = null;
    this.interceptor = options.interceptor || new NetworkInterceptor();
  }

  _checkSignal() {
    if (this.signal?.aborted) {
      throw new Error('Operation cancelled');
    }
  }

  _parseViewport(viewport) {
    const [width, height] = viewport.split('x').map(Number);
    return { width: width || 1920, height: height || 1080 };
  }

  _buildContextOptions(storageStatePath) {
    return {
      viewport: this.viewport,
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      locale: 'en-US',
      timezoneId: 'UTC',
      storageState: storageStatePath,
      serviceWorkers: 'block',
      recordHar: this.captureDir ? {
        path: path.join(this.captureDir, `${this._safeFileBase(this.url)}.har`),
        // Large commercial sites can spend minutes flushing attached HAR payloads.
        // We keep request-level HAR output for debugging, but omit bodies to avoid stalls.
        content: 'omit',
        mode: 'minimal',
      } : undefined,
    };
  }

  async _runWithTimeout(label, fn, timeoutMs = 8000) {
    let timer = null;
    try {
      await Promise.race([
        fn(),
        new Promise((_, reject) => {
          timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs);
        }),
      ]);
      return true;
    } catch (err) {
      logger.warn(`${label} skipped: ${err.message}`);
      return false;
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  async crawl() {
    logger.start(`Navigating page: ${this.url}`);

    try {
      this.browser = this.injectedBrowser || await chromium.launch({ headless: !this.headful });
      let storageStatePath;
      if (this.storageState) {
        try {
          storageStatePath = path.resolve(this.storageState);
          await fs.access(storageStatePath);
        } catch (err) {
          logger.warn(`Cannot read storage state file: ${this.storageState} (${err.message})`);
          storageStatePath = undefined;
        }
      }

      const context = await this.browser.newContext(this._buildContextOptions(storageStatePath));

      await context.addInitScript(() => {
        const key = '__FRONT_CLONE_ROUTES__';
        const routeSet = new Set([location.href]);
        const remember = () => {
          routeSet.add(location.href);
          window[key] = [...routeSet];
        };

        window[key] = [...routeSet];

        for (const name of ['pushState', 'replaceState']) {
          const original = history[name];
          history[name] = function (...args) {
            const result = original.apply(this, args);
            remember();
            return result;
          };
        }

        window.addEventListener('popstate', remember);
      });

      this.page = await context.newPage();

      if (this.cookieFile) {
        try {
          const filePath = path.resolve(this.cookieFile);
          const raw = await fs.readFile(filePath, 'utf-8');
          const parsed = JSON.parse(raw);
          const cookies = Array.isArray(parsed) ? parsed : parsed.cookies;
          if (Array.isArray(cookies) && cookies.length > 0) {
            await context.addCookies(cookies);
          }
        } catch (err) {
          logger.debug(`Cannot load cookie file: ${this.cookieFile} (${err.message})`);
        }
      }

      this.interceptor.attach(this.page);
      const resourceCountBefore = this.interceptor.getResponseCount();

      logger.update(`Loading page: ${this.url}`);
      const response = await this.page.goto(this.url, {
        waitUntil: 'domcontentloaded',
        timeout: PAGE_LOAD_TIMEOUT,
      });

      const effectiveWaitTime = getEffectiveWaitTime(this.waitTime, this.crawlProfile, this.networkPosture);
      const captureWarnings = [];
      if (effectiveWaitTime > 0) {
        logger.update(`Waiting ${effectiveWaitTime}ms after load`);
        await this.page.waitForTimeout(effectiveWaitTime);
      }

      this._checkSignal();

      logger.update('Running auto-scroll to trigger lazy loaded content');
      const autoScrollResult = await this._autoScroll();
      captureWarnings.push(...autoScrollResult.warnings);

      this._checkSignal();

      logger.update('Waiting for media and rendered content');
      await this._waitForImagesAndContent();

      this._checkSignal();

      logger.update('Running safe interaction discovery');
      const interactionResult = await this._runSafeInteractions();

      logger.update('Extracting page HTML');
      const html = await this.page.content();

      logger.update('Collecting image URLs, links, forms, and interactive hints');
      const pageSnapshot = await this.page.evaluate(() => {
        const recordedRoutes = Array.isArray(window.__FRONT_CLONE_ROUTES__) ? window.__FRONT_CLONE_ROUTES__ : [];
        const makeSelectorHint = (el) => {
          if (!(el instanceof Element)) return '';
          if (el.id) return `#${el.id}`;
          const name = el.getAttribute('name');
          if (name) return `${el.tagName.toLowerCase()}[name="${name}"]`;
          const testId = el.getAttribute('data-testid');
          if (testId) return `${el.tagName.toLowerCase()}[data-testid="${testId}"]`;
          const classes = [...el.classList].slice(0, 2).join('.');
          return classes ? `${el.tagName.toLowerCase()}.${classes}` : el.tagName.toLowerCase();
        };

        const imgUrls = new Set();
        document.querySelectorAll('img').forEach((img) => {
          if (img.src && img.src.startsWith('http')) imgUrls.add(img.src);
          if (img.currentSrc && img.currentSrc.startsWith('http')) imgUrls.add(img.currentSrc);
          if (img.srcset) {
            img.srcset.split(',').forEach((entry) => {
              const url = entry.trim().split(/\s+/)[0];
              if (url.startsWith('http')) imgUrls.add(url);
            });
          }
        });

        document.querySelectorAll('[style]').forEach((el) => {
          const bg = el.style.backgroundImage;
          if (bg) {
            const match = bg.match(/url\(['"]?(https?:[^'")]+)['"]?\)/);
            if (match) imgUrls.add(match[1]);
          }
        });

        const rawLinkCandidates = [];
        const resolveLandmark = (el) => {
          const landmark = el.closest('main, nav, header, footer, aside, article, section, [role="main"], [role="navigation"], [role="banner"], [role="contentinfo"], [role="complementary"]');
          if (!landmark) return 'unknown';
          const role = (landmark.getAttribute('role') || '').toLowerCase();
          if (role === 'main' || landmark.tagName.toLowerCase() === 'main') return 'main';
          if (role === 'navigation' || landmark.tagName.toLowerCase() === 'nav') return 'nav';
          if (role === 'banner' || landmark.tagName.toLowerCase() === 'header') return 'header';
          if (role === 'contentinfo' || landmark.tagName.toLowerCase() === 'footer') return 'footer';
          if (role === 'complementary' || landmark.tagName.toLowerCase() === 'aside') return 'aside';
          return landmark.tagName.toLowerCase();
        };

        [...document.querySelectorAll('a[href]')].forEach((a, index) => {
          if (!a.href || !a.href.startsWith('http')) return;
          rawLinkCandidates.push({
            url: a.href,
            rawHref: a.getAttribute('href') || '',
            sourceKind: 'anchor',
            anchorText: (a.textContent || '').trim(),
            domOrder: index,
            landmark: resolveLandmark(a),
            rel: a.getAttribute('rel') || '',
            isHashOnly: (a.getAttribute('href') || '').trim().startsWith('#'),
          });
        });

        const forms = [...document.querySelectorAll('form')].map((form, _index) => ({
          selectorHint: makeSelectorHint(form),
          action: form.getAttribute('action') || '',
          resolvedAction: form.action || '',
          method: (form.getAttribute('method') || 'GET').toUpperCase(),
          hasPassword: form.querySelector('input[type="password"]') !== null,
          fields: [...form.querySelectorAll('input, select, textarea')].map((field) => ({
            selectorHint: makeSelectorHint(field),
            tag: field.tagName.toLowerCase(),
            type: field.getAttribute('type') || '',
            name: field.getAttribute('name') || '',
          })),
        }));

        forms.forEach((form, index) => {
          if (!form.resolvedAction || !form.resolvedAction.startsWith('http')) return;
          if (form.method !== 'GET') return;
          rawLinkCandidates.push({
            url: form.resolvedAction,
            rawHref: form.action || '',
            sourceKind: 'form',
            anchorText: '',
            domOrder: 100000 + index,
            landmark: 'unknown',
            rel: '',
            isHashOnly: false,
          });
        });

        const interactiveElements = [...document.querySelectorAll('button, [role="button"], [onclick], input[type="submit"], input[type="button"]')]
          .slice(0, 200)
          .map((el) => ({
            selectorHint: makeSelectorHint(el),
            text: (el.textContent || el.getAttribute('value') || '').trim().slice(0, 120),
            tag: el.tagName.toLowerCase(),
            hasOnClick: el.hasAttribute('onclick'),
          }));

        return {
          liveImageUrls: [...imgUrls],
          linkCandidates: [
            ...rawLinkCandidates,
            ...recordedRoutes
              .filter((item) => typeof item === 'string')
              .map((item, index) => ({
                url: item,
                rawHref: item,
                sourceKind: 'spa-route',
                anchorText: '',
                domOrder: 200000 + index,
                landmark: 'unknown',
                rel: '',
                isHashOnly: false,
              })),
          ],
          forms,
          interactiveElements,
          title: document.title || '',
          documentEncoding: document.characterSet || document.charset || 'utf-8',
          routeCount: recordedRoutes.length,
          scriptCount: document.querySelectorAll('script').length,
        };
      });

      const classification = classifyPageSnapshot(pageSnapshot, this.page.url(), {
        crawlProfile: this.crawlProfile,
        enableRepresentativeQA: this.enableRepresentativeQA,
        takeScreenshot: this.takeScreenshot,
      });

      const linkCandidates = (pageSnapshot.linkCandidates || [])
        .map((candidate) => enrichLinkCandidate({
          ...candidate,
          discoveredFromPageClass: classification.pageClass,
        }, {
          currentPageUrl: this.page.url(),
          startUrl: this.frontierOriginUrl,
          domainScope: this.domainScope,
          discoveredFromPageClass: classification.pageClass,
        }))
        .filter(Boolean);

      logger.update('Extracting computed styles');
      const computedStyles = await ComputedStyleExtractor.extract(this.page);

      let screenshot = null;
      if (classification.shouldCaptureScreenshot) {
        logger.update('Taking screenshot');
        const screenshotResult = await this._captureScreenshot();
        screenshot = screenshotResult.buffer;
        captureWarnings.push(...screenshotResult.warnings);
      }

      const sessionStorageState = await this.page.evaluate(() => {
        const state = {};
        for (let i = 0; i < window.sessionStorage.length; i += 1) {
          const key = window.sessionStorage.key(i);
          if (!key) continue;
          state[key] = window.sessionStorage.getItem(key);
        }
        return state;
      }).catch((err) => {
        logger.debug(`sessionStorage capture failed: ${err.message}`);
        return {};
      });

      let storageState = null;
      if (this.captureDir) {
        await ensureDir(this.captureDir);
        storageState = await context.storageState({
          path: path.join(this.captureDir, `${this._safeFileBase(this.url)}.storage-state.json`),
        });
        await fs.writeFile(
          path.join(this.captureDir, `${this._safeFileBase(this.url)}.session-storage.json`),
          JSON.stringify(sessionStorageState, null, 2),
          'utf-8',
        );
      } else {
        storageState = await context.storageState();
      }

      const graphqlCapture = await this._captureGraphqlArtifacts({
        context,
        storageState,
      });

      const stats = this.interceptor.getStats();
      const totalResources = Object.values(stats).reduce((a, b) => a + b, 0);
      const resourceCountAfter = this.interceptor.getResponseCount();
      const qa = {
        requestedChecks: {
          resourceCount: this.enableRepresentativeQA,
          textSimilarity: this.enableRepresentativeQA,
          screenshotSimilarity: this.enableRepresentativeQA && classification.shouldCaptureScreenshot,
        },
        observedResources: resourceCountAfter - resourceCountBefore,
        screenshotCaptured: Boolean(screenshot),
        rawTextLength: extractTextLength(html),
        processedTextLength: extractTextLength(html),
        interactionCandidates: interactionResult.candidates.length,
        interactionsAttempted: interactionResult.attempted,
        interactionRoutesDiscovered: interactionResult.discoveredRoutes.length,
      };
      logger.succeed(`Crawler complete: ${totalResources} resources, ${pageSnapshot.liveImageUrls.length} images, ${linkCandidates.length} links`);

      return {
        html,
        interceptor: this.interceptor,
        screenshot,
        computedStyles,
        liveImageUrls: pageSnapshot.liveImageUrls,
        linkCandidates: [
          ...linkCandidates,
          ...interactionResult.discoveredRoutes
            .map((route, index) => enrichLinkCandidate({
              url: route,
              rawHref: route,
              sourceKind: 'spa-route',
              anchorText: '',
              domOrder: 300000 + index,
              landmark: 'unknown',
              rel: '',
              isHashOnly: false,
              discoveredFromPageClass: classification.pageClass,
            }, {
              currentPageUrl: this.page.url(),
              startUrl: this.frontierOriginUrl,
              domainScope: this.domainScope,
              discoveredFromPageClass: classification.pageClass,
            }))
            .filter(Boolean),
        ],
        internalLinks: [...new Set([
          ...linkCandidates.map((candidate) => candidate.normalizedUrl || candidate.url),
          ...interactionResult.discoveredRoutes,
        ])],
        forms: pageSnapshot.forms,
        interactiveElements: pageSnapshot.interactiveElements,
        interactionCandidates: interactionResult.candidates,
        title: pageSnapshot.title,
        documentEncoding: pageSnapshot.documentEncoding,
        classification,
        crawlProfile: this.crawlProfile,
        networkPosture: this.networkPosture,
        qa,
        finalUrl: this.page.url(),
        status: response?.status() || null,
        storageState,
        sessionStorageState,
        graphqlArtifacts: graphqlCapture.artifacts,
        captureWarnings: [...captureWarnings, ...interactionResult.warnings, ...graphqlCapture.warnings],
      };
    } catch (err) {
      logger.fail(`Failed to crawl page: ${err.message}`);
      throw err;
    } finally {
      const context = this.page?.context?.();
      if (context) {
        await this._runWithTimeout('Browser context shutdown', () => context.close());
      }
      if (!this.injectedBrowser && this.browser) {
        await this._runWithTimeout('Browser shutdown', () => this.browser.close());
      }
    }
  }

  async _autoScroll() {
    if (!this.scrollCount || this.scrollCount <= 0) {
      return { warnings: [] };
    }

    try {
      await this.page.evaluate(async ({ scrollCount, scrollIntervalMs }) => {
        const docEl = document.documentElement;
        const body = document.body;
        const scrollingElement = document.scrollingElement;
        const heightCandidates = [
          scrollingElement?.scrollHeight,
          docEl?.scrollHeight,
          body?.scrollHeight,
          window.innerHeight,
        ].filter((value) => Number.isFinite(value) && value > 0);
        const pageHeight = heightCandidates.length > 0 ? Math.max(...heightCandidates) : 0;
        const viewportHeight = Number.isFinite(window.innerHeight) && window.innerHeight > 0
          ? window.innerHeight
          : Math.max(docEl?.clientHeight || 0, body?.clientHeight || 0, 0);

        if (!pageHeight || pageHeight <= viewportHeight) {
          return;
        }

        await new Promise((resolve) => {
          let count = 0;
          const distance = Math.max(pageHeight / Math.max(scrollCount, 1), 300);
          const timer = setInterval(() => {
            window.scrollBy(0, distance);
            count += 1;
            if (count >= scrollCount) {
              clearInterval(timer);
              window.scrollTo(0, 0);
              resolve();
            }
          }, scrollIntervalMs);
        });
      }, {
        scrollCount: this.scrollCount,
        scrollIntervalMs: SCROLL_INTERVAL_MS,
      });
      return { warnings: [] };
    } catch (error) {
      const warning = `Auto-scroll skipped: ${error.message}`;
      logger.warn(warning);
      return { warnings: [warning] };
    }
  }

  async _measureScrollContext() {
    return this.page.evaluate(() => {
      const docEl = document.documentElement;
      const body = document.body;
      const scrollingElement = document.scrollingElement;
      const heightCandidates = [
        scrollingElement?.scrollHeight,
        docEl?.scrollHeight,
        body?.scrollHeight,
        window.innerHeight,
      ].filter((value) => Number.isFinite(value) && value > 0);
      const pageHeight = heightCandidates.length > 0 ? Math.max(...heightCandidates) : 0;
      const viewportHeight = Number.isFinite(window.innerHeight) && window.innerHeight > 0
        ? window.innerHeight
        : Math.max(docEl?.clientHeight || 0, body?.clientHeight || 0, 0);
      let scrollTargetKind = 'none';
      if (scrollingElement) {
        scrollTargetKind = 'scrollingElement';
      } else if (docEl) {
        scrollTargetKind = 'documentElement';
      } else if (body) {
        scrollTargetKind = 'body';
      }

      return {
        pageHeight,
        viewportHeight,
        canScroll: pageHeight > viewportHeight,
        scrollTargetKind,
      };
    });
  }

  async _captureScreenshot() {
    const warnings = [];

    try {
      const scrollContext = await this._measureScrollContext();
      if (!scrollContext.pageHeight) {
        const warning = 'Screenshot height measurement skipped: page height unavailable';
        logger.warn(warning);
        warnings.push(warning);
        return {
          buffer: await this.page.screenshot(),
          warnings,
        };
      }

      if (scrollContext.pageHeight > MAX_SCREENSHOT_HEIGHT) {
        return {
          buffer: await this.page.screenshot({
            clip: { x: 0, y: 0, width: this.viewport.width, height: MAX_SCREENSHOT_HEIGHT },
          }),
          warnings,
        };
      }

      return {
        buffer: await this.page.screenshot({ fullPage: true }),
        warnings,
      };
    } catch (error) {
      const warning = `Screenshot fallback used: ${error.message}`;
      logger.warn(warning);
      warnings.push(warning);
      return {
        buffer: await this.page.screenshot(),
        warnings,
      };
    }
  }

  async _waitForImagesAndContent() {
    try {
      await Promise.race([
        this.page.evaluate(() => {
          const imgs = [...document.querySelectorAll('img')];
          if (imgs.length === 0) return Promise.resolve();
          return Promise.all(
            imgs.map((img) => {
              if (img.complete) return Promise.resolve();
              return new Promise((resolve) => {
                img.onload = resolve;
                img.onerror = resolve;
              });
            }),
          );
        }).catch((err) => logger.debug(`Image wait evaluate failed: ${err.message}`)),
        this.page.waitForTimeout(IMAGE_WAIT_TIMEOUT),
      ]);
    } catch (err) {
      logger.debug(`Image/content wait failed: ${err.message}`);
    }

    try {
      await this.page.waitForLoadState('networkidle', { timeout: NETWORK_IDLE_TIMEOUT });
    } catch (err) {
      // Network idle timeout is expected on long-polling or SSE sites.
      logger.debug(`Network idle wait skipped: ${err.message}`);
    }

    await this.page.waitForTimeout(1000);
  }

  async _runSafeInteractions() {
    if (!this.interactionBudget || this.interactionBudget <= 0) {
      return { candidates: [], discoveredRoutes: [], attempted: 0, warnings: [] };
    }

    const candidates = await this.page.evaluate((limit) => {
      const key = '__frontCloneInteractionCounter';
      window[key] = 0;

      const normalizeText = (value) => String(value || '').replace(/\s+/g, ' ').trim().slice(0, 120);
      const makeSelectorHint = (el) => {
        if (!(el instanceof Element)) return '';
        if (el.id) return `#${el.id}`;
        const testId = el.getAttribute('data-testid');
        if (testId) return `${el.tagName.toLowerCase()}[data-testid="${testId}"]`;
        const classes = [...el.classList].slice(0, 2).join('.');
        return classes ? `${el.tagName.toLowerCase()}.${classes}` : el.tagName.toLowerCase();
      };
      const isHidden = (el) => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display === 'none'
          || style.visibility === 'hidden'
          || style.pointerEvents === 'none'
          || rect.width === 0
          || rect.height === 0;
      };
      const isSafe = (el) => {
        if (!(el instanceof HTMLElement) || isHidden(el)) return false;
        const text = normalizeText(el.textContent || el.getAttribute('aria-label') || el.getAttribute('value'));
        const lowerText = text.toLowerCase();
        const href = (el.getAttribute('href') || '').toLowerCase();
        const onClick = (el.getAttribute('onclick') || '').toLowerCase();
        const role = (el.getAttribute('role') || '').toLowerCase();
        const type = (el.getAttribute('type') || '').toLowerCase();
        const insideForm = Boolean(el.closest('form'));
        const destructive = /(logout|signout|sign out|delete|remove|checkout|pay|purchase|download|submit)/.test(`${lowerText} ${href} ${onClick}`);
        if (destructive || href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:')) return false;
        if (insideForm && ['submit', 'image'].includes(type)) return false;
        if (el.tagName.toLowerCase() === 'input' && !['button'].includes(type)) return false;
        if (el.tagName.toLowerCase() === 'a') return true;
        if (['tab', 'button'].includes(role)) return true;
        if (el.hasAttribute('aria-expanded')) return true;
        if (el.tagName.toLowerCase() === 'button' && type !== 'submit') return true;
        return /(tab|more|show|open|expand|next|prev|menu|filter)/.test(lowerText);
      };

      return [...document.querySelectorAll('a[href], button, [role="tab"], [role="button"], [aria-expanded], input[type="button"]')]
        .filter((el) => isSafe(el))
        .slice(0, limit)
        .map((el) => {
          const id = `fc-int-${window[key]++}`;
          el.setAttribute('data-front-clone-interaction-id', id);
          return {
            id,
            tag: el.tagName.toLowerCase(),
            role: el.getAttribute('role') || '',
            text: normalizeText(el.textContent || el.getAttribute('aria-label') || el.getAttribute('value')),
            selectorHint: makeSelectorHint(el),
          };
        });
    }, Math.min(this.interactionBudget, SAFE_INTERACTION_CANDIDATE_LIMIT));

    const discoveredRoutes = new Set();
    const warnings = [];
    let attempted = 0;

    for (const candidate of candidates) {
      attempted += 1;
      const beforeUrl = this.page.url();
      const beforeTextLength = await this.page.evaluate(() => document.body?.innerText?.length || 0).catch(() => 0);

      try {
        const locator = this.page.locator(`[data-front-clone-interaction-id="${candidate.id}"]`).first();
        if (!await locator.isVisible().catch(() => false)) continue;

        const [urlWaitResult, clickResult] = await Promise.allSettled([
          this.page.waitForURL((url) => url.href !== beforeUrl, { timeout: SAFE_INTERACTION_TIMEOUT }),
          locator.click({ timeout: SAFE_INTERACTION_TIMEOUT }),
        ]);
        if (clickResult.status === 'rejected') {
          throw clickResult.reason;
        }

        if (urlWaitResult.status === 'fulfilled' || this.page.url() !== beforeUrl) {
          discoveredRoutes.add(this.page.url());
          await this._waitForInteractionSettled(beforeTextLength);
          // goBack may fail if the navigation was intercepted or the context is closing; safe to ignore.
          await this.page.goBack({ waitUntil: 'domcontentloaded', timeout: PAGE_LOAD_TIMEOUT }).catch(() => {});
          await this._waitForImagesAndContent();
          continue;
        }

        const currentTextLength = await this.page.evaluate(() => document.body?.innerText?.length || 0).catch(() => beforeTextLength);
        const domChanged = Math.abs(currentTextLength - beforeTextLength) > 20;
        const visibleMain = await this.page.locator('main, body').first().isVisible().catch(() => true);
        if (domChanged && visibleMain) {
          const routes = await this.page.evaluate(() => Array.isArray(window.__FRONT_CLONE_ROUTES__) ? window.__FRONT_CLONE_ROUTES__ : []);
          for (const route of routes) {
            if (typeof route === 'string') discoveredRoutes.add(route);
          }
        }
      } catch (error) {
        warnings.push(`Safe interaction skipped for ${candidate.selectorHint || candidate.tag}: ${error.message}`);
      }
    }

    await this.page.evaluate(() => {
      document.querySelectorAll('[data-front-clone-interaction-id]').forEach((el) => {
        el.removeAttribute('data-front-clone-interaction-id');
      });
    }).catch(() => {});

    return {
      candidates,
      discoveredRoutes: [...discoveredRoutes],
      attempted,
      warnings,
    };
  }

  async _waitForInteractionSettled(beforeTextLength) {
    await this.page.waitForLoadState('domcontentloaded', { timeout: SAFE_INTERACTION_TIMEOUT }).catch(() => {});
    await this.page.waitForTimeout(300);
    const currentTextLength = await this.page.evaluate(() => document.body?.innerText?.length || 0).catch(() => beforeTextLength);
    const domChanged = Math.abs(currentTextLength - beforeTextLength) > 20;
    if (!domChanged) {
      await this.page.locator('main, body').first().isVisible({ timeout: SAFE_INTERACTION_TIMEOUT }).catch(() => {});
    }
  }

  async _captureGraphqlArtifacts({ context: _context, storageState }) {
    if (!this.enableGraphqlIntrospection) {
      return { artifacts: [], warnings: [] };
    }

    const warnings = [];
    const artifacts = [];
    const seen = new Set();
    const currentUrl = this.page?.url() || this.url;
    const currentOrigin = new URL(currentUrl).origin;
    const xhrRequests = this.interceptor.getXhrRequests();

    for (const request of xhrRequests) {
      const endpoint = this._getGraphqlEndpoint(request);
      if (!endpoint || seen.has(endpoint)) continue;

      try {
        if (new URL(endpoint).origin !== currentOrigin) continue;
        seen.add(endpoint);

        const result = await this.page.evaluate(async ({ endpoint: resolvedEndpoint, query }) => {
          try {
            const response = await fetch(resolvedEndpoint, {
              method: 'POST',
              headers: {
                'content-type': 'application/json',
                accept: 'application/graphql-response+json, application/json',
              },
              credentials: 'include',
              body: JSON.stringify({ query }),
            });
            const text = await response.text();
            return {
              ok: response.ok,
              status: response.status,
              contentType: response.headers.get('content-type') || '',
              bodyText: text,
            };
          } catch (error) {
            return {
              ok: false,
              status: 0,
              contentType: '',
              error: error.message,
              bodyText: '',
            };
          }
        }, {
          endpoint,
          query: getIntrospectionQuery(),
        });

        if (!result.ok) {
          warnings.push(`GraphQL introspection unavailable for ${endpoint}: ${result.error || `HTTP ${result.status}`}`);
          continue;
        }

        const parsed = safeJsonParse(result.bodyText);
        if (!parsed?.data?.__schema) {
          warnings.push(`GraphQL introspection returned no schema for ${endpoint}`);
          continue;
        }

        artifacts.push({
          endpoint,
          capturedAt: new Date().toISOString(),
          responseContentType: result.contentType,
          httpStatus: result.status,
          authSessionHash: this._hashGraphqlSession(storageState),
          schemaMayBeClientSpecific: true,
          schema: parsed,
        });
      } catch (error) {
        warnings.push(`GraphQL introspection failed for ${endpoint}: ${error.message}`);
      }
    }

    return { artifacts, warnings };
  }

  _getGraphqlEndpoint(request) {
    try {
      const requestUrl = new URL(request.url);
      const requestBody = safeJsonParse(request.postData);
      const searchPayload = requestUrl.searchParams;
      const looksLikeGraphql = requestUrl.pathname.toLowerCase().includes('graphql')
        || Boolean(requestBody && typeof requestBody === 'object' && ('query' in requestBody || 'operationName' in requestBody || 'extensions' in requestBody))
        || searchPayload.has('query')
        || searchPayload.has('operationName')
        || searchPayload.has('variables');
      return looksLikeGraphql ? requestUrl.origin + requestUrl.pathname : null;
    } catch {
      return null;
    }
  }

  _hashGraphqlSession(storageState) {
    const payload = storageState && typeof storageState === 'object' ? storageState : {};
    return this._safeFileBase(JSON.stringify(payload)).slice(0, 24);
  }

  _safeFileBase(value) {
    return String(value || 'page')
      .replace(/[^a-zA-Z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 80) || 'page';
  }
}

function extractTextLength(html) {
  return String(html || '')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .length;
}

function safeJsonParse(value) {
  if (!value) return value ?? null;
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function getIntrospectionQuery() {
  return `query IntrospectionQuery {
    __schema {
      queryType { name }
      mutationType { name }
      subscriptionType { name }
      types {
        kind
        name
        description
        fields(includeDeprecated: true) {
          name
          description
          args {
            name
            description
            defaultValue
            type {
              kind
              name
              ofType { kind name ofType { kind name } }
            }
          }
          type {
            kind
            name
            ofType { kind name ofType { kind name } }
          }
          isDeprecated
          deprecationReason
        }
      }
    }
  }`;
}
