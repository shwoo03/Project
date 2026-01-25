import React, { useState, useEffect } from 'react';
import { Container, Play, Square, Loader } from 'lucide-react';

interface Props {
    targetPath: string;
}

export default function DockerManager({ targetPath }: Props) {
    const [status, setStatus] = useState<'idle' | 'checking' | 'ready' | 'deploying' | 'running' | 'error'>('idle');
    const [deployType, setDeployType] = useState<string | null>(null);

    useEffect(() => {
        if (targetPath) {
            setStatus('checking');
            fetch('/api/docker', {
                method: 'POST',
                body: JSON.stringify({ targetPath, action: 'check' })
            })
                .then(r => r.json())
                .then(data => {
                    if (data.canDeploy) {
                        setStatus('ready');
                        setDeployType(data.type);
                    } else {
                        setStatus('idle');
                    }
                })
                .catch(() => setStatus('error'));
        }
    }, [targetPath]);

    const handleAction = async (action: 'start' | 'stop') => {
        setStatus(action === 'start' ? 'deploying' : 'checking');
        try {
            const res = await fetch('/api/docker', {
                method: 'POST',
                body: JSON.stringify({ targetPath, action })
            });
            if (!res.ok) throw new Error('Action failed');

            if (action === 'start') setStatus('running');
            else setStatus('ready');

            alert(action === 'start' ? 'Deployment Started! (Check Docker Desktop)' : 'Service Stopped.');
        } catch (e) {
            setStatus('error');
            alert('Docker Action Failed.');
        }
    };

    const [showLogs, setShowLogs] = useState(false);
    const [logs, setLogs] = useState<string[]>([]);

    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (showLogs) {
            // Poll logs
            const fetchLogs = () => {
                fetch('/api/docker', { method: 'POST', body: JSON.stringify({ action: 'logs' }) })
                    .then(r => r.json())
                    .then(d => { if (d.logs) setLogs(d.logs); });
            };
            fetchLogs();
            interval = setInterval(fetchLogs, 2000);
        }
        return () => clearInterval(interval);
    }, [showLogs]);

    if (status === 'idle' || status === 'error') return null;

    return (
        <div className="flex items-center gap-2 relative">
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 h-9">
                <span className="text-xs text-slate-400 font-mono flex items-center gap-1">
                    <Container size={12} className={status === 'running' ? 'text-green-500' : 'text-slate-500'} />
                    {deployType === 'compose' ? 'Compose' : (deployType === 'python' ? 'Python App' : 'Docker')}
                </span>

                <div className="h-4 w-[1px] bg-slate-700 mx-1"></div>

                {status === 'running' ? (
                    <>
                        <button
                            onClick={() => setShowLogs(!showLogs)}
                            className={`flex items-center gap-1 text-[10px] font-bold ${showLogs ? 'text-blue-400' : 'text-slate-400 hover:text-white'}`}
                        >
                            <Square size={8} className="rotate-90" /> LOGS
                        </button>
                        <div className="h-4 w-[1px] bg-slate-700 mx-1"></div>
                        <button
                            onClick={() => handleAction('stop')}
                            className="text-red-400 hover:text-red-300 flex items-center gap-1 text-[10px] font-bold"
                        >
                            <Square size={10} fill="currentColor" /> STOP
                        </button>
                    </>
                ) : (
                    <button
                        onClick={() => handleAction('start')}
                        disabled={status === 'deploying'}
                        className="text-green-400 hover:text-green-300 flex items-center gap-1 text-[10px] font-bold disabled:opacity-50"
                    >
                        {status === 'deploying' ? <Loader size={10} className="animate-spin" /> : <Play size={10} fill="currentColor" />}
                        DEPLOY
                    </button>
                )}
            </div>

            {/* Log Viewer Popover */}
            {showLogs && (
                <div className="absolute top-full mt-2 right-0 w-96 max-h-64 bg-black/90 border border-slate-700 rounded-lg shadow-2xl overflow-hidden z-50 flex flex-col backdrop-blur-md">
                    <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
                        <span className="text-xs font-bold text-slate-300">Server Logs ({logs.length} lines)</span>
                        <button onClick={() => setShowLogs(false)} className="text-slate-500 hover:text-white">✕</button>
                    </div>
                    <div className="flex-1 p-2 overflow-y-auto font-mono text-[10px] text-slate-300 space-y-1 custom-scrollbar">
                        {logs.length === 0 && <span className="text-slate-500 italic">No logs yet...</span>}
                        {logs.map((line, i) => (
                            <div key={i} className={`break-all ${line.includes('[ERR]') ? 'text-red-400' : line.includes('[INFO]') ? 'text-blue-400' : ''}`}>
                                {line}
                            </div>
                        ))}
                        <div ref={(el) => { if (el) el.scrollIntoView({ behavior: 'smooth' }); }} />
                    </div>
                </div>
            )}
        </div>
    );
}
