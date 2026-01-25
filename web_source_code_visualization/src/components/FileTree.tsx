import React, { useState } from 'react';
import { RouteData } from '@/lib/graph-transformer';
import { Folder, FileCode, AlertCircle, ChevronRight, ChevronDown } from 'lucide-react';

interface Props {
    routes: RouteData[]; // To identify vulnerable files
    onFileSelect: (filePath: string) => void;
}

// Helper to build file tree structure
const buildFileTree = (routes: RouteData[]) => {
    const root: any = {};

    routes.forEach(route => {
        const parts = route.file.split(/[\\/]/); // Handle windows/unix paths
        let current = root;

        parts.forEach((part, idx) => {
            if (!current[part]) {
                current[part] = {
                    name: part,
                    isDir: idx < parts.length - 1,
                    children: {},
                    hasVuln: false,
                    path: route.file // store full relative path on file nodes
                };
            }

            // Mark as vulnerable if route has critical/high sinks
            if (route.riskLevel === 'critical' || route.riskLevel === 'high') {
                current[part].hasVuln = true;
                // Bubble up vulnerability status (simple heuristic)
                // In a real tree, we'd need to propagate this up after build, but 1-pass is okay for shallow
            }

            current = current[part].children;
        });
    });

    return root;
};

// Recursive Tree Node
const TreeNode = ({ node, onSelect }: { node: any, onSelect: any }) => {
    const [isOpen, setIsOpen] = useState(true);
    const children = Object.values(node.children);

    return (
        <div className="pl-3 select-none">
            <div
                className={`flex items-center gap-2 py-1 cursor-pointer hover:bg-slate-800 rounded px-2 ${node.isDir ? 'text-slate-300' : 'text-blue-200'}`}
                onClick={() => node.isDir ? setIsOpen(!isOpen) : onSelect(node.path)}
            >
                <span className="opacity-50 text-xs">
                    {node.isDir && (isOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />)}
                </span>

                {node.isDir ? <Folder size={14} className="text-yellow-600" /> : <FileCode size={14} />}

                <span className="text-xs truncate max-w-[140px]">{node.name}</span>

                {node.hasVuln && (
                    <AlertCircle size={12} className="text-red-500 ml-auto" />
                )}
            </div>

            {node.isDir && isOpen && (
                <div className="border-l border-slate-800 ml-2">
                    {children.map((child: any) => (
                        <TreeNode key={child.name} node={child} onSelect={onSelect} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default function FileTree({ routes, onFileSelect }: Props) {
    const tree = buildFileTree(routes);

    return (
        <div className="w-64 bg-slate-900 border-r border-slate-800 h-full flex flex-col">
            <div className="p-3 border-b border-slate-800 font-bold text-sm text-slate-400 flex items-center gap-2">
                <Folder size={16} />
                Project Files
            </div>
            <div className="flex-1 overflow-y-auto p-2">
                {Object.values(tree).map((node: any) => (
                    <TreeNode key={node.name} node={node} onSelect={onFileSelect} />
                ))}
            </div>
        </div>
    );
}
