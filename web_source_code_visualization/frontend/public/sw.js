/**
 * Service Worker: 오프라인 캐싱 및 성능 최적화
 * 
 * API 응답과 정적 자산을 캐싱하여 성능을 향상시키고
 * 오프라인 상태에서도 일부 기능을 사용할 수 있게 합니다.
 * 
 * @file sw.js
 * @version 1.0.0
 */

const CACHE_VERSION = 'v1';
const STATIC_CACHE_NAME = `static-cache-${CACHE_VERSION}`;
const DYNAMIC_CACHE_NAME = `dynamic-cache-${CACHE_VERSION}`;
const API_CACHE_NAME = `api-cache-${CACHE_VERSION}`;

// 정적 자산 (앱 셸)
const STATIC_ASSETS = [
    '/',
    '/manifest.json',
    '/workers/graphLayoutWorker.js',
];

// API 캐시 설정
const API_CACHE_CONFIG = {
    // 분석 결과는 10분간 캐싱
    '/api/analysis': {
        maxAge: 10 * 60 * 1000, // 10분
        strategy: 'stale-while-revalidate',
    },
    // 보안 스캔은 5분간 캐싱
    '/api/security': {
        maxAge: 5 * 60 * 1000, // 5분
        strategy: 'stale-while-revalidate',
    },
    // 콜그래프는 10분간 캐싱
    '/api/call-graph': {
        maxAge: 10 * 60 * 1000, // 10분
        strategy: 'stale-while-revalidate',
    },
    // 코드 스니펫은 30분간 캐싱
    '/api/code': {
        maxAge: 30 * 60 * 1000, // 30분
        strategy: 'cache-first',
    },
};

// ============================================
// 유틸리티 함수
// ============================================

/**
 * URL이 API 요청인지 확인
 */
function isApiRequest(url) {
    return url.pathname.startsWith('/api/') || 
           url.hostname === 'localhost' && url.port === '8000';
}

/**
 * 해당 URL에 대한 캐시 설정 반환
 */
function getCacheConfig(url) {
    for (const [path, config] of Object.entries(API_CACHE_CONFIG)) {
        if (url.pathname.includes(path)) {
            return config;
        }
    }
    return null;
}

/**
 * 캐시된 응답이 만료되었는지 확인
 */
function isCacheExpired(cachedResponse, maxAge) {
    const cachedTime = cachedResponse.headers.get('sw-cached-time');
    if (!cachedTime) return true;
    
    return Date.now() - parseInt(cachedTime, 10) > maxAge;
}

/**
 * 응답에 캐시 시간 추가
 */
async function addCacheTimestamp(response) {
    const headers = new Headers(response.headers);
    headers.set('sw-cached-time', Date.now().toString());
    
    const blob = await response.blob();
    return new Response(blob, {
        status: response.status,
        statusText: response.statusText,
        headers: headers,
    });
}

// ============================================
// 캐시 전략
// ============================================

/**
 * Cache First: 캐시 우선, 없으면 네트워크
 */
async function cacheFirst(request, cacheName, maxAge) {
    const cache = await caches.open(cacheName);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse && !isCacheExpired(cachedResponse, maxAge)) {
        return cachedResponse;
    }
    
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const responseToCache = await addCacheTimestamp(networkResponse.clone());
            cache.put(request, responseToCache);
        }
        return networkResponse;
    } catch (error) {
        if (cachedResponse) {
            console.log('[SW] Network failed, returning stale cache');
            return cachedResponse;
        }
        throw error;
    }
}

/**
 * Stale While Revalidate: 캐시 반환 후 백그라운드 업데이트
 */
async function staleWhileRevalidate(request, cacheName, maxAge) {
    const cache = await caches.open(cacheName);
    const cachedResponse = await cache.match(request);
    
    // 백그라운드에서 네트워크 요청
    const fetchPromise = fetch(request)
        .then(async (networkResponse) => {
            if (networkResponse.ok) {
                const responseToCache = await addCacheTimestamp(networkResponse.clone());
                cache.put(request, responseToCache);
            }
            return networkResponse;
        })
        .catch((error) => {
            console.log('[SW] Network request failed:', error);
            return null;
        });
    
    // 캐시가 있고 유효하면 즉시 반환
    if (cachedResponse && !isCacheExpired(cachedResponse, maxAge)) {
        return cachedResponse;
    }
    
    // 캐시가 없거나 만료됐으면 네트워크 응답 대기
    const networkResponse = await fetchPromise;
    return networkResponse || cachedResponse || new Response('Offline', { status: 503 });
}

/**
 * Network First: 네트워크 우선, 실패시 캐시
 */
