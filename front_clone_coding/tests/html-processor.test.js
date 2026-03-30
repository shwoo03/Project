import test from 'node:test';
import assert from 'node:assert/strict';
import * as cheerio from 'cheerio';

import HtmlProcessor from '../src/processor/html-processor.js';
import { buildPagePathFallbackMap, extractPageReplaySignals } from '../src/index.js';

test('HtmlProcessor disables unmapped navigation targets while preserving safe protocols', () => {
  const html = [
    '<html><head></head><body>',
    '<a id="local" href="/dashboard">Dashboard</a>',
    '<a id="internal-uncloned" href="/settings">Settings</a>',
    '<a id="external" href="https://policies.google.com/privacy" target="_blank">Privacy</a>',
    '<area id="support-map" href="https://help.example.com/support" shape="rect" coords="0,0,10,10">',
    '<a id="hash" href="#faq">FAQ</a>',
    '<a id="mail" href="mailto:test@example.com">Mail</a>',
    '<form id="signup" action="https://example.com/signup" method="post"></form>',
    '</body></html>',
  ].join('');

  const urlMap = new Map([
    ['https://example.com/dashboard', 'dashboard.html'],
  ]);

  const processor = new HtmlProcessor('https://example.com');
  const output = processor.process(html, urlMap, 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#local').attr('href'), './dashboard');
  assert.equal($('#internal-uncloned').attr('href'), '#');
  assert.equal($('#internal-uncloned').attr('data-disabled-reason'), 'uncloned-target');
  assert.equal($('#external').attr('href'), '#');
  assert.equal($('#external').attr('data-disabled-link'), 'true');
  assert.equal($('#external').attr('data-disabled-reason'), 'external-target');
  assert.equal($('#external').attr('aria-disabled'), 'true');
  assert.equal($('#external').attr('onclick'), 'return false;');
  assert.equal($('#external').attr('target'), undefined);
  assert.equal($('#support-map').attr('href'), '#');
  assert.equal($('#support-map').attr('data-disabled-link'), 'true');
  assert.equal($('#support-map').attr('data-disabled-reason'), 'uncloned-target');
  assert.equal($('#hash').attr('href'), '#faq');
  assert.equal($('#mail').attr('href'), 'mailto:test@example.com');
  assert.equal($('#signup').attr('action'), '#');
  assert.equal($('#signup').attr('data-disabled-link'), 'true');
  assert.equal($('#signup').attr('data-disabled-reason'), 'uncloned-target');
  assert.equal($('#signup').attr('onsubmit'), 'return false;');
  assert.equal($('script[data-front-clone-guard="true"]').attr('src'), '/__front_clone_runtime_guard__.js');
});

test('HtmlProcessor rewrites option[value] to replayable local routes and disables unsaved in-scope targets', () => {
  const html = [
    '<html><head></head><body>',
    '<select>',
    '<option id="saved" value="https://example.com/Main.do?menuNo=1003">Saved</option>',
    '<option id="unsaved" value="https://example.com/Main.do?menuNo=1200">Unsaved</option>',
    '<option id="label" value="all">All</option>',
    '</select>',
    '</body></html>',
  ].join('');

  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map([
        ['https://example.com/Main.do?menuNo=1003', {
          savedPath: 'Main.do__q_menuNo-1003.html',
          replayRoute: '/Main.do__q_menuNo-1003',
          replayable: true,
        }],
      ]),
      fallbackMap: new Map(),
    },
  });

  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#saved').attr('value'), '/Main.do__q_menuNo-1003');
  assert.equal($('#unsaved').attr('value'), '');
  assert.equal($('#unsaved').attr('data-disabled-reason'), 'uncloned-target');
  assert.equal($('#label').attr('value'), 'all');
});

