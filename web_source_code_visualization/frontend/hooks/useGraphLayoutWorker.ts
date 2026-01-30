"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import type { Node, Edge } from 'reactflow';

export interface LayoutOptions {
    /** 노드 너비 */
    nodeWidth?: number;
    /** 노드 높이 */
    nodeHeight?: number;
    /** 레이어 간 간격 */
    rankSep?: number;
    /** 노드 간 간격 */
    nodeSep?: number;
    /** 방향: TB(위→아래), BT(아래→위), LR(왼쪽→오른쪽), RL(오른쪽→왼쪽) */
    direction?: 'TB' | 'BT' | 'LR' | 'RL';
    /** 점진적 레이아웃 사용 여부 */
    progressive?: boolean;
    /** 청크 크기 (점진적 레이아웃 시) */
    chunkSize?: number;
}

export interface LayoutResult {
    nodes: Node[];
    edges: Edge[];
    layoutTime: number;
    stats: {
        nodeCount: number;
        edgeCount: number;
        layerCount: number;
    };
}

export interface LayoutProgress {
    progress: number;
    processedNodes: number;
    totalNodes: number;
}

interface UseGraphLayoutWorkerOptions {
    /** 레이아웃 옵션 */
    layoutOptions?: LayoutOptions;
    /** 레이아웃 완료 콜백 */
    onLayoutComplete?: (result: LayoutResult) => void;
    /** 진행 상황 콜백 */
    onProgress?: (progress: LayoutProgress) => void;
    /** 에러 콜백 */
    onError?: (error: Error) => void;
}

interface WorkerMessage {
    type: string;
    id?: string;
    payload?: unknown;
}

/**
 * Web Worker를 사용한 그래프 레이아웃 계산 훅
 * 
 * 대규모 그래프의 레이아웃 계산을 백그라운드 스레드에서 실행하여
 * 메인 스레드 블로킹을 방지합니다.
 * 
 * @example
 * ```tsx
 * const { calculateLayout, isCalculating, progress, isReady } = useGraphLayoutWorker({
 *   onLayoutComplete: (result) => {
 *     setNodes(result.nodes);
 *   },
 * });
 * 
 * // 레이아웃 계산 시작
 * calculateLayout(nodes, edges, { direction: 'TB' });
 * ```
 */
