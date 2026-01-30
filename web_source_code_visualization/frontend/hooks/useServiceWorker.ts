"use client";

import { useEffect, useState, useCallback } from 'react';
import {
    registerServiceWorker,
    getServiceWorkerStatus,
    skipWaiting,
    clearAllCaches,
    clearApiCache,
    getCacheStats,
    checkForUpdates,
    type ServiceWorkerStatus,
    type CacheStats,
} from '@/lib/serviceWorker';

export interface UseServiceWorkerResult {
    /** Service Worker 상태 */
    status: ServiceWorkerStatus;
    /** 업데이트 가능 여부 */
    updateAvailable: boolean;
    /** 캐시 통계 */
    cacheStats: CacheStats | null;
    /** 로딩 상태 */
    isLoading: boolean;
    /** 업데이트 적용 */
    applyUpdate: () => Promise<void>;
    /** 모든 캐시 삭제 */
    clearCaches: () => Promise<boolean>;
    /** API 캐시만 삭제 */
    clearApiCache: () => Promise<boolean>;
    /** 캐시 통계 새로고침 */
    refreshCacheStats: () => Promise<void>;
    /** 업데이트 확인 */
    checkUpdates: () => Promise<void>;
}

/**
 * Service Worker 관리 훅
 * 
 * Service Worker의 등록, 상태 관리, 캐시 제어 기능을 제공합니다.
 * 
 * @example
 * ```tsx
 * const { 
 *   status, 
 *   updateAvailable, 
 *   applyUpdate,
 *   clearCaches 
 * } = useServiceWorker();
 * 
 * if (updateAvailable) {
 *   return <button onClick={applyUpdate}>업데이트</button>;
 * }
 * ```
 */
export function useServiceWorker(): UseServiceWorkerResult {
    const [status, setStatus] = useState<ServiceWorkerStatus>({
        supported: false,
        registered: false,
        controller: null,
        waiting: null,
        installing: null,
    });
    const [updateAvailable, setUpdateAvailable] = useState(false);
    const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    // 초기화 및 등록
    useEffect(() => {
        let mounted = true;

        const init = async () => {
            try {
                // Service Worker 등록
                await registerServiceWorker();
                
                // 상태 조회
                const currentStatus = await getServiceWorkerStatus();
                if (mounted) {
                    setStatus(currentStatus);
                    setIsLoading(false);
                }
            } catch (error) {
                console.error('Service Worker initialization failed:', error);
                if (mounted) {
                    setIsLoading(false);
                }
            }
        };

        init();

        // 업데이트 이벤트 리스너
        const handleUpdateAvailable = () => {
            setUpdateAvailable(true);
        };

        window.addEventListener('sw-update-available', handleUpdateAvailable);

        // 컨트롤러 변경 감지
        const handleControllerChange = () => {
            getServiceWorkerStatus().then((newStatus) => {
                if (mounted) {
                    setStatus(newStatus);
                }
            });
        };

        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.addEventListener('controllerchange', handleControllerChange);
        }

        return () => {
            mounted = false;
            window.removeEventListener('sw-update-available', handleUpdateAvailable);
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.removeEventListener('controllerchange', handleControllerChange);
            }
        };
    }, []);

    // 업데이트 적용
    const applyUpdate = useCallback(async () => {
        await skipWaiting();
        setUpdateAvailable(false);
    }, []);

    // 모든 캐시 삭제
    const clearCachesCallback = useCallback(async () => {
        const success = await clearAllCaches();
        if (success) {
            setCacheStats(null);
        }
        return success;
    }, []);

    // API 캐시 삭제
    const clearApiCacheCallback = useCallback(async () => {
        const success = await clearApiCache();
        if (success) {
            // 캐시 통계 새로고침
            const stats = await getCacheStats();
            setCacheStats(stats);
        }
        return success;
    }, []);

    // 캐시 통계 새로고침
    const refreshCacheStats = useCallback(async () => {
        const stats = await getCacheStats();
        setCacheStats(stats);
    }, []);

    // 업데이트 확인
    const checkUpdates = useCallback(async () => {
        await checkForUpdates();
    }, []);

    return {
        status,
        updateAvailable,
        cacheStats,
        isLoading,
        applyUpdate,
        clearCaches: clearCachesCallback,
        clearApiCache: clearApiCacheCallback,
        refreshCacheStats,
        checkUpdates,
    };
}

export default useServiceWorker;
