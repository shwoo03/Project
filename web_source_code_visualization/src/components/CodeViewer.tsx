import React, { useEffect, useState } from 'react';
import { X, Loader } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface Props {
    file: string | null;  // Relative path
    targetDir: string;    // Base project path
    onClose: () => void;
    highlightLine?: number; // Optional text highlighting
}

export default function CodeViewer({ file, targetDir, onClose, highlightLine }: Props) {
    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (file && targetDir) {
            setLoading(true);
            fetch('/api/files', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ targetDir, relativePath: file })
            })
                .then(r => r.json())
                .then(data => setContent(data.content || 'Error loading file'))
                .catch(e => setContent('Failed to load.'))
                .finally(() => setLoading(false));
        }
    }, [file, targetDir]);

    if (!file) return null;

    return (
        <div className="absolute inset-0 z-40 bg-black/60 backdrop-blur-sm flex items-center justify-center p-10">
            <div className="bg-slate-900 w-full h-full max-w-5xl rounded-xl border border-slate-700 shadow-2xl flex flex-col overflow-hidden">
                {/* Header */}
                <div className="h-12 border-b border-slate-800 flex items-center justify-between px-4 bg-slate-950">
                    <span className="font-mono text-sm text-slate-300">{file}</span>
                    <button onClick={onClose} className="p-1 hover:bg-slate-800 rounded text-slate-400">
                        <X size={18} />
                    </button>
                </div>

                {/* Code Body */}
                <div className="flex-1 overflow-auto relative bg-[#1e1e1e]">
                    {loading ? (
                        <div className="absolute inset-0 flex items-center justify-center text-slate-500 gap-2">
                            <Loader className="animate-spin" /> Loading source...
                        </div>
                    ) : (
                        <SyntaxHighlighter
                            language={file.endsWith('.py') ? 'python' : 'javascript'}
                            style={vscDarkPlus}
                            showLineNumbers={true}
                            wrapLines={true}
                            lineProps={(line) => {
                                const style: React.CSSProperties = { display: 'block' };
                                if (highlightLine && line === highlightLine) {
                                    style.backgroundColor = 'rgba(220, 38, 38, 0.2)'; // Red highlights
                                    style.borderLeft = '3px solid #ef4444';
                                }
                                return { style };
                            }}
                        >
                            {content}
                        </SyntaxHighlighter>
                    )}
                </div>
            </div>
        </div>
    );
}
