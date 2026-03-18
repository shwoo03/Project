import crypto from 'crypto';

import logger from '../utils/logger.js';
import {
  API_BODY_LIMIT,
  ASSET_BODY_LIMIT,
  MAX_RESPONSES,
  MAX_XHR_REQUESTS,
  MAX_WEBSOCKET_EVENTS,
} from '../utils/constants.js';

export default class NetworkInterceptor {
  constructor() {
    this.responses = new Map();
    this.responseKeysByUrl = new Map();
    this.xhrRequests = [];
    this.websocketEvents = [];
  }

  _evictOldestResponses() {
    while (this.responses.size > MAX_RESPONSES) {
      const oldestKey = this.responses.keys().next().value;
      const entry = this.responses.get(oldestKey);
      this.responses.delete(oldestKey);
      if (entry) {
        const keys = this.responseKeysByUrl.get(entry.url);
        if (keys) {
          const idx = keys.indexOf(oldestKey);
          if (idx !== -1) keys.splice(idx, 1);
          if (keys.length === 0) this.responseKeysByUrl.delete(entry.url);
        }
      }
    }
  }

  attach(page) {
    page.on('response', async (response) => {
      const request = response.request();
      const url = response.url();
      const resourceType = request.resourceType();

      if (url.startsWith('data:')) return;

      try {
        const mimeType = (response.headers()['content-type'] || '').split(';')[0].trim();
        const requestBody = request.postData() || '';
        const requestBodyHash = this._hashRequestBody(requestBody);
        const requestKey = this._createRequestKey(request.method(), url, requestBodyHash);
        let body = null;
        let bodyLength = 0;

        try {
          const responseBody = await response.body();
          bodyLength = responseBody.length;
          if (this._shouldStoreBody(resourceType, mimeType, responseBody.length)) {
            body = responseBody;
          }
        } catch {
          // Ignore bodies unavailable for redirects or streamed responses.
        }

        const entry = {
          key: requestKey,
          url,
          method: request.method(),
          requestBodyHash,
          type: resourceType,
          mimeType,
          headers: response.headers(),
          body,
          bodyLength,
          bodyStored: Boolean(body),
          status: response.status(),
          pageUrl: page.url(),
        };

        this.responses.set(requestKey, entry);
        this._indexResponse(url, requestKey);
        this._evictOldestResponses();

        if (resourceType === 'xhr' || resourceType === 'fetch') {
          this.xhrRequests.push({
            key: requestKey,
            method: request.method(),
            url,
            pageUrl: page.url(),
            postData: requestBody,
            requestBodyHash,
            resourceType,
            headers: request.headers(),
            responseStatus: response.status(),
            responseMimeType: mimeType,
            responseBody: body ? body.toString('utf-8') : null,
            responseBodyStored: Boolean(body),
          });
          if (this.xhrRequests.length > MAX_XHR_REQUESTS) {
            this.xhrRequests = this.xhrRequests.slice(-MAX_XHR_REQUESTS);
          }
        }
      } catch (err) {
        logger.debug(`Network capture failed: ${url} - ${err.message}`);
      }
    });

    page.on('requestfailed', (request) => {
      logger.debug(`Request failed: ${request.url()} - ${request.failure()?.errorText}`);
    });

    page.on('websocket', (socket) => {
      this._pushWebsocketEvent({
        type: 'open',
        pageUrl: page.url(),
        url: socket.url(),
        timestamp: new Date().toISOString(),
      });

      socket.on('framesent', (payload) => {
        this._pushWebsocketEvent({
          type: 'frame-sent',
          pageUrl: page.url(),
          url: socket.url(),
          payload: String(payload),
          timestamp: new Date().toISOString(),
        });
      });

      socket.on('framereceived', (payload) => {
        this._pushWebsocketEvent({
          type: 'frame-received',
          pageUrl: page.url(),
          url: socket.url(),
          payload: String(payload),
          timestamp: new Date().toISOString(),
        });
      });

      socket.on('close', () => {
        this._pushWebsocketEvent({
          type: 'close',
          pageUrl: page.url(),
          url: socket.url(),
          timestamp: new Date().toISOString(),
        });
      });
    });
  }

  _pushWebsocketEvent(event) {
    this.websocketEvents.push(event);
    if (this.websocketEvents.length > MAX_WEBSOCKET_EVENTS) {
      this.websocketEvents = this.websocketEvents.slice(-MAX_WEBSOCKET_EVENTS);
    }
  }

  _createRequestKey(method, url, requestBodyHash) {
    return `${method.toUpperCase()} ${url} ${requestBodyHash}`;
  }

  _hashRequestBody(value) {
    if (!value) return 'no-body';
    return crypto.createHash('sha1').update(value).digest('hex').slice(0, 12);
  }

  _shouldStoreBody(resourceType, mimeType, bodyLength) {
    const isApi = resourceType === 'xhr' || resourceType === 'fetch';
    if (isApi) {
      return bodyLength <= API_BODY_LIMIT;
    }

    const isTextLike =
      mimeType.startsWith('text/') ||
      mimeType.includes('javascript') ||
      mimeType.includes('json') ||
      mimeType.includes('xml') ||
      mimeType.includes('svg') ||
      mimeType.includes('font') ||
      mimeType.startsWith('image/');

    if (!isTextLike) return false;
    return bodyLength <= ASSET_BODY_LIMIT;
  }

  _indexResponse(url, requestKey) {
    const keys = this.responseKeysByUrl.get(url) || [];
    keys.push(requestKey);
    this.responseKeysByUrl.set(url, keys);
  }

  getByType(...types) {
    const result = new Map();
    for (const [key, data] of this.responses) {
      if (types.includes(data.type)) {
        result.set(key, data);
      }
    }
    return result;
  }

  getAssets() {
    const result = new Map();
    for (const [key, data] of this.responses) {
      if (data.type !== 'document' && data.body) {
        result.set(key, data);
      }
    }
    return result;
  }

  getLatestResponse(url) {
    const keys = this.responseKeysByUrl.get(url) || [];
    const latestKey = keys[keys.length - 1];
    return latestKey ? this.responses.get(latestKey) || null : null;
  }

  getResponsesByUrl(url) {
    const keys = this.responseKeysByUrl.get(url) || [];
    return keys
      .map((key) => this.responses.get(key))
      .filter(Boolean);
  }

  getXhrRequests() {
    return this.xhrRequests;
  }

  getWebsocketEvents() {
    return this.websocketEvents;
  }

  getStats() {
    const stats = {};
    for (const [, data] of this.responses) {
      stats[data.type] = (stats[data.type] || 0) + 1;
    }
    return stats;
  }
}
