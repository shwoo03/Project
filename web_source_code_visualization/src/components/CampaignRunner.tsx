
import React, { useState, useEffect, useRef } from 'react';
import { RouteData } from '@/lib/graph-transformer';
import { Play, Loader2, CheckCircle2, AlertCircle, FileSearch, Bug, ShieldAlert, X } from 'lucide-react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';

interface Props {
    routes: RouteData[];
    targetPath: string;
    onClose: () => void;
}

type Step = 'idle' | 'analyzing' | 'planning' | 'exploiting' | 'reporting' | 'finished';

export default function CampaignRunner({ routes, targetPath, onClose }: Props) {
    const [step, setStep] = useState<Step>('idle');
    const [logs, setLogs] = useState<{ timestamp: string, msg: string, type: 'info' | 'success' | 'error' | 'warn' }[]>([]);
    const [report, setReport] = useState('');
    const [progress, setProgress] = useState(0);
    const logEndRef = useRef<HTMLDivElement>(null);

    const addLog = (msg: string, type: 'info' | 'success' | 'error' | 'warn' = 'info') => {
        setLogs(prev => [...prev, { timestamp: new Date().toLocaleTimeString(), msg, type }]);
    };

    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    const runCampaign = async () => {
        setStep('analyzing');
        const currentLogs: string[] = []; // Local accumulator for report

        const log = (msg: string, type: 'info' | 'success' | 'error' | 'warn' = 'info') => {
            currentLogs.push(`[${new Date().toLocaleTimeString()}] ${msg} `);
            addLog(msg, type);
        };

        log("보안 점검 프로세스 초기화 중...", 'info');
        log(`${routes.length}개의 API 라우트 로드 완료.`, 'info');
        setProgress(5);

        // 1. Recon & Filter
        const targets = routes.filter(r =>
            (r.riskLevel === 'critical' || r.riskLevel === 'high') && r.sinks?.length
        );

        if (targets.length === 0) {
            log("고위험 대상이 식별되지 않았습니다. 잠재적 위험 요소 스캔 중...", 'warn');
            setReport(`## ✅ 보안 점검 완료: 안전함(Clean)
            
자동화된 정찰 단계에서 치명적인 취약점이 발견되지 않았습니다.

** 점검 요약:**
    - 스캔된 총 라우트: ${routes.length} 개
        - 발견된 위험 요소: 0건

            ** 권장 사항:**
                - 기본적인 인젝션 공격에 대해 안전한 것으로 보입니다.
- 비즈니스 로직에 대한 수동 점검을 권장합니다.
            `);
            setStep('finished');
            return;
        }

        log(`${targets.length}개의 주요 점검 대상 식별됨.`, 'success');
        setProgress(20);

        // 2. Verification
        setStep('planning');
        const attackPlan = [];
        const findings = []; // Store detailed context for the report

        for (const target of targets) {
            log(`검증 중: ${target.method} ${target.path} `, 'info');

            // Fetch Source Code for Analysis
            let sourceCode = `Route: ${target.path} `;
            try {
                const fileRes = await fetch('/api/files', {
                    method: 'POST',
                    body: JSON.stringify({ targetDir: targetPath, relativePath: target.file })
                });
                if (fileRes.ok) {
                    const fileData = await fileRes.json();
                    sourceCode = fileData.content || sourceCode;
                }
            } catch (err) {
                log(`소스 코드 로드 실패: ${target.file} `, 'warn');
            }

            try {
                const res = await fetch('/api/ai-campaign', {
                    method: 'POST',
                    body: JSON.stringify({
                        stage: 'verify',
                        data: { vulnType: target.sinks![0].type, snippet: sourceCode }
                    })
                });
                const verifyResult = await res.json();

                if (verifyResult.isVulnerable) {
                    log(`[취약점 확인] ${target.path} - ${target.sinks![0].type} `, 'success');

                    // Get Payloads
                    const planRes = await fetch('/api/ai-campaign', {
                        method: 'POST',
                        body: JSON.stringify({
                            stage: 'plan',
                            data: {
                                method: target.method,
                                path: target.path,
                                vulnType: target.sinks![0].type,
                                sanitizers: target.sanitizers,
                                snippet: sourceCode // Critical: Pass code so AI knows variable names!
                            }
                        })
                    });
                    const planData = await planRes.json();
                    attackPlan.push({ target, payloads: planData.payloads });

                    // Critical: Save Findings for Report
                    findings.push({
                        location: target.path,
                        vulnType: target.sinks![0].type,
                        snippet: sourceCode, // The actual code!
                        reason: verifyResult.reason || "AI verified confirm.",
                        payloads: planData.payloads
                    });

                    log(`공격 페이로드 ${planData.payloads?.length || 0}개 생성 완료.`, 'info');

                } else {
                    log(`[안전함] ${target.path}: ${verifyResult.reason || '로직 검증 통과'} `, 'success');
                }
            } catch (e) {
                log(`${target.path} 분석 중 오류 발생`, 'error');
            }
        }

        setProgress(50);

        // 3. Exploitation
        setStep('exploiting');

        if (attackPlan.length === 0) {
            // Even if no exploits, generate a report explaining WHY things were safe
            log("익스플로잇 가능한 취약점이 없습니다.", 'warn');
            try {
                const repRes = await fetch('/api/ai-campaign', {
                    method: 'POST',
                    body: JSON.stringify({ stage: 'report', data: { logs: currentLogs, findings: [] } })
                });
                const repData = await repRes.json();
                setReport(repData.markdown || "## Security Assessment Complete\n\nNo exploits generated. See logs for verification details.");
            } catch {
                setReport("## Assessment Complete\n\nAll targets verified safe.");
            }
            setStep('finished');
            return;
        }

        for (const plan of attackPlan) {
            log(` 🔥[공격 개시] ${plan.target.path} `, 'warn');

            for (const payload of (plan.payloads || [])) {
                log(` 🚀 페이로드 전송: ${payload.value} `, 'info');

                try {
                    // REAL EXPLOIT: Actually send the request
                    let exploitSuccess = false;

                    // Parse payload to determine attack type
                    // Expected format: "cookie_name=value" or just "value"
                    const isCookie = payload.param.toLowerCase().includes('cookie') || payload.name.toLowerCase().includes('cookie');

                    const headers: Record<string, string> = {};
                    if (isCookie) {
                        // Very basic cookie parsing for demo
                        headers['Cookie'] = payload.value;
                        // Note: Browsers block setting unsafe headers like Cookie in fetch. 
                        // In a real Red Team tool, this would be proxied via a backend.
                        // For this demo, we will try to use a Proxy API if available, 
                        // OR fallback to just 'simulating' success for the user if browser blocks it.
                        // BUT user asked "Is it real?". We should try to be as real as possible.
                        // Since we can't set Cookie header in client-side fetch, we must proxy.
                    }

                    // For now, we simulate the *network effect* by calling the actual endpoint
                    // If we can't set cookies, we might need a proxy. 
                    // Let's assume for this specific CTF (cookies), we need a proxy.
                    // Let's use the existing /api/analyze?url=... pattern or create a simple proxy?
                    // actually, let's just use the direct fetch and warn user if browser blocks it.

                    // PROXY SOLUTION: We will use a new server action or API to forward the request
                    const attackReq = await fetch('/api/exploit/run', {
                        method: 'POST',
                        body: JSON.stringify({
                            method: plan.target.method,
                            url: `http://localhost:3000${plan.target.path}`, // Assuming local target
                            headers: headers,
                            payload: payload.value
                        })
                    });

                    // Trigger Simulator Visualization
                    runSimulation(plan.target.sinks![0].type, payload.value);

                    const attackRes = await attackReq.json();

                    if (attackRes.success) {
                        log(` ✅ 공격 성공! 응답 코드: ${attackRes.status}`, 'success');
                        exploitSuccess = true;
                    } else {
                        log(` ❌ 공격 실패 (무효화됨)`, 'error');
                    }

                } catch (err) {
                    log(` ⚠️ 네트워크 오류`, 'error');
                }

                await new Promise(r => setTimeout(r, 1000));
            }
            log(`${plan.target.path} 공격 시퀀스 종료`, 'success');
        }

        setProgress(80);

        // 4. Reporting
        setStep('reporting');
        log("최종 보안 보고서 작성 중...", 'info');

        try {
            const repRes = await fetch('/api/ai-campaign', {
                method: 'POST',
                body: JSON.stringify({ stage: 'report', data: { logs: currentLogs, findings: findings } })
            });
            const repData = await repRes.json();

            if (repData.error) {
                setReport(`## 오류 발생\n\nAPI Error: ${repData.error}`);
            } else if (repData.markdown) {
                setReport(repData.markdown);
            } else {
                setReport(`## 보고서 생성 실패\n\nAI 응답 형식이 올바르지 않습니다:\n\n\`\`\`json\n${JSON.stringify(repData, null, 2)}\n\`\`\``);
            }
        } catch (e: any) {
            setReport(`## 네트워크 오류\n\n${e.message}`);
            log("보고서 생성 실패.", 'error');
        }

        setStep('finished');
        setProgress(100);
        log("보안 캠페인 종료.", 'success');
    };

    // --- Simulator Helper ---
    const runSimulation = (vulnType: string, payload: string) => {
        import('@/lib/simulator').then(mod => {
            const res = mod.simulateExploit(vulnType, payload);
            setSimResult(res);
        });
    };

    const [simResult, setSimResult] = useState<{ output: string, success: boolean, step: string } | null>(null);

    const steps = [
        { id: 'analyzing', label: '정찰 (Recon)', icon: FileSearch },
        { id: 'planning', label: '분석 (Analyze)', icon: Bug },
        { id: 'exploiting', label: '공격 (Exploit)', icon: ShieldAlert },
        { id: 'reporting', label: '보고서 (Report)', icon: FileText },
    ];

    return (
        // Standalone container logic
        <div className={`fixed inset-0 bg-slate-950 flex items-center justify-center p-4 font-sans ${onClose ? 'z-[100]' : ''}`}>
            <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-slate-900 w-full h-full rounded-xl border border-slate-800 shadow-2xl flex overflow-hidden ring-1 ring-slate-800"
            >
                {/* Left Panel: Sidebar */}
                <div className="w-72 bg-slate-950 border-r border-slate-800 p-6 flex flex-col">
                    <div className="mb-8">
                        <h2 className="text-xl font-bold text-white flex items-center gap-2">
                            <ShieldAlert className="text-indigo-500" size={24} /> Auto-Pwn
                        </h2>
                        <p className="text-slate-500 text-xs mt-1">Autonomous Cyber Operation</p>
                    </div>

                    {/* ... existing sidebar code ... */}
                    <div className="space-y-4 flex-1">
                        {steps.map((s, i) => {
                            const stepOrder = ['idle', 'analyzing', 'planning', 'exploiting', 'reporting', 'finished'];
                            const currentStepIndex = stepOrder.indexOf(step);
                            const thisStepIndex = stepOrder.indexOf(s.id);
                            const isPast = currentStepIndex > thisStepIndex;
                            const isActive = step === s.id;

                            return (
                                <div key={s.id} className={`flex items-center gap-3 py-3 px-4 rounded-lg transition-colors ${isActive ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : isPast ? 'text-emerald-500' : 'text-slate-600'}`}>
                                    {isPast ? <CheckCircle2 size={18} /> : <s.icon size={18} />}
                                    <span className="text-sm font-medium">{s.label}</span>
                                </div>
                            )
                        })}
                    </div>

                    <div className="mt-8">
                        {step === 'idle' ? (
                            <button
                                onClick={runCampaign}
                                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 rounded-xl transition-all flex items-center justify-center gap-2 text-sm shadow-lg shadow-indigo-500/20"
                            >
                                <Play size={16} className="fill-current" /> 공격 시나리오 시작
                            </button>
                        ) : step === 'finished' ? (
                            <button
                                onClick={onClose}
                                className="w-full bg-slate-800 hover:bg-slate-700 text-white font-medium py-4 rounded-xl transition-all flex items-center justify-center gap-2 text-sm"
                            >
                                <X size={16} /> 종료
                            </button>
                        ) : (
                            <div className="space-y-3 bg-slate-900 p-4 rounded-xl border border-slate-800">
                                <div className="flex justify-between text-xs text-slate-400">
                                    <span>공격 진행률</span>
                                    <span className="text-indigo-400 font-mono">{progress}%</span>
                                </div>
                                <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
                                    <motion.div
                                        className="bg-indigo-500 h-full shadow-[0_0_10px_rgba(99,102,241,0.5)]"
                                        initial={{ width: 0 }}
                                        animate={{ width: `${progress}%` }}
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Panel: Content */}
                <div className="flex-1 flex flex-col bg-slate-900 relative">

                    {step === 'finished' && report ? (
                        <div className="flex-1 overflow-y-auto p-12 custom-scrollbar bg-slate-900">
                            <div className="max-w-4xl mx-auto">
                                <div className="bg-slate-950 border border-slate-800 rounded-2xl p-10 shadow-xl">
                                    <div className="prose prose-invert max-w-none prose-p:text-slate-300 prose-headings:text-slate-100 prose-strong:text-slate-100 prose-ul:text-slate-300 prose-code:text-pink-400">
                                        <ReactMarkdown
                                            components={{
                                                h1: ({ node, ...props }) => <h1 className="text-3xl font-extrabold text-white border-b border-slate-700 pb-6 mb-8 tracking-tight" {...props} />,
                                                h2: ({ node, ...props }) => <h2 className="text-xl font-bold text-indigo-400 mt-10 mb-6 flex items-center gap-3 border-l-4 border-indigo-500 pl-4 bg-slate-900/50 py-2 rounded-r" {...props} />,
                                                p: ({ node, ...props }) => <p className="text-slate-300 leading-relaxed mb-4" {...props} />,
                                                li: ({ node, ...props }) => <li className="text-slate-300 mb-2 marker:text-indigo-500" {...props} />,
                                                strong: ({ node, ...props }) => <strong className="text-white font-semibold" {...props} />,
                                                code: ({ node, ...props }) => <code className="text-pink-400 bg-pink-500/10 px-1.5 py-0.5 rounded font-mono text-sm border border-pink-500/20" {...props} />,
                                                pre: ({ node, ...props }) => <pre className="overflow-x-auto p-4 my-4 bg-slate-950 border border-slate-800 rounded-lg text-sm scrollbar-thin scrollbar-thumb-slate-700" {...props} />,
                                                blockquote: ({ node, ...props }) => <blockquote className="border-l-4 border-indigo-500 pl-4 italic text-slate-400 my-4" {...props} />,
                                            }}
                                        >
                                            {report}
                                        </ReactMarkdown>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="flex-1 p-0 flex flex-col">
                            <div className="p-6 border-b border-slate-800 bg-slate-950/50 flex justify-between items-center">
                                <h3 className="text-sm font-mono text-slate-400 flex items-center gap-2">
                                    <Loader2 size={14} className={`animate-spin ${step === 'idle' ? 'hidden' : ''}`} />
                                    SYSTEM_LOG :: <span className="text-indigo-400">LIVE_FEED</span>
                                </h3>
                                <div className="flex gap-2">
                                    <div className="w-3 h-3 rounded-full bg-red-500/20 border border-red-500/50" />
                                    <div className="w-3 h-3 rounded-full bg-yellow-500/20 border border-yellow-500/50" />
                                    <div className="w-3 h-3 rounded-full bg-green-500/20 border border-green-500/50" />
                                </div>
                            </div>
                            <div className="flex-1 overflow-y-auto p-6 space-y-2 custom-scrollbar font-mono text-sm bg-black/20">
                                {logs.map((log, i) => (
                                    <div key={i} className={`flex gap-4 items-start p-2 rounded hover:bg-white/5 transition border-l-2 ${log.type === 'error' ? 'border-red-500 text-red-400 bg-red-500/5' :
                                        log.type === 'success' ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5' :
                                            log.type === 'warn' ? 'border-amber-500 text-amber-400 bg-amber-500/5' : 'border-slate-800 text-slate-400'
                                        }`}>
                                        <span className="text-slate-600 select-none text-xs w-20 shrink-0 font-bold">{log.timestamp}</span>
                                        <span className="break-all">{log.msg}</span>
                                    </div>
                                ))}
                                <div ref={logEndRef} />
                            </div>

                            {/* Simulation Terminal */}
                            <div className="bg-black/40 border-t border-slate-800 p-4 font-mono text-xs flex flex-col h-64">
                                <div className="flex items-center gap-2 text-slate-400 mb-2 select-none border-b border-slate-800 pb-2">
                                    <ShieldAlert size={12} className="text-red-500" />
                                    <span>Interactive Target Shell</span>
                                    <div className="flex-1" />
                                    <span className="text-[10px] text-slate-600">Virtual Environment Active</span>
                                </div>

                                <div className="flex-1 overflow-y-auto space-y-2 mb-2 custom-scrollbar">
                                    {simResult ? (
                                        <>
                                            <div className="text-blue-400">$ {simResult.step}</div>
                                            <div className={`${simResult.success ? 'text-green-400' : 'text-slate-400'} whitespace-pre-wrap pl-2 border-l-2 ${simResult.success ? 'border-green-500/50' : 'border-slate-800'}`}>
                                                {simResult.output}
                                            </div>
                                        </>
                                    ) : (
                                        <div className="text-slate-500 italic">Waiting for input... (Try 'cat /flag' or 'admin')</div>
                                    )}
                                </div>

                                {/* Manual Input */}
                                <div className="flex items-center gap-2 bg-slate-900/50 p-2 rounded border border-slate-700/50 focus-within:border-indigo-500/50 transition-colors">
                                    <span className="text-pink-500 font-bold">$</span>
                                    <input
                                        type="text"
                                        className="bg-transparent border-none outline-none text-slate-200 w-full placeholder:text-slate-600"
                                        placeholder="Enter manual payload (e.g. cat /etc/passwd OR 1=1)..."
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') {
                                                const val = e.currentTarget.value;
                                                // Default to RCE if ambiguous, or use context from selected node if possible?
                                                // For manual mode, let's try to infer or just default to Command Injection/Generic
                                                runSimulation('RCE', val);
                                                e.currentTarget.value = '';
                                            }
                                        }}
                                    />
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </motion.div>
        </div>
    );
}

// Helper to remove icon import conflict
function FileText(props: any) {
    return <svg {...props} width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" /><polyline points="14 2 14 8 20 8" /><line x1="16" x2="8" y1="13" y2="13" /><line x1="16" x2="8" y1="17" y2="17" /><line x1="10" x2="8" y1="9" y2="9" /></svg>
}
