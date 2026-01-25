'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Loader, AlertTriangle, FileCode } from 'lucide-react';

function CodeContent() {
    const searchParams = useSearchParams();
    const file = searchParams.get('file');
    const base = searchParams.get('base');
    const line = searchParams.get('line');

    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!file || !base) {
            setError("Missing file or base path parameters.");
            setLoading(false);
            return;
        }

        fetch('/api/files', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ targetDir: base, relativePath: file })
        })
            .then(async (r) => {
                const data = await r.json();
                if (!r.ok) throw new Error(data.error || 'Failed to load');
                setContent(data.content);
            })
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, [file, base]);

    useEffect(() => {
        // Auto-scroll to line if present
        if (!loading && line) {
            setTimeout(() => {
                const el = document.getElementById(`line-${line}`);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 500);
        }
    }, [loading, line]);

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-screen text-red-500 gap-2 bg-slate-950">
                <AlertTriangle size={48} />
                <h2 className="text-xl font-bold">Error Loading File</h2>
                <p>{error}</p>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-screen text-slate-400 gap-2 bg-slate-950">
                <Loader size={32} className="animate-spin" />
                <p>Fetching source code...</p>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#1e1e1e]">
            <header className="fixed top-0 left-0 right-0 h-10 bg-slate-900 border-b border-slate-800 flex items-center px-4 justify-between z-10 text-slate-300 text-sm font-mono">
                <div className="flex items-center gap-2">
                    <FileCode size={16} className="text-blue-400" />
                    <span>{file}</span>
                </div>
                {line && <span className="text-slate-500">Line {line}</span>}
            </header>

            <div className="pt-10 overflow-auto h-full">
                <SyntaxHighlighter
                    language={file?.endsWith('.py') ? 'python' : 'javascript'}
                    style={vscDarkPlus}
                    showLineNumbers={true}
                    wrapLines={true}
                    lineProps={(lineNumber: number) => {
                        const style: React.CSSProperties = { display: 'block' };
                        // Parse line from query param (handle potential string/number mismatch)
                        const targetLine = line ? parseInt(line, 10) : -1;

                        if (targetLine > 0 && lineNumber === targetLine) {
                            style.backgroundColor = 'rgba(220, 38, 38, 0.4)'; // Darker Red for visibility
                            style.borderLeft = '4px solid #ef4444';
                            style.width = '100%';
                        }
                        return { style, id: `line-${lineNumber}` };
                    }}
                >
                    {content}
                </SyntaxHighlighter>
            </div>
        </div>
    );
}

export default function CodePage() {
    return (
        <Suspense fallback={<div className="bg-slate-950 h-screen text-white p-10">Loading...</div>}>
            <CodeContent />
        </Suspense>
    );
}