test('HtmlProcessor rewrites inline hidden navigation handlers to local replay routes', () => {
  const html = [
    '<html><head></head><body>',
    '<button id="cta" onclick="location.href=\'https://example.com/Main.do?menuNo=1003\'">Go</button>',
    '<a id="js-link" href="javascript:window.open(\'https://example.com/login?serverState=abc\')">Login</a>',
    '</body></html>',
  ].join('');

  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map([
        ['https://example.com/Main.do?menuNo=1003', {
          savedPath: 'Main.do__q_menuNo-1003.html',
          replayRoute: '/Main.do__q_menuNo-1003',
          replayable: true,
        }],
        ['https://example.com/login', {
          savedPath: 'login.html',
          replayRoute: '/login',
          replayable: true,
        }],
      ]),
      fallbackMap: new Map([
        ['example.com/login', {
          savedPath: 'login.html',
          replayRoute: '/login',
          replayable: true,
        }],
      ]),
    },
  });

  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#cta').attr('onclick'), "location.href='/Main.do__q_menuNo-1003'");
  assert.equal($('#cta').attr('data-hidden-navigation-localized'), 'true');
  assert.equal($('#js-link').attr('href'), '/login');
  assert.equal($('#js-link').attr('data-hidden-navigation-localized'), 'true');
});

test('HtmlProcessor disables unsaved hidden navigation targets instead of leaking live routes', () => {
  const html = [
    '<html><head></head><body>',
    '<button id="missing" onclick="window.location.href=\'https://example.com/Main.do?menuNo=1200\'">Missing</button>',
    '<a id="external-js" href="javascript:window.open(\'https://outside.example.org/help\')">External</a>',
    '</body></html>',
  ].join('');

  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map(),
    },
  });

  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#missing').attr('onclick'), 'return false;');
  assert.equal($('#missing').attr('data-hidden-navigation-disabled'), 'true');
  assert.equal($('#missing').attr('data-disabled-reason'), 'uncloned-target');
  assert.equal($('#external-js').attr('href'), '#');
  assert.equal($('#external-js').attr('data-hidden-navigation-disabled'), 'true');
  assert.equal($('#external-js').attr('data-disabled-reason'), 'external-target');
});

test('HtmlProcessor does not force ambiguous dynamic hidden navigation handlers to a local route', () => {
  const html = '<html><body><button id="dynamic" onclick="goPage(baseUrl + menuNo)">Go</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', { useBaseHref: true });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#dynamic').attr('onclick'), 'goPage(baseUrl + menuNo)');
  assert.equal($('#dynamic').attr('data-hidden-navigation-localized'), undefined);
  assert.equal($('#dynamic').attr('data-hidden-navigation-disabled'), undefined);
});

test('HtmlProcessor rewrites bare relative hidden navigation targets and simple string concatenations', () => {
  const html = [
    '<html><head></head><body>',
    '<button id="wrapper" onclick="goUrl(\'Main.do?menuNo=1003\')">Menu</button>',
    '<button id="concat" onclick="location.href=\'/Main.do?menuNo=\' + \'1003\'">Concat</button>',
    '</body></html>',
  ].join('');

  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map([
        ['https://example.com/Main.do?menuNo=1003', {
          savedPath: 'Main.do__q_menuNo-1003.html',
          replayRoute: '/Main.do__q_menuNo-1003',
          replayable: true,
        }],
      ]),
      fallbackMap: new Map(),
    },
  });

  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#wrapper').attr('onclick'), "goUrl('/Main.do__q_menuNo-1003')");
  assert.equal($('#wrapper').attr('data-hidden-navigation-localized'), 'true');
  assert.equal($('#wrapper').attr('data-hidden-navigation-class'), 'page-route');
  assert.equal($('#concat').attr('onclick'), "location.href='/Main.do__q_menuNo-1003'");
  assert.equal($('#concat').attr('data-hidden-navigation-localized'), 'true');
  assert.equal($('#concat').attr('data-hidden-navigation-class'), 'page-route');
});

