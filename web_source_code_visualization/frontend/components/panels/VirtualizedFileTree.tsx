"use client";

import React, { useRef, useMemo, useState, useEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';

interface VirtualizedFileTreeProps {
    files: string[];
    selectedFiles: Set<string>;
    onToggleFile: (file: string) => void;
    onSelectAll: () => void;
    onSelectNone: () => void;
}

/**
 * Virtualized file tree component for handling large numbers of files efficiently.
 * Uses @tanstack/react-virtual for rendering only visible items.
 * Optimized for 10,000+ files.
 */
export function VirtualizedFileTree({
    files,
    selectedFiles,
    onToggleFile,
    onSelectAll,
    onSelectNone
}: VirtualizedFileTreeProps) {
    const parentRef = useRef<HTMLDivElement>(null);
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [mounted, setMounted] = useState(false);

    // Hydration 에러 방지: 클라이언트에서만 렌더링
    useEffect(() => {
        setMounted(true);
    }, []);

    // Memoize file data to prevent unnecessary re-renders
    const fileItems = useMemo(() => 
        files.map(file => ({
            fullPath: file,
            fileName: file.split(/[/\\]/).pop() || file,
            isSelected: selectedFiles.has(file)
        })),
        [files, selectedFiles]
    );

    // Calculate selection statistics
    const selectedCount = selectedFiles.size;
    const totalCount = files.length;

    // 파일 수가 적으면 일반 렌더링 사용 (성능 충분)
    const useVirtualization = totalCount > 50;

    // SSR 시에는 간단한 placeholder 반환
    if (!mounted) {
        return (
            <div className="absolute top-24 left-4 z-40 w-72 bg-black/95 backdrop-blur-lg rounded-xl border border-white/20 flex flex-col overflow-hidden shadow-2xl"
                 style={{ maxHeight: 'calc(100vh - 150px)' }}>
                <div className="p-3 border-b border-white/10 bg-gradient-to-r from-cyan-900/30 to-blue-900/30">
                    <div className="flex justify-between items-center">
                        <span className="font-bold text-sm text-zinc-200">파일 목록 로딩 중...</span>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="absolute top-24 left-4 z-40 w-72 bg-black/95 backdrop-blur-lg rounded-xl border border-white/20 flex flex-col overflow-hidden shadow-2xl"
             style={{ maxHeight: isCollapsed ? 'auto' : 'calc(100vh - 150px)' }}>
            {/* Header */}
            <div className="p-3 border-b border-white/10 bg-gradient-to-r from-cyan-900/30 to-blue-900/30">
                <div className="flex justify-between items-center">
                    <button 
                        onClick={() => setIsCollapsed(!isCollapsed)}
                        className="font-bold text-sm text-zinc-200 hover:text-white flex items-center gap-2"
                    >
                        <span>{isCollapsed ? '▶' : '▼'}</span>
                        <span>📁 File Browser</span>
                    </button>
                    <div className="flex gap-2 text-xs">
                        <button
                            onClick={onSelectAll}
                            className="hover:text-cyan-300 text-zinc-400 hover:bg-white/10 px-2 py-0.5 rounded transition-colors"
                        >
                            All
                        </button>
                        <button
                            onClick={onSelectNone}
                            className="hover:text-cyan-300 text-zinc-400 hover:bg-white/10 px-2 py-0.5 rounded transition-colors"
                        >
                            None
                        </button>
                    </div>
                </div>
                
                {/* Statistics bar */}
                <div className="mt-2 flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                        <div 
                            className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-300"
                            style={{ width: `${(selectedCount / Math.max(totalCount, 1)) * 100}%` }}
                        />
                    </div>
                    <span className="text-xs text-zinc-400 tabular-nums font-mono">
                        {selectedCount}/{totalCount}
                    </span>
                </div>
            </div>

            {/* File list */}
            {!isCollapsed && (
                <>
                    {totalCount === 0 ? (
                        <div className="p-4 text-center text-zinc-500 text-sm">
                            📂 No files found.<br/>
                            <span className="text-xs">Click "시각화" to analyze project.</span>
                        </div>
                    ) : useVirtualization ? (
                        <VirtualizedList 
                            fileItems={fileItems} 
                            onToggleFile={onToggleFile}
                            parentRef={parentRef}
                            totalCount={totalCount}
                        />
                    ) : (
                        <SimpleList 
                            fileItems={fileItems} 
                            onToggleFile={onToggleFile} 
                        />
                    )}
                </>
            )}
        </div>
    );
}

// 단순 목록 (파일 수가 적을 때)
function SimpleList({ 
    fileItems, 
    onToggleFile 
}: { 
    fileItems: { fullPath: string; fileName: string; isSelected: boolean }[];
    onToggleFile: (file: string) => void;
}) {
    return (
        <div className="overflow-y-auto py-1" style={{ maxHeight: 350 }}>
            {fileItems.map((item, index) => (
                <FileTreeItem
                    key={item.fullPath}
                    fileName={item.fileName}
                    fullPath={item.fullPath}
                    isSelected={item.isSelected}
                    onClick={() => onToggleFile(item.fullPath)}
                />
            ))}
        </div>
    );
}

// 가상화 목록 (파일 수가 많을 때)
function VirtualizedList({ 
    fileItems, 
    onToggleFile,
    parentRef,
    totalCount
}: { 
    fileItems: { fullPath: string; fileName: string; isSelected: boolean }[];
    onToggleFile: (file: string) => void;
    parentRef: React.RefObject<HTMLDivElement | null>;
    totalCount: number;
}) {
    const virtualizer = useVirtualizer({
        count: fileItems.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 32,
        overscan: 10,
    });

    const virtualItems = virtualizer.getVirtualItems();

    return (
        <>
            <div 
                ref={parentRef}
                className="overflow-y-auto overflow-x-hidden"
                style={{ height: Math.min(totalCount * 32, 350) }}
            >
                <div
                    style={{
                        height: `${virtualizer.getTotalSize()}px`,
                        width: '100%',
                        position: 'relative',
                    }}
                >
                    {virtualItems.map((virtualItem) => {
                        const item = fileItems[virtualItem.index];
                        return (
                            <div
                                key={virtualItem.key}
                                style={{
                                    position: 'absolute',
                                    top: 0,
                                    left: 0,
                                    width: '100%',
                                    height: `${virtualItem.size}px`,
                                    transform: `translateY(${virtualItem.start}px)`,
                                }}
                            >
                                <FileTreeItem
                                    fileName={item.fileName}
                                    fullPath={item.fullPath}
                                    isSelected={item.isSelected}
                                    onClick={() => onToggleFile(item.fullPath)}
                                />
                            </div>
                        );
                    })}
                </div>
            </div>
            {/* Footer */}
            <div className="px-3 py-1.5 border-t border-white/10 bg-white/5 text-[10px] text-zinc-500">
                <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 bg-green-500 rounded-full" />
                    Virtualized: {virtualItems.length} visible
                </span>
            </div>
        </>
    );
}

/**
 * Individual file item component - memoized for performance
 */
const FileTreeItem = React.memo(function FileTreeItem({
    fileName,
    fullPath,
    isSelected,
    onClick
}: {
    fileName: string;
    fullPath: string;
    isSelected: boolean;
    onClick: () => void;
}) {
    // Determine file icon based on extension
    const getFileIcon = (name: string) => {
        const ext = name.split('.').pop()?.toLowerCase();
        switch (ext) {
            case 'py': return '🐍';
            case 'js': return '📜';
            case 'ts': case 'tsx': return '💠';
            case 'java': return '☕';
            case 'php': return '🐘';
            case 'go': return '🔷';
            case 'html': return '🌐';
            case 'css': return '🎨';
            case 'json': return '📋';
            case 'yaml': case 'yml': return '⚙️';
            default: return '📄';
        }
    };

    return (
        <div
            className={`flex items-center gap-2 mx-2 px-2 py-1 rounded cursor-pointer text-xs transition-all duration-150 ${
                isSelected 
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30' 
                    : 'hover:bg-white/5 text-zinc-500 hover:text-zinc-300 border border-transparent'
            }`}
            onClick={onClick}
            title={fullPath}
        >
            {/* Selection indicator */}
            <div className={`w-3 h-3 flex-shrink-0 rounded-sm border transition-all ${
                isSelected 
                    ? 'bg-cyan-500 border-cyan-400' 
                    : 'border-zinc-600'
            }`}>
                {isSelected && (
                    <svg className="w-full h-full text-black" viewBox="0 0 12 12">
                        <path 
                            d="M3.5 6L5 7.5L8.5 4" 
                            stroke="currentColor" 
                            strokeWidth="1.5" 
                            fill="none" 
                            strokeLinecap="round" 
                            strokeLinejoin="round"
                        />
                    </svg>
                )}
            </div>
            
            {/* File icon */}
            <span className="flex-shrink-0">{getFileIcon(fileName)}</span>
            
            {/* File name */}
            <span className="truncate flex-1">{fileName}</span>
        </div>
    );
});

export default VirtualizedFileTree;
