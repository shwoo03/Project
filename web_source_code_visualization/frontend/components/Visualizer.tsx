"use client";

import React, { useCallback, useState, useEffect } from 'react';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
    addEdge,
    Connection,
    Node,
    Edge
} from 'reactflow';
import 'reactflow/dist/style.css';
import { AnimatePresence } from 'framer-motion';
import dagre from 'dagre';

// Types
import { AnalysisData, GraphNode, AIAnalysisState, Endpoint, SecurityFinding } from '@/types/graph';
import { AppError, createError, getErrorMessage, getErrorType } from '@/types/errors';

// Hooks
import { useResizePanel } from '@/hooks/useResizePanel';
import { useBacktrace } from '@/hooks/useBacktrace';

// Utils
import { getNodeStyle, ROOT_STYLE } from '@/utils/nodeStyles';

// Components
import { ControlBar } from '@/components/controls/ControlBar';
import { FileTreeSidebar } from '@/components/panels/FileTreeSidebar';
import { DetailPanel } from '@/components/panels/DetailPanel';
import { ErrorToast } from '@/components/feedback/ErrorToast';

const API_BASE = 'http://localhost:8000';

const Visualizer = () => {
    // Graph State
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    // UI State
    const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
    const [currentCode, setCurrentCode] = useState<string>("");
    const [aiAnalysis, setAiAnalysis] = useState<AIAnalysisState>({ loading: false, result: null });
    const [projectPath, setProjectPath] = useState<string>("C:/Users/dntmd/OneDrive/Desktop/my/프로젝트/Project/web_source_code_visualization/xss-1/deploy");
    const [loading, setLoading] = useState(false);
    const [securityFindings, setSecurityFindings] = useState<SecurityFinding[]>([]);
    const [scanning, setScanning] = useState(false);
    const [error, setError] = useState<AppError | null>(null);

    // Filter State
    const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
    const [allFiles, setAllFiles] = useState<string[]>([]);
    const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
    const [showFileTree, setShowFileTree] = useState(true);
    const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());

    // Custom Hooks
    const { panelWidth, isResizing, startResizing } = useResizePanel({ initialWidth: 800 });
    const { highlightBacktrace, resetHighlight } = useBacktrace();

    // Process nodes when filters change
    useEffect(() => {
        if (analysisData && analysisData.endpoints) {
            const topClusters = new Set<string>();
            analysisData.endpoints.forEach((ep: Endpoint) => {
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

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    );

    const loadSnippet = async (filePath?: string, startLine?: number, endLine?: number) => {
        if (!filePath || !startLine) return;
        try {
            const res = await fetch(`${API_BASE}/api/snippet`, {
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

        setSelectedNode(node as GraphNode);
        setCurrentCode("");

        // Apply backtrace highlight
        highlightBacktrace(nodes, edges, node.id, setNodes, setEdges);

        await loadSnippet(node.data.file_path, node.data.line_number, node.data.end_line_number);
    };

    const onPaneClick = () => {
        setSelectedNode(null);
        setAiAnalysis({ loading: false, result: null });
        resetHighlight(setNodes, setEdges);
    };

    const getConnectedFiles = (startNodeId: string): string[] => {
        const connectedFiles = new Set<string>();
        const queue = [startNodeId];
        const visited = new Set<string>();

        const startNode = nodes.find(n => n.id === startNodeId);
        if (startNode?.data.file_path) {
            connectedFiles.add(startNode.data.file_path);
        }

        while (queue.length > 0) {
            const currentId = queue.shift()!;
            if (visited.has(currentId)) continue;
            visited.add(currentId);

            const relatedEdges = edges.filter(e => e.source === currentId || e.target === currentId);
            relatedEdges.forEach(edge => {
                const neighborId = edge.source === currentId ? edge.target : edge.source;
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

        const relatedPaths = getConnectedFiles(selectedNode.id);

        try {
            const res = await fetch(`${API_BASE}/api/analyze/ai`, {
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
            const res = await fetch(`${API_BASE}/api/analyze/semgrep`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: projectPath })
            });
            const data = await res.json();

            if (data.findings && data.findings.length > 0) {
                setSecurityFindings(data.findings);
                setNodes((nds) => nds.map((node) => {
                    const nodeFindings = data.findings.filter((f: SecurityFinding) =>
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
            setError(createError(getErrorType(e), '보안 스캔 실패', getErrorMessage(e)));
        } finally {
            setScanning(false);
        }
    };

    const analyzeProject = async () => {
        if (!projectPath) return;
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/api/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: projectPath, cluster: true })
            });
            const data = await res.json();

            if (data.endpoints) {
                setAnalysisData(data);

                const files = new Set<string>();
                data.endpoints.forEach((ep: Endpoint) => {
                    if (ep.file_path) files.add(ep.file_path);
                });

                const fileList = Array.from(files).sort();
                setAllFiles(fileList);

                const defaults = new Set<string>();
                fileList.forEach(f => {
                    const lower = f.toLowerCase();
                    if (lower.endsWith("app.py") || lower.endsWith("main.py") || lower.endsWith("index.js")) {
                        defaults.add(f);
                    }
                });

                if (defaults.size === 0) {
                    fileList.slice(0, 3).forEach(f => defaults.add(f));
                }

                setSelectedFiles(defaults);
            }
        } catch (e) {
            console.error(e);
            setError(createError(getErrorType(e), '프로젝트 분석 실패', getErrorMessage(e)));
        } finally {
            setLoading(false);
        }
    };

    const processNodes = (endpoints: Endpoint[]) => {
        const g = new dagre.graphlib.Graph();
        g.setGraph({ rankdir: 'TB', nodesep: 100, ranksep: 80 });
        g.setDefaultEdgeLabel(() => ({}));

        const newNodes: Node[] = [];
        const newEdges: Edge[] = [];
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

        // Root Node
        const rootId = 'PROJECT_ROOT';
        addNodeSafe({
            id: rootId,
            position: { x: 0, y: 0 },
            data: {
                label: 'Root URL',
                initialStyle: ROOT_STYLE
            },
            style: { ...ROOT_STYLE, width: 180 }
        }, 180, 60);

        // Recursive Node Processor
        const processNode = (node: Endpoint, parentId: string, level: number) => {
            let style: React.CSSProperties = {};
            let label = node.path;
            let nodeType = 'default';
            let width = 200;
            let height = 60;

            if (node.type === 'cluster') {
                label = `📁 ${node.path}`;
                const { style: s, width: w, height: h } = getNodeStyle('cluster');
                style = s; width = w; height = h;
            } else if (label && label.toString().startsWith('Template:')) {
                const { style: s, width: w, height: h } = getNodeStyle('template');
                style = s; width = w; height = h;
            } else if (node.type === 'root') {
                const { style: s, width: w, height: h } = getNodeStyle('root');
                style = s; width = w; height = h;
            } else if (node.method === 'FUNC' || node.type === 'function') {
                const { style: s, width: w, height: h } = getNodeStyle('function');
                style = s; width = w; height = h;
            } else if (node.type === 'call' || node.type === 'child') {
                label = label?.startsWith('Call:') ? label : `Call: ${node.path}`;
                const { style: s, width: w, height: h } = getNodeStyle('call');
                style = s; width = w; height = h;
            } else if (node.type === 'database') {
                label = `🗄️ ${node.path.replace("Table: ", "")}`;
                const { style: s, width: w, height: h } = getNodeStyle('database');
                style = s; width = w; height = h;
            } else if (node.type === 'input') {
                return;
            } else {
                const { style: s, width: w, height: h } = getNodeStyle('default');
                style = s; width = w; height = h;
            }

            // Extract inputs from children (type='input' nodes)
            const extractedInputs = (node.children || [])
                .filter((child: Endpoint) => child.type === 'input')
                .map((inp: Endpoint) => ({
                    name: inp.path,
                    source: inp.method || 'unknown'
                }));

            if (!addedNodeIds.has(node.id)) {
                addNodeSafe({
                    id: node.id,
                    position: { x: 0, y: 0 },
                    data: {
                        label: label,
                        ...node,
                        params: node.params || [],
                        inputs: extractedInputs,
                        initialStyle: style
                    },
                    style: { ...style, width, height },
                    type: nodeType
                }, width, height);
            }

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

            const isCluster = node.type === 'cluster';
            const shouldRecurse = !isCluster || expandedClusters.has(node.id);

            if (shouldRecurse && node.children && node.children.length > 0) {
                node.children.forEach((child: Endpoint) => {
                    processNode(child, node.id, level + 1);
                });
            }
        };

        endpoints.forEach((ep: Endpoint) => {
            if (ep.type !== 'cluster' && !selectedFiles.has(ep.file_path || '')) return;
            processNode(ep, rootId, 1);
        });

        dagre.layout(g);

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

    // File toggle handler
    const handleToggleFile = (file: string) => {
        const next = new Set(selectedFiles);
        if (next.has(file)) next.delete(file);
        else next.add(file);
        setSelectedFiles(next);
    };

    return (
        <div className="flex h-screen w-full bg-[#050505] text-white">
            {/* Control Bar */}
            <ControlBar
                projectPath={projectPath}
                onProjectPathChange={setProjectPath}
                onAnalyze={analyzeProject}
                onScan={scanSecurity}
                onToggleFileTree={() => setShowFileTree(!showFileTree)}
                loading={loading}
                scanning={scanning}
                showFileTree={showFileTree}
            />

            {/* File Tree Sidebar */}
            {showFileTree && (
                <FileTreeSidebar
                    files={allFiles}
                    selectedFiles={selectedFiles}
                    onToggleFile={handleToggleFile}
                    onSelectAll={() => setSelectedFiles(new Set(allFiles))}
                    onSelectNone={() => setSelectedFiles(new Set())}
                />
            )}

            {/* Main Graph Area */}
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

            {/* Detail Panel */}
            <AnimatePresence>
                {selectedNode && (
                    <DetailPanel
                        node={selectedNode}
                        code={currentCode}
                        aiAnalysis={aiAnalysis}
                        onClose={() => setSelectedNode(null)}
                        onAnalyzeAI={analyzeCodeWithAI}
                        panelWidth={panelWidth}
                        isResizing={isResizing}
                        onStartResize={startResizing}
                    />
                )}
            </AnimatePresence>

            {/* Error Toast */}
            <ErrorToast error={error} onDismiss={() => setError(null)} />
        </div>
    );
};

export default Visualizer;
