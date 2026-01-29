"use client";

import React, { useCallback, useState, useEffect, useRef } from 'react';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
    addEdge,
    Connection,
    Edge,
    Node,
    MarkerType,
    Position
} from 'reactflow';
import 'reactflow/dist/style.css';
import { motion, AnimatePresence } from 'framer-motion';
import { Maximize2, X, Play, Search, Network, Bot } from 'lucide-react';
import dagre from 'dagre';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const Visualizer = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNode, setSelectedNode] = useState<Node | null>(null);
    const [currentCode, setCurrentCode] = useState<string>("");
    const [aiAnalysis, setAiAnalysis] = useState<{ loading: boolean; result: string | null; model?: string }>({ loading: false, result: null });
    const [projectPath, setProjectPath] = useState<string>("C:/Users/dntmd/OneDrive/Desktop/my/프로젝트/Project/web_source_code_visualization/xss-1/deploy");
    const [loading, setLoading] = useState(false);
    const [securityFindings, setSecurityFindings] = useState<any[]>([]);
    const [scanning, setScanning] = useState(false);
    const [panelWidth, setPanelWidth] = useState(800);
    const [isResizing, setIsResizing] = useState(false);
    const sidebarRef = useRef<HTMLDivElement>(null);

    // Filter State
    const [analysisData, setAnalysisData] = useState<any>(null); // Store raw data
    const [allFiles, setAllFiles] = useState<string[]>([]);
    const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
    const [showFileTree, setShowFileTree] = useState(true);
    const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());

    // When selectedFiles changes, re-process nodes
    useEffect(() => {
        if (analysisData && analysisData.endpoints) {
            // Auto-expand top-level clusters
            const topClusters = new Set<string>();
            analysisData.endpoints.forEach((ep: any) => {
                if (ep.type === 'cluster') {
                    topClusters.add(ep.id);
                }
            });
            if (topClusters.size > 0) {
                setExpandedClusters(prev => {
                    const next = new Set(prev);
                    topClusters.forEach(id => next.add(id));
                    return next;
                });
            }
            processNodes(analysisData.endpoints);
        }
    }, [selectedFiles, analysisData, expandedClusters]);

    const getNamedArg = (args: string[] | undefined, name: string) => {
        if (!args || args.length === 0) return null;
        const match = args.find((arg) => arg.trim().startsWith(`${name}=`));
        if (!match) return null;
        const parts = match.split("=");
        return parts.slice(1).join("=").trim() || null;
    };

    const describeFilterBehavior = (name: string, args: string[] | undefined) => {
        const lower = name.toLowerCase();
        if (lower === 'urllib.parse.quote' || lower === 'urllib.parse.quote_plus') {
            const safeArg = getNamedArg(args, 'safe') || (args && args.length > 1 ? args[1] : null);
            const safeLabel = safeArg ? `safe=${safeArg}` : "safe='/'";
            const behaviorBase = lower.endsWith('quote_plus')
                ? 'URL-encode (space -> +)'
                : 'URL-encode';
            return {
                behavior: `${behaviorBase}; leaves ${safeLabel} unescaped`,
                examples: "space, '\"', <, >, #, ?, &, %, +, ="
            };
        }

        if (lower === 'html.escape' || lower === 'markupsafe.escape' || lower === 'flask.escape' || lower === 'werkzeug.utils.escape' || lower === 'cgi.escape') {
            const quoteArg = getNamedArg(args, 'quote');
            const quotesEscaped = !quoteArg || !/false/i.test(quoteArg);
            return {
                behavior: 'HTML escape',
                examples: quotesEscaped ? '&, <, >, ", \'' : '&, <, >'
            };
        }

        if (lower === 'bleach.clean') {
            return {
                behavior: 'Strip/clean HTML tags and attributes',
                examples: '<script>, onclick='
            };
        }

        if (lower.endsWith('.escape') || lower.endsWith('.sanitize') || lower === 'escape' || lower === 'sanitize') {
            return {
                behavior: 'Custom sanitizer (unknown behavior)',
                examples: 'inspect function body'
            };
        }

        return {
            behavior: 'Unknown sanitizer',
            examples: '-'
        };
    };

    const formatParamType = (param: any) => {
        if (param?.source && ['path', 'query', 'body', 'header', 'cookie'].includes(param.source)) {
            switch (param.source) {
                case 'path':
                    return 'Path Param';
                case 'query':
                    return 'Query';
                case 'body':
                    return 'Body';
                case 'header':
                    return 'Header';
                case 'cookie':
                    return 'Cookie';
            }
        }
        return param?.type || 'Unknown';
    };

    const templateContextNames = selectedNode?.data?.template_context
        ? new Set(selectedNode.data.template_context.map((c: any) => c.name))
        : null;
    const isTemplateNode = selectedNode?.data?.label?.includes("Template:");


    const startResizing = useCallback((mouseDownEvent: React.MouseEvent) => {
        setIsResizing(true);
    }, []);

    const stopResizing = useCallback(() => {
        setIsResizing(false);
    }, []);

    const resize = useCallback(
        (mouseMoveEvent: MouseEvent) => {
            if (isResizing) {
                const newWidth = window.innerWidth - mouseMoveEvent.clientX;
                if (newWidth > 400 && newWidth < window.innerWidth - 100) {
                    setPanelWidth(newWidth);
                }
            }
        },
        [isResizing]
    );

    useEffect(() => {
        window.addEventListener("mousemove", resize);
        window.addEventListener("mouseup", stopResizing);
        return () => {
            window.removeEventListener("mousemove", resize);
            window.removeEventListener("mouseup", stopResizing);
        };
    }, [resize, stopResizing]);


    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    );

    const loadSnippet = async (filePath?: string, startLine?: number, endLine?: number) => {
        if (!filePath || !startLine) return;
        try {
            const res = await fetch('http://localhost:8000/api/snippet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_path: filePath,
                    start_line: startLine,
                    end_line: endLine || (startLine + 20)
                })
            });
            const data = await res.json();
            if (data.code) {
                setCurrentCode(data.code);
            }
        } catch (e) {
            console.error("Failed to fetch code", e);
            setCurrentCode("# Failed to load code snippet.");
        }
    };

    const onNodeClick = async (event: React.MouseEvent, node: Node) => {
        if (node.type === 'cluster') {
            const next = new Set(expandedClusters);
            if (next.has(node.id)) next.delete(node.id);
            else next.add(node.id);
            setExpandedClusters(next);
            return;
        }

        setSelectedNode(node);
        setCurrentCode("");

        // --- Backtrace Logic Start ---
        // 1. Reset all styles first
        const resetNodes = nodes.map(n => ({
            ...n,
            style: { ...n.style, opacity: 0.3 } // Dim everything by default
        }));
        const resetEdges = edges.map(e => ({
            ...e,
            style: { ...e.style, stroke: '#333', strokeWidth: 1, opacity: 0.2 },
            animated: false
        }));

        // 2. Find upstream paths
        const upstreamNodes = new Set<string>();
        const upstreamEdges = new Set<string>();
        const queue = [node.id];
        upstreamNodes.add(node.id);

        while (queue.length > 0) {
            const currentId = queue.shift();
            // Find edges connecting to this node
            const incomingEdges = edges.filter(e => e.target === currentId);
            incomingEdges.forEach(e => {
                upstreamEdges.add(e.id);
                if (!upstreamNodes.has(e.source)) {
                    upstreamNodes.add(e.source);
                    queue.push(e.source);
                }
            });
        }

        // 3. Apply Highlight Styles
        setNodes(resetNodes.map(n => {
            if (upstreamNodes.has(n.id)) {
                const isSelected = n.id === node.id;
                return {
                    ...n,
                    style: {
                        ...n.style,
                        opacity: 1,
                        boxShadow: isSelected ? '0 0 30px #bd00ff60' : '0 0 20px #ffae0040',
                        border: isSelected ? '2px solid #bd00ff' : '2px solid #ffae00'
                    }
                };
            }
            return n;
        }));

        setEdges(resetEdges.map(e => {
            if (upstreamEdges.has(e.id)) {
                return {
                    ...e,
                    animated: true,
                    style: { stroke: '#ffae00', strokeWidth: 2, opacity: 1 },
                    zIndex: 10
                };
            }
            return e;
        }));
        // --- Backtrace Logic End ---

        await loadSnippet(node.data.file_path, node.data.line_number, node.data.end_line_number);
    };

    const onPaneClick = () => {
        // Reset to default view when clicking background
        setSelectedNode(null);
        setAiAnalysis({ loading: false, result: null });
        setNodes(nds => nds.map(n => ({
            ...n,
            style: { ...n.data.initialStyle, opacity: 1 }
        })));
        setEdges(eds => eds.map(e => ({
            ...e,
            animated: e.id.includes('PROJECT'),
            style: { stroke: e.id.includes('PROJECT') ? '#00f0ff' : '#555', strokeWidth: e.id.includes('PROJECT') ? 2 : 1, opacity: 1 }
        })));
    };

    const getConnectedFiles = (startNodeId: string): string[] => {
        const connectedFiles = new Set<string>();
        const queue = [startNodeId];
        const visited = new Set<string>();

        // Add start node's file
        const startNode = nodes.find(n => n.id === startNodeId);
        if (startNode?.data.file_path) {
            connectedFiles.add(startNode.data.file_path);
        }

        while (queue.length > 0) {
            const currentId = queue.shift()!;
            if (visited.has(currentId)) continue;
            visited.add(currentId);

            // Find all connected edges (both directions)
            const relatedEdges = edges.filter(e => e.source === currentId || e.target === currentId);

            relatedEdges.forEach(edge => {
                const neighborId = edge.source === currentId ? edge.target : edge.source;

                // Add neighbor file
                const neighborNode = nodes.find(n => n.id === neighborId);
                if (neighborNode) {
                    if (neighborNode.data.file_path) {
                        connectedFiles.add(neighborNode.data.file_path);
                    }
                    if (!visited.has(neighborId)) {
                        queue.push(neighborId);
                    }
                }
            });
        }
        return Array.from(connectedFiles);
    };

    const analyzeCodeWithAI = async () => {
        if (!currentCode || !selectedNode) return;
        setAiAnalysis({ loading: true, result: null });

        // Gather connected files (Context-aware)
        const relatedPaths = getConnectedFiles(selectedNode.id);

        try {
            const res = await fetch('http://localhost:8000/api/analyze/ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: currentCode,
                    context: `File: ${selectedNode.data.file_path}, Function: ${selectedNode.data.label}`,
                    project_path: projectPath,
                    related_paths: relatedPaths
                })
            });
            const data = await res.json();
            if (data.success) {
                setAiAnalysis({ loading: false, result: data.analysis, model: data.model });
            } else {
                setAiAnalysis({ loading: false, result: `Analysis Failed: ${data.error}` });
            }
        } catch (e) {
            setAiAnalysis({ loading: false, result: "Network error occurred." });
        }
    };

    const scanSecurity = async () => {
        if (!projectPath) return;
        setScanning(true);
        try {
            const res = await fetch('http://localhost:8000/api/analyze/semgrep', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: projectPath })
            });
            const data = await res.json();
            console.log("Semgrep Results:", data);

            if (data.findings && data.findings.length > 0) {
                setSecurityFindings(data.findings);
                // Update nodes to show badges
                setNodes((nds) => nds.map((node) => {
                    const nodeFindings = data.findings.filter((f: any) =>
                        node.data.file_path && node.data.file_path.includes(f.path)
                    );

                    if (nodeFindings.length > 0) {
                        return {
                            ...node,
                            data: {
                                ...node.data,
                                vulnerabilityCount: nodeFindings.length,
                                findings: nodeFindings,
                                label: `${node.data.label} 🔴`
                            },
                            style: { ...node.style, border: '2px solid red', boxShadow: '0 0 15px red' }
                        };
                    }
                    return node;
                }));
                alert(`🚨 ${data.findings.length}개 취약점 발견! 그래프에서 빨간 노드를 확인하세요.`);
            } else {
                alert("✅ Semgrep 스캔 완료: 알려진 취약점 패턴이 탐지되지 않았습니다.");
            }
        } catch (e) {
            console.error(e);
            alert("보안 스캔 실패. 콘솔을 확인하세요.");
        } finally {
            setScanning(false);
        }
    };


    const analyzeProject = async () => {
        if (!projectPath) return;
        setLoading(true);
        try {
            const res = await fetch('http://localhost:8000/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: projectPath, cluster: true })
            });
            const data = await res.json();

            if (data.endpoints) {
                setAnalysisData(data);

                // Extract unique files
                const files = new Set<string>();
                data.endpoints.forEach((ep: any) => {
                    if (ep.file_path) files.add(ep.file_path);
                });

                const fileList = Array.from(files).sort();
                setAllFiles(fileList);

                // Default: Select first 5 files or 'app.py'/'main.py'
                const defaults = new Set<string>();
                fileList.forEach(f => {
                    const lower = f.toLowerCase();
                    if (lower.endsWith("app.py") || lower.endsWith("main.py") || lower.endsWith("index.js")) {
                        defaults.add(f);
                    }
                });

                // If no key files found, select first 3
                if (defaults.size === 0) {
                    fileList.slice(0, 3).forEach(f => defaults.add(f));
                }

                setSelectedFiles(defaults);
                // processNodes called via useEffect
            }
        } catch (e) {
            console.error(e);
            alert("분석 실패. 백엔드 서버가 실행 중인지 확인하세요.");
        } finally {
            setLoading(false);
        }
    };

    const processNodes = (endpoints: any[]) => {
        const g = new dagre.graphlib.Graph();
        g.setGraph({ rankdir: 'TB', nodesep: 100, ranksep: 80 });
        g.setDefaultEdgeLabel(() => ({}));

        const newNodes: Node[] = [];
        const newEdges: Edge[] = [];

        // Sets to track added IDs and avoid duplicates
        const addedNodeIds = new Set<string>();
        const addedEdgeIds = new Set<string>();

        const addNodeSafe = (node: Node, width: number, height: number) => {
            if (!addedNodeIds.has(node.id)) {
                addedNodeIds.add(node.id);
                g.setNode(node.id, { label: node.data.label, width, height });
                newNodes.push(node);
            }
        };

        const addEdgeSafe = (edge: Edge) => {
            if (!addedEdgeIds.has(edge.id)) {
                addedEdgeIds.add(edge.id);
                g.setEdge(edge.source, edge.target);
                newEdges.push(edge);
            }
        };

        // 1. Root Project Node
        const rootId = 'PROJECT_ROOT';
        addNodeSafe({
            id: rootId,
            position: { x: 0, y: 0 },
            data: {
                label: 'Root URL',
                initialStyle: {
                    background: '#1a0000',
                    color: '#ff0000',
                    border: '2px dashed #ff0000',
                    fontWeight: 'bold',
                    borderRadius: '8px',
                    width: 180,
                    padding: '10px',
                    textAlign: 'center',
                    boxShadow: '0 0 20px #ff000040'
                }
            },
            style: {
                background: '#1a0000',
                color: '#ff0000',
                border: '2px dashed #ff0000', // Red Dashed as requested
                fontWeight: 'bold',
                borderRadius: '8px',
                width: 180,
                padding: '10px',
                textAlign: 'center',
                boxShadow: '0 0 20px #ff000040'
            }
        }, 180, 60);

        // Recursive Node Processor
        const processNode = (node: any, parentId: string, level: number) => {
            // FILTER: If it's a file node, check selection.
            // If it's a cluster, we might want to show it if ANY child is selected?
            // For now, lenient filtering. To avoid empty graph, maybe show all clusters?
            // Or filter clusters that contain NO selected files?

            // Visual config based on type
            let style = {};
            let label = node.path;
            let nodeType = 'default';
            let width = 200;
            let height = 60;

            if (node.type === 'cluster') {
                label = `📁 ${node.path}`;
                style = {
                    background: '#1e293b',
                    color: '#fcd34d', // Amber-300
                    border: '2px dashed #fcd34d',
                    borderRadius: '8px',
                    padding: '10px',
                    fontWeight: 'bold',
                    textAlign: 'center'
                };
            } else if (label && label.toString().startsWith('Template:')) {
                style = {
                    background: '#0f172a',
                    border: '2px solid #38bdf8',
                    color: '#e0f2fe',
                    borderRadius: '8px',
                    padding: '10px',
                    fontWeight: 'bold',
                    textAlign: 'center',
                    boxShadow: '0 0 15px #38bdf840'
                };
            } else if (node.type === 'root') {
                // Root File Node
                style = {
                    background: '#0a0a0a',
                    color: '#00f0ff',
                    borderRadius: '12px',
                    border: '2px solid #00f0ff',
                    padding: '10px',
                    fontWeight: 'bold',
                    textAlign: 'center',
                    boxShadow: '0 0 15px #00f0ff20'
                };
            } else if (node.method === 'FUNC' || node.type === 'function') {
                // Function
                width = 160;
                height = 40;
                style = {
                    background: '#1a1a1a',
                    border: '1px solid #7c3aed',
                    color: '#ddd6fe',
                    borderRadius: '6px',
                    padding: '8px',
                    fontSize: '12px',
                    fontWeight: '500',
                    boxShadow: '0 0 10px #7c3aed20'
                };
            } else if (node.type === 'call' || node.type === 'child') {
                // Generic Call or Child that didn't match FUNC
                label = label.startsWith('Call:') ? label : `Call: ${node.path}`;
                width = 150; height = 40;
                style = {
                    background: '#1a001a',
                    border: '1px dashed #bd00ff',
                    color: '#bd00ff',
                    borderRadius: '4px',
                    padding: '5px 10px',
                    fontSize: '12px'
                };
            } else if (node.type === 'database') {
                // ... existing database style
                label = `🗄️ ${node.path.replace("Table: ", "")}`;
                width = 180;
                style = {
                    background: '#1c1c1c',
                    border: '2px solid #ea580c',
                    color: '#fb923c',
                    borderRadius: '12px',
                    padding: '10px',
                    textAlign: 'center'
                };
            } else if (node.type === 'input') {
                return;
            } else {
                // DEFAULT FALLBACK: Any unmatched node gets dark style
                style = {
                    background: '#1a1a1a',
                    border: '1px solid #6b7280',
                    color: '#e5e7eb',
                    borderRadius: '6px',
                    padding: '8px',
                    fontSize: '12px',
                    fontWeight: '500'
                };
            }

            // Add Node
            if (!addedNodeIds.has(node.id)) {
                addNodeSafe({
                    id: node.id,
                    position: { x: 0, y: 0 }, // Position calculated later
                    data: {
                        label: label,
                        ...node,
                        params: node.params || [],
                        initialStyle: style // Persist initial style for restoration
                    },
                    style: { ...style, width, height },
                    type: nodeType
                }, width, height);
            }

            // Add Edge from Parent
            if (parentId) {
                addEdgeSafe({
                    id: `e-${parentId}-${node.id}`,
                    source: parentId,
                    target: node.id,
                    type: 'smoothstep',
                    animated: true,
                    style: { stroke: '#475569', strokeWidth: 1.5 }
                });
            }

            // Recurse children
            // Recurse children
            const isCluster = node.type === 'cluster';
            const shouldRecurse = !isCluster || expandedClusters.has(node.id);

            if (shouldRecurse && node.children && node.children.length > 0) {
                node.children.forEach((child: any) => {
                    processNode(child, node.id, level + 1);
                });
            }
        };

        // 2. Process Routes (Endpoints) recursively
        endpoints.forEach((ep: any) => {
            // Top level filter
            if (ep.type !== 'cluster' && !selectedFiles.has(ep.file_path)) return;

            // Connect to Root
            processNode(ep, rootId, 1);
        });

        dagre.layout(g);

        // Apply calculated positions
        newNodes.forEach((node) => {
            const nodeWithPos = g.node(node.id);
            if (nodeWithPos) {
                node.position = {
                    x: nodeWithPos.x - nodeWithPos.width / 2,
                    y: nodeWithPos.y - nodeWithPos.height / 2,
                };
            }
        });

        setNodes(newNodes);
        setEdges(newEdges);
    };
    return (
        <div className="flex h-screen w-full bg-[#050505] text-white">
            {/* Header/Control Bar */}
            <div className="absolute top-4 left-4 z-50 flex gap-4 bg-black/50 backdrop-blur p-4 rounded-xl border border-white/10">
                <div className="flex items-center gap-2 px-3 py-2 bg-white/5 rounded-lg border border-white/10 w-[500px]">
                    <Search className="text-zinc-500" size={18} />
                    <input
                        type="text"
                        value={projectPath}
                        onChange={(e) => setProjectPath(e.target.value)}
                        className="bg-transparent border-none outline-none text-white w-full text-sm font-mono"
                        placeholder="분석할 프로젝트의 절대 경로를 입력하세요..."
                    />
                </div>
                <button
                    onClick={analyzeProject}
                    disabled={loading}
                    className="px-6 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-lg font-bold hover:shadow-[0_0_20px_rgba(6,182,212,0.5)] transition-all disabled:opacity-50"
                >
                    {loading ? '분석 중...' : '▶ 시각화'}
                </button>
                <button
                    onClick={scanSecurity}
                    disabled={scanning}
                    className="px-6 py-2 bg-gradient-to-r from-red-500 to-orange-500 rounded-lg font-bold hover:shadow-[0_0_20px_rgba(239,68,68,0.5)] transition-all disabled:opacity-50 flex items-center gap-2"
                >
                    {scanning ? '스캔 중...' : '🛡️ 보안 스캔 (Semgrep)'}
                </button>
                <button
                    onClick={() => setShowFileTree(!showFileTree)}
                    className={`px-4 py-2 rounded-lg border transition-all font-bold flex items-center gap-2 ${showFileTree ? 'bg-blue-500/20 text-blue-400 border-blue-500/50' : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'}`}
                >
                    📂 파일 목록
                </button>
            </div>

            {/* File Tree Sidebar */}
            {allFiles.length > 0 && showFileTree && (
                <div className="absolute top-24 left-4 z-40 w-64 max-h-[calc(100vh-150px)] bg-black/80 backdrop-blur rounded-xl border border-white/10 flex flex-col overflow-hidden shadow-xl">
                    <div className="p-3 border-b border-white/10 bg-white/5 flex justify-between items-center">
                        <span className="font-bold text-sm text-zinc-300">File Browser ({allFiles.length})</span>
                        <div className="flex gap-2 text-xs">
                            <button onClick={() => setSelectedFiles(new Set(allFiles))} className="hover:text-white text-zinc-500 hover:bg-white/10 px-1 rounded">All</button>
                            <button onClick={() => setSelectedFiles(new Set())} className="hover:text-white text-zinc-500 hover:bg-white/10 px-1 rounded">None</button>
                        </div>
                    </div>
                    <div className="overflow-y-auto p-2 space-y-1">
                        {allFiles.map(file => {
                            const isSelected = selectedFiles.has(file);
                            const fileName = file.split(/[/\\]/).pop(); // Simple basename
                            return (
                                <div key={file}
                                    className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-xs transition-colors ${isSelected ? 'bg-blue-500/20 text-blue-300' : 'hover:bg-white/5 text-zinc-500'}`}
                                    onClick={() => {
                                        const next = new Set(selectedFiles);
                                        if (next.has(file)) next.delete(file);
                                        else next.add(file);
                                        setSelectedFiles(next);
                                    }}
                                >
                                    <div className={`w-3 h-3 flex-shrink-0 rounded-full border ${isSelected ? 'bg-blue-500 border-blue-400' : 'border-zinc-600'}`} />
                                    <span className="truncate" title={file}>{fileName}</span>
                                </div >
                            );
                        })}
                    </div >
                </div >
            )}

            <div className="flex-1 h-full relative">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    onNodeClick={onNodeClick}
                    onPaneClick={onPaneClick}
                    fitView
                    className="bg-black/50"
                >
                    <Background color="#333" gap={20} />
                    <Controls className="bg-zinc-800 border-zinc-700 fill-white" />
                    <MiniMap className="bg-zinc-900 border-zinc-700" nodeColor="#00f0ff" />
                </ReactFlow>
            </div>

            {/* Global Controls */}
            <div className="absolute top-4 right-4 flex gap-2 z-50">
                <button
                    onClick={scanSecurity}
                    disabled={scanning}
                    className="flex items-center gap-2 px-6 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg border border-red-500/30 transition-all font-bold disabled:opacity-50"
                >
                    {scanning ? (
                        <div className="w-5 h-5 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
                    ) : (
                        <Bot size={18} />
                    )}
                    {scanning ? "보안 스캔 중..." : "AI 보안 분석"}
                </button>

                <button
                    onClick={() => setShowFileTree(!showFileTree)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all ${showFileTree ? 'bg-blue-500/20 text-blue-400 border-blue-500/50' : 'bg-white/5 text-zinc-400 border-white/10'}`}
                >
                    📂 파일 목록
                </button>
            </div>

            {/* File Tree Sidebar */}
            {
                allFiles.length > 0 && showFileTree && (
                    <div className="absolute top-24 left-4 z-40 w-64 max-h-[calc(100vh-150px)] bg-black/80 backdrop-blur rounded-xl border border-white/10 flex flex-col overflow-hidden">
                        <div className="p-3 border-b border-white/10 bg-white/5 flex justify-between items-center">
                            <span className="font-bold text-sm text-zinc-300">File Browser ({allFiles.length})</span>
                            <div className="flex gap-2 text-xs">
                                <button onClick={() => setSelectedFiles(new Set(allFiles))} className="hover:text-white text-zinc-500">All</button>
                                <button onClick={() => setSelectedFiles(new Set())} className="hover:text-white text-zinc-500">None</button>
                            </div>
                        </div>
                        <div className="overflow-y-auto p-2 space-y-1">
                            {allFiles.map(file => {
                                const isSelected = selectedFiles.has(file);
                                const fileName = file.split(/[/\\]/).pop(); // Simple basename
                                return (
                                    <div key={file}
                                        className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-xs ${isSelected ? 'bg-blue-500/20 text-blue-300' : 'hover:bg-white/5 text-zinc-500'}`}
                                        onClick={() => {
                                            const next = new Set(selectedFiles);
                                            if (next.has(file)) next.delete(file);
                                            else next.add(file);
                                            setSelectedFiles(next);
                                        }}
                                    >
                                        <div className={`w-3 h-3 rounded-full border ${isSelected ? 'bg-blue-500 border-blue-400' : 'border-zinc-600'}`} />
                                        <span className="truncate" title={file}>{fileName}</span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )
            }

            <AnimatePresence>
                {selectedNode && (
                    <motion.div
                        initial={{ x: 300, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: 300, opacity: 0 }}
                        style={{ width: panelWidth }}
                        className="absolute right-0 top-0 bottom-0 bg-black/80 backdrop-blur-md border-l border-white/10 p-6 shadow-2xl z-50 overflow-y-auto"
                    >
                        {/* Resizing Handle */}
                        <div
                            onMouseDown={startResizing}
                            className={`absolute left-0 top-0 bottom-0 w-2 cursor-col-resize hover:bg-cyan-500/50 transition-colors z-[60] ${isResizing ? 'bg-cyan-500' : 'bg-transparent'}`}
                        />

                        <div className="flex justify-between items-center mb-6">
                            <h2 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-purple-500">
                                상세 정보 (Details)
                            </h2>
                            <button onClick={() => setSelectedNode(null)} className="p-1 hover:bg-white/10 rounded-full">
                                <X size={20} />
                            </button>
                        </div>

                        {/* AI Analysis Button */}
                        {currentCode && (
                            <div className="mb-6">
                                <button
                                    onClick={analyzeCodeWithAI}
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
                                                    code({ node, inline, className, children, ...props }: any) {
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
                            <div className="p-4 rounded-lg bg-white/5 border border-white/10">
                                <label className="text-xs text-zinc-500 uppercase tracking-wider block mb-1">라벨 (Label)</label>
                                <p className="font-mono text-sm text-cyan-300 break-words">{selectedNode.data.label}</p>
                            </div>

                            {selectedNode.data.params && (
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
                                                {selectedNode.data.params.length > 0 ? (
                                                    selectedNode.data.params.map((p: any, i: number) => (
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

                            {selectedNode.data.filters && (
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
                                                {selectedNode.data.filters.length > 0 ? (
                                                    selectedNode.data.filters.map((f: any, i: number) => (
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
                            )}

                            {selectedNode.data.filters && (
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
                                                {selectedNode.data.filters.length > 0 ? (
                                                    selectedNode.data.filters.map((f: any, i: number) => {
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
                            )}

                            {isTemplateNode && (
                                <div className="space-y-4">
                                    {selectedNode.data.template_context && (
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
                                                        {selectedNode.data.template_context.length > 0 ? (
                                                            selectedNode.data.template_context.map((v: any, i: number) => (
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

                                    {selectedNode.data.template_usage && (
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
                                                        {selectedNode.data.template_usage.length > 0 ? (
                                                            selectedNode.data.template_usage.map((u: any, i: number) => {
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

                            {/* Security Findings Section */}
                            {selectedNode.data.findings && selectedNode.data.findings.length > 0 && (
                                <div className="mb-6 border border-red-500/30 bg-red-900/10 rounded-lg p-4">
                                    <h3 className="text-red-400 font-bold flex items-center gap-2 mb-3">
                                        🚨 보안 취약점 발견 ({selectedNode.data.findings.length})
                                    </h3>
                                    <div className="space-y-3">
                                        {selectedNode.data.findings.map((finding: any, idx: number) => (
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

                            {/* Code Snippet Viewer */}
                            <div>
                                <label className="text-xs text-zinc-500 uppercase tracking-wider block mb-2">
                                    소스 코드 (Source Code)
                                </label>
                                <div className="rounded-lg overflow-hidden border border-white/10 text-sm">
                                    {currentCode ? (
                                        <SyntaxHighlighter
                                            language="python"
                                            style={vscDarkPlus}
                                            showLineNumbers={true}
                                            startingLineNumber={selectedNode.data.line_number || 1}
                                            customStyle={{ margin: 0, padding: '1.5rem', background: '#0a0a0a' }}
                                        >
                                            {currentCode}
                                        </SyntaxHighlighter>
                                    ) : (
                                        <div className="p-8 text-center text-zinc-600 bg-[#0a0a0a]">
                                            {selectedNode.data.file_path ? "로드 중..." : "소스 코드를 찾을 수 없습니다."}
                                        </div>
                                    )}
                                </div>
                                {selectedNode.data.file_path && (
                                    <p className="text-xs text-zinc-600 mt-2 font-mono text-right">
                                        {selectedNode.data.file_path}:{selectedNode.data.line_number}
                                    </p>
                                )}
                            </div>
                        </div>
                    </motion.div >
                )}
            </AnimatePresence >
        </div >
    );
};

export default Visualizer;
