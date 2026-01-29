"use client";

import { useCallback, useMemo, useRef, useState, useEffect } from 'react';
import { Node, Edge, useReactFlow, Viewport } from 'reactflow';

interface ViewportBounds {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
}

interface UseViewportOptimizationOptions {
    /** Extra padding around viewport for pre-rendering nodes (in pixels) */
    padding?: number;
    /** Minimum zoom level to enable optimization (below this, show all) */
    minZoomForOptimization?: number;
    /** Maximum nodes to render when fully zoomed out */
    maxNodesWhenZoomedOut?: number;
    /** Throttle time for viewport updates (ms) */
    throttleMs?: number;
}

interface ViewportOptimizationResult {
    /** Nodes visible in current viewport */
    visibleNodes: Node[];
    /** Edges where both source and target are visible */
    visibleEdges: Edge[];
    /** Current viewport bounds */
    bounds: ViewportBounds | null;
    /** Whether optimization is active */
    isOptimizing: boolean;
    /** Statistics for debugging */
    stats: {
        totalNodes: number;
        visibleNodes: number;
        totalEdges: number;
        visibleEdges: number;
        renderRatio: number;
    };
}

/**
 * Hook for viewport-based node/edge visibility optimization.
 * Only renders nodes within the visible viewport area.
 * Dramatically improves performance for graphs with 1000+ nodes.
 */
export function useViewportOptimization(
    allNodes: Node[],
    allEdges: Edge[],
    options: UseViewportOptimizationOptions = {}
): ViewportOptimizationResult {
    const {
        padding = 200,
        minZoomForOptimization = 0.1,
        maxNodesWhenZoomedOut = 500,
        throttleMs = 50
    } = options;

    const [bounds, setBounds] = useState<ViewportBounds | null>(null);
    const lastUpdateRef = useRef<number>(0);
    const pendingUpdateRef = useRef<NodeJS.Timeout | null>(null);

    // Try to get ReactFlow instance (may not be available during SSR)
    let reactFlowInstance: ReturnType<typeof useReactFlow> | null = null;
    try {
        reactFlowInstance = useReactFlow();
    } catch {
        // Not inside ReactFlowProvider, return all nodes
    }

    // Update viewport bounds with throttling
    const updateBounds = useCallback((viewport: Viewport, width: number, height: number) => {
        const now = Date.now();
        
        // Throttle updates
        if (now - lastUpdateRef.current < throttleMs) {
            if (pendingUpdateRef.current) {
                clearTimeout(pendingUpdateRef.current);
            }
            pendingUpdateRef.current = setTimeout(() => {
                updateBounds(viewport, width, height);
            }, throttleMs);
            return;
        }
        
        lastUpdateRef.current = now;

        const scale = viewport.zoom;
        const paddedPadding = padding / scale;

        const newBounds: ViewportBounds = {
            minX: (-viewport.x / scale) - paddedPadding,
            maxX: (-viewport.x / scale) + (width / scale) + paddedPadding,
            minY: (-viewport.y / scale) - paddedPadding,
            maxY: (-viewport.y / scale) + (height / scale) + paddedPadding,
        };

        setBounds(newBounds);
    }, [padding, throttleMs]);

    // Listen to viewport changes
    useEffect(() => {
        if (!reactFlowInstance) return;

        const viewport = reactFlowInstance.getViewport();
        const container = document.querySelector('.react-flow');
        if (container) {
            const rect = container.getBoundingClientRect();
            updateBounds(viewport, rect.width, rect.height);
        }
    }, [reactFlowInstance, updateBounds]);

    // Calculate visible nodes
    const visibleNodes = useMemo(() => {
        // If no bounds or not enough nodes, show all
        if (!bounds || allNodes.length < 100) {
            return allNodes;
        }

        // If very zoomed out, limit nodes intelligently
        const zoom = reactFlowInstance?.getViewport().zoom ?? 1;
        if (zoom < minZoomForOptimization) {
            // Show only important nodes (entry points, clusters, etc.)
            const importantNodes = allNodes.filter(node => 
                node.data?.is_entry_point || 
                node.data?.type === 'cluster' ||
                node.data?.type === 'root' ||
                node.id === 'PROJECT_ROOT'
            );
            
            if (importantNodes.length < maxNodesWhenZoomedOut) {
                // Fill remaining slots with other nodes
                const otherNodes = allNodes
                    .filter(n => !importantNodes.includes(n))
                    .slice(0, maxNodesWhenZoomedOut - importantNodes.length);
                return [...importantNodes, ...otherNodes];
            }
            return importantNodes.slice(0, maxNodesWhenZoomedOut);
        }

        // Normal viewport culling
        return allNodes.filter(node => {
            const { x, y } = node.position;
            const width = (node.style?.width as number) || 150;
            const height = (node.style?.height as number) || 50;

            // Check if node overlaps with viewport
            return !(
                x + width < bounds.minX ||
                x > bounds.maxX ||
                y + height < bounds.minY ||
                y > bounds.maxY
            );
        });
    }, [allNodes, bounds, reactFlowInstance, minZoomForOptimization, maxNodesWhenZoomedOut]);

    // Calculate visible edges (only if both endpoints are visible)
    const visibleEdges = useMemo(() => {
        if (!bounds || allEdges.length < 100) {
            return allEdges;
        }

        const visibleNodeIds = new Set(visibleNodes.map(n => n.id));
        
        return allEdges.filter(edge => 
            visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
        );
    }, [allEdges, visibleNodes, bounds]);

    // Calculate statistics
    const stats = useMemo(() => ({
        totalNodes: allNodes.length,
        visibleNodes: visibleNodes.length,
        totalEdges: allEdges.length,
        visibleEdges: visibleEdges.length,
        renderRatio: allNodes.length > 0 
            ? Math.round((visibleNodes.length / allNodes.length) * 100) 
            : 100
    }), [allNodes.length, visibleNodes.length, allEdges.length, visibleEdges.length]);

    return {
        visibleNodes,
        visibleEdges,
        bounds,
        isOptimizing: allNodes.length >= 100 && bounds !== null,
        stats
    };
}

