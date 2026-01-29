"use client";

import { useCallback } from 'react';
import { Node, Edge } from 'reactflow';

interface UseBacktraceReturn {
    highlightBacktrace: (
        nodes: Node[],
        edges: Edge[],
        selectedNodeId: string,
        setNodes: (updater: (nodes: Node[]) => Node[]) => void,
        setEdges: (updater: (edges: Edge[]) => Edge[]) => void
    ) => void;
    resetHighlight: (
        setNodes: (updater: (nodes: Node[]) => Node[]) => void,
        setEdges: (updater: (edges: Edge[]) => Edge[]) => void
    ) => void;
}

/**
 * Custom hook for handling backtrace highlighting logic
 */
export function useBacktrace(): UseBacktraceReturn {

    const highlightBacktrace = useCallback((
        nodes: Node[],
        edges: Edge[],
        selectedNodeId: string,
        setNodes: (updater: (nodes: Node[]) => Node[]) => void,
        setEdges: (updater: (edges: Edge[]) => Edge[]) => void
    ) => {
        // 1. Find all upstream nodes using BFS
        const upstreamNodes = new Set<string>();
        const upstreamEdges = new Set<string>();
        const queue = [selectedNodeId];
        upstreamNodes.add(selectedNodeId);

        while (queue.length > 0) {
            const currentId = queue.shift();
            const incomingEdges = edges.filter(e => e.target === currentId);
            incomingEdges.forEach(e => {
                upstreamEdges.add(e.id);
                if (!upstreamNodes.has(e.source)) {
                    upstreamNodes.add(e.source);
                    queue.push(e.source);
                }
            });
        }

        // 2. Apply highlight styles to nodes
        setNodes((nds) => nds.map(n => {
            const isUpstream = upstreamNodes.has(n.id);
            const isSelected = n.id === selectedNodeId;

            return {
                ...n,
                style: {
                    ...n.style,
                    opacity: isUpstream ? 1 : 0.3,
                    boxShadow: isSelected
                        ? '0 0 30px #bd00ff60'
                        : isUpstream
                            ? '0 0 20px #ffae0040'
                            : undefined,
                    border: isSelected
                        ? '2px solid #bd00ff'
                        : isUpstream
                            ? '2px solid #ffae00'
                            : n.style?.border
                }
            };
        }));

        // 3. Apply highlight styles to edges
        setEdges((eds) => eds.map(e => {
            const isUpstream = upstreamEdges.has(e.id);
            return {
                ...e,
                animated: isUpstream,
                style: isUpstream
                    ? { stroke: '#ffae00', strokeWidth: 2, opacity: 1 }
                    : { stroke: '#333', strokeWidth: 1, opacity: 0.2 },
                zIndex: isUpstream ? 10 : 0
            };
        }));
    }, []);

    const resetHighlight = useCallback((
        setNodes: (updater: (nodes: Node[]) => Node[]) => void,
        setEdges: (updater: (edges: Edge[]) => Edge[]) => void
    ) => {
        setNodes((nds) => nds.map(n => ({
            ...n,
            style: { ...n.data.initialStyle, opacity: 1 }
        })));

        setEdges((eds) => eds.map(e => ({
            ...e,
            animated: e.id.includes('PROJECT'),
            style: {
                stroke: e.id.includes('PROJECT') ? '#00f0ff' : '#555',
                strokeWidth: e.id.includes('PROJECT') ? 2 : 1,
                opacity: 1
            }
        })));
    }, []);

    return {
        highlightBacktrace,
        resetHighlight
    };
}