async function networkFirst(request, cacheName) {
    const cache = await caches.open(cacheName);
    
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const responseToCache = await addCacheTimestamp(networkResponse.clone());
            cache.put(request, responseToCache);
        }
        return networkResponse;
    } catch (error) {
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        throw error;
    }
}

// ============================================
// 이벤트 핸들러
// ============================================

/**
 * 설치 이벤트: 정적 자산 프리캐싱
 */
self.addEventListener('install', (event) => {
    console.log('[SW] Installing...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE_NAME)
            .then((cache) => {
                console.log('[SW] Precaching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('[SW] Install complete');
                return self.skipWaiting();
            })
            .catch((error) => {
                console.error('[SW] Install failed:', error);
            })
    );
});

/**
 * 활성화 이벤트: 오래된 캐시 정리
 */
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating...');
    
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => {
                            return name.startsWith('static-cache-') && name !== STATIC_CACHE_NAME ||
                                   name.startsWith('dynamic-cache-') && name !== DYNAMIC_CACHE_NAME ||
                                   name.startsWith('api-cache-') && name !== API_CACHE_NAME;
                        })
                        .map((name) => {
                            console.log('[SW] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                console.log('[SW] Activate complete');
                return self.clients.claim();
            })
    );
});

/**
 * 요청 가로채기
 */
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // API 요청 처리
    if (isApiRequest(url)) {
        const config = getCacheConfig(url);
        
        if (config && event.request.method === 'GET') {
            event.respondWith(
                config.strategy === 'cache-first'
                    ? cacheFirst(event.request, API_CACHE_NAME, config.maxAge)
                    : staleWhileRevalidate(event.request, API_CACHE_NAME, config.maxAge)
            );
            return;
        }
    }
    
    // 정적 자산 처리
    if (event.request.destination === 'image' || 
        event.request.destination === 'script' ||
        event.request.destination === 'style' ||
        event.request.destination === 'font') {
        event.respondWith(
            cacheFirst(event.request, DYNAMIC_CACHE_NAME, 24 * 60 * 60 * 1000) // 24시간
        );
        return;
    }
    
    // 나머지는 네트워크 우선
    event.respondWith(
        networkFirst(event.request, DYNAMIC_CACHE_NAME)
    );
});

/**
 * 백그라운드 동기화 (나중에 추가 가능)
 */
self.addEventListener('sync', (event) => {
    console.log('[SW] Sync event:', event.tag);
    
    if (event.tag === 'sync-analysis') {
        // 오프라인에서 요청된 분석을 동기화
        event.waitUntil(syncPendingAnalysis());
    }
});

/**
 * 푸시 알림 (나중에 추가 가능)
 */
self.addEventListener('push', (event) => {
    console.log('[SW] Push event');
    
    if (event.data) {
        const data = event.data.json();
        event.waitUntil(
            self.registration.showNotification(data.title, {
                body: data.body,
                icon: '/icon-192.png',
                badge: '/badge.png',
            })
        );
    }
});

/**
 * 메시지 핸들러 (클라이언트와 통신)
 */
self.addEventListener('message', (event) => {
    const { type, payload } = event.data;
    
    switch (type) {
        case 'SKIP_WAITING':
            self.skipWaiting();
            break;
            
        case 'CLEAR_CACHE':
            event.waitUntil(
                Promise.all([
                    caches.delete(STATIC_CACHE_NAME),
                    caches.delete(DYNAMIC_CACHE_NAME),
                    caches.delete(API_CACHE_NAME),
                ]).then(() => {
                    event.ports[0].postMessage({ success: true });
                })
            );
            break;
            
        case 'CLEAR_API_CACHE':
            event.waitUntil(
                caches.delete(API_CACHE_NAME).then(() => {
                    event.ports[0].postMessage({ success: true });
                })
            );
            break;
            
        case 'GET_CACHE_STATS':
            event.waitUntil(
                getCacheStats().then((stats) => {
                    event.ports[0].postMessage(stats);
                })
            );
            break;
    }
});

/**
 * 캐시 통계 조회
 */
async function getCacheStats() {
    const cacheNames = await caches.keys();
    const stats = {};
    
    for (const name of cacheNames) {
        const cache = await caches.open(name);
        const keys = await cache.keys();
        stats[name] = {
            count: keys.length,
            urls: keys.map(req => req.url).slice(0, 10), // 최대 10개
        };
    }
    
    return stats;
}

/**
 * 대기 중인 분석 동기화 (플레이스홀더)
 */
async function syncPendingAnalysis() {
    // IndexedDB에서 대기 중인 요청 가져와서 처리
    console.log('[SW] Syncing pending analysis...');
}

console.log('[SW] Service Worker loaded');
