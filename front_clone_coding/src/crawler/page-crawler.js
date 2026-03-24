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
} from '../utils/constants.js';
import {
  DEFAULT_CRAWL_PROFILE,
  DEFAULT_NETWORK_POSTURE,
  classifyPageSnapshot,
  getEffectiveWaitTime,
} from '../utils/crawl-config.js';
import fs from 'fs/promises';
import path from 'path';
import { ensureDir } from '../utils/file-utils.js';

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
    this.storageState = options.storageState || null;
    this.cookieFile = options.cookieFile || null;
    this.headful = options.headful || false;
    this.captureDir = options.captureDir || null;

    this.browser = null;
    this.injectedBrowser = options.browser || null;
    this.page = null;
    this.interceptor = options.interceptor || new NetworkInterceptor();
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
      if (effectiveWaitTime > 0) {
        logger.update(`Waiting ${effectiveWaitTime}ms after load`);
        await this.page.waitForTimeout(effectiveWaitTime);
      }

      logger.update('Running auto-scroll to trigger lazy loaded content');
      await this._autoScroll();

      logger.update('Waiting for media and rendered content');
      await this._waitForImagesAndContent();

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

        const links = new Set();
        document.querySelectorAll('a[href]').forEach((a) => {
          if (a.href && a.href.startsWith('http')) {
            links.add(a.href);
          }
        });

        const forms = [...document.querySelectorAll('form')].map((form) => ({
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
          internalLinks: [...new Set([...links, ...recordedRoutes.filter((item) => typeof item === 'string')])],
          forms,
          interactiveElements,
          title: document.title || '',
          routeCount: recordedRoutes.length,
          scriptCount: document.querySelectorAll('script').length,
        };
      });

      const classification = classifyPageSnapshot(pageSnapshot, this.page.url(), {
        crawlProfile: this.crawlProfile,
        enableRepresentativeQA: this.enableRepresentativeQA,
        takeScreenshot: this.takeScreenshot,
      });

      logger.update('Extracting computed styles');
      const computedStyles = await ComputedStyleExtractor.extract(this.page);

      let screenshot = null;
      if (classification.shouldCaptureScreenshot) {
        logger.update('Taking screenshot');
        const maxScreenshotHeight = MAX_SCREENSHOT_HEIGHT;
        const pageHeight = await this.page.evaluate(() => document.body.scrollHeight);
        if (pageHeight > maxScreenshotHeight) {
          screenshot = await this.page.screenshot({
            clip: { x: 0, y: 0, width: this.viewport.width, height: maxScreenshotHeight },
          });
        } else {
          screenshot = await this.page.screenshot({ fullPage: true });
        }
      }

      const sessionStorageState = await this.page.evaluate(() => {
        const state = {};
        for (let i = 0; i < window.sessionStorage.length; i += 1) {
          const key = window.sessionStorage.key(i);
          if (!key) continue;
          state[key] = window.sessionStorage.getItem(key);
        }
        return state;
      }).catch(() => ({}));

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
      };
      logger.succeed(`Crawler complete: ${totalResources} resources, ${pageSnapshot.liveImageUrls.length} images, ${pageSnapshot.internalLinks.length} links`);

      return {
        html,
        interceptor: this.interceptor,
        screenshot,
        computedStyles,
        liveImageUrls: pageSnapshot.liveImageUrls,
        internalLinks: pageSnapshot.internalLinks,
        forms: pageSnapshot.forms,
        interactiveElements: pageSnapshot.interactiveElements,
        title: pageSnapshot.title,
        classification,
        crawlProfile: this.crawlProfile,
        networkPosture: this.networkPosture,
        qa,
        finalUrl: this.page.url(),
        status: response?.status() || null,
        storageState,
        sessionStorageState,
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
      return;
    }

    await this.page.evaluate(async ({ scrollCount, scrollIntervalMs }) => {
      await new Promise((resolve) => {
        let count = 0;
        const pageHeight = document.body.scrollHeight;
        const distance = Math.max(pageHeight / scrollCount, 300);
        const timer = setInterval(() => {
          window.scrollBy(0, distance);
          count++;
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
        }).catch(() => {}),
        this.page.waitForTimeout(IMAGE_WAIT_TIMEOUT),
      ]);
    } catch {
      // Ignore transient browser timing errors.
    }

    try {
      await this.page.waitForLoadState('networkidle', { timeout: NETWORK_IDLE_TIMEOUT });
    } catch {
      // Ignore network idle timeout on long-polling sites.
    }

    await this.page.waitForTimeout(1000);
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