test('HtmlProcessor marks value-driven hidden navigation as localized when replayable option values remain', () => {
  const html = [
    '<html><head></head><body>',
    '<select id="nav" onchange="window.open(value, \'_blank\');">',
    '<option value="">Choose</option>',
    '<option value="gallery/galleryMain.do">Gallery</option>',
    '<option value="Main.do?menuNo=1003">Menu</option>',
    '</select>',
    '</body></html>',
  ].join('');

  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map([
        ['https://example.com/gallery/galleryMain.do', {
          savedPath: 'gallery/galleryMain.do.html',
          replayRoute: '/gallery/galleryMain.do',
          replayable: true,
        }],
        ['https://example.com/Main.do?menuNo=1003', {
          savedPath: 'Main.do__q_menuNo-1003.html',
          replayRoute: '/Main.do__q_menuNo-1003',
          replayable: true,
        }],
      ]),
      fallbackMap: new Map(),
    },
  });

  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#nav').attr('data-hidden-navigation-localized'), 'true');
  assert.equal($('#nav').attr('data-hidden-navigation-class'), 'value-driven-navigation');
  assert.equal($('#nav').attr('data-hidden-navigation-count'), '2');
  const optionValues = $('#nav option').toArray().map((el) => $(el).attr('value'));
  assert.deepEqual(optionValues, ['', '/gallery/galleryMain.do', '/Main.do__q_menuNo-1003']);
});

test('HtmlProcessor rewrites mapped asset URLs embedded inside inline scripts', () => {
  const html = [
    '<html><head></head><body>',
    '<script>',
    'window.__DATA__ = {"hero":"https:\\x2F\\x2Fcdn.example.com\\x2Fimg\\x2Fhero.webp","card":"https://cdn.example.com/img/card.webp"};',
    '</script>',
    '</body></html>',
  ].join('');

  const urlMap = new Map([
    ['https://cdn.example.com/img/hero.webp', 'img/cdn.example.com/img/hero.webp'],
    ['https://cdn.example.com/img/card.webp', 'img/cdn.example.com/img/card.webp'],
  ]);

  const processor = new HtmlProcessor('https://example.com', { useBaseHref: true });
  const output = processor.process(html, urlMap, 'index.html');

  assert.equal(output.includes('https:\\x2F\\x2Fcdn.example.com\\x2Fimg\\x2Fhero.webp'), false);
  assert.equal(output.includes('https://cdn.example.com/img/card.webp'), false);
  assert.match(output, /"hero":"\/img\/cdn\.example\.com\/img\/hero\.webp"/);
  assert.match(output, /"card":"\/img\/cdn\.example\.com\/img\/card\.webp"/);
});

test('HtmlProcessor rewrites serialized same-scope navigation URLs using unique host-path fallback', () => {
  const html = [
    '<html><head></head><body>',
    '<script>',
    'window.__DATA__ = {"help":"https://help.example.com","contact":"https:\\x2F\\x2Fhelp.example.com\\x2Fcontactus","login":"https:\\u002F\\u002Fwww.example.com\\u002Flogin?serverState=abc"};',
    '</script>',
    '</body></html>',
  ].join('');

  const urlMap = new Map([
    ['https://www.example.com/', 'index.html'],
    ['https://help.example.com/en', 'en.html'],
    ['https://www.example.com/login', 'login.html'],
  ]);

  const processor = new HtmlProcessor('https://www.example.com', {
    useBaseHref: true,
    pagePathFallbackMap: new Map([
      ['help.example.com/', 'en.html'],
      ['help.example.com/contactus', 'en/contactus.html'],
      ['www.example.com/login', 'login.html'],
    ]),
  });

  const output = processor.process(html, urlMap, 'index.html');

  assert.equal(output.includes('https://help.example.com'), false);
  assert.equal(output.includes('https:\\x2F\\x2Fhelp.example.com\\x2Fcontactus'), false);
  assert.equal(output.includes('https:\\u002F\\u002Fwww.example.com\\u002Flogin?serverState=abc'), false);
  assert.match(output, /"help":"\/en"/);
  assert.match(output, /"contact":"\/en\/contactus"/);
  assert.match(output, /"login":"\/login"/);
});

