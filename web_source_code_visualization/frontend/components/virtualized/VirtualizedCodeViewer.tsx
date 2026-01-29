"use client";

import React, { useRef, useMemo, useCallback, useState, useEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';

interface VirtualizedCodeViewerProps {
    code: string;
    language?: string;
    highlightLines?: number[];
    startLine?: number;
    maxHeight?: string;
}

/**
 * Virtualized code viewer for rendering large source files efficiently.
 * Renders only visible lines to handle files with 10,000+ lines.
 */
export function VirtualizedCodeViewer({
    code,
    language = 'python',
    highlightLines = [],
    startLine = 1,
    maxHeight = '400px'
}: VirtualizedCodeViewerProps) {
    const parentRef = useRef<HTMLDivElement>(null);
    const [isReady, setIsReady] = useState(false);

    // Parse code into lines
    const lines = useMemo(() => {
        return code.split('\n').map((content, index) => ({
            lineNumber: startLine + index,
            content,
            isHighlighted: highlightLines.includes(startLine + index)
        }));
    }, [code, startLine, highlightLines]);

    // Virtual configuration
    const virtualizer = useVirtualizer({
        count: lines.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 22, // ~22px per line
        overscan: 20, // Render extra lines for smoother scrolling
    });

    // Wait for mount before rendering
    useEffect(() => {
        setIsReady(true);
    }, []);

    const virtualItems = virtualizer.getVirtualItems();

    // Syntax highlighting colors (simplified for performance)
    const getTokenColor = useCallback((content: string) => {
        // Keywords
        if (/^(def|class|import|from|return|if|else|elif|for|while|try|except|with|as|lambda|yield|raise|async|await|function|const|let|var|export|default)\s/.test(content.trim())) {
            return 'text-purple-400';
        }
        // Comments
        if (/^\s*(#|\/\/|\/\*)/.test(content)) {
            return 'text-zinc-500 italic';
        }
        // Strings
        if (/['"`]/.test(content)) {
            return 'text-green-400';
        }
        return 'text-zinc-300';
    }, []);

    if (lines.length === 0) {
        return (
            <div className="text-zinc-500 text-center py-4 italic">
                No code to display
            </div>
        );
    }

    return (
        <div className="relative rounded-lg border border-white/10 bg-black/50 overflow-hidden">
            {/* Stats bar */}
            <div className="flex justify-between items-center px-3 py-1.5 bg-white/5 border-b border-white/10 text-[10px] text-zinc-500">
                <span>{language.toUpperCase()}</span>
                <span className="flex items-center gap-2">
                    <span>{lines.length.toLocaleString()} lines</span>
                    {lines.length > 100 && (
                        <span className="flex items-center gap-1">
                            <span className="w-1.5 h-1.5 bg-green-500 rounded-full" />
                            virtualized
                        </span>
                    )}
                </span>
            </div>

            {/* Virtualized code area */}
            <div
                ref={parentRef}
                className="overflow-auto font-mono text-xs"
                style={{ maxHeight, contain: 'strict' }}
            >
                {isReady && (
                    <div
                        style={{
                            height: `${virtualizer.getTotalSize()}px`,
                            width: '100%',
                            position: 'relative',
                        }}
                    >
                        {virtualItems.map((virtualItem) => {
                            const line = lines[virtualItem.index];
                            return (
                                <div
                                    key={virtualItem.key}
                                    data-index={virtualItem.index}
                                    style={{
                                        position: 'absolute',
                                        top: 0,
                                        left: 0,
                                        width: '100%',
                                        height: `${virtualItem.size}px`,
                                        transform: `translateY(${virtualItem.start}px)`,
                                    }}
                                    className={`flex ${line.isHighlighted ? 'bg-yellow-500/20' : ''}`}
                                >
                                    {/* Line number */}
                                    <span className="w-12 flex-shrink-0 text-right pr-3 text-zinc-600 select-none border-r border-white/5">
                                        {line.lineNumber}
                                    </span>
                                    
                                    {/* Code content */}
                                    <code className={`pl-3 whitespace-pre ${getTokenColor(line.content)}`}>
                                        {line.content || ' '}
                                    </code>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}

interface VirtualizedListProps<T> {
    items: T[];
    renderItem: (item: T, index: number) => React.ReactNode;
    itemHeight?: number;
    maxHeight?: string;
    overscan?: number;
    emptyMessage?: string;
}

/**
 * Generic virtualized list component for any data type.
 * Use for rendering large lists of findings, endpoints, etc.
 */
export function VirtualizedList<T>({
    items,
    renderItem,
    itemHeight = 48,
    maxHeight = '300px',
    overscan = 5,
    emptyMessage = 'No items'
}: VirtualizedListProps<T>) {
    const parentRef = useRef<HTMLDivElement>(null);

    const virtualizer = useVirtualizer({
        count: items.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => itemHeight,
        overscan,
    });

    const virtualItems = virtualizer.getVirtualItems();

    if (items.length === 0) {
        return (
            <div className="text-zinc-500 text-center py-4 italic text-sm">
                {emptyMessage}
            </div>
        );
    }

    return (
        <div className="relative">
            {/* Stats */}
            {items.length > 50 && (
                <div className="text-[10px] text-zinc-500 mb-1 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 bg-green-500 rounded-full" />
                    {virtualItems.length} / {items.length.toLocaleString()} visible
                </div>
            )}

            {/* Virtualized list */}
            <div
                ref={parentRef}
                className="overflow-auto"
                style={{ maxHeight, contain: 'strict' }}
            >
                <div
                    style={{
                        height: `${virtualizer.getTotalSize()}px`,
                        width: '100%',
                        position: 'relative',
                    }}
                >
                    {virtualItems.map((virtualItem) => (
                        <div
                            key={virtualItem.key}
                            data-index={virtualItem.index}
                            style={{
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                width: '100%',
                                height: `${virtualItem.size}px`,
                                transform: `translateY(${virtualItem.start}px)`,
                            }}
                        >
                            {renderItem(items[virtualItem.index], virtualItem.index)}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

export default VirtualizedCodeViewer;
