import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { ShieldAlert, Box, ScanLine } from 'lucide-react';

const CustomNode = ({ data }: NodeProps) => {
    const { label, details, isCritical } = data;
    const isSelected = data.selected; // ReactFlow passes selected prop if using standard hook, but here we might rely on global state or prop passing if custom. actually simplified:

    // Colors based on method
    const getMethodColor = (method: string) => {
        switch (method) {
            case 'GET': return 'bg-blue-600 border-blue-400';
            case 'POST': return 'bg-green-600 border-green-400';
            case 'PUT': return 'bg-yellow-600 border-yellow-400';
            case 'DELETE': return 'bg-red-600 border-red-400';
            default: return 'bg-slate-600 border-slate-400';
        }
    };

    const headerColor = getMethodColor(details?.method);

    return (
        <div className={`shadow-lg rounded-lg overflow-hidden min-w-[240px] transition-all bg-slate-900 
      ${isCritical ? 'ring-2 ring-red-500 shadow-[0_0_15px_rgba(239,68,68,0.5)] border-red-500' : 'border border-slate-700'}`}
        >
            <Handle type="target" position={Position.Top} className="w-3 h-3 bg-slate-400" />

            {/* Header */}
            <div className={`px-3 py-2 flex items-center justify-between ${headerColor} text-white`}>
                <div className="flex items-center gap-2">
                    <span className="font-bold text-xs">{details?.method}</span>
                    <span className="font-mono text-xs opacity-90 truncate max-w-[150px]" title={details?.path}>
                        {details?.path}
                    </span>
                </div>
                {isCritical && (
                    <div className="flex items-center gap-1">
                        {details.sinks?.[0] && (
                            <span className="text-[10px] bg-red-600 px-1 rounded font-bold uppercase shadow-sm">
                                {details.sinks[0].type}
                            </span>
                        )}
                        <ShieldAlert size={16} className="text-white animate-pulse" />
                    </div>
                )}
            </div>

            {/* Body */}
            <div className="p-3 space-y-2">
                {/* Params Summary */}
                {details?.params && details.params.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                        {details.params.slice(0, 3).map((p: string, i: number) => (
                            <span key={i} className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded border border-slate-700 flex items-center gap-1">
                                <Box size={10} /> {p.split('.').pop()}
                            </span>
                        ))}
                        {details.params.length > 3 && (
                            <span className="text-[10px] text-slate-500">+{details.params.length - 3}</span>
                        )}
                    </div>
                )}

                {/* Sinks / Risk Warning */}
                {details?.sinks && details.sinks.length > 0 ? (
                    <div className="text-[10px] text-red-400 bg-red-950/30 p-1.5 rounded border border-red-900/50 flex items-start gap-1">
                        <ScanLine size={12} className="mt-0.5 shrink-0" />
                        <span>
                            {details.sinks[0].detail}
                            {details.sinks.length > 1 && ` (+${details.sinks.length - 1})`}
                        </span>
                    </div>
                ) : (
                    <div className="text-[10px] text-slate-600 italic">No sinks detected</div>
                )}
            </div>

            <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-slate-400" />
        </div>
    );
};

export default memo(CustomNode);