test('HtmlProcessor does not force ambiguous same-scope serialized URLs to a local page', () => {
  const html = [
    '<html><head></head><body>',
    '<script>window.__DATA__ = {"help":"https://help.example.com/contactus"};</script>',
    '</body></html>',
  ].join('');

  const processor = new HtmlProcessor('https://www.example.com', {
    useBaseHref: true,
    pagePathFallbackMap: new Map(),
  });

  const output = processor.process(html, new Map(), 'index.html');

  assert.match(output, /https:\/\/help\.example\.com\/contactus/);
});

test('HtmlProcessor rewrites inline public asset base paths for runtime chunk loading', () => {
  const html = [
    '<html><head></head><body>',
    '<script>window.__public_path__ = "https://assets.example.com/app/";</script>',
    '</body></html>',
  ].join('');

  const urlMap = new Map([
    ['https://assets.example.com/app/runtime/chunk.js', 'js/external/assets.example.com/app/runtime/chunk.js'],
  ]);

  const processor = new HtmlProcessor('https://example.com', { useBaseHref: true });
  const output = processor.process(html, urlMap, 'index.html');

  assert.match(output, /window\.__public_path__ = "\/js\/external\/assets\.example\.com\/app\/"/);
});

test('HtmlProcessor rewrites common bundler asset base assignments generically', () => {
  const html = [
    '<html><head></head><body>',
    '<script>',
    '__webpack_public_path__ = "https://cdn.example.com/assets/";',
    '__webpack_require__.p = "https://cdn.example.com/assets/";',
    'window.assetPrefix = "https://cdn.example.com/assets/";',
    'const config = { publicPath: "https://cdn.example.com/assets/" };',
    '</script>',
    '</body></html>',
  ].join('');

  const urlMap = new Map([
    ['https://cdn.example.com/assets/chunks/app.js', 'js/external/cdn.example.com/assets/chunks/app.js'],
  ]);

  const processor = new HtmlProcessor('https://example.com', { useBaseHref: true });
  const output = processor.process(html, urlMap, 'index.html');

  assert.match(output, /__webpack_public_path__ = "\/js\/external\/cdn\.example\.com\/assets\/"/);
  assert.match(output, /__webpack_require__\.p = "\/js\/external\/cdn\.example\.com\/assets\/"/);
  assert.match(output, /window\.assetPrefix = "\/js\/external\/cdn\.example\.com\/assets\/"/);
  assert.match(output, /publicPath: "\/js\/external\/cdn\.example\.com\/assets\/"/);
});

test('HtmlProcessor removes integrity and crossorigin from local rewritten script and stylesheet assets', () => {
  const html = [
    '<html><head>',
    '<link rel="stylesheet" href="https://cdn.example.com/app.css" integrity="sha512-old" crossorigin="anonymous">',
    '</head><body>',
    '<script src="https://cdn.example.com/app.js" integrity="sha512-old" crossorigin="anonymous"></script>',
    '</body></html>',
  ].join('');

  const urlMap = new Map([
    ['https://cdn.example.com/app.css', 'css/external/cdn.example.com/app.css'],
    ['https://cdn.example.com/app.js', 'js/external/cdn.example.com/app.js'],
  ]);

  const processor = new HtmlProcessor('https://example.com', { useBaseHref: true });
  const output = processor.process(html, urlMap, 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('link').attr('href'), '/css/external/cdn.example.com/app.css');
  assert.equal($('script[src="/js/external/cdn.example.com/app.js"]').length, 1);
  assert.equal($('link').attr('integrity'), undefined);
  assert.equal($('script[src="/js/external/cdn.example.com/app.js"]').attr('integrity'), undefined);
  assert.equal($('link').attr('crossorigin'), undefined);
  assert.equal($('script[src="/js/external/cdn.example.com/app.js"]').attr('crossorigin'), undefined);
});

