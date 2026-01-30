"use client";

import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import { AnalysisData, SecurityFinding, CallGraphData } from '@/types/graph';

const API_BASE = 'http://localhost:8000';

// ===========================
// API 함수들
// ===========================

interface AnalyzeRequest {
    path: string;
    use_cache?: boolean;
}

interface AnalyzeResponse {
    project_path: string;
    endpoints: any[];
    taint_flows: any[];
    files: string[];
    stats: {
        total_files: number;
        processed_files: number;
        failed_files: number;
        parse_time_ms: number;
    };
}

async function analyzeProject(request: AnalyzeRequest): Promise<AnalyzeResponse> {
    const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    });

    if (!res.ok) {
        throw new Error(`Analysis failed: ${res.statusText}`);
    }

    return res.json();
}

interface ScanRequest {
    path: string;
    rules?: string[];
}

async function scanSecurity(request: ScanRequest): Promise<SecurityFinding[]> {
    const res = await fetch(`${API_BASE}/api/semgrep/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    });

    if (!res.ok) {
        throw new Error(`Security scan failed: ${res.statusText}`);
    }

    const data = await res.json();
    return data.findings || [];
}

async function fetchCallGraph(path: string): Promise<CallGraphData> {
    const res = await fetch(`${API_BASE}/api/callgraph`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
    });

    if (!res.ok) {
        throw new Error(`Call graph fetch failed: ${res.statusText}`);
    }

    return res.json();
}

async function fetchCodeSnippet(filePath: string, startLine: number, endLine: number): Promise<string> {
    const res = await fetch(`${API_BASE}/api/snippet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            file_path: filePath,
            start_line: startLine,
            end_line: endLine,
        }),
    });

    if (!res.ok) {
        throw new Error(`Snippet fetch failed: ${res.statusText}`);
    }

    const data = await res.json();
    return data.code || '';
}

interface VulnerabilitiesRequest {
    path: string;
    page: number;
    pageSize: number;
    severity?: string;
}

interface VulnerabilitiesResponse {
    items: SecurityFinding[];
    total: number;
    page: number;
    pageSize: number;
    hasMore: boolean;
}

async function fetchVulnerabilities(request: VulnerabilitiesRequest): Promise<VulnerabilitiesResponse> {
    const params = new URLSearchParams({
        path: request.path,
        page: String(request.page),
        page_size: String(request.pageSize),
    });

    if (request.severity) {
        params.append('severity', request.severity);
    }

    const res = await fetch(`${API_BASE}/api/vulnerabilities?${params}`, {
        method: 'GET',
    });

    if (!res.ok) {
        // 엔드포인트가 없으면 빈 결과 반환
        return {
            items: [],
            total: 0,
            page: request.page,
            pageSize: request.pageSize,
            hasMore: false,
        };
    }

    return res.json();
}

// ===========================
// React Query 훅들
// ===========================

/**
 * 프로젝트 분석 쿼리 훅
 * 캐싱을 활용하여 동일한 프로젝트 재분석 시 성능 향상
 */
export function useAnalysis(path: string, options?: { enabled?: boolean; useCache?: boolean }) {
    return useQuery({
        queryKey: ['analysis', path],
        queryFn: () => analyzeProject({ path, use_cache: options?.useCache ?? true }),
        enabled: !!path && (options?.enabled ?? true),
        staleTime: 10 * 60 * 1000, // 10분
    });
}

/**
 * 보안 스캔 쿼리 훅
 */
export function useSecurityScan(path: string, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: ['securityScan', path],
        queryFn: () => scanSecurity({ path }),
        enabled: !!path && (options?.enabled ?? true),
        staleTime: 5 * 60 * 1000, // 5분
    });
}

/**
 * Call Graph 쿼리 훅
 */
export function useCallGraph(path: string, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: ['callGraph', path],
        queryFn: () => fetchCallGraph(path),
        enabled: !!path && (options?.enabled ?? true),
        staleTime: 10 * 60 * 1000, // 10분
    });
}

/**
 * 코드 스니펫 쿼리 훅
 * 파일 경로와 라인 범위를 키로 사용하여 캐싱
 */
