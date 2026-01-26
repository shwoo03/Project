"use client";

import React, { useCallback, useState } from 'react';
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
import { Maximize2, X, Play, Search, Network } from 'lucide-react';
import dagre from 'dagre';

const Visualizer = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNode, setSelectedNode] = useState<Node | null>(null);
    const [projectPath, setProjectPath] = useState<string>("C:/Users/dntmd/OneDrive/Desktop/my/프로젝트/Project/web_source_code_visualization/xss-1/deploy");
    const [loading, setLoading] = useState(false);

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    );

    const onNodeClick = (event: React.MouseEvent, node: Node) => {
        setSelectedNode(node);
    };

    const analyzeProject = async () => {
        if (!projectPath) return;
        setLoading(true);
        try {
            const res = await fetch('http://localhost:8000/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: projectPath })
            });
            const data = await res.json();

            if (data.endpoints) {
                processNodes(data.endpoints);
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

        // 1. Root Project Node
        const rootId = 'PROJECT_ROOT';
        g.setNode(rootId, { label: 'Root URL', width: 180, height: 60 });
        newNodes.push({
            id: rootId,
            position: { x: 0, y: 0 },
            data: { label: 'Root URL' },
            style: {
                background: '#fff',
                color: '#000',
                border: '2px solid #fff',
                fontWeight: 'bold',
                borderRadius: '8px',
                width: 180,
                padding: '10px',
                textAlign: 'center'
            }
        });

        // 2. Process Routes
        endpoints.forEach((ep: any) => {
            if (ep.type === 'root') {
                const routeId = ep.id;
                // Aggregate discovered inputs to display in Details Panel
                const inputParams = (ep.children || [])
                    .filter((c: any) => c.type === 'input')
                    .map((c: any) => {
                        let typeLabel = "Unknown";
                        if (c.method === 'GET') typeLabel = 'Query Param (GET)';
                        else if (c.method === 'POST') typeLabel = 'Form Data (POST)';
                        else if (c.method === 'COOKIE') typeLabel = 'Cookie (HEADER)';

                        return {
                            name: c.path,
                            type: typeLabel,
                            source: 'discovered'
                        };
                    });

                // Route Node (Depth 1)
                g.setNode(routeId, { label: ep.path, width: 220, height: 70 });
                newNodes.push({
                    id: routeId,
                    position: { x: 0, y: 0 },
                    data: {
                        label: ep.path,
                        params: [...ep.params, ...inputParams] // Merge explicit params and discovered inputs
                    },
                    style: {
                        background: '#0a0a0a',
                        color: '#00f0ff',
                        borderRadius: '12px',
                        border: '2px solid #00f0ff',
                        padding: '10px',
                        width: 220,
                        fontWeight: 'bold',
                        textAlign: 'center',
                        boxShadow: '0 0 15px #00f0ff20'
                    },
                    type: 'default'
                });

                // Connect Root -> Route
                g.setEdge(rootId, routeId);
                newEdges.push({
                    id: `e-${rootId}-${routeId}`,
                    source: rootId,
                    target: routeId,
                    type: 'smoothstep',
                    animated: true,
                    style: { stroke: '#00f0ff', strokeWidth: 2 }
                });

                // Process Inputs & Calls (Children) - Linear Flow
                // We want them to appear sequentially below the Route.
                // We can chain them: Route -> Node1 -> Node2 ...

                let previousNodeId = routeId;

                if (ep.children && ep.children.length > 0) {
                    ep.children.forEach((child: any, i: number) => {
                        // Skip Input nodes for visualization (requested by user)
                        if (child.type === 'input') return;

                        const childId = child.id;
                        let childLabel = "";
                        let childStyle = {};

                        if (child.type === 'child') { // Call
                            childLabel = `Call: ${child.path}()`;
                            childStyle = {
                                background: '#1a001a',
                                border: '1px dashed #bd00ff',
                                color: '#bd00ff',
                                borderRadius: '4px',
                                padding: '5px 10px',
                                fontSize: '12px',
                                width: 150
                            };
                        } else {
                            return;
                        }

                        g.setNode(childId, { label: childLabel, width: 150, height: 40 });
                        newNodes.push({
                            id: childId,
                            position: { x: 0, y: 0 },
                            data: { label: childLabel },
                            style: childStyle,
                            type: 'default' // Using default simplifier
                        });

                        g.setEdge(previousNodeId, childId);
                        newEdges.push({
                            id: `e-${previousNodeId}-${childId}`,
                            source: previousNodeId,
                            target: childId,
                            type: 'smoothstep',
                            markerEnd: { type: MarkerType.ArrowClosed, color: '#555' },
                            style: { stroke: '#555', strokeDasharray: '5,5' }
                        });

                        previousNodeId = childId;
                    });
                }
            }
        });

        dagre.layout(g);

        // Apply calculated positions
        newNodes.forEach((node) => {
            const nodeWithPos = g.node(node.id);
            node.position = {
                x: nodeWithPos.x - nodeWithPos.width / 2,
                y: nodeWithPos.y - nodeWithPos.height / 2,
            };
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
                    className="flex items-center gap-2 px-6 py-2 bg-cyan-500 hover:bg-cyan-400 text-black font-bold rounded-lg transition-all disabled:opacity-50"
                >
                    {loading ? <Network className="animate-spin" /> : <Play size={18} />}
                    {loading ? "분석 중..." : "시각화"}
                </button>
            </div>

            <div className="flex-1 h-full relative">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    onNodeClick={onNodeClick}
                    fitView
                    className="bg-black/50"
                >
                    <Background color="#333" gap={20} />
                    <Controls className="bg-zinc-800 border-zinc-700 fill-white" />
                    <MiniMap className="bg-zinc-900 border-zinc-700" nodeColor="#00f0ff" />
                </ReactFlow>
            </div>

            <AnimatePresence>
                {selectedNode && (
                    <motion.div
                        initial={{ x: 300, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: 300, opacity: 0 }}
                        className="absolute right-0 top-0 bottom-0 w-96 bg-black/80 backdrop-blur-md border-l border-white/10 p-6 shadow-2xl z-50 overflow-y-auto"
                    >
                        <div className="flex justify-between items-center mb-6">
                            <h2 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-purple-500">
                                상세 정보 (Details)
                            </h2>
                            <button onClick={() => setSelectedNode(null)} className="p-1 hover:bg-white/10 rounded-full">
                                <X size={20} />
                            </button>
                        </div>

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
                                                            <td className="px-3 py-2 text-zinc-400">{p.type}</td>
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
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default Visualizer;
