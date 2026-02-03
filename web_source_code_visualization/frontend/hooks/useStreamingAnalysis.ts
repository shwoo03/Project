"use client";

import { useState, useCallback, useRef, useEffect } from 'react';

// ============================================
// Types
// ============================================

export type StreamEventType =
    | 'init'
    | 'progress'
    | 'symbols'
    | 'endpoints'
    | 'taint'
    | 'stats'
    | 'complete'
    | 'error';

export interface StreamEvent<T = any> {
    type: StreamEventType;
    data: T;
    timestamp: number;
}

export interface ProgressData {
    phase: 'collecting' | 'symbols' | 'parsing' | 'clustering' | 'taint';
    message?: string;
    scanned?: number;
    parsed?: number;
    cached?: number;
    failed?: number;
    total?: number;
    percent?: number;
}

export interface EndpointData {
    id: string;
    type: string;
    path: string;
    method?: string;
    file_path?: string;
    line_number?: number;
    children?: EndpointData[];
}

export interface TaintFlowData {
    id: string;
    source_node_id: string;
    sink_node_id: string;
    vulnerability_type: string;
    severity: string;
}

export interface StatsData {
    language_stats: Record<string, number>;
    total_files: number;
    parsed_files: number;
    cached_files: number;
    total_endpoints: number;
    taint_flows: number;
}

export interface CompleteData {
    message: string;
    elapsed_ms: number;
    project_path: string;
    summary: {
        files: number;
        endpoints: number;
        taint_flows: number;
        cache_hit_rate: number;
    };
}

export interface StreamingAnalysisState {
    isStreaming: boolean;
    phase: string;
    progress: number;
    message: string;
    endpoints: EndpointData[];
    taintFlows: TaintFlowData[];
    stats: StatsData | null;
    error: string | null;
    elapsedMs: number | null;
}

export interface UseStreamingAnalysisOptions {
    onProgress?: (data: ProgressData) => void;
    onEndpoints?: (endpoints: EndpointData[]) => void;
    onTaintFlows?: (flows: TaintFlowData[]) => void;
    onComplete?: (data: CompleteData) => void;
    onError?: (error: string) => void;
}

// ============================================
// Hook Implementation
// ============================================

const API_BASE = 'http://localhost:8000';

/**
 * Hook for streaming analysis with real-time progress updates.
 * 
 * @example
 * ```tsx
 * const { 
 *   startStream, 
 *   cancelStream, 
 *   state 
 * } = useStreamingAnalysis({
 *   onProgress: (data) => console.log(`${data.percent}%`),
 *   onComplete: (data) => console.log(`Done in ${data.elapsed_ms}ms`)
 * });
 * 
 * // Start streaming analysis
 * startStream('/path/to/project');
 * ```
 */
