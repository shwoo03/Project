import React, { useState } from 'react';
import { RouteData } from '@/lib/graph-transformer';
import { Bot, RefreshCw, AlertTriangle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface Props {
    data: RouteData;
    codeSnippet?: string; // Optional: Passing actual code could be complex, we'll use metadata for now
}

export default function AiAuditor({ data }: Props) {
    const [analysis, setAnalysis] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [usedModel, setUsedModel] = useState<string>('');
    const [error, setError] = useState<string | null>(null);

    const handleAudit = async () => {
        setLoading(true);
        setError(null);
        setAnalysis(null);

        try {
            // For demo, we construct a pseudo-code representation if actual source code isn't available in memory
            // In a real app, you'd fetch the file content from the server via API.
            const pseudoCode = `
// Method: ${data.method}
// Path: ${data.path}
// File: ${data.file}:${data.line}
// Params: ${data.params?.join(', ') || 'None'}
// Sinks: ${data.sinks?.map(s => s.type).join(', ') || 'None'}
      `;

            const res = await fetch('/api/ai-audit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: pseudoCode,
                    context: `Web Framework: ${data.framework}. Analysis: Found ${data.sinks?.length} static sinks.`
                })
            });

            const result = await res.json();
            if (!res.ok) throw new Error(result.error);

            setAnalysis(result.result);
            setUsedModel(result.model);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="mt-6 bg-slate-950 rounded-lg border border-slate-800 overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 bg-indigo-950/30 border-b border-indigo-900/50">
                <div className="flex items-center gap-2 text-indigo-300 text-xs font-semibold">
                    <Bot size={14} />
                    <span>AI Security Auditor</span>
                </div>
                {!analysis && !loading && (
                    <button
                        onClick={handleAudit}
                        className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-2 py-1 rounded transition-colors flex items-center gap-1"
                    >
                        Start Audit
                    </button>
                )}
            </div>

            <div className="p-4 text-xs">
                {loading && (
                    <div className="flex items-center gap-2 text-slate-400 animate-pulse">
                        <RefreshCw size={14} className="animate-spin" />
                        Analyzing endpoint logic...
                    </div>
                )}

                {error && (
                    <div className="text-red-400 flex items-center gap-2">
                        <AlertTriangle size={14} />
                        Failed: {error}
                    </div>
                )}

                {analysis && (
                    <div>
                        <div className="prose prose-invert prose-xs max-w-none">
                            {/* @ts-ignore */}
                            <ReactMarkdown>{analysis}</ReactMarkdown>
                        </div>
                        <div className="mt-3 text-[10px] text-slate-500 text-right">
                            Analyzed by: {usedModel}
                        </div>
                        <button
                            onClick={handleAudit}
                            className="mt-2 text-[10px] text-indigo-400 hover:text-indigo-300 underline"
                        >
                            Re-run Audit
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