test('buildPagePathFallbackMap adds locale-stripped aliases for uniquely captured localized pages', () => {
  const fallbackMap = buildPagePathFallbackMap(new Map([
    ['https://www.example.com/en-us/login', 'www.example.com/en-us/login.html'],
    ['https://www.example.com/en-us/help', 'www.example.com/en-us/help.html'],
  ]));

  assert.equal(fallbackMap.get('www.example.com/en-us/login'), 'www.example.com/en-us/login.html');
  assert.equal(fallbackMap.get('www.example.com/login'), 'www.example.com/en-us/login.html');
  assert.equal(fallbackMap.get('www.example.com/help'), 'www.example.com/en-us/help.html');
});

test('HtmlProcessor rewrites localized login navigation to extensionless local replay routes', () => {
  const html = '<html><head></head><body><a id="login" href="https://www.example.com/login">Sign In</a></body></html>';
  const fallbackMap = buildPagePathFallbackMap(new Map([
    ['https://www.example.com/en-us/login', 'www.example.com/en-us/login.html'],
  ]));

  const processor = new HtmlProcessor('https://www.example.com/en-us/', {
    useBaseHref: true,
    pagePathFallbackMap: fallbackMap,
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#login').attr('href'), '/www.example.com/en-us/login');
  assert.equal($('#login').attr('data-disabled-link'), undefined);
});

test('HtmlProcessor removes non-critical external runtime elements and preserves consent UI', () => {
  const html = [
    '<html><head>',
    '<script src="https://www.google.com/recaptcha/api.js"></script>',
    '<script src="https://www.googletagmanager.com/gtag/js?id=123"></script>',
    '</head><body>',
    '<iframe id="ad" src="https://ae.nflximg.net/monet/scripts/adtech_iframe_target_05.html"></iframe>',
    '<div id="consent-banner">Privacy settings</div>',
    '<noscript><img src="https://www.facebook.com/tr?id=123"></noscript>',
    '<div class="grecaptcha-badge"><iframe title="reCAPTCHA" src="https://www.google.com/recaptcha/enterprise/anchor?x=1"></iframe></div>',
    '<textarea class="g-recaptcha-response" name="g-recaptcha-response"></textarea>',
    '</body></html>',
  ].join('');

  const processor = new HtmlProcessor('https://example.com', { useBaseHref: true });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('script[src*="recaptcha"]').length, 0);
  assert.equal($('script[src*="googletagmanager"]').length, 0);
  assert.equal($('#ad').length, 0);
  assert.equal($('noscript').length, 0);
  assert.equal($('.grecaptcha-badge').length, 0);
  assert.equal($('.g-recaptcha-response').length, 0);
  assert.equal($('#consent-banner').length, 1);
});

test('HtmlProcessor rewrites inline non-critical runtime calls to inert targets', () => {
  const html = [
    '<html><head></head><body>',
    '<script>',
    'fetch("https://logs.netflix.com/log/www/cl/2");',
    'var req = new XMLHttpRequest(); req.open("GET", "https://www.netflix.com/log/www/1");',
    'var req2 = new XMLHttpRequest(); req2.open("GET", "https://logs.netflix.com/log/wwwhead/cl/2?fetchType=js" + "&winw=" + window.outerWidth, true);',
    'navigator.sendBeacon("https://www.google.com/recaptcha/api.js", "{}");',
    'new Image().src = "https://www.facebook.com/tr?id=123";',
    'const cfg = { src: "https://analytics.tiktok.com/i18n/pixel/events.js" };',
    'fetch("https://example.com/bootstrap");',
    '</script>',
    '</body></html>',
  ].join('');

  const processor = new HtmlProcessor('https://example.com', { useBaseHref: true });
  const output = processor.process(html, new Map(), 'index.html');

  assert.match(output, /fetch\("\/__front_clone_noop__"\)/);
  assert.match(output, /open\("GET", "\/__front_clone_noop__"\)/);
  assert.equal(output.includes('logs.netflix.com/log/wwwhead/cl/2'), false);
  assert.match(output, /sendBeacon\("\/__front_clone_noop__"/);
  assert.match(output, /new Image\(\)\.src = "data:,"/);
  assert.match(output, /src: "\/__front_clone_noop__"/);
  assert.match(output, /fetch\("https:\/\/example\.com\/bootstrap"\)/);
});

test('HtmlProcessor rewrites render-critical inline runtime calls to local api paths', () => {
  const html = [
    '<html><head></head><body>',
    '<script>',
    'fetch("https://example.com/bootstrap");',
    'var req = new XMLHttpRequest(); req.open("GET", "/widget-data");',
    '</script>',
    '</body></html>',
  ].join('');

  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    renderCriticalRuntimeMap: new Map([
      ['https://example.com/bootstrap', '/api/bootstrap'],
      ['https://example.com/widget-data', '/api/widget-data'],
    ]),
  });
  const output = processor.process(html, new Map(), 'index.html');

  assert.match(output, /fetch\("\/api\/bootstrap"\)/);
  assert.match(output, /open\("GET", "\/api\/widget-data"\)/);
});

