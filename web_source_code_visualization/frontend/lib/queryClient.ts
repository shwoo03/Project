"use client";

import { QueryClient } from '@tanstack/react-query';

/**
 * React Query 클라이언트 설정
 * 
 * 성능 최적화를 위한 기본 설정:
 * - staleTime: 데이터가 오래된 것으로 간주되는 시간 (5분)
 * - gcTime: 가비지 컬렉션 시간 (30분)
 * - refetchOnWindowFocus: 창 포커스 시 재요청 비활성화
 * - retry: 실패 시 재시도 횟수
 */
export function makeQueryClient() {
    return new QueryClient({
        defaultOptions: {
            queries: {
                // 5분 동안 데이터를 신선하게 유지
                staleTime: 5 * 60 * 1000,
                // 30분 후 캐시에서 제거
                gcTime: 30 * 60 * 1000,
                // 창 포커스 시 자동 재요청 비활성화 (성능 향상)
                refetchOnWindowFocus: false,
                // 마운트 시 재요청 비활성화
                refetchOnMount: false,
                // 재연결 시 재요청
                refetchOnReconnect: true,
                // 실패 시 1회만 재시도
                retry: 1,
                // 재시도 지연 시간
                retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
            },
            mutations: {
                // 뮤테이션 실패 시 재시도 없음
                retry: 0,
            },
        },
    });
}

// 싱글톤 인스턴스 (서버 사이드에서는 매번 새로 생성)
let browserQueryClient: QueryClient | undefined = undefined;

export function getQueryClient() {
    if (typeof window === 'undefined') {
        // 서버: 항상 새로운 쿼리 클라이언트 생성
        return makeQueryClient();
    } else {
        // 브라우저: 싱글톤 패턴 사용
        if (!browserQueryClient) {
            browserQueryClient = makeQueryClient();
        }
        return browserQueryClient;
    }
}
