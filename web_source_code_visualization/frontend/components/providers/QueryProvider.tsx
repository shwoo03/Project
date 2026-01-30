"use client";

import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { getQueryClient } from '@/lib/queryClient';
import React, { useState } from 'react';

interface QueryProviderProps {
    children: React.ReactNode;
}

/**
 * React Query Provider 래퍼
 * 
 * 앱 전체에 React Query 컨텍스트를 제공합니다.
 * 개발 환경에서는 DevTools도 함께 렌더링됩니다.
 */
export function QueryProvider({ children }: QueryProviderProps) {
    // useState로 QueryClient를 한 번만 생성 (SSR 안전)
    const [queryClient] = useState(() => getQueryClient());

    return (
        <QueryClientProvider client={queryClient}>
            {children}
            {process.env.NODE_ENV === 'development' && (
                <ReactQueryDevtools initialIsOpen={false} position="bottom" />
            )}
        </QueryClientProvider>
    );
}