// --- Hidden Navigation 3차 확장: partial literal matching ---

test('HtmlProcessor rewrites partial literal prefix + variable suffix when fallback is unambiguous', () => {
  const html = '<html><body><button id="partial" onclick="location.href=\'/board/list.do?menuNo=\' + menuNo">Go</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map([
        ['example.com/board/list.do', {
          savedPath: 'board__s_list.do__q_menuNo-1003.html',
          replayRoute: '/board__s_list.do__q_menuNo-1003',
          replayable: true,
        }],
      ]),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#partial').attr('onclick'), "location.href='/board__s_list.do__q_menuNo-1003'");
  assert.equal($('#partial').attr('data-hidden-navigation-localized'), 'true');
  assert.equal($('#partial').attr('data-hidden-navigation-class'), 'partial-literal-match');
});

test('HtmlProcessor rewrites wrapper function with partial literal prefix + variable', () => {
  const html = '<html><body><button id="wp" onclick="goPage(\'/portal/contents.do?menuNo=\' + no)">Go</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map([
        ['example.com/portal/contents.do', {
          savedPath: 'portal__s_contents.do__q_menuNo-1003.html',
          replayRoute: '/portal__s_contents.do__q_menuNo-1003',
          replayable: true,
        }],
      ]),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#wp').attr('onclick'), "goPage('/portal__s_contents.do__q_menuNo-1003')");
  assert.equal($('#wp').attr('data-hidden-navigation-localized'), 'true');
  assert.equal($('#wp').attr('data-hidden-navigation-class'), 'partial-literal-match');
});

test('HtmlProcessor does not rewrite partial literal prefix when fallback is ambiguous', () => {
  const html = '<html><body><button id="ambiguous" onclick="location.href=\'/multi/page.do?id=\' + id">Go</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map(),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#ambiguous').attr('onclick'), "location.href='/multi/page.do?id=' + id");
  assert.equal($('#ambiguous').attr('data-hidden-navigation-localized'), undefined);
});

test('HtmlProcessor rewrites window.open with partial literal prefix', () => {
  const html = '<html><body><button id="popup" onclick="window.open(\'/popup/view.do?seq=\' + seq)">View</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map([
        ['example.com/popup/view.do', {
          savedPath: 'popup__s_view.do__q_seq-1.html',
          replayRoute: '/popup__s_view.do__q_seq-1',
          replayable: true,
        }],
      ]),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.match($('#popup').attr('onclick'), /window\.open\('\/popup__s_view\.do__q_seq-1'\)/);
  assert.equal($('#popup').attr('data-hidden-navigation-localized'), 'true');
});

test('HtmlProcessor rewrites variable prefix + literal suffix via fallback match', () => {
  const html = '<html><body><button id="vp" onclick="location.href = baseUrl + \'/page.do\'">Go</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map([
        ['example.com/page.do', {
          savedPath: 'page.do.html',
          replayRoute: '/page.do',
          replayable: true,
        }],
      ]),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#vp').attr('onclick'), "location.href = '/page.do'");
  assert.equal($('#vp').attr('data-hidden-navigation-localized'), 'true');
  assert.equal($('#vp').attr('data-hidden-navigation-class'), 'partial-literal-match');
});

