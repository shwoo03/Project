import { CSSProperties } from 'react';

// ============================================
// Node Style Constants
// ============================================

export const ROOT_STYLE: CSSProperties = {
    background: '#1a0000',
    color: '#ff0000',
    border: '2px dashed #ff0000',
    fontWeight: 'bold',
    borderRadius: '8px',
    padding: '10px',
    textAlign: 'center',
    boxShadow: '0 0 20px #ff000040'
};

export const CLUSTER_STYLE: CSSProperties = {
    background: '#1e293b',
    color: '#fcd34d',
    border: '2px dashed #fcd34d',
    borderRadius: '8px',
    padding: '10px',
    fontWeight: 'bold',
    textAlign: 'center'
};

export const TEMPLATE_STYLE: CSSProperties = {
    background: '#0f172a',
    border: '2px solid #38bdf8',
    color: '#e0f2fe',
    borderRadius: '8px',
    padding: '10px',
    fontWeight: 'bold',
    textAlign: 'center',
    boxShadow: '0 0 15px #38bdf840'
};

export const ROOT_FILE_STYLE: CSSProperties = {
    background: '#0a0a0a',
    color: '#00f0ff',
    borderRadius: '12px',
    border: '2px solid #00f0ff',
    padding: '10px',
    fontWeight: 'bold',
    textAlign: 'center',
    boxShadow: '0 0 15px #00f0ff20'
};

export const FUNCTION_STYLE: CSSProperties = {
    background: '#1a1a1a',
    border: '1px solid #7c3aed',
    color: '#ddd6fe',
    borderRadius: '6px',
    padding: '8px',
    fontSize: '12px',
    fontWeight: 500,
    boxShadow: '0 0 10px #7c3aed20'
};

export const CALL_STYLE: CSSProperties = {
    background: '#1a001a',
    border: '1px dashed #bd00ff',
    color: '#bd00ff',
    borderRadius: '4px',
    padding: '5px 10px',
    fontSize: '12px'
};

export const DATABASE_STYLE: CSSProperties = {
    background: '#1c1c1c',
    border: '2px solid #ea580c',
    color: '#fb923c',
    borderRadius: '12px',
    padding: '10px',
    textAlign: 'center'
};

export const DEFAULT_STYLE: CSSProperties = {
    background: '#1a1a1a',
    border: '1px solid #6b7280',
    color: '#e5e7eb',
    borderRadius: '6px',
    padding: '8px',
    fontSize: '12px',
    fontWeight: 500
};

// ============================================
// Style Getter Function
// ============================================

export type NodeType = 'cluster' | 'template' | 'root' | 'function' | 'call' | 'child' | 'database' | 'default';

interface NodeStyleResult {
    style: CSSProperties;
    width: number;
    height: number;
}

export function getNodeStyle(type: NodeType, label?: string): NodeStyleResult {
    switch (type) {
        case 'cluster':
            return { style: CLUSTER_STYLE, width: 200, height: 60 };
        case 'template':
            return { style: TEMPLATE_STYLE, width: 200, height: 60 };
        case 'root':
            return { style: ROOT_FILE_STYLE, width: 200, height: 60 };
        case 'function':
            return { style: FUNCTION_STYLE, width: 160, height: 40 };
        case 'call':
        case 'child':
            return { style: CALL_STYLE, width: 150, height: 40 };
        case 'database':
            return { style: DATABASE_STYLE, width: 180, height: 60 };
        default:
            return { style: DEFAULT_STYLE, width: 200, height: 60 };
    }
}

// ============================================
// Highlight Styles
// ============================================

export const HIGHLIGHT_SELECTED_STYLE: CSSProperties = {
    boxShadow: '0 0 30px #bd00ff60',
    border: '2px solid #bd00ff'
};

export const HIGHLIGHT_UPSTREAM_STYLE: CSSProperties = {
    boxShadow: '0 0 20px #ffae0040',
    border: '2px solid #ffae00'
};

export const DIMMED_STYLE: CSSProperties = {
    opacity: 0.3
};
