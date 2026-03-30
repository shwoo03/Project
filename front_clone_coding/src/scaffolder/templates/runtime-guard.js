(function () {
  if (window.__FRONT_CLONE_RUNTIME__?.guardActive) return;

  const runtime = window.__FRONT_CLONE_RUNTIME__ = {
    guardActive: true,
    version: 1,
    exceptions: [],
    resourceErrors: [],
  };

  function limit(list, entry) {
    if (!entry) return;
    list.push(entry);
    if (list.length > 100) list.shift();
  }

  function classifyDomAssumption(message) {
    const lower = String(message || '').toLowerCase();
    if (/(cannot (set|read) properties of null|cannot (set|read) properties of undefined|null is not an object|undefined is not an object|appendchild|removechild|insertbefore|queryselector)/.test(lower)) {
      return 'runtime-dom-assumption';
    }
    if (/chunk|module script|loading chunk|importing a module script failed/.test(lower)) {
      return 'runtime-script-failed';
    }
    return 'runtime-exception';
  }

  function classifyResource(resourceType, url) {
    if (resourceType === 'script') return 'runtime-script-failed';
    if (resourceType === 'stylesheet') return 'runtime-style-failed';
    return 'runtime-resource-missing';
  }

  function toResourceType(target, url) {
    const tag = String(target?.tagName || '').toLowerCase();
    if (tag === 'script') return 'script';
    if (tag === 'link') return 'stylesheet';
    if (tag === 'img' || tag === 'image') return 'image';
    if (tag === 'video' || tag === 'audio' || tag === 'source') return 'media';
    const lowerUrl = String(url || '').toLowerCase();
    if (lowerUrl.endsWith('.js')) return 'script';
    if (lowerUrl.endsWith('.css')) return 'stylesheet';
    return 'resource';
  }

  function normalizeUrl(rawUrl) {
    if (!rawUrl) return '';
    try {
      return new URL(rawUrl, location.href).href;
    } catch {
      return String(rawUrl || '');
    }
  }

  function recordException(error, source) {
    const message = String(error?.message || error || '').trim();
    if (!message) return;
    limit(runtime.exceptions, {
      name: String(error?.name || 'Error'),
      message,
      source: source || 'runtime',
      failureClass: classifyDomAssumption(message),
      sameOrigin: true,
      stack: String(error?.stack || '').split('\n').slice(0, 5).join('\n'),
    });
  }

  function recordResourceError(target, rawUrl, source) {
    const url = normalizeUrl(rawUrl || target?.src || target?.href || '');
    if (!url) return;
    let sameOrigin = false;
    try {
      sameOrigin = new URL(url, location.href).origin === location.origin;
    } catch {
      sameOrigin = false;
    }
    limit(runtime.resourceErrors, {
      url,
      sameOrigin,
      source: source || 'resource-error',
      resourceType: toResourceType(target, url),
      failureClass: classifyResource(toResourceType(target, url), url),
    });
  }

  window.addEventListener('error', (event) => {
    const target = event.target;
    if (target && target !== window) {
      recordResourceError(target, target.src || target.href || '', 'element-error');
      return;
    }
    recordException(event.error || new Error(event.message || 'runtime error'), 'window-error');
  }, true);

  window.addEventListener('unhandledrejection', (event) => {
    recordException(event.reason || new Error('unhandled rejection'), 'unhandledrejection');
  });

  const callbackMap = new WeakMap();
  function wrapCallback(callback, source) {
    if (typeof callback !== 'function') return callback;
    if (callbackMap.has(callback)) return callbackMap.get(callback);
    const wrapped = function (...args) {
      try {
        return callback.apply(this, args);
      } catch (error) {
        recordException(error, source);
        return undefined;
      }
    };
    callbackMap.set(callback, wrapped);
    return wrapped;
  }

  const originalSetTimeout = window.setTimeout.bind(window);
  window.setTimeout = function (callback, delay, ...args) {
    return originalSetTimeout(wrapCallback(callback, 'setTimeout'), delay, ...args);
  };

  const originalSetInterval = window.setInterval.bind(window);
  window.setInterval = function (callback, delay, ...args) {
    return originalSetInterval(wrapCallback(callback, 'setInterval'), delay, ...args);
  };

  const originalRequestAnimationFrame = window.requestAnimationFrame?.bind(window);
  if (originalRequestAnimationFrame) {
    window.requestAnimationFrame = function (callback) {
      return originalRequestAnimationFrame(wrapCallback(callback, 'requestAnimationFrame'));
    };
  }

  const originalAddEventListener = EventTarget.prototype.addEventListener;
  const originalRemoveEventListener = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    return originalAddEventListener.call(this, type, wrapCallback(listener, 'event:' + type), options);
  };
  EventTarget.prototype.removeEventListener = function (type, listener, options) {
    return originalRemoveEventListener.call(this, type, callbackMap.get(listener) || listener, options);
  };
})();