export function useCodeSnippet(
    filePath: string | undefined,
    startLine: number | undefined,
    endLine: number | undefined
) {
    return useQuery({
        queryKey: ['snippet', filePath, startLine, endLine],
        queryFn: () => fetchCodeSnippet(filePath!, startLine!, endLine || startLine! + 20),
        enabled: !!filePath && !!startLine,
        staleTime: 30 * 60 * 1000, // 30분 (코드는 자주 변경되지 않음)
        gcTime: 60 * 60 * 1000, // 1시간
    });
}

/**
 * 취약점 목록 무한 스크롤 쿼리 훅
 */
export function useInfiniteVulnerabilities(
    path: string,
    pageSize: number = 20,
    severity?: string
) {
    return useInfiniteQuery({
        queryKey: ['vulnerabilities', path, severity],
        queryFn: ({ pageParam = 1 }) =>
            fetchVulnerabilities({ path, page: pageParam, pageSize, severity }),
        initialPageParam: 1,
        getNextPageParam: (lastPage) =>
            lastPage.hasMore ? lastPage.page + 1 : undefined,
        enabled: !!path,
        staleTime: 5 * 60 * 1000, // 5분
    });
}

/**
 * 분석 뮤테이션 훅 (새로 분석 실행)
 */
export function useAnalyzeMutation() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: analyzeProject,
        onSuccess: (data, variables) => {
            // 분석 완료 후 캐시 업데이트
            queryClient.setQueryData(['analysis', variables.path], data);
            // 관련 쿼리들 무효화
            queryClient.invalidateQueries({ queryKey: ['securityScan', variables.path] });
            queryClient.invalidateQueries({ queryKey: ['callGraph', variables.path] });
            queryClient.invalidateQueries({ queryKey: ['vulnerabilities', variables.path] });
        },
    });
}

/**
 * 보안 스캔 뮤테이션 훅
 */
export function useScanMutation() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: scanSecurity,
        onSuccess: (data, variables) => {
            queryClient.setQueryData(['securityScan', variables.path], data);
        },
    });
}

/**
 * 캐시 프리페치 함수
 * 예상되는 데이터를 미리 로드
 */
export function usePrefetchAnalysis() {
    const queryClient = useQueryClient();

    return (path: string) => {
        queryClient.prefetchQuery({
            queryKey: ['analysis', path],
            queryFn: () => analyzeProject({ path, use_cache: true }),
            staleTime: 10 * 60 * 1000,
        });
    };
}

/**
 * 캐시 무효화 함수
 * 특정 프로젝트의 모든 캐시 삭제
 */
export function useInvalidateProjectCache() {
    const queryClient = useQueryClient();

    return (path: string) => {
        queryClient.invalidateQueries({ queryKey: ['analysis', path] });
        queryClient.invalidateQueries({ queryKey: ['securityScan', path] });
        queryClient.invalidateQueries({ queryKey: ['callGraph', path] });
        queryClient.invalidateQueries({ queryKey: ['vulnerabilities', path] });
        // 스니펫 캐시도 관련 파일 것만 삭제
        queryClient.invalidateQueries({
            queryKey: ['snippet'],
            predicate: (query) => {
                const [, filePath] = query.queryKey;
                return typeof filePath === 'string' && filePath.startsWith(path);
            },
        });
    };
}

/**
 * 캐시 통계 조회
 */
export function useCacheStats() {
    const queryClient = useQueryClient();

    return () => {
        const cache = queryClient.getQueryCache();
        const queries = cache.getAll();

        return {
            totalQueries: queries.length,
            activeQueries: queries.filter((q) => q.state.status === 'pending').length,
            staleQueries: queries.filter((q) => q.isStale()).length,
            freshQueries: queries.filter((q) => !q.isStale()).length,
            errorQueries: queries.filter((q) => q.state.status === 'error').length,
            byType: {
                analysis: queries.filter((q) => q.queryKey[0] === 'analysis').length,
                securityScan: queries.filter((q) => q.queryKey[0] === 'securityScan').length,
                callGraph: queries.filter((q) => q.queryKey[0] === 'callGraph').length,
                snippet: queries.filter((q) => q.queryKey[0] === 'snippet').length,
                vulnerabilities: queries.filter((q) => q.queryKey[0] === 'vulnerabilities').length,
            },
        };
    };
}