// --- Hidden Navigation 3차 확장: form GET reconstruction ---

test('HtmlProcessor rewrites form GET with hidden inputs to matched local route', () => {
  const html = [
    '<html><body>',
    '<form id="search" method="get" action="/search.do">',
    '<input type="hidden" name="menuNo" value="1003">',
    '<input type="text" name="q">',
    '<button type="submit">Search</button>',
    '</form>',
    '</body></html>',
  ].join('');
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map([
        ['https://example.com/search.do?menuNo=1003', {
          savedPath: 'search.do__q_menuNo-1003.html',
          replayRoute: '/search.do__q_menuNo-1003',
          replayable: true,
        }],
      ]),
      fallbackMap: new Map(),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#search').attr('action'), '/search.do__q_menuNo-1003');
  assert.equal($('#search').attr('data-hidden-navigation-localized'), 'true');
  assert.equal($('#search').attr('data-hidden-navigation-class'), 'form-get-reconstruction');
  assert.equal($('#search input[type="hidden"]').length, 0);
  assert.equal($('#search input[type="text"]').length, 1);
});

test('HtmlProcessor rewrites form GET via pathname fallback when exact reconstruction fails', () => {
  const html = [
    '<html><body>',
    '<form id="nav-form" method="get" action="/board/list.do">',
    '<input type="hidden" name="menuNo" value="5001">',
    '</form>',
    '</body></html>',
  ].join('');
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map([
        ['example.com/board/list.do', {
          savedPath: 'board__s_list.do__q_menuNo-1003.html',
          replayRoute: '/board__s_list.do__q_menuNo-1003',
          replayable: true,
        }],
      ]),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#nav-form').attr('action'), '/board__s_list.do__q_menuNo-1003');
  assert.equal($('#nav-form').attr('data-hidden-navigation-localized'), 'true');
  assert.equal($('#nav-form').attr('data-hidden-navigation-class'), 'form-get-reconstruction');
});

test('HtmlProcessor does not reconstruct form POST action from hidden inputs', () => {
  const html = [
    '<html><body>',
    '<form id="post-form" method="post" action="/submit.do">',
    '<input type="hidden" name="menuNo" value="1003">',
    '</form>',
    '</body></html>',
  ].join('');
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map([
        ['https://example.com/submit.do?menuNo=1003', {
          savedPath: 'submit.do__q_menuNo-1003.html',
          replayRoute: '/submit.do__q_menuNo-1003',
          replayable: true,
        }],
      ]),
      fallbackMap: new Map(),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#post-form').attr('data-hidden-navigation-localized'), undefined);
  assert.equal($('#post-form').attr('data-hidden-navigation-class'), undefined);
  assert.equal($('#post-form input[type="hidden"]').length, 1);
});

// --- Hidden Navigation 4차 확장: variable prefix + literal suffix & template literals ---

test('HtmlProcessor rewrites variable prefix + literal suffix via wrapper function', () => {
  const html = '<html><body><button id="wp" onclick="goPage(prefix + \'/portal/contents.do\')">Go</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map([
        ['example.com/portal/contents.do', {
          savedPath: 'portal__s_contents.do.html',
          replayRoute: '/portal__s_contents.do',
          replayable: true,
        }],
      ]),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#wp').attr('onclick'), "goPage('/portal__s_contents.do')");
  assert.equal($('#wp').attr('data-hidden-navigation-localized'), 'true');
  assert.equal($('#wp').attr('data-hidden-navigation-class'), 'partial-literal-match');
});

