"use client";

import React, { memo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, Check, X, FileCode, Database, GitBranch, Shield } from 'lucide-react';

interface StreamingProgressProps {
    isStreaming: boolean;
    phase: string;
    progress: number;
    message: string;
    stats?: {
        parsed_files?: number;
        cached_files?: number;
        total_files?: number;
        total_endpoints?: number;
        taint_flows?: number;
    } | null;
    error?: string | null;
    elapsedMs?: number | null;
    onCancel?: () => void;
}

const PHASES = [
    { id: 'init', label: 'Initialize', icon: FileCode },
    { id: 'symbols', label: 'Scan Symbols', icon: Database },
    { id: 'parsing', label: 'Parse Files', icon: GitBranch },
    { id: 'clustering', label: 'Cluster', icon: GitBranch },
    { id: 'taint', label: 'Taint Analysis', icon: Shield },
];

/**
 * Streaming analysis progress component.
 * Shows real-time progress with phase indicators and statistics.
 */
export const StreamingProgress = memo(function StreamingProgress({
    isStreaming,
    phase,
    progress,
    message,
    stats,
    error,
    elapsedMs,
    onCancel
}: StreamingProgressProps) {
    if (!isStreaming && !error && !elapsedMs) {
        return null;
    }

    const currentPhaseIndex = PHASES.findIndex(p => p.id === phase);

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="absolute top-20 left-1/2 transform -translate-x-1/2 z-50 w-[500px]"
            >
                <div className="bg-black/90 backdrop-blur-xl rounded-xl border border-white/10 shadow-2xl overflow-hidden">
                    {/* Header */}
                    <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            {isStreaming ? (
                                <Loader2 size={16} className="text-cyan-400 animate-spin" />
                            ) : error ? (
                                <X size={16} className="text-red-400" />
                            ) : (
                                <Check size={16} className="text-green-400" />
                            )}
                            <span className="text-sm font-medium text-zinc-200">
                                {isStreaming ? 'Streaming Analysis' : error ? 'Analysis Failed' : 'Analysis Complete'}
                            </span>
                        </div>
                        
                        {isStreaming && onCancel && (
                            <button
                                onClick={onCancel}
                                className="text-xs text-zinc-500 hover:text-red-400 transition-colors"
                            >
                                Cancel
                            </button>
                        )}

                        {elapsedMs && !isStreaming && (
                            <span className="text-xs text-zinc-500">
                                {elapsedMs.toFixed(0)}ms
                            </span>
                        )}
                    </div>

                    {/* Phase indicators */}
                    <div className="px-4 py-3 flex items-center gap-1">
                        {PHASES.map((p, index) => {
                            const Icon = p.icon;
                            const isActive = p.id === phase;
                            const isComplete = currentPhaseIndex > index;
                            const isPending = currentPhaseIndex < index;

                            return (
                                <React.Fragment key={p.id}>
                                    <div
                                        className={`flex items-center gap-1.5 px-2 py-1 rounded-md transition-all ${
                                            isActive 
                                                ? 'bg-cyan-500/20 text-cyan-300' 
                                                : isComplete 
                                                    ? 'text-green-400' 
                                                    : 'text-zinc-600'
                                        }`}
                                    >
                                        <Icon size={12} />
                                        <span className="text-[10px] font-medium">{p.label}</span>
                                        {isComplete && <Check size={10} />}
                                    </div>
                                    
                                    {index < PHASES.length - 1 && (
                                        <div className={`flex-1 h-px max-w-4 ${
                                            isComplete ? 'bg-green-400/50' : 'bg-zinc-700'
                                        }`} />
                                    )}
                                </React.Fragment>
                            );
                        })}
                    </div>

                    {/* Progress bar */}
                    <div className="px-4">
                        <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                            <motion.div
                                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500"
                                initial={{ width: 0 }}
                                animate={{ width: `${progress}%` }}
                                transition={{ duration: 0.3, ease: "easeOut" }}
                            />
                        </div>
                        <div className="flex justify-between items-center mt-1.5 mb-3">
                            <span className="text-xs text-zinc-400">{message}</span>
                            <span className="text-xs text-zinc-500 tabular-nums">{progress}%</span>
                        </div>
                    </div>

                    {/* Error display */}
                    {error && (
                        <div className="mx-4 mb-3 p-2 bg-red-500/10 border border-red-500/30 rounded-lg">
                            <p className="text-xs text-red-300">{error}</p>
                        </div>
                    )}

                    {/* Stats */}
                    {stats && (
                        <div className="px-4 pb-3">
                            <div className="grid grid-cols-4 gap-2">
                                <StatBox 
                                    label="Files" 
                                    value={stats.parsed_files ?? 0}
                                    subValue={stats.cached_files ? `${stats.cached_files} cached` : undefined}
                                />
                                <StatBox 
                                    label="Total" 
                                    value={stats.total_files ?? 0}
                                />
                                <StatBox 
                                    label="Endpoints" 
                                    value={stats.total_endpoints ?? 0}
                                />
                                <StatBox 
                                    label="Taint Flows" 
                                    value={stats.taint_flows ?? 0}
                                    highlight={(stats.taint_flows ?? 0) > 0}
                                />
                            </div>
                        </div>
                    )}
                </div>
            </motion.div>
        </AnimatePresence>
    );
});

const StatBox = memo(function StatBox({ 
    label, 
    value, 
    subValue,
    highlight = false
}: { 
    label: string; 
    value: number; 
    subValue?: string;
    highlight?: boolean;
}) {
    return (
        <div className={`p-2 rounded-lg ${highlight ? 'bg-orange-500/10 border border-orange-500/30' : 'bg-white/5'}`}>
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">{label}</div>
            <div className={`text-sm font-bold tabular-nums ${highlight ? 'text-orange-300' : 'text-zinc-200'}`}>
                {value.toLocaleString()}
            </div>
            {subValue && (
                <div className="text-[10px] text-zinc-600">{subValue}</div>
            )}
        </div>
    );
});

export default StreamingProgress;
