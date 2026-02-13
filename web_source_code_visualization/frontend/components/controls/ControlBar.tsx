"use client";

import React, { useState } from 'react';
import { Search, Bot, AlertTriangle, GitBranch, Network, Zap, FolderOpen, X } from 'lucide-react';
import { ControlBarProps } from '@/types/graph';

interface ProjectOption {
    name: string;
    path: string;
    full_path: string;
}

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
    onToggleStreaming,
    loading,
    scanning,
    showFileTree,
    showSinks,
    showTaintFlows,
    showCallGraph,
    useStreaming = false,
    isStreaming = false,
    availableProjects = []
}: ControlBarProps & { availableProjects?: ProjectOption[] }) {
    const [showProjectDropdown, setShowProjectDropdown] = useState(false);

    const handleProjectSelect = (project: ProjectOption) => {
        onProjectPathChange(project.full_path);
        setShowProjectDropdown(false);
    };

    return (
        <div className="absolute top-4 left-4 z-50 flex gap-4 bg-black/50 backdrop-blur p-4 rounded-xl border border-white/10">
            <div className="flex items-center gap-2 relative">
                {/* Direct path input */}
                <div className="flex items-center gap-2 px-3 py-2 bg-white/5 rounded-lg border border-white/10 w-[500px]">
                    <Search className="text-zinc-500" size={18} />
                    <input
                        type="text"
                        value={projectPath}
                        onChange={(e) => onProjectPathChange(e.target.value)}
                        className="bg-transparent border-none outline-none text-white w-full text-sm font-mono"
                        placeholder="직접 경로 입력 또는 오른쪽 버튼으로 선택..."
                    />
                    {projectPath && (
                        <button
                            onClick={() => onProjectPathChange('')}
                            className="text-zinc-500 hover:text-white transition-colors"
                        >
                            <X size={16} />
                        </button>
                    )}
                </div>

                {/* Projects dropdown button */}
                <button
                    onClick={() => setShowProjectDropdown(!showProjectDropdown)}
                    className="px-4 py-2 bg-white/5 rounded-lg border border-white/10 hover:bg-white/10 transition-all flex items-center gap-2 text-zinc-400"
                    title="Projects 폴더에서 선택"
                >
                    <FolderOpen size={18} />
                    <span className="text-sm font-medium">Projects</span>
                </button>

                {/* Project dropdown menu */}
                {showProjectDropdown && (
                    <div className="absolute top-full mt-2 left-0 w-[500px] bg-black/90 backdrop-blur rounded-lg border border-white/20 shadow-2xl overflow-hidden z-50">
                        <div className="p-3 bg-white/5 border-b border-white/10">
                            <p className="text-sm text-zinc-400 font-medium">
                                📂 Projects 디렉터리
                            </p>
                        </div>
                        <div className="max-h-96 overflow-y-auto">
                            {availableProjects.length === 0 ? (
                                <div className="p-6 text-center text-zinc-500">
                                    <p>projects 디렉터리에 프로젝트가 없습니다</p>
                                </div>
                            ) : (
                                availableProjects.map((project) => (
                                    <button
                                        key={project.full_path}
                                        onClick={() => handleProjectSelect(project)}
                                        className="w-full text-left px-4 py-3 hover:bg-white/10 transition-colors border-b border-white/5 last:border-b-0"
                                    >
                                        <div className="flex items-center gap-3">
                                            <FolderOpen className="text-blue-400" size={18} />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-white font-medium truncate">
                                                    {project.name}
                                                </p>
                                                <p className="text-xs text-zinc-500 font-mono truncate">
                                                    {project.full_path}
                                                </p>
                                            </div>
                                        </div>
                                    </button>
                                ))
                            )}
                        </div>
                    </div>
                )}
            </div>

            <button
                onClick={onAnalyze}
                disabled={loading || isStreaming}
                className="px-6 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-lg font-bold hover:shadow-[0_0_20px_rgba(6,182,212,0.5)] transition-all disabled:opacity-50"
            >
                {loading || isStreaming ? '분석 중...' : '▶ 시각화'}
            </button>
            <button
                onClick={onScan}
                disabled={scanning}
                className="px-6 py-2 bg-gradient-to-r from-red-500 to-orange-500 rounded-lg font-bold hover:shadow-[0_0_20px_rgba(239,68,68,0.5)] transition-all disabled:opacity-50 flex items-center gap-2"
            >
                {scanning ? '스캔 중...' : '🛡️ 보안 스캔'}
            </button>
            {onToggleStreaming && (
                <button
                    onClick={onToggleStreaming}
                    className={`px-4 py-2 rounded-lg border transition-all font-bold flex items-center gap-2 ${useStreaming
                        ? 'bg-green-500/20 text-green-400 border-green-500/50'
                        : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'
                        }`}
                    title="스트리밍 모드: 대규모 프로젝트에서 실시간 진행률 표시"
                >
                    <Zap size={16} />
                    Stream
                </button>
            )}

            {/* Upload Button */}
            <div className="relative">
                <input
                    type="file"
                    id="project-upload"
                    accept=".zip"
                    className="hidden"
                    onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;

                        if (!file.name.endsWith('.zip')) {
                            alert('오직 .zip 파일만 업로드 가능합니다.');
                            return;
                        }

                        // Create form data
                        const formData = new FormData();
                        formData.append('file', file);

                        try {
                            // Show loading state (optimistic UI or simple alert for now)
                            const btn = document.getElementById('upload-btn');
                            if (btn) btn.innerText = 'Uploading...';

                            const API_BASE = ''; // Use relative URL via Next.js proxy
                            const res = await fetch(`${API_BASE}/api/upload`, {
                                method: 'POST',
                                body: formData,
                            });

                            if (!res.ok) {
                                const err = await res.json();
                                throw new Error(err.detail || 'Upload failed');
                            }

                            const data = await res.json();
                            alert(`프로젝트 업로드 완료: ${data.project_name}`);

                            // Trigger refresh if callback provided, or just update path
                            if (onProjectPathChange) {
                                onProjectPathChange(data.path);
                            }

                            // Clear input
                            e.target.value = '';

                        } catch (err: any) {
                            console.error(err);
                            alert(`업로드 실패: ${err.message}`);
                        } finally {
                            const btn = document.getElementById('upload-btn');
                            if (btn) btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-upload"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg> Upload';
                        }
                    }}
                />
                <button
                    id="upload-btn"
                    onClick={() => document.getElementById('project-upload')?.click()}
                    className="px-4 py-2 bg-white/5 rounded-lg border border-white/10 hover:bg-white/10 transition-all flex items-center gap-2 text-zinc-400"
                    title="프로젝트 업로드 (.zip)"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-upload"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" x2="12" y1="3" y2="15" /></svg>
                    Upload
                </button>
            </div>
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

