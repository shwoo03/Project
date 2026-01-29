"use client";

import React, { useState, useEffect, useCallback, memo } from 'react';
import { Activity, Layers, GitBranch, Zap } from 'lucide-react';

interface PerformanceStats {
    totalNodes: number;
    visibleNodes: number;
    totalEdges: number;
    visibleEdges: number;
    renderRatio: number;
    fps?: number;
    memoryUsage?: number;
}

interface PerformanceMonitorProps {
    stats: PerformanceStats;
    isVirtualized?: boolean;
    showDetails?: boolean;
}

/**
 * Performance monitor component showing rendering statistics.
 * Useful for debugging and demonstrating optimization benefits.
 */
export const PerformanceMonitor = memo(function PerformanceMonitor({
    stats,
    isVirtualized = false,
    showDetails = false
}: PerformanceMonitorProps) {
    const [fps, setFps] = useState(60);
    const [expanded, setExpanded] = useState(showDetails);

    // FPS monitoring
    useEffect(() => {
        let frameCount = 0;
        let lastTime = performance.now();
        let animationId: number;

        const measureFps = () => {
            frameCount++;
            const currentTime = performance.now();
            
            if (currentTime - lastTime >= 1000) {
                setFps(frameCount);
                frameCount = 0;
                lastTime = currentTime;
            }
            
            animationId = requestAnimationFrame(measureFps);
        };

        animationId = requestAnimationFrame(measureFps);
        return () => cancelAnimationFrame(animationId);
    }, []);

    // Performance rating
    const getPerformanceRating = useCallback(() => {
        if (fps >= 55 && stats.renderRatio <= 30) return { label: 'Excellent', color: 'text-green-400', bg: 'bg-green-500' };
        if (fps >= 45 && stats.renderRatio <= 50) return { label: 'Good', color: 'text-cyan-400', bg: 'bg-cyan-500' };
        if (fps >= 30) return { label: 'Fair', color: 'text-yellow-400', bg: 'bg-yellow-500' };
        return { label: 'Poor', color: 'text-red-400', bg: 'bg-red-500' };
    }, [fps, stats.renderRatio]);

    const rating = getPerformanceRating();

    // Don't show for small graphs
    if (stats.totalNodes < 50 && !expanded) {
        return null;
    }

    return (
        <div className="absolute bottom-4 left-4 z-40">
            <div 
                className={`bg-black/80 backdrop-blur rounded-lg border border-white/10 shadow-xl transition-all duration-300 ${
                    expanded ? 'w-64' : 'w-auto'
                }`}
            >
                {/* Collapsed view - just performance indicator */}
                <div 
                    className="flex items-center gap-2 px-3 py-2 cursor-pointer"
                    onClick={() => setExpanded(!expanded)}
                >
                    <div className={`w-2 h-2 rounded-full ${rating.bg} ${fps >= 30 ? 'animate-pulse' : ''}`} />
                    <span className={`text-xs font-medium ${rating.color}`}>{fps} FPS</span>
                    
                    {isVirtualized && (
                        <span className="text-[10px] bg-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded">
                            <Zap size={10} className="inline mr-0.5" />
                            Virtual
                        </span>
                    )}
                    
                    <span className="text-[10px] text-zinc-500">
                        {stats.visibleNodes}/{stats.totalNodes}
                    </span>
                </div>

                {/* Expanded view - detailed stats */}
                {expanded && (
                    <div className="px-3 pb-3 border-t border-white/10 pt-2 space-y-2">
                        {/* Performance bar */}
                        <div className="flex items-center justify-between text-xs">
                            <span className="text-zinc-400">Performance</span>
                            <span className={rating.color}>{rating.label}</span>
                        </div>
                        
                        {/* Stats grid */}
                        <div className="grid grid-cols-2 gap-2 text-xs">
                            <StatItem 
                                icon={<Layers size={12} />}
                                label="Nodes" 
                                value={`${stats.visibleNodes}/${stats.totalNodes}`}
                                subtext={`${stats.renderRatio}% rendered`}
                            />
                            <StatItem 
                                icon={<GitBranch size={12} />}
                                label="Edges" 
                                value={`${stats.visibleEdges}/${stats.totalEdges}`}
                            />
                            <StatItem 
                                icon={<Activity size={12} />}
                                label="FPS" 
                                value={fps.toString()}
                                highlight={fps < 30}
                            />
                            <StatItem 
                                icon={<Zap size={12} />}
                                label="Optimized" 
                                value={isVirtualized ? 'Yes' : 'No'}
                            />
                        </div>

                        {/* Render savings */}
                        {stats.renderRatio < 100 && (
                            <div className="text-[10px] text-zinc-500 border-t border-white/5 pt-2">
                                💡 Saving {100 - stats.renderRatio}% render time via viewport culling
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
});

const StatItem = memo(function StatItem({ 
    icon, 
    label, 
    value, 
    subtext,
    highlight = false 
}: { 
    icon: React.ReactNode; 
    label: string; 
    value: string;
    subtext?: string;
    highlight?: boolean;
}) {
    return (
        <div className={`p-2 rounded bg-white/5 ${highlight ? 'border border-red-500/30' : ''}`}>
            <div className="flex items-center gap-1 text-zinc-500 mb-0.5">
                {icon}
                <span>{label}</span>
            </div>
            <div className={`font-medium ${highlight ? 'text-red-400' : 'text-zinc-300'}`}>
                {value}
            </div>
            {subtext && (
                <div className="text-[10px] text-zinc-600">{subtext}</div>
            )}
        </div>
    );
});

export default PerformanceMonitor;