export function useGraphLayoutWorker(options: UseGraphLayoutWorkerOptions = {}) {
    const { layoutOptions, onLayoutComplete, onProgress, onError } = options;

    const workerRef = useRef<Worker | null>(null);
    const pendingCallbacks = useRef<Map<string, {
        resolve: (result: LayoutResult) => void;
        reject: (error: Error) => void;
    }>>(new Map());

    const [isReady, setIsReady] = useState(false);
    const [isCalculating, setIsCalculating] = useState(false);
    const [progress, setProgress] = useState<LayoutProgress | null>(null);
    const [error, setError] = useState<Error | null>(null);

    // Worker 초기화
    useEffect(() => {
        // 브라우저 환경 확인
        if (typeof window === 'undefined') return;

        try {
            const worker = new Worker('/workers/graphLayoutWorker.js');
            workerRef.current = worker;

            worker.onmessage = (event: MessageEvent<WorkerMessage>) => {
                const { type, id, payload } = event.data;

                switch (type) {
                    case 'READY':
                        setIsReady(true);
                        break;

                    case 'LAYOUT_COMPLETE': {
                        setIsCalculating(false);
                        setProgress(null);
                        const result = payload as LayoutResult;
                        
                        if (id && pendingCallbacks.current.has(id)) {
                            const { resolve } = pendingCallbacks.current.get(id)!;
                            pendingCallbacks.current.delete(id);
                            resolve(result);
                        }
                        
                        onLayoutComplete?.(result);
                        break;
                    }

                    case 'LAYOUT_PROGRESS': {
                        const progressData = payload as LayoutProgress;
                        setProgress(progressData);
                        onProgress?.(progressData);
                        break;
                    }

                    case 'ERROR': {
                        setIsCalculating(false);
                        setProgress(null);
                        const errorPayload = payload as { message: string; stack?: string };
                        const err = new Error(errorPayload.message);
                        err.stack = errorPayload.stack;
                        setError(err);
                        
                        if (id && pendingCallbacks.current.has(id)) {
                            const { reject } = pendingCallbacks.current.get(id)!;
                            pendingCallbacks.current.delete(id);
                            reject(err);
                        }
                        
                        onError?.(err);
                        break;
                    }

                    case 'PONG':
                        // 연결 테스트 응답
                        break;
                }
            };

            worker.onerror = (event) => {
                const err = new Error(event.message);
                setError(err);
                setIsCalculating(false);
                onError?.(err);
            };

        } catch (err) {
            console.error('Failed to create Web Worker:', err);
            setError(err as Error);
        }

        return () => {
            workerRef.current?.terminate();
            workerRef.current = null;
            pendingCallbacks.current.clear();
        };
    }, [onLayoutComplete, onProgress, onError]);

    // 고유 ID 생성
    const generateId = useCallback(() => {
        return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }, []);

    // 레이아웃 계산
    const calculateLayout = useCallback(
        (nodes: Node[], edges: Edge[], options?: LayoutOptions): Promise<LayoutResult> => {
            return new Promise((resolve, reject) => {
                if (!workerRef.current) {
                    const err = new Error('Worker not initialized');
                    reject(err);
                    return;
                }

                const id = generateId();
                const mergedOptions = { ...layoutOptions, ...options };
                const isProgressive = mergedOptions.progressive ?? (nodes.length > 200);

                setIsCalculating(true);
                setError(null);
                setProgress(null);

                pendingCallbacks.current.set(id, { resolve, reject });

                workerRef.current.postMessage({
                    type: isProgressive ? 'CALCULATE_LAYOUT_PROGRESSIVE' : 'CALCULATE_LAYOUT',
                    id,
                    payload: {
                        nodes: nodes.map(n => ({ id: n.id, data: n.data, type: n.type })),
                        edges: edges.map(e => ({ source: e.source, target: e.target, id: e.id })),
                        options: mergedOptions,
                    },
                });
            });
        },
        [layoutOptions, generateId]
    );

    // 연결 테스트
    const ping = useCallback((): Promise<number> => {
        return new Promise((resolve, reject) => {
            if (!workerRef.current) {
                reject(new Error('Worker not initialized'));
                return;
            }

            const id = generateId();
            const startTime = Date.now();

            const handler = (event: MessageEvent<WorkerMessage>) => {
                if (event.data.type === 'PONG' && event.data.id === id) {
                    workerRef.current?.removeEventListener('message', handler);
                    resolve(Date.now() - startTime);
                }
            };

            workerRef.current.addEventListener('message', handler);
            workerRef.current.postMessage({ type: 'PING', id });

            // 타임아웃
            setTimeout(() => {
                workerRef.current?.removeEventListener('message', handler);
                reject(new Error('Ping timeout'));
            }, 5000);
        });
    }, [generateId]);

    // 취소
    const cancel = useCallback(() => {
        if (workerRef.current) {
            workerRef.current.terminate();
            workerRef.current = null;
            setIsCalculating(false);
            setProgress(null);
            pendingCallbacks.current.forEach(({ reject }) => {
                reject(new Error('Calculation cancelled'));
            });
            pendingCallbacks.current.clear();
        }
    }, []);

    return {
        /** 레이아웃 계산 함수 */
        calculateLayout,
        /** Worker 준비 상태 */
        isReady,
        /** 계산 중 여부 */
        isCalculating,
        /** 진행 상황 */
        progress,
        /** 에러 */
        error,
        /** 연결 테스트 */
        ping,
        /** 취소 */
        cancel,
    };
}

export default useGraphLayoutWorker;