export function useStreamingAnalysis(options: UseStreamingAnalysisOptions = {}) {
    const [state, setState] = useState<StreamingAnalysisState>({
        isStreaming: false,
        phase: '',
        progress: 0,
        message: '',
        endpoints: [],
        taintFlows: [],
        stats: null,
        error: null,
        elapsedMs: null
    });

    const abortControllerRef = useRef<AbortController | null>(null);
    const endpointsRef = useRef<EndpointData[]>([]);

    /**
     * Start streaming analysis for a project path.
     */
    const startStream = useCallback(async (
        projectPath: string,
        cluster: boolean = true,
        useCache: boolean = true
    ) => {
        // Cancel any existing stream
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        // Reset state
        endpointsRef.current = [];
        setState({
            isStreaming: true,
            phase: 'init',
            progress: 0,
            message: 'Starting analysis...',
            endpoints: [],
            taintFlows: [],
            stats: null,
            error: null,
            elapsedMs: null
        });

        const abortController = new AbortController();
        abortControllerRef.current = abortController;

        try {
            const response = await fetch(`${API_BASE}/api/analyze/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    path: projectPath,
                    cluster,
                    use_cache: useCache,
                    format: 'ndjson'  // Using NDJSON for easier parsing
                }),
                signal: abortController.signal
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const reader = response.body?.getReader();
            if (!reader) {
                throw new Error('No readable stream');
            }

            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();

                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Process complete lines (NDJSON format)
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';  // Keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.trim()) continue;

                    try {
                        const event: StreamEvent = JSON.parse(line);
                        handleEvent(event);
                    } catch (e) {
                        console.warn('Failed to parse event:', line);
                    }
                }
            }

            // Process any remaining buffer
            if (buffer.trim()) {
                try {
                    const event: StreamEvent = JSON.parse(buffer);
                    handleEvent(event);
                } catch (e) {
                    console.warn('Failed to parse final event:', buffer);
                }
            }

        } catch (error: any) {
            if (error.name === 'AbortError') {
                setState(prev => ({
                    ...prev,
                    isStreaming: false,
                    message: 'Analysis cancelled'
                }));
            } else {
                const errorMessage = error.message || 'Unknown error';
                setState(prev => ({
                    ...prev,
                    isStreaming: false,
                    error: errorMessage
                }));
                options.onError?.(errorMessage);
            }
        }

        function handleEvent(event: StreamEvent) {
            switch (event.type) {
                case 'init':
                    setState(prev => ({
                        ...prev,
                        phase: 'init',
                        message: event.data.message || 'Initializing...'
                    }));
                    break;

                case 'progress':
                    const progressData = event.data as ProgressData;
                    setState(prev => ({
                        ...prev,
                        phase: progressData.phase,
                        progress: progressData.percent || 0,
                        message: progressData.message || `${progressData.phase}: ${progressData.percent || 0}%`
                    }));
                    options.onProgress?.(progressData);
                    break;

                case 'symbols':
                    setState(prev => ({
                        ...prev,
                        message: `Found ${event.data.total_symbols} symbols`
                    }));
                    break;

                case 'endpoints':
                    const newEndpoints = event.data.endpoints as EndpointData[];
                    endpointsRef.current = [...endpointsRef.current, ...newEndpoints];
                    setState(prev => ({
                        ...prev,
                        endpoints: endpointsRef.current
                    }));
                    options.onEndpoints?.(newEndpoints);
                    break;

                case 'taint':
                    const flows = event.data.flows as TaintFlowData[];
                    setState(prev => ({
                        ...prev,
                        taintFlows: flows
                    }));
                    options.onTaintFlows?.(flows);
                    break;

                case 'stats':
                    setState(prev => ({
                        ...prev,
                        stats: event.data as StatsData
                    }));
                    break;

                case 'complete':
                    const completeData = event.data as CompleteData;
                    setState(prev => ({
                        ...prev,
                        isStreaming: false,
                        phase: 'complete',
                        progress: 100,
                        message: `Complete: ${completeData.elapsed_ms}ms`,
                        elapsedMs: completeData.elapsed_ms
                    }));
                    options.onComplete?.(completeData);
                    break;

                case 'error':
                    setState(prev => ({
                        ...prev,
                        isStreaming: false,
                        error: event.data.message
                    }));
                    options.onError?.(event.data.message);
                    break;
            }
        }
    }, [options]);

    /**
     * Cancel ongoing streaming analysis.
     */
    const cancelStream = useCallback(async () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }

        // Also notify backend to stop
        try {
            await fetch(`${API_BASE}/api/analyze/stream/cancel`, {
                method: 'POST'
            });
        } catch (e) {
            // Ignore cancel errors
        }

        setState(prev => ({
            ...prev,
            isStreaming: false,
            message: 'Analysis cancelled'
        }));
    }, []);

    /**
     * Reset state to initial values.
     */
    const reset = useCallback(() => {
        endpointsRef.current = [];
        setState({
            isStreaming: false,
            phase: '',
            progress: 0,
            message: '',
            endpoints: [],
            taintFlows: [],
            stats: null,
            error: null,
            elapsedMs: null
        });
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, []);

    return {
        startStream,
        cancelStream,
        reset,
        state,
        // Convenience getters
        isStreaming: state.isStreaming,
        progress: state.progress,
        phase: state.phase,
        endpoints: state.endpoints,
        taintFlows: state.taintFlows,
        stats: state.stats
    };
}

export default useStreamingAnalysis;
