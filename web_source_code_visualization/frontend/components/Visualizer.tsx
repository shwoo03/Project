"use client";

import React, { useCallback, useState, useEffect, useMemo } from 'react';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
    addEdge,
    Connection,
    Node,
    Edge,
    ReactFlowProvider
} from 'reactflow';
import 'reactflow/dist/style.css';
import { AnimatePresence } from 'framer-motion';
import dagre from 'dagre';

// Types
import { AnalysisData, GraphNode, AIAnalysisState, Endpoint, SecurityFinding, TaintFlowEdge, CallGraphData, CallGraphNode, CallGraphEdge } from '@/types/graph';
import { AppError, createError, getErrorMessage, getErrorType } from '@/types/errors';

// Hooks
import { useResizePanel } from '@/hooks/useResizePanel';
import { useBacktrace } from '@/hooks/useBacktrace';
import { useProgressiveLoading } from '@/hooks/useViewportOptimization';
import { useStreamingAnalysis } from '@/hooks/useStreamingAnalysis';

// Utils
import { getNodeStyle, ROOT_STYLE } from '@/utils/nodeStyles';

// Components
import { ControlBar } from '@/components/controls/ControlBar';
import { VirtualizedFileTree } from '@/components/panels/VirtualizedFileTree';
import { DetailPanel } from '@/components/panels/DetailPanel';
import { ErrorToast } from '@/components/feedback/ErrorToast';
import { PerformanceMonitor } from '@/components/feedback/PerformanceMonitor';
import { StreamingProgress } from '@/components/feedback/StreamingProgress';

const API_BASE = 'http://localhost:8000';

// Threshold for enabling virtualization
const VIRTUALIZATION_THRESHOLD = 100;

