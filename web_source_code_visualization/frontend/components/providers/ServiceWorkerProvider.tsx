"use client";

import { ReactNode, useEffect, useState } from 'react';
import { useServiceWorker } from '@/hooks/useServiceWorker';

interface ServiceWorkerProviderProps {
    children: ReactNode;
}

/**
 * Service Worker 관리 Provider
 * 
 * 앱 전역에서 Service Worker를 초기화하고 업데이트를 관리합니다.
 */
export function ServiceWorkerProvider({ children }: ServiceWorkerProviderProps) {
    const { updateAvailable, applyUpdate } = useServiceWorker();
    const [showUpdateBanner, setShowUpdateBanner] = useState(false);

    useEffect(() => {
        if (updateAvailable) {
            setShowUpdateBanner(true);
        }
    }, [updateAvailable]);

    const handleUpdate = async () => {
        setShowUpdateBanner(false);
        await applyUpdate();
    };

    const dismissBanner = () => {
        setShowUpdateBanner(false);
    };

    return (
        <>
            {children}
            
            {/* 업데이트 알림 배너 */}
            {showUpdateBanner && (
                <div className="fixed bottom-4 right-4 z-50 bg-blue-600 text-white rounded-lg shadow-lg p-4 max-w-sm animate-slide-in">
                    <div className="flex items-start gap-3">
                        <span className="text-xl">🔄</span>
                        <div className="flex-1">
                            <h4 className="font-medium mb-1">새 버전 사용 가능</h4>
                            <p className="text-sm text-blue-100 mb-3">
                                앱이 업데이트되었습니다. 새 버전을 적용하시겠습니까?
                            </p>
                            <div className="flex gap-2">
                                <button
                                    onClick={handleUpdate}
                                    className="px-3 py-1 bg-white text-blue-600 rounded text-sm font-medium hover:bg-blue-50 transition-colors"
                                >
                                    지금 업데이트
                                </button>
                                <button
                                    onClick={dismissBanner}
                                    className="px-3 py-1 text-blue-100 hover:text-white text-sm transition-colors"
                                >
                                    나중에
                                </button>
                            </div>
                        </div>
                        <button
                            onClick={dismissBanner}
                            className="text-blue-200 hover:text-white"
                            aria-label="닫기"
                        >
                            ✕
                        </button>
                    </div>
                </div>
            )}
        </>
    );
}

export default ServiceWorkerProvider;