/**
 * Hook for progressive node loading.
 * Loads nodes in batches to prevent UI freeze.
 */
export function useProgressiveLoading<T>(
    items: T[],
    batchSize: number = 100,
    intervalMs: number = 50
): { loadedItems: T[]; isLoading: boolean; progress: number } {
    const [loadedCount, setLoadedCount] = useState(0);

    useEffect(() => {
        if (items.length === 0) {
            setLoadedCount(0);
            return;
        }

        setLoadedCount(Math.min(batchSize, items.length));

        if (items.length <= batchSize) {
            return;
        }

        const interval = setInterval(() => {
            setLoadedCount(prev => {
                const next = prev + batchSize;
                if (next >= items.length) {
                    clearInterval(interval);
                    return items.length;
                }
                return next;
            });
        }, intervalMs);

        return () => clearInterval(interval);
    }, [items, batchSize, intervalMs]);

    return {
        loadedItems: items.slice(0, loadedCount),
        isLoading: loadedCount < items.length,
        progress: items.length > 0 ? Math.round((loadedCount / items.length) * 100) : 100
    };
}

/**
 * Simple node clustering for zoomed-out views.
 * Groups nearby nodes into cluster representatives.
 */
export function useNodeClustering(
    nodes: Node[],
    gridSize: number = 200,
    enabled: boolean = true
): Node[] {
    return useMemo(() => {
        if (!enabled || nodes.length < 500) {
            return nodes;
        }

        const grid = new Map<string, Node[]>();
        
        // Group nodes by grid cell
        nodes.forEach(node => {
            const cellX = Math.floor(node.position.x / gridSize);
            const cellY = Math.floor(node.position.y / gridSize);
            const key = `${cellX}:${cellY}`;
            
            if (!grid.has(key)) {
                grid.set(key, []);
            }
            grid.get(key)!.push(node);
        });

        // Create cluster representatives
        const clusteredNodes: Node[] = [];
        
        grid.forEach((cellNodes, key) => {
            if (cellNodes.length === 1) {
                clusteredNodes.push(cellNodes[0]);
            } else {
                // Use first node as representative
                const representative = { ...cellNodes[0] };
                representative.data = {
                    ...representative.data,
                    label: `${cellNodes.length} nodes`,
                    isClusterRepresentative: true,
                    clusteredNodeIds: cellNodes.map(n => n.id)
                };
                representative.style = {
                    ...representative.style,
                    opacity: 0.8,
                    border: '2px dashed #6366f1'
                };
                clusteredNodes.push(representative);
            }
        });

        return clusteredNodes;
    }, [nodes, gridSize, enabled]);
}

export default useViewportOptimization;
