"use client";

/**
 * Service Worker 등록 및 관리 유틸리티
 * 
 * @file serviceWorker.ts
 */

export interface ServiceWorkerStatus {
    supported: boolean;
    registered: boolean;
    controller: ServiceWorker | null;
    waiting: ServiceWorker | null;
    installing: ServiceWorker | null;
}

export interface CacheStats {
    [cacheName: string]: {
        count: number;
        urls: string[];
    };
}

/**
 * Service Worker 등록
 */
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
        console.log('[SW Client] Service Worker not supported');
        return null;
    }

    try {
        const registration = await navigator.serviceWorker.register('/sw.js', {
            scope: '/',
        });

        console.log('[SW Client] Service Worker registered:', registration.scope);

        // 업데이트 이벤트 리스너
        registration.addEventListener('updatefound', () => {
            const newWorker = registration.installing;
            console.log('[SW Client] New Service Worker found');

            newWorker?.addEventListener('statechange', () => {
                console.log('[SW Client] Service Worker state:', newWorker.state);
                
                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                    // 새 버전 사용 가능
                    console.log('[SW Client] New content available');
                    window.dispatchEvent(new CustomEvent('sw-update-available'));
                }
            });
        });

        return registration;
    } catch (error) {
        console.error('[SW Client] Service Worker registration failed:', error);
        return null;
    }
}

/**
 * Service Worker 해제
 */
export async function unregisterServiceWorker(): Promise<boolean> {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
        return false;
    }

    try {
        const registration = await navigator.serviceWorker.getRegistration();
        if (registration) {
            const success = await registration.unregister();
            console.log('[SW Client] Service Worker unregistered:', success);
            return success;
        }
        return false;
    } catch (error) {
        console.error('[SW Client] Failed to unregister Service Worker:', error);
        return false;
    }
}

/**
 * Service Worker 상태 조회
 */
export async function getServiceWorkerStatus(): Promise<ServiceWorkerStatus> {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
        return {
            supported: false,
            registered: false,
            controller: null,
            waiting: null,
            installing: null,
        };
    }

    try {
        const registration = await navigator.serviceWorker.getRegistration();
        
        return {
            supported: true,
            registered: !!registration,
            controller: navigator.serviceWorker.controller,
            waiting: registration?.waiting || null,
            installing: registration?.installing || null,
        };
    } catch (error) {
        console.error('[SW Client] Failed to get status:', error);
        return {
            supported: true,
            registered: false,
            controller: null,
            waiting: null,
            installing: null,
        };
    }
}

/**
 * Service Worker에 메시지 전송
 */
export function sendMessageToServiceWorker<T = unknown>(
    type: string, 
    payload?: unknown
): Promise<T> {
    return new Promise((resolve, reject) => {
        if (!navigator.serviceWorker.controller) {
            reject(new Error('No active Service Worker'));
            return;
        }

        const messageChannel = new MessageChannel();
        
        messageChannel.port1.onmessage = (event) => {
            resolve(event.data as T);
        };

        navigator.serviceWorker.controller.postMessage(
            { type, payload },
            [messageChannel.port2]
        );

        // 타임아웃
        setTimeout(() => {
            reject(new Error('Service Worker message timeout'));
        }, 10000);
    });
}

/**
 * 대기 중인 Service Worker 활성화
 */
export async function skipWaiting(): Promise<void> {
    if (!navigator.serviceWorker.controller) {
        console.log('[SW Client] No controller, refreshing');
        window.location.reload();
        return;
    }

    const registration = await navigator.serviceWorker.getRegistration();
    if (registration?.waiting) {
        registration.waiting.postMessage({ type: 'SKIP_WAITING' });
        
        // 페이지 새로고침 대기
        navigator.serviceWorker.addEventListener('controllerchange', () => {
            window.location.reload();
        });
    }
}

/**
 * 모든 캐시 삭제
 */
export async function clearAllCaches(): Promise<boolean> {
    try {
        const result = await sendMessageToServiceWorker<{ success: boolean }>('CLEAR_CACHE');
        return result.success;
    } catch (error) {
        console.error('[SW Client] Failed to clear caches:', error);
        
        // Fallback: 직접 캐시 삭제
        if ('caches' in window) {
            const cacheNames = await caches.keys();
            await Promise.all(cacheNames.map(name => caches.delete(name)));
            return true;
        }
        
        return false;
    }
}

/**
 * API 캐시만 삭제
 */
export async function clearApiCache(): Promise<boolean> {
    try {
        const result = await sendMessageToServiceWorker<{ success: boolean }>('CLEAR_API_CACHE');
        return result.success;
    } catch (error) {
        console.error('[SW Client] Failed to clear API cache:', error);
        return false;
    }
}

/**
 * 캐시 통계 조회
 */
export async function getCacheStats(): Promise<CacheStats> {
    try {
        return await sendMessageToServiceWorker<CacheStats>('GET_CACHE_STATS');
    } catch (error) {
        console.error('[SW Client] Failed to get cache stats:', error);
        return {};
    }
}

/**
 * 업데이트 확인
 */
export async function checkForUpdates(): Promise<void> {
    const registration = await navigator.serviceWorker.getRegistration();
    if (registration) {
        await registration.update();
    }
}
