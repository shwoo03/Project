'use client';

import React, { useState, useCallback, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Node
} from 'reactflow';
import 'reactflow/dist/style.css';
import { transformRoutesToGraph, RouteData } from '@/lib/graph-transformer';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Server, ShieldCheck, FolderOpen } from 'lucide-react';
import CustomNode from '@/components/CustomNode';

export default function Dashboard() {
  const [targetPath, setTargetPath] = useState('');
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<RouteData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nodeTypes = useMemo(() => ({ custom: CustomNode }), []);

  const handleAnalyze = async () => {
    if (!targetPath) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ targetPath })
      });

      const data = await res.json();

      if (res.ok) {
        const { nodes: flowNodes, edges: flowEdges } = transformRoutesToGraph(data.routes);
        setNodes(flowNodes);
        setEdges(flowEdges);
      } else {
        setError(data.error || 'Analysis failed');
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    if (node.data.details) {
      setSelectedNode(node.data.details);
    } else {
      setSelectedNode(null);
    }
  }, []);

  return (
    <div className="flex h-screen w-full bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar/Drawer for Details */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            className="absolute right-0 top-0 h-full w-96 bg-slate-900 border-l border-slate-800 shadow-2xl z-50 p-6 overflow-y-auto"
          >
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-blue-400">Endpoint Details</h2>
              <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <div className="space-y-4">
              <div className="p-4 bg-slate-800 rounded-lg">
                <span className="text-xs text-slate-400 block mb-1">Method</span>
                <span className={`text-lg font-bold ${getMethodColor(selectedNode.method)}`}>{selectedNode.method}</span>
              </div>

              <div className="p-4 bg-slate-800 rounded-lg">
                <span className="text-xs text-slate-400 block mb-1">Path</span>
                <code className="text-sm text-green-300 break-all">{selectedNode.path}</code>
              </div>

              <div className="p-4 bg-slate-800 rounded-lg">
                <span className="text-xs text-slate-400 block mb-1">File Location</span>
                <div className="text-sm text-slate-300 break-all flex items-center gap-2">
                  <FolderOpen size={14} />
                  {selectedNode.file}:{selectedNode.line}
                </div>
              </div>

              {/* Input Parameters Section */}
              {selectedNode.params && selectedNode.params.length > 0 && (
                <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
                  <span className="text-xs text-slate-400 block mb-2">Input Parameters</span>
                  <div className="flex flex-wrap gap-2">
                    {selectedNode.params.map((param: string) => (
                      <span key={param} className="text-xs bg-slate-700 text-blue-200 px-2 py-1 rounded border border-slate-600 font-mono">
                        {param}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Security Analysis Section */}
              <div className={`p-4 rounded-lg border ${selectedNode.riskLevel === 'critical' ? 'bg-red-900/20 border-red-500/50' : 'bg-slate-800 border-slate-700'}`}>
                <div className={`flex items-center gap-2 mb-2 ${selectedNode.riskLevel === 'critical' ? 'text-red-400' : 'text-slate-400'}`}>
                  <ShieldCheck size={16} />
                  <span className="font-semibold text-sm">Security Analysis</span>
                </div>

                {selectedNode.sinks && selectedNode.sinks.length > 0 ? (
                  <div className="space-y-2 mt-2">
                    {selectedNode.sinks.map((sink: any, idx: number) => (
                      <div key={idx} className="text-xs bg-red-950/50 text-red-200 p-2 rounded border border-red-900 flex items-start gap-2">
                        <span className="font-bold text-red-500">⚠ {sink.type}</span>
                        <span>{sink.detail}</span>
                      </div>
                    ))}
                    <p className="text-xs text-red-400 mt-2 font-bold">Critical Vulnerability Detected!</p>
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">
                    No immediate high-risk sinks detected. Review business logic manually.
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-16 border-b border-slate-800 flex items-center px-6 justify-between bg-slate-950/50 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <Server size={18} className="text-white" />
            </div>
            <h1 className="font-bold text-lg tracking-tight">SourceViz <span className="text-slate-500 font-normal">v1.0</span></h1>
          </div>

          <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-lg p-1 pr-4 w-[500px]">
            <Search size={16} className="ml-3 text-slate-500" />
            <input
              type="text"
              placeholder="Enter absolute project path..."
              className="bg-transparent border-none focus:outline-none text-sm text-slate-200 w-full placeholder:text-slate-600"
              value={targetPath}
              onChange={(e) => setTargetPath(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
            />
            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 py-1.5 rounded transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Scanning...' : 'Analyze'}
            </button>
          </div>

          <div className="flex items-center gap-4 text-sm text-slate-400">
            <span>Nodes: {nodes.filter(n => n.type !== 'input').length}</span>
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700"></div>
          </div>
        </header>

        {/* Main Canvas */}
        <div className="flex-1 relative bg-slate-900">
          {nodes.length === 0 && !loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 gap-4 pointer-events-none z-10">
              <Server size={48} className="text-slate-700" opacity={0.5} />
              <p>Enter a directory path to start mapping your API surface.</p>
            </div>
          )}

          {error && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-red-500/10 border border-red-500/50 text-red-500 px-4 py-2 rounded-lg z-20">
              {error}
            </div>
          )}

          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            className="bg-slate-950"
          >
            <Background color="#334155" gap={20} />
            <Controls className="bg-slate-800 border-slate-700 fill-slate-400 text-slate-400" />
            <MiniMap
              nodeStrokeColor={(n) => '#64748b'}
              nodeColor={(n) => '#1e293b'}
              className="bg-slate-900 border-slate-800"
              maskColor="rgba(15, 23, 42, 0.7)"
            />
          </ReactFlow>
        </div>
      </div>
    </div>
  );
}

function getMethodColor(method: string) {
  switch (method) {
    case 'GET': return 'text-blue-500';
    case 'POST': return 'text-green-500';
    case 'DELETE': return 'text-red-500';
    case 'PUT': return 'text-yellow-500';
    default: return 'text-slate-400';
  }
}
