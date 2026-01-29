"use client";

import React from 'react';
import { Search, Bot, AlertTriangle, GitBranch, Network } from 'lucide-react';
import { ControlBarProps } from '@/types/graph';

/**
 * Top control bar with project path input and action buttons
 */
export function ControlBar({
    projectPath,
    onProjectPathChange,
    onAnalyze,
    onScan,
    onToggleFileTree,
    onToggleSinks,
    onToggleTaintFlows,
    onToggleCallGraph,
    loading,
    scanning,
    showFileTree,
    showSinks,
    showTaintFlows,
    showCallGraph
}: ControlBarProps) {
    return (
        <div className="absolute top-4 left-4 z-50 flex gap-4 bg-black/50 backdrop-blur p-4 rounded-xl border border-white/10">
            <div className="flex items-center gap-2 px-3 py-2 bg-white/5 rounded-lg border border-white/10 w-[500px]">
                <Search className="text-zinc-500" size={18} />
                <input
                    type="text"
                    value={projectPath}
                    onChange={(e) => onProjectPathChange(e.target.value)}
                    className="bg-transparent border-none outline-none text-white w-full text-sm font-mono"
                    placeholder="분석할 프로젝트의 절대 경로를 입력하세요..."
                />
            </div>
            <button
                onClick={onAnalyze}
                disabled={loading}
                className="px-6 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-lg font-bold hover:shadow-[0_0_20px_rgba(6,182,212,0.5)] transition-all disabled:opacity-50"
            >
                {loading ? '분석 중...' : '▶ 시각화'}
            </button>
            <button
                onClick={onScan}
                disabled={scanning}
                className="px-6 py-2 bg-gradient-to-r from-red-500 to-orange-500 rounded-lg font-bold hover:shadow-[0_0_20px_rgba(239,68,68,0.5)] transition-all disabled:opacity-50 flex items-center gap-2"
            >
                {scanning ? '스캔 중...' : '🛡️ 보안 스캔'}
            </button>
            <button
                onClick={onToggleCallGraph}
                className={`px-4 py-2 rounded-lg border transition-all font-bold flex items-center gap-2 ${showCallGraph ? 'bg-purple-500/20 text-purple-400 border-purple-500/50' : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'}`}
                title="함수 호출 관계 그래프 표시"
            >
                <Network size={16} />
                Call Graph
            </button>
            <button
                onClick={onToggleTaintFlows}
                className={`px-4 py-2 rounded-lg border transition-all font-bold flex items-center gap-2 ${showTaintFlows ? 'bg-red-500/20 text-red-400 border-red-500/50' : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'}`}
                title="입력→위험함수 데이터 흐름 표시"
            >
                <GitBranch size={16} />
                Taint
            </button>
            <button
                onClick={onToggleSinks}
                className={`px-4 py-2 rounded-lg border transition-all font-bold flex items-center gap-2 ${showSinks ? 'bg-amber-500/20 text-amber-400 border-amber-500/50' : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'}`}
                title="위험 함수 호출(Sink) 노드 표시/숨기기"
            >
                <AlertTriangle size={16} />
                Sink
            </button>
            <button
                onClick={onToggleFileTree}
                className={`px-4 py-2 rounded-lg border transition-all font-bold flex items-center gap-2 ${showFileTree ? 'bg-blue-500/20 text-blue-400 border-blue-500/50' : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'}`}
            >
                📂
            </button>
        </div>
    );
}

export default ControlBar;
