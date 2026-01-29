"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { X, Bot } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { DetailPanelProps, Parameter, Filter, TemplateContext, TemplateUsage, SecurityFinding } from '@/types/graph';
import { describeFilterBehavior, formatParamType } from '@/utils/filterBehavior';

/**
 * Right-side detail panel showing node information, source code, and AI analysis
 */
export function DetailPanel({
    node,
    code,
    aiAnalysis,
    onClose,
    onAnalyzeAI,
    panelWidth,
    isResizing,
    onStartResize
}: DetailPanelProps) {
    const isTemplateNode = node.data.label?.includes("Template:");
    const templateContextNames = node.data.template_context
        ? new Set(node.data.template_context.map((c: TemplateContext) => c.name))
        : null;

    return (
        <motion.div
            initial={{ x: 300, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 300, opacity: 0 }}
            style={{ width: panelWidth }}
            className="absolute right-0 top-0 bottom-0 bg-black/80 backdrop-blur-md border-l border-white/10 p-6 shadow-2xl z-50 overflow-y-auto"
        >
            {/* Resizing Handle */}
            <div
                onMouseDown={onStartResize}
                className={`absolute left-0 top-0 bottom-0 w-2 cursor-col-resize hover:bg-cyan-500/50 transition-colors z-[60] ${isResizing ? 'bg-cyan-500' : 'bg-transparent'}`}
            />

            {/* Header */}
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-purple-500">
                    상세 정보 (Details)
                </h2>
                <button onClick={onClose} className="p-1 hover:bg-white/10 rounded-full">
                    <X size={20} />
                </button>
            </div>

            {/* AI Analysis Button */}
            {code && (
                <div className="mb-6">
                    <button
                        onClick={onAnalyzeAI}
                        disabled={aiAnalysis.loading}
                        className="w-full flex items-center justify-center gap-2 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 rounded-lg font-bold transition-all disabled:opacity-50"
                    >
                        {aiAnalysis.loading ? (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                <span>AI 분석 중...</span>
                            </>
                        ) : (
                            <>
                                <Bot size={18} />
                                <span>AI 보안 분석 (Security Analysis)</span>
                            </>
                        )}
                    </button>

                    {/* AI Analysis Result */}
                    {aiAnalysis.result && (
                        <div className="mt-4 p-4 bg-violet-900/20 border border-violet-500/30 rounded-lg">
                            <div className="flex justify-between items-center mb-2">
                                <h3 className="text-violet-300 font-bold text-sm flex items-center gap-2">
                                    <Bot size={14} /> AI 분석 결과
                                </h3>
                                {aiAnalysis.model && (
                                    <span className="text-[10px] bg-violet-500/20 px-2 py-1 rounded text-violet-300">
                                        {aiAnalysis.model}
                                    </span>
                                )}
                            </div>
                            <div className="prose prose-invert max-w-none text-zinc-300 leading-relaxed break-words
                                prose-headings:font-bold prose-headings:text-violet-300
                                prose-h1:text-2xl prose-h1:mt-8 prose-h1:mb-4 prose-h1:pb-2 prose-h1:border-b prose-h1:border-white/10
                                prose-h2:text-xl prose-h2:mt-6 prose-h2:mb-3
                                prose-h3:text-lg prose-h3:mt-4 prose-h3:mb-2
                                prose-p:text-base prose-p:my-3 prose-p:leading-7
                                prose-strong:text-violet-400 prose-strong:font-bold
                                prose-ul:list-disc prose-ul:pl-5 prose-ul:my-4 prose-li:my-1
                                prose-ol:list-decimal prose-ol:pl-5 prose-ol:my-4
                                prose-code:text-cyan-300 prose-code:bg-white/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:font-mono prose-code:text-sm prose-code:before:content-none prose-code:after:content-none
                                prose-pre:bg-black/50 prose-pre:border prose-pre:border-white/10 prose-pre:my-4
                                prose-a:text-indigo-400 prose-a:no-underline hover:prose-a:underline
                                prose-table:border-collapse prose-th:text-left prose-th:p-2 prose-td:p-2 prose-tr:border-b prose-tr:border-white/10
                                ">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        h1: ({ node, ...props }) => <h1 className="text-3xl font-extrabold text-violet-300 mt-8 mb-4 border-b border-white/10 pb-2" {...props} />,
                                        h2: ({ node, ...props }) => <h2 className="text-2xl font-bold text-violet-200 mt-6 mb-3" {...props} />,
                                        h3: ({ node, ...props }) => <h3 className="text-xl font-bold text-violet-100 mt-5 mb-2" {...props} />,
                                        strong: ({ node, ...props }) => <strong className="font-bold text-cyan-300" {...props} />,
                                        p: ({ node, ...props }) => <p className="leading-relaxed my-4 text-zinc-300" {...props} />,
                                        li: ({ node, ...props }) => <li className="my-1.5 ml-4" {...props} />,
                                        code({ node, inline, className, children, ...props }: { node?: any; inline?: boolean; className?: string; children?: React.ReactNode }) {
                                            const match = /language-(\w+)/.exec(className || '')
                                            return !inline && match ? (
                                                <SyntaxHighlighter
                                                    {...props}
                                                    style={vscDarkPlus}
                                                    language={match[1]}
                                                    PreTag="div"
                                                    customStyle={{ margin: '1.5em 0', borderRadius: '0.75rem', background: '#00000060', border: '1px solid #ffffff15' }}
                                                >
                                                    {String(children).replace(/\n$/, '')}
                                                </SyntaxHighlighter>
                                            ) : (
                                                <code className="bg-white/10 text-cyan-200 rounded px-1.5 py-0.5 font-mono text-sm" {...props}>
                                                    {children}
                                                </code>
                                            )
                                        }
                                    }}
                                >
                                    {aiAnalysis.result}
                                </ReactMarkdown>
                            </div>
                        </div>
                    )}
                </div>
            )}

            <div className="space-y-6">
                {/* Label */}
                <div className="p-4 rounded-lg bg-white/5 border border-white/10">
                    <label className="text-xs text-zinc-500 uppercase tracking-wider block mb-1">라벨 (Label)</label>
                    <p className="font-mono text-sm text-cyan-300 break-words">{node.data.label}</p>
                </div>

                {/* Parameters Table */}
                {node.data.params && (
                    <div>
                        <label className="text-xs text-zinc-500 uppercase tracking-wider block mb-2">입력 파라미터 (Parameters)</label>
                        <div className="bg-white/5 border border-white/10 rounded-lg overflow-hidden">
                            <table className="w-full text-sm text-left">
                                <thead>
                                    <tr className="bg-white/5 text-zinc-400 border-b border-white/10">
                                        <th className="px-3 py-2 font-medium">이름</th>
                                        <th className="px-3 py-2 font-medium">타입</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {node.data.params.length > 0 ? (
                                        node.data.params.map((p: Parameter, i: number) => (
                                            <tr key={i}>
                                                <td className="px-3 py-2 font-mono text-cyan-200">{p.name}</td>
                                                <td className="px-3 py-2 text-zinc-400">{formatParamType(p)}</td>
                                            </tr>
                                        ))
                                    ) : (
                                        <tr>
                                            <td colSpan={2} className="px-3 py-4 text-center text-zinc-500 italic">
                                                파라미터 없음
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {/* Filters Table */}
                {node.data.filters && (
                    <>
                        <div>
                            <label className="text-xs text-zinc-500 uppercase tracking-wider block mb-2">방어/필터 함수 (Sanitizers)</label>
                            <div className="bg-white/5 border border-white/10 rounded-lg overflow-hidden">
                                <table className="w-full text-sm text-left">
                                    <thead>
                                        <tr className="bg-white/5 text-zinc-400 border-b border-white/10">
                                            <th className="px-3 py-2 font-medium">함수</th>
                                            <th className="px-3 py-2 font-medium">인자</th>
                                            <th className="px-3 py-2 font-medium">라인</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {node.data.filters.length > 0 ? (
                                            node.data.filters.map((f: Filter, i: number) => (
                                                <tr key={i}>
                                                    <td className="px-3 py-2 font-mono text-cyan-200 break-all">{f.name}</td>
                                                    <td className="px-3 py-2 text-zinc-400 break-all">
                                                        {f.args && f.args.length > 0 ? f.args.join(", ") : "-"}
                                                    </td>
                                                    <td className="px-3 py-2 text-zinc-400">{f.line ?? "-"}</td>
                                                </tr>
                                            ))
                                        ) : (
                                            <tr>
                                                <td colSpan={3} className="px-3 py-4 text-center text-zinc-500 italic">
                                                    탐지된 필터 없음
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Filter Behavior Table */}
                        <div>
                            <label className="text-xs text-zinc-500 uppercase tracking-wider block mb-2">필터링 내용 (Filter Behavior)</label>
                            <div className="bg-white/5 border border-white/10 rounded-lg overflow-hidden">
                                <table className="w-full text-sm text-left">
                                    <thead>
                                        <tr className="bg-white/5 text-zinc-400 border-b border-white/10">
                                            <th className="px-3 py-2 font-medium">함수</th>
                                            <th className="px-3 py-2 font-medium">필터링/인코딩</th>
                                            <th className="px-3 py-2 font-medium">예시</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {node.data.filters.length > 0 ? (
                                            node.data.filters.map((f: Filter, i: number) => {
                                                const info = describeFilterBehavior(f.name, f.args);
                                                return (
                                                    <tr key={i}>
                                                        <td className="px-3 py-2 font-mono text-cyan-200 break-all">{f.name}</td>
                                                        <td className="px-3 py-2 text-zinc-400 break-words">{info.behavior}</td>
                                                        <td className="px-3 py-2 text-zinc-400 break-words">{info.examples}</td>
                                                    </tr>
                                                );
                                            })
                                        ) : (
                                            <tr>
                                                <td colSpan={3} className="px-3 py-4 text-center text-zinc-500 italic">
                                                    필터링 정보 없음
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </>
                )}

                {/* Template Context and Usage (for template nodes) */}
                {isTemplateNode && (
                    <div className="space-y-4">
                        {node.data.template_context && (
                            <div>
                                <label className="text-xs text-zinc-500 uppercase tracking-wider block mb-2">템플릿 컨텍스트 (Template Context)</label>
                                <div className="bg-white/5 border border-white/10 rounded-lg overflow-hidden">
                                    <table className="w-full text-sm text-left">
                                        <thead>
                                            <tr className="bg-white/5 text-zinc-400 border-b border-white/10">
                                                <th className="px-3 py-2 font-medium">변수</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {node.data.template_context.length > 0 ? (
                                                node.data.template_context.map((v: TemplateContext, i: number) => (
                                                    <tr key={i}>
                                                        <td className="px-3 py-2 font-mono text-cyan-200 break-all">{v.name}</td>
                                                    </tr>
                                                ))
                                            ) : (
                                                <tr>
                                                    <td className="px-3 py-4 text-center text-zinc-500 italic">
                                                        전달된 컨텍스트 없음
                                                    </td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}

                        {node.data.template_usage && (
                            <div>
                                <label className="text-xs text-zinc-500 uppercase tracking-wider block mb-2">템플릿 사용 (Template Usage)</label>
                                <div className="bg-white/5 border border-white/10 rounded-lg overflow-hidden">
                                    <table className="w-full text-sm text-left">
                                        <thead>
                                            <tr className="bg-white/5 text-zinc-400 border-b border-white/10">
                                                <th className="px-3 py-2 font-medium">변수</th>
                                                <th className="px-3 py-2 font-medium">라인</th>
                                                <th className="px-3 py-2 font-medium">상태</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {node.data.template_usage.length > 0 ? (
                                                node.data.template_usage.map((u: TemplateUsage, i: number) => {
                                                    const isPassed = templateContextNames?.has(u.name);
                                                    return (
                                                        <tr key={i}>
                                                            <td className="px-3 py-2 font-mono text-cyan-200 break-all">{u.name}</td>
                                                            <td className="px-3 py-2 text-zinc-400">{u.line ?? "-"}</td>
                                                            <td className="px-3 py-2 text-zinc-400">
                                                                {isPassed ? "passed" : "unknown"}
                                                            </td>
                                                        </tr>
                                                    );
                                                })
                                            ) : (
                                                <tr>
                                                    <td colSpan={3} className="px-3 py-4 text-center text-zinc-500 italic">
                                                        사용된 변수 없음
                                                    </td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* Security Findings */}
                {node.data.findings && node.data.findings.length > 0 && (
                    <div className="mb-6 border border-red-500/30 bg-red-900/10 rounded-lg p-4">
                        <h3 className="text-red-400 font-bold flex items-center gap-2 mb-3">
                            🚨 보안 취약점 발견 ({node.data.findings.length})
                        </h3>
                        <div className="space-y-3">
                            {node.data.findings.map((finding: SecurityFinding, idx: number) => (
                                <div key={idx} className="bg-black/40 border border-red-500/20 rounded p-3 text-sm">
                                    <div className="flex justify-between items-start mb-1">
                                        <span className="font-mono text-red-300 font-bold text-xs bg-red-900/40 px-2 py-0.5 rounded break-all">
                                            {finding.check_id}
                                        </span>
                                        <span className="text-xs text-zinc-500 uppercase ml-2 shrink-0">
                                            {finding.severity}
                                        </span>
                                    </div>
                                    <p className="text-zinc-300 mt-2 text-sm leading-relaxed">
                                        {finding.message}
                                    </p>
                                    <div className="mt-2 text-xs text-zinc-500 font-mono">
                                        Line: {finding.line}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Source Code Viewer */}
                <div>
                    <label className="text-xs text-zinc-500 uppercase tracking-wider block mb-2">
                        소스 코드 (Source Code)
                    </label>
                    <div className="rounded-lg overflow-hidden border border-white/10 text-sm">
                        {code ? (
                            <SyntaxHighlighter
                                language="python"
                                style={vscDarkPlus}
                                showLineNumbers={true}
                                startingLineNumber={node.data.line_number || 1}
                                customStyle={{ margin: 0, padding: '1.5rem', background: '#0a0a0a' }}
                            >
                                {code}
                            </SyntaxHighlighter>
                        ) : (
                            <div className="p-8 text-center text-zinc-600 bg-[#0a0a0a]">
                                {node.data.file_path ? "로드 중..." : "소스 코드를 찾을 수 없습니다."}
                            </div>
                        )}
                    </div>
                    {node.data.file_path && (
                        <p className="text-xs text-zinc-600 mt-2 font-mono text-right">
                            {node.data.file_path}:{node.data.line_number}
                        </p>
                    )}
                </div>
            </div>
        </motion.div>
    );
}

export default DetailPanel;
