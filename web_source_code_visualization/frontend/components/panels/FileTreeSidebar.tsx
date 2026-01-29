"use client";

import React from 'react';
import { FileTreeSidebarProps } from '@/types/graph';

/**
 * File browser sidebar component
 */
export function FileTreeSidebar({
    files,
    selectedFiles,
    onToggleFile,
    onSelectAll,
    onSelectNone
}: FileTreeSidebarProps) {
    if (files.length === 0) return null;

    return (
        <div className="absolute top-24 left-4 z-40 w-64 max-h-[calc(100vh-150px)] bg-black/80 backdrop-blur rounded-xl border border-white/10 flex flex-col overflow-hidden shadow-xl">
            <div className="p-3 border-b border-white/10 bg-white/5 flex justify-between items-center">
                <span className="font-bold text-sm text-zinc-300">File Browser ({files.length})</span>
                <div className="flex gap-2 text-xs">
                    <button
                        onClick={onSelectAll}
                        className="hover:text-white text-zinc-500 hover:bg-white/10 px-1 rounded"
                    >
                        All
                    </button>
                    <button
                        onClick={onSelectNone}
                        className="hover:text-white text-zinc-500 hover:bg-white/10 px-1 rounded"
                    >
                        None
                    </button>
                </div>
            </div>
            <div className="overflow-y-auto p-2 space-y-1">
                {files.map(file => {
                    const isSelected = selectedFiles.has(file);
                    const fileName = file.split(/[/\\]/).pop();
                    return (
                        <div
                            key={file}
                            className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-xs transition-colors ${isSelected ? 'bg-blue-500/20 text-blue-300' : 'hover:bg-white/5 text-zinc-500'}`}
                            onClick={() => onToggleFile(file)}
                        >
                            <div className={`w-3 h-3 flex-shrink-0 rounded-full border ${isSelected ? 'bg-blue-500 border-blue-400' : 'border-zinc-600'}`} />
                            <span className="truncate" title={file}>{fileName}</span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export default FileTreeSidebar;