const VisualizerContent = () => {
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
    const [showSinks, setShowSinks] = useState(false); // Default: OFF
    const [showTaintFlows, setShowTaintFlows] = useState(true); // Taint flow visualization
    const [showCallGraph, setShowCallGraph] = useState(false); // Call graph mode
    const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
    
    // Streaming mode (for large projects)
    const [useStreaming, setUseStreaming] = useState(false);

    // Custom Hooks
    const { panelWidth, isResizing, startResizing } = useResizePanel({ initialWidth: 800 });
    const { highlightBacktrace, resetHighlight } = useBacktrace();
    
    // Streaming analysis hook
    const {
        startStream,
        cancelStream,
        state: streamState,
        isStreaming
    } = useStreamingAnalysis({
        onComplete: (data) => {
            console.log(`[Streaming] Complete: ${data.elapsed_ms}ms, ${data.summary.endpoints} endpoints`);
        },
        onError: (err) => {
            setError(createError('stream', 'Streaming analysis failed', err));
        }
    });

    // Performance Stats for virtualization
    const performanceStats = useMemo(() => ({
        totalNodes: nodes.length,
        visibleNodes: nodes.length, // Will be updated by viewport optimization
        totalEdges: edges.length,
        visibleEdges: edges.length,
        renderRatio: 100
    }), [nodes.length, edges.length]);

    // Check if virtualization should be enabled
    const isVirtualized = useMemo(() => 
        allFiles.length >= VIRTUALIZATION_THRESHOLD || nodes.length >= VIRTUALIZATION_THRESHOLD,
        [allFiles.length, nodes.length]
    );

    // Progressive loading for large node sets
    const { loadedItems: progressiveNodes, isLoading: nodesLoading, progress: loadProgress } = 
        useProgressiveLoading(nodes, 200, 30);

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
    }, [selectedFiles, analysisData, expandedClusters, showSinks, showTaintFlows]);

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
        
        // Use streaming for potentially large projects
        if (useStreaming) {
            startStream(projectPath, true, true);
            return;
        }
        
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
    
    // Process streaming results into graph data
    useEffect(() => {
        if (streamState.endpoints.length > 0 && !isStreaming) {
            // Convert streaming endpoints to AnalysisData format
            const endpoints = streamState.endpoints as unknown as Endpoint[];
            const taintFlows = streamState.taintFlows as unknown as TaintFlowEdge[];
            
            const data: AnalysisData = {
                root_path: projectPath,
                language_stats: streamState.stats?.language_stats || {},
                endpoints,
                taint_flows: taintFlows
            };
            
            setAnalysisData(data);
            
            // Extract files
            const files = new Set<string>();
            endpoints.forEach((ep: Endpoint) => {
                if (ep.file_path) files.add(ep.file_path);
            });
            
            const fileList = Array.from(files).sort();
            setAllFiles(fileList);
            
            // Select default files
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
    }, [streamState.endpoints, streamState.taintFlows, streamState.stats, isStreaming, projectPath]);

    // Call Graph data loading and visualization
    const [callGraphData, setCallGraphData] = useState<CallGraphData | null>(null);

    const loadCallGraph = async () => {
        if (!projectPath) return;
        
        try {
            const res = await fetch(`${API_BASE}/api/callgraph`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: projectPath })
            });
            const data = await res.json();
            setCallGraphData(data);
            processCallGraphNodes(data);
        } catch (e) {
            console.error("Failed to load call graph", e);
            setError(createError(getErrorType(e), 'Call Graph 로딩 실패', getErrorMessage(e)));
        }
    };

    // Effect: Load call graph when toggled ON
    useEffect(() => {
        if (showCallGraph && projectPath) {
            loadCallGraph();
        } else if (!showCallGraph && analysisData) {
            // Revert to normal visualization
            processNodes(analysisData.endpoints);
        }
    }, [showCallGraph, projectPath]);

    const processCallGraphNodes = (data: CallGraphData) => {
        const g = new dagre.graphlib.Graph();
        // 가독성 개선: LR(좌→우) 방향, 넓은 간격
        g.setGraph({ 
            rankdir: 'LR',  // 좌→우 방향이 Call Graph에 더 적합
            nodesep: 60,    // 같은 레벨 노드 간격
            ranksep: 200,   // 레벨 간 간격 (넓게)
            marginx: 50,
            marginy: 50,
        });
        g.setDefaultEdgeLabel(() => ({}));

        const newNodes: Node[] = [];
        const newEdges: Edge[] = [];

        // Create nodes for each function
        data.nodes.forEach((cgNode: CallGraphNode) => {
            // Determine node style based on type - 가독성 개선
            let nodeStyle: React.CSSProperties = {
                padding: '16px 24px',
                borderRadius: 12,
                border: '2px solid rgba(120,120,120,0.6)',
                background: 'linear-gradient(135deg, #1a1a2e 0%, #252540 100%)',
                color: '#f0f0f0',
                fontSize: '14px',
                fontWeight: 600,
                minWidth: '180px',
                textAlign: 'center' as const,
                boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            };

            // Entry points (route handlers) - 진입점 강조
            if (cgNode.is_entry_point) {
                nodeStyle = {
                    ...nodeStyle,
                    border: '3px solid #22d3ee',
                    background: 'linear-gradient(135deg, #0e4a5a 0%, #1e6a7a 100%)',
                    color: '#22d3ee',
                    boxShadow: '0 0 25px rgba(34,211,238,0.5), inset 0 0 20px rgba(34,211,238,0.1)',
                    fontSize: '15px',
                };
            }

            // Sinks (dangerous functions) - 위험 함수 강조
            if (cgNode.is_sink) {
                nodeStyle = {
                    ...nodeStyle,
                    border: '3px solid #ef4444',
                    background: 'linear-gradient(135deg, #5a1e1e 0%, #7a2d2d 100%)',
                    color: '#ff6b6b',
                    boxShadow: '0 0 30px rgba(239,68,68,0.6), inset 0 0 20px rgba(239,68,68,0.1)',
                    fontSize: '15px',
                    fontWeight: 700,
                };
            }

            // Classes - 클래스 노드
            if (cgNode.node_type === 'class') {
                nodeStyle = {
                    ...nodeStyle,
                    border: '3px solid #a855f7',
                    background: 'linear-gradient(135deg, #4a2060 0%, #5a3070 100%)',
                    color: '#c084fc',
                    boxShadow: '0 0 20px rgba(168,85,247,0.4)',
                };
            }

            // Determine label - 가독성 개선
            let label = cgNode.name;
            let displayLabel = label;
            
            // 아이콘 추가로 시각적 구분
            if (cgNode.is_entry_point) {
                displayLabel = `🚀 ${label}`;
            } else if (cgNode.is_sink) {
                displayLabel = `⚠️ ${label}`;
            } else if (cgNode.node_type === 'class') {
                displayLabel = `📦 ${label}`;
            } else if (cgNode.node_type === 'method') {
                displayLabel = `⚙️ ${label}`;
            } else if (cgNode.node_type === 'function') {
                displayLabel = `ƒ ${label}`;
            }
            
            if (cgNode.node_type === 'method' && cgNode.qualified_name.includes('.')) {
                const parts = cgNode.qualified_name.split('.');
                if (parts.length >= 2) {
                    const shortName = `${parts[parts.length - 2]}.${parts[parts.length - 1]}`;
                    displayLabel = displayLabel.replace(label, shortName);
                }
            }

            // 노드 크기 계산 (레이블 길이에 따라)
            const nodeWidth = Math.max(200, displayLabel.length * 10 + 60);
            const nodeHeight = 60;

            const node: Node = {
                id: cgNode.id,
                position: { x: 0, y: 0 },
                data: {
                    label: displayLabel,
                    file_path: cgNode.file_path,
                    line_number: cgNode.line_number,
                    end_line_number: cgNode.end_line,
                    node_type: cgNode.node_type,
                    is_entry_point: cgNode.is_entry_point,
                    is_sink: cgNode.is_sink,
                    callers: cgNode.callers,
                    callees: cgNode.callees,
                    initialStyle: nodeStyle,
                },
                style: { ...nodeStyle, width: nodeWidth },
            };

            newNodes.push(node);
            g.setNode(cgNode.id, { label: displayLabel, width: nodeWidth, height: nodeHeight });
        });

        // Create edges for call relationships - 엣지 가독성 개선
        data.edges.forEach((cgEdge: CallGraphEdge) => {
            const targetNode = data.nodes.find(n => n.id === cgEdge.target_id);
            const sourceNode = data.nodes.find(n => n.id === cgEdge.source_id);
            
            let edgeStyle: React.CSSProperties = {
                stroke: '#6b7280',
                strokeWidth: 2,
            };

            // 시작점에서 나가는 엣지 강조
            if (sourceNode?.is_entry_point) {
                edgeStyle.stroke = '#22d3ee';
                edgeStyle.strokeWidth = 2.5;
            }

            // Sink로 들어가는 엣지는 빨간색으로 강조
            if (targetNode?.is_sink) {
                edgeStyle.stroke = '#ef4444';
                edgeStyle.strokeWidth = 3;
            }

            const edge: Edge = {
                id: cgEdge.id,
                source: cgEdge.source_id,
                target: cgEdge.target_id,
                type: 'smoothstep',
                animated: targetNode?.is_sink || sourceNode?.is_entry_point,
                style: edgeStyle,
                label: cgEdge.call_type !== 'direct' ? cgEdge.call_type : undefined,
                labelStyle: { fill: '#d1d5db', fontSize: 11, fontWeight: 500 },
                labelBgStyle: { fill: '#1a1a2e', fillOpacity: 0.9 },
                markerEnd: {
                    type: 'arrowclosed' as any,
                    color: edgeStyle.stroke as string,
                    width: 20,
                    height: 20,
                },
            };

            newEdges.push(edge);
            g.setEdge(cgEdge.source_id, cgEdge.target_id);
        });

        // Apply dagre layout
        dagre.layout(g);

        // Update positions - 중앙 정렬 개선
        newNodes.forEach(node => {
            const nodeWithPosition = g.node(node.id);
            if (nodeWithPosition) {
                node.position = {
                    x: nodeWithPosition.x - (nodeWithPosition.width || 200) / 2,
                    y: nodeWithPosition.y - (nodeWithPosition.height || 60) / 2,
                };
            }
        });

        setNodes(newNodes);
        setEdges(newEdges);
    };

    const processNodes = (endpoints: Endpoint[]) => {
        const g = new dagre.graphlib.Graph();
        // 일반 시각화도 가독성 개선
        g.setGraph({ 
            rankdir: 'TB', 
            nodesep: 120,   // 같은 레벨 노드 간격 증가
            ranksep: 100,   // 레벨 간 간격 증가
            marginx: 40,
            marginy: 40,
        });
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
            // Skip sink nodes if showSinks is false
            const isSinkNode = node.type === 'sink' || 
                               node.type === 'api_call' || 
                               node.type === 'event_handler' ||
                               (node.path && node.path.startsWith('⚠️'));
            
            if (isSinkNode && !showSinks) {
                return; // Skip this node
            }

            let style: React.CSSProperties = {};
            let label = node.path;
            let nodeType = 'default';
            let width = 200;
            let height = 60;

            if (node.type === 'cluster') {
                label = `📁 ${node.path}`;
                const { style: s, width: w, height: h } = getNodeStyle('cluster');
                style = s; width = w; height = h;
            } else if (node.type === 'sink') {
                // Sink node styling - warning appearance
                label = node.path.startsWith('⚠️') ? node.path : `⚠️ ${node.path}`;
                style = {
                    background: 'linear-gradient(135deg, #4a1c1c 0%, #2d1b1b 100%)',
                    border: '2px solid #f59e0b',
                    borderRadius: '8px',
                    color: '#fbbf24',
                    fontSize: '12px',
                    fontWeight: 'bold',
                    padding: '8px 12px',
                    boxShadow: '0 0 10px rgba(245, 158, 11, 0.3)',
                };
                width = 180;
                height = 40;
            } else if (node.type === 'api_call') {
                label = `🌐 ${node.path}`;
                style = {
                    background: 'linear-gradient(135deg, #1e3a5f 0%, #1a2744 100%)',
                    border: '1px solid #3b82f6',
                    borderRadius: '8px',
                    color: '#60a5fa',
                    fontSize: '11px',
                    padding: '6px 10px',
                };
                width = 200;
                height = 36;
            } else if (node.type === 'event_handler') {
                label = `📎 ${node.path}`;
                style = {
                    background: 'linear-gradient(135deg, #3d1f5c 0%, #2a1640 100%)',
                    border: '1px solid #a855f7',
                    borderRadius: '8px',
                    color: '#c084fc',
                    fontSize: '11px',
                    padding: '6px 10px',
                };
                width = 140;
                height = 36;
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

        // Add Taint Flow edges (red dashed lines from source to sink)
        if (showTaintFlows && analysisData?.taint_flows) {
            analysisData.taint_flows.forEach((flow: TaintFlowEdge) => {
                // Only add if both source and sink nodes exist
                if (addedNodeIds.has(flow.source_node_id) && addedNodeIds.has(flow.sink_node_id)) {
                    const edgeId = `taint-${flow.source_node_id}-${flow.sink_node_id}`;
                    if (!addedEdgeIds.has(edgeId)) {
                        addedEdgeIds.add(edgeId);
                        
                        // Color based on severity
                        let strokeColor = '#ef4444'; // red for HIGH
                        if (flow.severity === 'MEDIUM') strokeColor = '#f97316'; // orange
                        if (flow.severity === 'LOW') strokeColor = '#eab308'; // yellow
                        
                        newEdges.push({
                            id: edgeId,
                            source: flow.source_node_id,
                            target: flow.sink_node_id,
                            type: 'smoothstep',
                            animated: true,
                            style: { 
                                stroke: strokeColor, 
                                strokeWidth: 2.5,
                                strokeDasharray: '5,5',
                            },
                            label: `⚠️ ${flow.vulnerability_type}`,
                            labelStyle: { 
                                fill: strokeColor, 
                                fontWeight: 'bold',
                                fontSize: '10px'
                            },
                            labelBgStyle: { 
                                fill: '#1a1a1a', 
                                fillOpacity: 0.8 
                            },
                        });
                    }
                }
            });
        }

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
                onToggleSinks={() => setShowSinks(!showSinks)}
                onToggleTaintFlows={() => setShowTaintFlows(!showTaintFlows)}
                onToggleCallGraph={() => setShowCallGraph(!showCallGraph)}
                onToggleStreaming={() => setUseStreaming(!useStreaming)}
                loading={loading}
                scanning={scanning}
                showFileTree={showFileTree}
                showSinks={showSinks}
                showTaintFlows={showTaintFlows}
                showCallGraph={showCallGraph}
                useStreaming={useStreaming}
                isStreaming={isStreaming}
            />

            {/* Streaming Progress Overlay */}
            {isStreaming && (
                <StreamingProgress
                    isStreaming={isStreaming}
                    phase={streamState.phase}
                    progress={streamState.progress}
                    message={streamState.message}
                    stats={streamState.stats}
                    error={streamState.error}
                    elapsedMs={streamState.elapsedMs}
                    onCancel={cancelStream}
                />
            )}

            {/* File Tree Sidebar - Virtualized for large file lists */}
            {showFileTree && (
                <VirtualizedFileTree
                    files={allFiles}
                    selectedFiles={selectedFiles}
                    onToggleFile={handleToggleFile}
                    onSelectAll={() => setSelectedFiles(new Set(allFiles))}
                    onSelectNone={() => setSelectedFiles(new Set())}
                />
            )}

            {/* Loading progress indicator for large graphs */}
            {nodesLoading && !isStreaming && (
                <div className="absolute top-20 left-1/2 transform -translate-x-1/2 z-50 bg-black/80 backdrop-blur px-4 py-2 rounded-lg border border-white/10">
                    <div className="flex items-center gap-3">
                        <div className="w-4 h-4 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                        <span className="text-sm text-zinc-300">Loading nodes... {loadProgress}%</span>
                    </div>
                    <div className="w-48 h-1 bg-zinc-700 rounded-full mt-2 overflow-hidden">
                        <div 
                            className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-300"
                            style={{ width: `${loadProgress}%` }}
                        />
                    </div>
                </div>
            )}

            {/* Main Graph Area */}
            <div className="flex-1 h-full relative">
                <ReactFlow
                    nodes={nodesLoading ? progressiveNodes : nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    onNodeClick={onNodeClick}
                    onPaneClick={onPaneClick}
                    fitView
                    fitViewOptions={{
                        padding: 0.2,
                        minZoom: 0.3,
                        maxZoom: 1.5,
                    }}
                    className="bg-black/50"
                    // Performance optimizations for large graphs
                    minZoom={0.05}
                    maxZoom={3}
                    defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
                    nodesDraggable={nodes.length < 1000}
                    nodesConnectable={nodes.length < 500}
                    elementsSelectable={true}
                >
                    <Background color="#444" gap={25} />
                    <Controls className="bg-zinc-800 border-zinc-700 fill-white" />
                    <MiniMap 
                        className="bg-zinc-900 border-zinc-700"
                        nodeStrokeWidth={3}
                        nodeColor={(node) => {
                            if (node.data?.is_sink) return '#ef4444';
                            if (node.data?.is_entry_point) return '#22d3ee';
                            if (node.data?.vulnerabilityCount > 0) return '#f59e0b';
                            return '#00f0ff';
                        }}
                        maskColor="rgba(0, 0, 0, 0.8)"
                        pannable
                        zoomable
                    />
                </ReactFlow>

                {/* Performance Monitor - shows when graph is large */}
                <PerformanceMonitor 
                    stats={performanceStats}
                    isVirtualized={isVirtualized}
                />
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

/**
 * Main Visualizer component wrapped with ReactFlowProvider
 * for viewport optimization hooks to work properly.
 */
const Visualizer = () => {
    return (
        <ReactFlowProvider>
            <VisualizerContent />
        </ReactFlowProvider>
    );
};

export default Visualizer;