test('HtmlProcessor rewrites variable prefix + literal suffix via window.open', () => {
  const html = '<html><body><button id="wo" onclick="window.open(base + \'/popup/view.do\')">View</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map([
        ['example.com/popup/view.do', {
          savedPath: 'popup__s_view.do.html',
          replayRoute: '/popup__s_view.do',
          replayable: true,
        }],
      ]),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.match($('#wo').attr('onclick'), /window\.open\('\/popup__s_view\.do'\)/);
  assert.equal($('#wo').attr('data-hidden-navigation-localized'), 'true');
});

test('HtmlProcessor does not rewrite variable prefix + literal suffix without fallback', () => {
  const html = '<html><body><button id="nf" onclick="location.href = baseUrl + \'/unknown.do\'">Go</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map(),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.match($('#nf').attr('onclick'), /baseUrl/);
  assert.equal($('#nf').attr('data-hidden-navigation-localized'), undefined);
});

test('HtmlProcessor rewrites template literal with static suffix via location.href', () => {
  const html = '<html><body><button id="tl" onclick="location.href = `${baseUrl}/page.do`">Go</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map([
        ['example.com/page.do', {
          savedPath: 'page.do.html',
          replayRoute: '/page.do',
          replayable: true,
        }],
      ]),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#tl').attr('onclick'), "location.href = '/page.do'");
  assert.equal($('#tl').attr('data-hidden-navigation-localized'), 'true');
  assert.equal($('#tl').attr('data-hidden-navigation-class'), 'partial-literal-match');
});

test('HtmlProcessor rewrites template literal with static suffix via wrapper function', () => {
  const html = '<html><body><button id="tlw" onclick="goPage(`${prefix}/portal/contents.do`)">Go</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map([
        ['example.com/portal/contents.do', {
          savedPath: 'portal__s_contents.do.html',
          replayRoute: '/portal__s_contents.do',
          replayable: true,
        }],
      ]),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.equal($('#tlw').attr('onclick'), "goPage('/portal__s_contents.do')");
  assert.equal($('#tlw').attr('data-hidden-navigation-localized'), 'true');
});

test('HtmlProcessor does not rewrite template literal without fallback', () => {
  const html = '<html><body><button id="tlnf" onclick="location.href = `${baseUrl}/unknown.do`">Go</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map(),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.match($('#tlnf').attr('onclick'), /\$\{baseUrl\}/);
  assert.equal($('#tlnf').attr('data-hidden-navigation-localized'), undefined);
});

test('HtmlProcessor does not rewrite pure variable template literal without static suffix', () => {
  const html = '<html><body><button id="pv" onclick="location.href = `${fullUrl}`">Go</button></body></html>';
  const processor = new HtmlProcessor('https://example.com', {
    useBaseHref: true,
    pageRouteIndex: {
      exactUrlMap: new Map(),
      normalizedIdentityMap: new Map(),
      fallbackMap: new Map([
        ['example.com/page.do', { savedPath: 'page.do.html', replayRoute: '/page.do', replayable: true }],
      ]),
    },
  });
  const output = processor.process(html, new Map(), 'index.html');
  const $ = cheerio.load(output);

  assert.match($('#pv').attr('onclick'), /\$\{fullUrl\}/);
  assert.equal($('#pv').attr('data-hidden-navigation-localized'), undefined);
});

test('extractPageReplaySignals detects inline framework bootstrap and streaming hydration hints', () => {
  const signals = extractPageReplaySignals([
    '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"userInfo":{"membershipStatus":"ANONYMOUS"}}}}</script>',
    '<script>self.__next_f.push([1,"flight"])</script>',
    '<div id="__next"></div>',
  ].join(''));

  assert.equal(signals.hasInlineBootstrapState, true);
  assert.equal(signals.hasFrameworkBootstrap, true);
  assert.equal(signals.hasNextDataScript, true);
  assert.equal(signals.hasStreamingHydrationHints, true);
  assert.equal(signals.hasRenderableStateFallback, true);
  assert.equal(signals.bootstrapEvidenceLevel, 'strong');
  assert.equal(signals.frameworkKinds.includes('next-pages-router'), true);
  assert.equal(signals.frameworkKinds.includes('streaming-hydration'), true);
});
