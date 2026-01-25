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

    if (status === 'idle' || status === 'error') return null;

    return (
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 h-9">
            <span className="text-xs text-slate-400 font-mono flex items-center gap-1">
                <Container size={12} className={status === 'running' ? 'text-green-500' : 'text-slate-500'} />
                {deployType === 'compose' ? 'Compose' : 'Docker'}
            </span>

            <div className="h-4 w-[1px] bg-slate-700 mx-1"></div>

            {status === 'running' ? (
                <button
                    onClick={() => handleAction('stop')}
                    className="text-red-400 hover:text-red-300 flex items-center gap-1 text-[10px] font-bold"
                >
                    <Square size={10} fill="currentColor" /> STOP
                </button>
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
    );
}
